# ABOUTME: Tests clean Prime baseline and fixed-candidate qualification across pump profiles.
# ABOUTME: Confirms that qualification records evidence but makes no promotion decision.

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.trial_record import AgentConfiguration, CostRecord, ExecutionEnvironmentRef, TrialInput
from aec_bench.experimentation.qualification.prime_refinement import (
    DEFAULT_QUALIFICATION_PROFILES,
    PrimeRefinementTreatment,
    run_prime_refinement_qualification,
)
from aec_bench.harness.pump_station_prime.evidence import PumpStationPrimeJourneyLimits
from aec_bench.prime_agent.acp import PrimeAcpIsolation
from aec_bench.prime_agent.refinement import (
    PrimeRefinementCandidate,
    PrimeRefinementEntry,
    PrimeRefinementKind,
    PrimeRefinementMode,
    PrimeRefinementScope,
    empty_refinement_candidate,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.evaluation import (
    evaluate_pump_station_reference_run,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from tests.support.trial_record_factories import make_trial_record


def _candidate() -> PrimeRefinementCandidate:
    return PrimeRefinementCandidate(
        prime_harness_schema=1,
        entries=(
            PrimeRefinementEntry(
                id="compact-action-state",
                kind=PrimeRefinementKind.MEMORY,
                title="Keep compact action state",
                content="Keep one compact state and reconcile it with observe().",
                path="pump/stewardship",
                scope=PrimeRefinementScope.LOCAL,
                reference={},
                arguments={},
                metadata={},
                source="refine",
                created_at="2026-08-09T00:00:00Z",
                updated_at="2026-08-09T00:00:00Z",
                version=1,
            ),
        ),
    )


def _limits() -> PumpStationPrimeJourneyLimits:
    return PumpStationPrimeJourneyLimits(
        max_sessions=4,
        max_host_controls=4,
        max_world_actions=100,
        max_model_calls=20,
        max_tokens=10_000,
        max_cost_usd=Decimal("20"),
        max_wall_seconds=600,
    )


@pytest.mark.asyncio
async def test_qualifies_one_candidate_in_clean_fixed_treatment_cells(
    tmp_path: Path,
) -> None:
    candidate = _candidate()
    calls: list[dict[str, Any]] = []
    selected_profiles: list[str] = []

    async def fake_trial(task: Any, trial: Any) -> Any:
        calls.append(dict(trial.agent.parameters))
        assert trial.agent.parameters["refinement_mode"] == PrimeRefinementMode.CANDIDATE.value
        world_directory = tmp_path / "fake-worlds" / trial.trial_id
        repository = PumpStationWorldRunRepository(world_directory)
        run = PumpStationWorldRun.create_reference_system(
            repository=repository,
            run_id=f"{trial.trial_id}-run",
            episode_id=f"{trial.trial_id}-episode",
            world_branch_id=f"{trial.trial_id}-branch",
            reference_system_id=task.profile.profile_id,
        )
        selected_profiles.append(run.manifest.reference_system_id)
        run_file = tmp_path / "fake-journeys" / f"{trial.trial_id}.json"
        run_file.parent.mkdir(parents=True, exist_ok=True)
        run_file.write_text(json.dumps({"host_policy_sha256": "a" * 64}) + "\n", encoding="utf-8")
        stewardship = evaluate_pump_station_reference_run(run, evaluation_scope="bounded_continuation")
        return make_trial_record(
            trial_id=trial.trial_id,
            experiment_id=trial.experiment_id,
            task_id=task.task_id,
            task={"task_id": task.task_id, "task_revision": task.task_revision},
            agent=AgentConfiguration(
                adapter=trial.agent.adapter,
                model=trial.agent.model,
                configuration={},
            ),
            environment=ExecutionEnvironmentRef(runtime_image="test", compute_backend="local"),
            input=TrialInput(
                instruction=task.instruction,
                task_revision=task.task_revision,
                task_kind="world",
                visibility=task.visibility,
            ),
            output={
                "agent_output": AgentOutput(
                    status=AgentOutputStatus.COMPLETED,
                    output_path=str(run_file),
                    output_format="json",
                ),
                "agent_result": {
                    "completion": "completed",
                    "world_state": "active",
                    "stop_reason": "test-complete",
                    "world_action_count": 0,
                },
                "terminated": True,
                "truncated": False,
                "final_reason": "test-complete",
            },
            evaluation=EvaluationResult(
                reward=1.0,
                validity=ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True),
                stewardship=stewardship,
            ),
            cost=CostRecord(
                model_calls=1,
                tokens_in=10,
                tokens_out=5,
                cache_read_tokens=0,
                cache_write_tokens=0,
                estimated_cost_usd=0.1,
            ),
        )

    result = await run_prime_refinement_qualification(
        output_directory=tmp_path / "qualification",
        qualification_id="prime-refinement-study",
        candidate=candidate,
        instruction="Complete the pump-station stewardship task.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.MACOS_SANDBOX,
        limits=_limits(),
        run_trial=fake_trial,
    )

    assert selected_profiles == [
        DEFAULT_QUALIFICATION_PROFILES[0],
        DEFAULT_QUALIFICATION_PROFILES[1],
        DEFAULT_QUALIFICATION_PROFILES[0],
        DEFAULT_QUALIFICATION_PROFILES[1],
    ]
    assert [PrimeRefinementCandidate.model_validate(call["refinement_candidate"]) for call in calls] == [
        empty_refinement_candidate(),
        empty_refinement_candidate(),
        candidate,
        candidate,
    ]
    assert result.report.decision == "pending"
    assert result.report.evidence_valid
    assert [observation.treatment for observation in result.report.observations] == [
        PrimeRefinementTreatment.BASELINE,
        PrimeRefinementTreatment.CANDIDATE,
        PrimeRefinementTreatment.BASELINE,
        PrimeRefinementTreatment.CANDIDATE,
    ]
    assert len(result.report.contrasts) == 2
    report_text = result.report_file.read_text(encoding="utf-8")
    assert str(tmp_path) not in report_text
    assert result.report.content_sha256 in report_text


@pytest.mark.asyncio
async def test_rejects_an_unknown_profile_before_creating_evidence(tmp_path: Path) -> None:
    output_directory = tmp_path / "qualification"

    with pytest.raises(ValueError, match="unknown pump reference profiles"):
        await run_prime_refinement_qualification(
            output_directory=output_directory,
            qualification_id="prime-refinement-study",
            candidate=_candidate(),
            instruction="Complete the pump-station stewardship task.",
            model="anthropic/test",
            isolation=PrimeAcpIsolation.MACOS_SANDBOX,
            limits=_limits(),
            profile_ids=("unknown-profile",),
        )

    assert not output_directory.exists()
