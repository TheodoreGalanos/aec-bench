# ABOUTME: Proves Prime receives only the scoped actor surface for one host-owned world episode.
# ABOUTME: Covers exact retries, stale decisions, forbidden selectors, evidence safety, and closure.

from __future__ import annotations

import importlib
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.contracts.world_session import (
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.prime_agent.acp import PrimeAcpIsolation
from aec_bench.prime_agent.world import (
    WORLD_ACTOR_CAPABILITY_ENV,
    WORLD_ACTOR_SOCKET_ENV,
    PrimeWorldActorProxy,
    install_aec_world_skill,
    run_prime_pump_world_session,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.episode_runtime import (
    PUMP_STATION_TASK_WORLD_ID,
)


def _session_request() -> WorldSessionRequest:
    return WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.START,
        session_id="prime-session",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id="prime-composite-actor",
        run_id="prime-run",
        episode_id="prime-episode",
        world_branch_id="prime-branch",
    )


def _load_skill(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    install_aec_world_skill(workspace)
    monkeypatch.syspath_prepend(str(workspace))
    sys.modules.pop("aec_world", None)
    return importlib.import_module("aec_world")


def _raw_call(socket_path: str, payload: dict[str, Any]) -> dict[str, Any]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(socket_path)
        client.sendall(json.dumps(payload).encode("utf-8") + b"\n")
        response = client.makefile("rb").readline()
    return cast(dict[str, Any], json.loads(response))


@pytest.mark.asyncio
async def test_scoped_proxy_preserves_actor_semantics_and_redacted_transport_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world_directory = tmp_path / "private-world" / "do-not-expose"
    actor_workspace = tmp_path / "actor-workspace"
    actor_workspace.mkdir()
    evidence_file = tmp_path / "host-evidence" / "actor-transport.jsonl"
    client = _load_skill(actor_workspace, monkeypatch)
    proxy = PrimeWorldActorProxy(
        world_run_directory=world_directory,
        socket_directory=actor_workspace / ".actor",
        evidence_file=evidence_file,
    )
    proxy.open_world_session(_session_request())

    with proxy:
        environment = proxy.connection_environment()
        monkeypatch.setenv(WORLD_ACTOR_SOCKET_ENV, environment[WORLD_ACTOR_SOCKET_ENV])
        monkeypatch.setenv(WORLD_ACTOR_CAPABILITY_ENV, environment[WORLD_ACTOR_CAPABILITY_ENV])

        catalogue = await client.capabilities()
        observation = await client.observe()
        with pytest.raises(client.ActorError):
            await client.invoke(
                "not_a_world_action",
                {},
                decision_id=observation["decision_id"],
                request_id="prime-action-unknown",
            )
        request_id = "prime-action-1"
        first = await client.invoke(
            "continue_operation",
            {"reason": "Advance the current world once."},
            decision_id=observation["decision_id"],
            request_id=request_id,
        )
        retry = await client.invoke(
            "continue_operation",
            {"reason": "Advance the current world once."},
            decision_id=observation["decision_id"],
            request_id=request_id,
        )

        assert catalogue["task_world_id"] == PUMP_STATION_TASK_WORLD_ID
        assert retry == first
        with pytest.raises(client.ActorError, match="actor-request-id-conflict"):
            await client.invoke(
                "continue_operation",
                {"reason": "Different content under one request identity."},
                decision_id=observation["decision_id"],
                request_id=request_id,
            )
        with pytest.raises(client.ActorError, match="decision-stale"):
            await client.invoke(
                "continue_operation",
                {"reason": "Use an expired decision."},
                decision_id=observation["decision_id"],
                request_id="prime-action-stale",
            )

        forbidden = _raw_call(
            environment[WORLD_ACTOR_SOCKET_ENV],
            {
                "capability": environment[WORLD_ACTOR_CAPABILITY_ENV],
                "request": {"operation": "observe", "run_id": str(world_directory)},
            },
        )
        assert forbidden == {
            "error": {"code": "actor-request-invalid", "detail": "actor request does not match the contract"}
        }
        forbidden_control = _raw_call(
            environment[WORLD_ACTOR_SOCKET_ENV],
            {
                "capability": environment[WORLD_ACTOR_CAPABILITY_ENV],
                "request": {"operation": "execute", "authority_id": "host"},
            },
        )
        assert forbidden_control == forbidden

    assert not Path(environment[WORLD_ACTOR_SOCKET_ENV]).exists()
    evidence = evidence_file.read_text(encoding="utf-8")
    assert environment[WORLD_ACTOR_CAPABILITY_ENV] not in evidence
    assert str(world_directory) not in evidence
    events = [json.loads(line) for line in evidence.splitlines()]
    assert [event["request"]["operation"] for event in events] == [
        "capabilities",
        "observe",
        "invoke",
        "invoke",
        "invoke",
        "invoke",
        "invoke",
    ]


def test_packaged_skill_has_only_the_three_actor_operations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "actor"
    workspace.mkdir()
    client = _load_skill(workspace, monkeypatch)

    assert client.__all__ == ["ActorError", "capabilities", "invoke", "observe"]
    assert not hasattr(client, "run")
    assert not hasattr(client, "branch")
    assert not hasattr(client, "profile")
    assert not hasattr(client, "verify")
    assert not hasattr(client, "evaluate")
    assert not hasattr(client, "rollout")
    assert not hasattr(client, "host_control")


@pytest.mark.asyncio
async def test_prime_end_turn_while_world_is_live_is_recorded_incomplete(tmp_path: Path) -> None:
    from tests.prime_agent.test_acp import _fake_prime_agent

    result = await run_prime_pump_world_session(
        actor_workspace=tmp_path / "actor",
        world_run_directory=tmp_path / "private-world",
        evidence_directory=tmp_path / "host-evidence",
        session_request=_session_request(),
        instruction="Advance the current world, then end the turn.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        timeout_seconds=5,
        executable=str(_fake_prime_agent(tmp_path)),
        environment={**os.environ, "FAKE_ACP_SCENARIO": "world"},
    )

    assert result.prime.session_state == "ended"
    assert result.world_state == "active"
    assert result.completion == "incomplete"
    assert result.verification.valid
    assert result.evaluation.valid is False
    assert result.actor_transport_file.exists()
    assert not result.prime.benchmark_valid


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS Seatbelt boundary")
async def test_sandboxed_prime_reaches_world_only_through_the_scoped_proxy(tmp_path: Path) -> None:
    from tests.prime_agent.test_acp import _fake_prime_agent

    result = await run_prime_pump_world_session(
        actor_workspace=tmp_path / "actor",
        world_run_directory=tmp_path / "private-world",
        evidence_directory=tmp_path / "host-evidence",
        session_request=_session_request(),
        instruction="Advance the current world, then end the turn.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.MACOS_SANDBOX,
        timeout_seconds=5,
        executable=str(_fake_prime_agent(tmp_path)),
        environment={**os.environ, "FAKE_ACP_SCENARIO": "world"},
    )

    assert result.prime.session_state == "ended"
    assert result.world_state == "active"
    assert result.completion == "incomplete"
    assert result.verification.valid
    assert result.prime.benchmark_valid
    assert result.benchmark_valid
