# ABOUTME: Proves Prime receives only the scoped dam seepage actor surface.
# ABOUTME: Covers bounded transport, exact profile execution, replay, evaluation, and treatment skills.

from __future__ import annotations

import json
import os
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from aec_bench.contracts.interactive_world import InteractiveWorldProfileRef
from aec_bench.harness.dam_seepage_prime.session import (
    DamSeepagePrimeSessionError,
    DamSeepagePrimeSessionLimits,
    run_dam_seepage_prime_session,
)
from aec_bench.prime_agent.acp import PrimeAcpIsolation
from aec_bench.prime_agent.skills import (
    ACTOR_LEDGER_PLAN_INSTRUCTION,
)
from aec_bench.worlds.monitoring.dam_seepage.definition import (
    dam_seepage_world_definition,
)
from aec_bench.worlds.monitoring.dam_seepage.world import SeepageAction


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
    assert result.world_action_count == len(action_plan)
    assert not result.benchmark_valid
    evidence = json.loads(result.run_file.read_text(encoding="utf-8"))
    assert evidence["profile"] == asdict(_profile_ref())
    assert evidence["treatment"] == "open"
    assert evidence["actions"] == [action["action_name"] for action in action_plan]
    assert evidence["world_actor_client_sha256"] == result.world_actor_client_sha256
    assert evidence["world_actor_close_complete"] is True
    assert evidence["evaluation"]["successful"] is True
    assert result.actor_authority_file.is_file()
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
