# ABOUTME: Proves Prime receives only the scoped actor surface for one host-owned world episode.
# ABOUTME: Covers exact retries, stale decisions, forbidden selectors, evidence safety, and closure.

from __future__ import annotations

import importlib
import inspect
import json
import os
import socket
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.harness.pump_station_prime.actor_proxy import PumpStationPrimeActorProxy
from aec_bench.harness.pump_station_prime.session import (
    PUMP_STATION_GUIDANCE_INSTRUCTION,
    PumpStationPrimeSessionLimits,
    install_pump_station_guidance_skill,
    run_pump_station_prime_session,
)
from aec_bench.prime_agent.acp import PrimeAcpIsolation
from aec_bench.prime_agent.refinement import PrimeRefinementMode
from aec_bench.prime_agent.skills import (
    WORLD_ACTOR_CAPABILITY_ENV,
    WORLD_ACTOR_SOCKET_ENV,
    PrimeSkillInstallError,
    install_aec_world_skill,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PUMP_STATION_TASK_WORLD_ID,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
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


def _limits(*, max_world_actions: int = 20) -> PumpStationPrimeSessionLimits:
    return PumpStationPrimeSessionLimits(
        max_world_actions=max_world_actions,
        max_model_calls=10,
        max_tokens=1_000,
        max_cost_usd=Decimal("10"),
        max_wall_seconds=5,
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


def test_reused_world_skill_rejects_nested_symbolic_links(tmp_path: Path) -> None:
    workspace = tmp_path / "actor-workspace"
    workspace.mkdir()
    install_aec_world_skill(workspace)
    package_file = workspace / "aec_world" / "__init__.py"
    matching_file = workspace / "matching.py"
    matching_file.write_bytes(package_file.read_bytes())
    package_file.unlink()
    package_file.symlink_to(matching_file)

    with pytest.raises(PrimeSkillInstallError, match="different content"):
        install_aec_world_skill(workspace)


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
    proxy = PumpStationPrimeActorProxy(
        world_run_directory=world_directory,
        socket_directory=actor_workspace / ".actor",
        max_world_actions=20,
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
        unauthorized = _raw_call(
            environment[WORLD_ACTOR_SOCKET_ENV],
            {"capability": "wrong-capability-secret", "request": {"operation": "observe"}},
        )
        assert unauthorized == {"error": {"code": "actor-unauthorized", "detail": "actor capability is invalid"}}

    assert not Path(environment[WORLD_ACTOR_SOCKET_ENV]).exists()
    evidence = evidence_file.read_text(encoding="utf-8")
    assert environment[WORLD_ACTOR_CAPABILITY_ENV] not in evidence
    assert "wrong-capability-secret" not in evidence
    assert str(world_directory) not in evidence
    events = [json.loads(line) for line in evidence.splitlines()]
    assert [event["operation"] for event in events] == [
        "capabilities",
        "observe",
        "invoke",
        "invoke",
        "invoke",
        "invoke",
        "invoke",
        "observe",
        None,
        "observe",
    ]
    assert all(datetime.fromisoformat(event["received_at"]) for event in events)
    assert events[-3]["request"] is None
    assert events[-2]["request"] is None
    assert events[-1]["request"] is None


@pytest.mark.asyncio
async def test_world_action_budget_preserves_exact_retry_and_blocks_a_new_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world_directory = tmp_path / "private-world"
    actor_workspace = tmp_path / "actor-workspace"
    actor_workspace.mkdir()
    evidence_file = tmp_path / "host-evidence" / "actor-transport.jsonl"
    client = _load_skill(actor_workspace, monkeypatch)
    proxy = PumpStationPrimeActorProxy(
        world_run_directory=world_directory,
        socket_directory=actor_workspace / ".actor",
        max_world_actions=1,
        evidence_file=evidence_file,
    )
    proxy.open_world_session(_session_request())

    with proxy:
        environment = proxy.connection_environment()
        monkeypatch.setenv(WORLD_ACTOR_SOCKET_ENV, environment[WORLD_ACTOR_SOCKET_ENV])
        monkeypatch.setenv(WORLD_ACTOR_CAPABILITY_ENV, environment[WORLD_ACTOR_CAPABILITY_ENV])
        observation = await client.observe()
        first = await client.invoke(
            "continue_operation",
            {"reason": "Advance once."},
            decision_id=observation["decision_id"],
            request_id="action-1",
        )
        retry = await client.invoke(
            "continue_operation",
            {"reason": "Advance once."},
            decision_id=observation["decision_id"],
            request_id="action-1",
        )
        assert retry == first
        with pytest.raises(client.ActorError, match="world-action-budget-exhausted"):
            await client.invoke(
                "continue_operation",
                {"reason": "Try another action."},
                decision_id=first["next_observation"]["decision_id"],
                request_id="action-2",
            )

    assert proxy.world_action_attempts == 2
    assert proxy.world_action_limit_reached
    events = [json.loads(line) for line in evidence_file.read_text(encoding="utf-8").splitlines()]
    assert events[-1]["error"]["code"] == "world-action-budget-exhausted"


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


def test_packaged_pump_guidance_is_markdown_only_and_contains_no_instance_plan(tmp_path: Path) -> None:
    workspace = tmp_path / "actor"
    workspace.mkdir()

    guidance = install_pump_station_guidance_skill(workspace)
    files = sorted(path.relative_to(guidance).as_posix() for path in guidance.rglob("*") if path.is_file())
    text = "\n".join((guidance / relative).read_text(encoding="utf-8") for relative in files)

    assert files == ["SKILL.md", "references/compact-state.md", "references/decision-method.md"]
    assert "guidance_id: aecbench.pump-station-guidance" in text
    assert "two-reference-profiles" in text
    assert "NO_ACCESSIBLE_RESULT" in text
    assert "after a `planned-outage-capacity` rejection" in text
    assert "Run eligibility alone is" in text
    assert "exact ledger" in text
    assert "one IPython cell for each `invoke` attempt" in text
    assert "not an action-selection rule" in text
    assert "remaining action budget" not in text
    assert "model-call limit" not in text
    assert "closure threshold" not in text
    for forbidden in (
        "pump-a",
        "pump-b",
        "backlog-a",
        "restriction-a",
        "world_run_directory",
        "--run-dir",
        "host_control",
        "expected score",
    ):
        assert forbidden not in text.lower()

    parameters = inspect.signature(run_pump_station_prime_session).parameters
    assert parameters["pump_station_guidance"].default is False
    assert "skill_directory" not in parameters
    assert "skill_directories" not in parameters


@pytest.mark.asyncio
async def test_prime_end_turn_while_world_is_live_is_recorded_incomplete(tmp_path: Path) -> None:
    from tests.prime_agent.test_acp import _fake_prime_agent

    result = await run_pump_station_prime_session(
        actor_workspace=tmp_path / "actor",
        world_run_directory=tmp_path / "private-world",
        evidence_directory=tmp_path / "host-evidence",
        session_request=_session_request(),
        instruction="Advance the current world, then end the turn.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        limits=_limits(),
        executable=str(_fake_prime_agent(tmp_path)),
        environment={**os.environ, "FAKE_ACP_SCENARIO": "world"},
    )

    assert result.prime.session_state == "ended"
    assert result.world_state == "active"
    assert result.completion == "incomplete"
    assert result.verification.valid
    assert result.evaluation.evaluation_scope == "bounded_continuation"
    assert result.evaluation.valid
    assert result.evaluation.metrics.terminal_liability.active_restriction_count == 2
    assert result.actor_transport_file.exists()
    assert result.run_file.exists()
    assert result.world_action_attempts == 1
    assert not result.prime.benchmark_valid
    run_evidence = json.loads(result.run_file.read_text(encoding="utf-8"))
    assert run_evidence["evaluation_scope"] == "bounded_continuation"
    assert run_evidence["evaluation_valid"] is True
    assert run_evidence["world_state"] == "active"
    assert run_evidence["completion"] == "incomplete"
    assert not (tmp_path / "actor" / ".prime-skills" / "pump-station-guidance").exists()
    inbound = result.prime.paths.inbound_file.read_text(encoding="utf-8")
    assert PUMP_STATION_GUIDANCE_INSTRUCTION not in inbound
    provenance = json.loads(result.prime.paths.run_file.read_text(encoding="utf-8"))
    assert [skill["name"] for skill in provenance["skills"]] == ["aec-world"]


@pytest.mark.asyncio
async def test_explicit_guided_treatment_adds_only_the_ordered_skill_and_instruction(tmp_path: Path) -> None:
    from tests.prime_agent.test_acp import _fake_prime_agent

    instruction = "Advance the current world, then end the turn."
    result = await run_pump_station_prime_session(
        actor_workspace=tmp_path / "actor",
        world_run_directory=tmp_path / "private-world",
        evidence_directory=tmp_path / "host-evidence",
        session_request=_session_request(),
        instruction=instruction,
        model="anthropic/test",
        isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        limits=_limits(),
        pump_station_guidance=True,
        executable=str(_fake_prime_agent(tmp_path)),
        environment={**os.environ, "FAKE_ACP_SCENARIO": "world"},
    )

    observed = json.loads((tmp_path / "actor" / "observed-acp.json").read_text(encoding="utf-8"))
    skill_arguments = [
        observed["argv"][index + 1] for index, argument in enumerate(observed["argv"]) if argument == "--skill"
    ]
    assert [Path(argument).name for argument in skill_arguments] == ["aec-world", "pump-station-guidance"]
    inbound = result.prime.paths.inbound_file.read_text(encoding="utf-8")
    assert instruction in inbound
    assert PUMP_STATION_GUIDANCE_INSTRUCTION in inbound
    assert "host model-call limit" not in inbound
    assert "closure no later than" not in inbound
    provenance = json.loads(result.prime.paths.run_file.read_text(encoding="utf-8"))
    assert [skill["name"] for skill in provenance["skills"]] == ["aec-world", "pump-station-guidance"]
    assert [skill["order"] for skill in provenance["skills"]] == [0, 1]
    assert provenance["skill_sha256"] == provenance["skills"][0]["sha256"]
    serialized_provenance = json.dumps(provenance)
    assert str(tmp_path / "actor") not in serialized_provenance
    assert all(argument not in serialized_provenance for argument in skill_arguments)
    assert result.verification.valid
    assert result.evaluation.evaluation_scope == "bounded_continuation"


@pytest.mark.asyncio
async def test_discovery_mode_adds_prime_refine_skill(tmp_path: Path) -> None:
    from tests.prime_agent.test_acp import _fake_prime_agent

    result = await run_pump_station_prime_session(
        actor_workspace=tmp_path / "actor",
        world_run_directory=tmp_path / "private-world",
        evidence_directory=tmp_path / "host-evidence",
        session_request=_session_request(),
        instruction="Advance the current world and refine only an evidence-backed lesson.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        limits=_limits(),
        refinement_mode=PrimeRefinementMode.DISCOVER,
        executable=str(_fake_prime_agent(tmp_path)),
        environment={**os.environ, "FAKE_ACP_SCENARIO": "world"},
    )

    observed = json.loads((tmp_path / "actor" / "observed-acp.json").read_text(encoding="utf-8"))
    skill_arguments = [
        observed["argv"][index + 1] for index, argument in enumerate(observed["argv"]) if argument == "--skill"
    ]
    assert [Path(argument).name for argument in skill_arguments] == ["aec-world", "refine"]
    provenance = json.loads(result.prime.paths.run_file.read_text(encoding="utf-8"))
    assert [skill["name"] for skill in provenance["skills"]] == ["aec-world", "refine"]


@pytest.mark.asyncio
async def test_repeated_prime_sessions_share_actor_files_but_not_prime_runtime(tmp_path: Path) -> None:
    from tests.prime_agent.test_acp import _fake_prime_agent

    actor_workspace = tmp_path / "actor"
    world_directory = tmp_path / "private-world"
    executable = str(_fake_prime_agent(tmp_path))
    first_runtime = actor_workspace / ".prime-runtimes" / "segment-000"
    first = await run_pump_station_prime_session(
        actor_workspace=actor_workspace,
        world_run_directory=world_directory,
        evidence_directory=tmp_path / "host-evidence-000",
        prime_runtime_directory=first_runtime,
        session_request=_session_request(),
        instruction="Advance the current world, then save your actor-owned state.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        limits=_limits(),
        executable=executable,
        environment={**os.environ, "FAKE_ACP_SCENARIO": "world", "FAKE_WORLD_REQUEST_ID": "segment-000-action"},
    )
    (actor_workspace / "state.json").write_text('{"retained":true}\n', encoding="utf-8")
    first_observed = json.loads((actor_workspace / "observed-acp.json").read_text(encoding="utf-8"))

    snapshot = PumpStationWorldRunRepository(world_directory).current_snapshot()
    second_runtime = actor_workspace / ".prime-runtimes" / "segment-001"
    second = await run_pump_station_prime_session(
        actor_workspace=actor_workspace,
        world_run_directory=world_directory,
        evidence_directory=tmp_path / "host-evidence-001",
        prime_runtime_directory=second_runtime,
        session_request=WorldSessionRequest(
            execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
            open_mode=WorldSessionOpenMode.RESUME,
            session_id="prime-session-001",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            agent_tenure_id="prime-composite-actor",
            run_id=snapshot.run_id,
            episode_id=snapshot.episode_id,
            world_branch_id=snapshot.world_branch_id,
            start_snapshot=StewardshipStateSnapshotRef(
                run_id=snapshot.run_id,
                episode_id=snapshot.episode_id,
                world_branch_id=snapshot.world_branch_id,
                sequence=snapshot.sequence,
                state_id=snapshot.state_id,
                commit_id=snapshot.commit_id,
            ),
        ),
        instruction="Continue from the actor-owned files and current observation.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        limits=_limits(),
        executable=executable,
        environment={**os.environ, "FAKE_ACP_SCENARIO": "world", "FAKE_WORLD_REQUEST_ID": "segment-001-action"},
    )
    second_observed = json.loads((actor_workspace / "observed-acp.json").read_text(encoding="utf-8"))

    assert first.prime.session_state == second.prime.session_state == "ended"
    assert first_observed["actor_state_exists"] is False
    assert second_observed["actor_state_exists"] is True
    assert Path(first_observed["home"]).is_relative_to(first_runtime)
    assert Path(second_observed["home"]).is_relative_to(second_runtime)
    assert first.prime.paths.state_dir != second.prime.paths.state_dir
    assert first.prime.paths.session_dir != second.prime.paths.session_dir
    assert (actor_workspace / "state.json").read_text(encoding="utf-8") == '{"retained":true}\n'


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS Seatbelt boundary")
async def test_sandboxed_prime_reaches_world_only_through_the_scoped_proxy(tmp_path: Path) -> None:
    from tests.prime_agent.test_acp import _fake_prime_agent

    result = await run_pump_station_prime_session(
        actor_workspace=tmp_path / "actor",
        world_run_directory=tmp_path / "private-world",
        evidence_directory=tmp_path / "host-evidence",
        session_request=_session_request(),
        instruction="Advance the current world, then end the turn.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.MACOS_SANDBOX,
        limits=_limits(),
        executable=str(_fake_prime_agent(tmp_path)),
        environment={**os.environ, "FAKE_ACP_SCENARIO": "world"},
    )

    assert result.prime.session_state == "ended"
    assert result.world_state == "active"
    assert result.completion == "incomplete"
    assert result.verification.valid
    assert result.evaluation.evaluation_scope == "bounded_continuation"
    assert result.evaluation.valid
    assert result.prime.benchmark_valid
    assert result.benchmark_valid
