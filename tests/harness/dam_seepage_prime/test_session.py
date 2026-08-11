# ABOUTME: Proves Prime receives only the scoped dam seepage actor surface.
# ABOUTME: Covers bounded transport, exact profile execution, replay, evaluation, and treatment skills.

from __future__ import annotations

import importlib
import json
import os
import socket
import sys
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.contracts.interactive_world import InteractiveWorldProfileRef
from aec_bench.harness.dam_seepage_prime.session import (
    DamSeepagePrimeSessionError,
    DamSeepagePrimeSessionLimits,
    run_dam_seepage_prime_session,
)
from aec_bench.harness.prime_actor_endpoint import PrimeActorEndpoint
from aec_bench.prime_agent.acp import PrimeAcpIsolation
from aec_bench.prime_agent.skills import (
    ACTOR_LEDGER_PLAN_INSTRUCTION,
    WORLD_ACTOR_CAPABILITY_ENV,
    WORLD_ACTOR_SOCKET_ENV,
    install_aec_world_skill,
)
from aec_bench.worlds.monitoring.dam_seepage.definition import (
    DamSeepageProfile,
    dam_seepage_world_definition,
)
from aec_bench.worlds.monitoring.dam_seepage.episode_runtime import DamSeepageEpisodeHost
from aec_bench.worlds.monitoring.dam_seepage.world import SeepageAction


def _profile() -> DamSeepageProfile:
    definition = dam_seepage_world_definition()
    loaded = definition.load_profile(definition.profiles[0])
    assert isinstance(loaded.value, DamSeepageProfile)
    return loaded.value


def _profile_ref() -> InteractiveWorldProfileRef:
    return dam_seepage_world_definition().profiles[0]


def _limits(*, max_world_actions: int = 10) -> DamSeepagePrimeSessionLimits:
    return DamSeepagePrimeSessionLimits(
        max_world_actions=max_world_actions,
        max_model_calls=10,
        max_tokens=1_000,
        max_cost_usd=Decimal("10"),
        max_wall_seconds=5,
    )


def _load_world_client(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
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


def _complete_actions() -> list[dict[str, Any]]:
    return [
        {
            "action_name": SeepageAction.CHECK_MEASUREMENT_SYSTEM.value,
            "arguments": {},
            "request_id": "check-system",
        },
        {
            "action_name": SeepageAction.RECORD_CONFIRMATION_READING.value,
            "arguments": {},
            "request_id": "reading-2",
        },
        {
            "action_name": SeepageAction.RECORD_CONFIRMATION_READING.value,
            "arguments": {},
            "request_id": "reading-3",
        },
        {
            "action_name": SeepageAction.INSPECT_DOWNSTREAM_AREA.value,
            "arguments": {},
            "request_id": "inspect-current-area",
        },
        {
            "action_name": SeepageAction.ESCALATE_FOR_ENGINEERING_REVIEW.value,
            "arguments": {},
            "request_id": "submit-assessment",
        },
    ]


def _fake_prime_agent_with_bundled_skills(tmp_path: Path) -> Path:
    from tests.prime_agent.test_acp import _fake_prime_agent

    package_root = tmp_path / "fake-prime-package"
    executable_directory = package_root / "dist" / "bundle"
    executable_directory.mkdir(parents=True)
    executable = _fake_prime_agent(executable_directory)
    (package_root / "package.json").write_text(json.dumps({"name": "prime-agent"}), encoding="utf-8")
    for skill_name in ("agent-message", "agent-observe"):
        skill_directory = package_root / "dist" / "skills" / skill_name
        skill_directory.mkdir(parents=True)
        (skill_directory / "SKILL.md").write_text(
            f"---\nname: {skill_name}\ndescription: Test {skill_name}.\n---\n",
            encoding="utf-8",
        )
    return executable


@pytest.mark.asyncio
async def test_scoped_endpoint_limits_actions_and_redacts_transport_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor_workspace = tmp_path / "actor"
    actor_workspace.mkdir()
    evidence_file = tmp_path / "private-host-evidence" / "transport.jsonl"
    client = _load_world_client(actor_workspace, monkeypatch)
    endpoint = PrimeActorEndpoint(
        host=DamSeepageEpisodeHost(profile=_profile()),
        socket_directory=actor_workspace / ".actor",
        max_world_actions=1,
        evidence_file=evidence_file,
    )

    with endpoint:
        environment = endpoint.connection_environment()
        monkeypatch.setenv(WORLD_ACTOR_SOCKET_ENV, environment[WORLD_ACTOR_SOCKET_ENV])
        monkeypatch.setenv(WORLD_ACTOR_CAPABILITY_ENV, environment[WORLD_ACTOR_CAPABILITY_ENV])

        catalogue = await client.capabilities()
        observation = await client.observe()
        first = await client.invoke(
            SeepageAction.CHECK_MEASUREMENT_SYSTEM.value,
            {},
            decision_id=observation["decision_id"],
            request_id="one-action",
        )
        retry = await client.invoke(
            SeepageAction.CHECK_MEASUREMENT_SYSTEM.value,
            {},
            decision_id=observation["decision_id"],
            request_id="one-action",
        )
        with pytest.raises(client.ActorError, match="world-action-budget-exhausted"):
            await client.invoke(
                SeepageAction.RECORD_CONFIRMATION_READING.value,
                {},
                decision_id=retry["next_observation"]["decision_id"],
                request_id="second-action",
            )

        forbidden = _raw_call(
            environment[WORLD_ACTOR_SOCKET_ENV],
            {
                "capability": environment[WORLD_ACTOR_CAPABILITY_ENV],
                "request": {"operation": "observe", "run_id": "forbidden-run"},
            },
        )
        unauthorized = _raw_call(
            environment[WORLD_ACTOR_SOCKET_ENV],
            {"capability": "wrong-secret", "request": {"operation": "observe"}},
        )

        assert catalogue["task_world_id"] == "dam-seepage-monitoring"
        assert retry == first
        assert forbidden == {
            "error": {
                "code": "actor-request-invalid",
                "detail": "actor request does not match the contract",
            }
        }
        assert unauthorized == {"error": {"code": "actor-unauthorized", "detail": "actor capability is invalid"}}
        assert endpoint.world_action_attempts == 2
        assert endpoint.world_action_limit_reached

    assert not Path(environment[WORLD_ACTOR_SOCKET_ENV]).exists()
    evidence = evidence_file.read_text(encoding="utf-8")
    assert environment[WORLD_ACTOR_CAPABILITY_ENV] not in evidence
    assert "wrong-secret" not in evidence
    assert str(evidence_file.parent) not in evidence
    assert "required_response" not in evidence


@pytest.mark.asyncio
async def test_open_session_completes_exact_profile_and_keeps_evaluation_separate(tmp_path: Path) -> None:
    from tests.prime_agent.test_acp import _fake_prime_agent

    action_plan = _complete_actions()
    result = await run_dam_seepage_prime_session(
        actor_workspace=tmp_path / "actor",
        evidence_directory=tmp_path / "host-evidence",
        profile_ref=_profile_ref(),
        instruction="Assess the current dam seepage evidence and submit the correct response.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        limits=_limits(),
        executable=str(_fake_prime_agent(tmp_path)),
        environment={
            **os.environ,
            "FAKE_ACP_SCENARIO": "world",
            "FAKE_WORLD_ACTIONS": json.dumps(action_plan),
        },
    )

    assert result.prime.session_state == "ended"
    assert result.world_state == "completed"
    assert result.completion == "completed"
    assert result.evaluation.successful
    assert result.replay_valid
    assert result.world_action_attempts == len(action_plan)
    assert not result.benchmark_valid
    evidence = json.loads(result.run_file.read_text(encoding="utf-8"))
    assert evidence["profile"] == asdict(_profile_ref())
    assert evidence["treatment"] == "open"
    assert evidence["actions"] == [action["action_name"] for action in action_plan]
    assert evidence["evaluation"]["successful"] is True
    provenance = json.loads(result.prime.paths.run_file.read_text(encoding="utf-8"))
    assert [skill["name"] for skill in provenance["skills"]] == ["aec-world"]


@pytest.mark.asyncio
async def test_planned_session_installs_shared_ordered_skills(tmp_path: Path) -> None:
    executable = _fake_prime_agent_with_bundled_skills(tmp_path)
    result = await run_dam_seepage_prime_session(
        actor_workspace=tmp_path / "actor",
        evidence_directory=tmp_path / "host-evidence",
        profile_ref=_profile_ref(),
        instruction="Assess the current dam seepage evidence and submit the correct response.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        limits=_limits(),
        actor_ledger_plan=True,
        executable=str(executable),
        environment={
            **os.environ,
            "FAKE_ACP_SCENARIO": "world",
            "FAKE_WORLD_ACTIONS": json.dumps(_complete_actions()),
        },
    )

    observed = json.loads((tmp_path / "actor" / "observed-acp.json").read_text(encoding="utf-8"))
    skill_arguments = [
        observed["argv"][index + 1] for index, argument in enumerate(observed["argv"]) if argument == "--skill"
    ]
    assert [Path(argument).name for argument in skill_arguments] == [
        "aec-world",
        "aec-actor-ledger",
        "agent-message",
        "agent-observe",
    ]
    assert ACTOR_LEDGER_PLAN_INSTRUCTION in result.prime.paths.inbound_file.read_text(encoding="utf-8")
    assert result.evaluation.successful
    assert json.loads(result.run_file.read_text(encoding="utf-8"))["treatment"] == "planned"


@pytest.mark.asyncio
async def test_session_rejects_actor_workspace_inside_host_evidence(tmp_path: Path) -> None:
    with pytest.raises(DamSeepagePrimeSessionError, match="must be separate"):
        await run_dam_seepage_prime_session(
            actor_workspace=tmp_path / "run" / "actor",
            evidence_directory=tmp_path / "run",
            profile_ref=_profile_ref(),
            instruction="Do the task.",
            model="anthropic/test",
            isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
            limits=_limits(),
        )
