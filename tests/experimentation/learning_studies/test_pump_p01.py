from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from aec_bench import worlds
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.learning_study import (
    ExperienceRole,
    LearningArmSpec,
    LearningExperienceSpec,
    LearningStudySpec,
    RunExperienceStep,
    StudyArmRole,
)
from aec_bench.contracts.trial_record import EvaluationStatus, ExecutionStatus
from aec_bench.experimentation.learning_studies.planning import compile_learning_study
from aec_bench.experimentation.learning_studies.pump_p01 import (
    PUMP_RS1_PROFILE_ID,
    PUMP_RS1_TASK_ID,
    PUMP_RS2_PROFILE_ID,
    PUMP_RS2_TASK_ID,
    PUMP_STATION_WORLD_ID,
    PumpJourneyTrialRunner,
    build_pump_p01_binding,
    pump_journey_public_feedback,
    pump_p01_outcome_projections,
    resolve_pump_task_id,
)
from aec_bench.experimentation.learning_studies.runtime import run_learning_study
from aec_bench.experimentation.learning_studies.worlds import (
    WorldLearningExecutionCondition,
)


def test_pump_task_ids_resolve_only_registered_profiles() -> None:
    assert resolve_pump_task_id(PUMP_RS1_TASK_ID).profile_id == PUMP_RS1_PROFILE_ID
    assert resolve_pump_task_id(PUMP_RS2_TASK_ID).profile_id == PUMP_RS2_PROFILE_ID
    with pytest.raises(ValueError):
        resolve_pump_task_id(f"world/{PUMP_STATION_WORLD_ID}/unknown")
    with pytest.raises(ValueError):
        resolve_pump_task_id(f"world/{PUMP_STATION_WORLD_ID}//{PUMP_RS1_PROFILE_ID}")
    with pytest.raises(ValueError):
        resolve_pump_task_id(f"world/{PUMP_STATION_WORLD_ID}/{PUMP_RS1_PROFILE_ID}/extra")


def test_deterministic_runner_wraps_one_complete_journey(tmp_path: Path) -> None:
    task = worlds.task(
        PUMP_STATION_WORLD_ID,
        profile=PUMP_RS1_PROFILE_ID,
        instruction="Run the complete pump journey.",
        task_id=PUMP_RS1_TASK_ID,
    )
    trial = _trial(PUMP_RS1_TASK_ID)
    record = asyncio.run(
        PumpJourneyTrialRunner(world_run_root=tmp_path / "world-runs")(task, trial, actor=_unused_actor)
    )
    assert record.trial_id == trial.trial_id
    assert record.task_id == PUMP_RS1_TASK_ID
    assert record.execution_status is ExecutionStatus.COMPLETED
    assert record.evaluation_status is EvaluationStatus.COMPLETED
    assert record.evaluation is not None
    assert record.evaluation.breakdown["benchmark_valid"] is True
    assert record.evaluation.breakdown["valid"] is True
    assert len(record.evaluation.breakdown["metrics"]) >= 6
    assert record.output is not None
    assert record.output.agent_output is not None
    assert "world-runs" in record.output.agent_output.output_path
    assert len(record.authority_evidence) == 1
    feedback = pump_journey_public_feedback(record)
    assert b"reference_controller" not in feedback
    projection = pump_p01_outcome_projections()["pump.evaluation-valid"](record)
    assert projection.eligible is True
    assert projection.value == 1.0


def test_cold_reset_runs_through_common_learning_study_runtime(tmp_path: Path) -> None:
    agent = AgentConfig(name="fixed", adapter="fixed", model="reference", parameters={})
    spec = LearningStudySpec(
        study_id="pump-p01-cold-reset-test",
        title="Pump cold reset",
        research_question="Does one journey remain one experience?",
        agent=agent,
        compute=ComputeConfig(backend="local"),
        experiences=(
            LearningExperienceSpec(
                experience_id="cold-journey",
                task_id=PUMP_RS1_TASK_ID,
                role=ExperienceRole.ACQUISITION,
            ),
        ),
        arms=(
            LearningArmSpec(
                arm_id="cold-reset",
                role=StudyArmRole.CONTROL,
                treatment_id="reset",
                steps=(RunExperienceStep(step_id="journey", experience_id="cold-journey"),),
            ),
        ),
    )
    plan = compile_learning_study(
        study_run_id="pump-p01-cold-runtime",
        spec=spec,
        resolve_task=resolve_pump_task_id,
    )
    binding = build_pump_p01_binding(
        run_root=tmp_path / "learner",
        world_run_root=tmp_path / "world",
        execution_condition=WorldLearningExecutionCondition(
            actor=_unused_actor,
            actor_binding_label="deterministic-reference",
        ),
        consolidation_operation=lambda _context: None,
    )
    execution = asyncio.run(run_learning_study(plan=plan, operations=binding.operations))
    arm = execution.arm_runs[0]
    assert arm.status.value == "completed"
    assert len(arm.trial_records) == 1
    record = arm.trial_records[0]
    assert record.task_id == PUMP_RS1_TASK_ID
    assert record.evaluation_status is EvaluationStatus.COMPLETED
    assert record.execution_status is ExecutionStatus.COMPLETED
    assert arm.initial_state_id is not None
    assert arm.final_state_id is not None
    assert not list((tmp_path / "learner").rglob("pump-world-evidence.json"))


def test_probe_candidate_state_is_discarded_by_common_runtime(tmp_path: Path) -> None:
    agent = AgentConfig(name="fixed", adapter="fixed", model="reference", parameters={})
    spec = LearningStudySpec(
        study_id="pump-p01-probe-discard-test",
        title="Pump probe discard",
        research_question="Is probe state discarded?",
        agent=agent,
        compute=ComputeConfig(backend="local"),
        experiences=(
            LearningExperienceSpec(
                experience_id="acquisition",
                task_id=PUMP_RS1_TASK_ID,
                role=ExperienceRole.ACQUISITION,
            ),
            LearningExperienceSpec(
                experience_id="probe",
                task_id=PUMP_RS2_TASK_ID,
                role=ExperienceRole.PROBE,
            ),
        ),
        arms=(
            LearningArmSpec(
                arm_id="cold-reset",
                role=StudyArmRole.CONTROL,
                treatment_id="reset",
                steps=(
                    RunExperienceStep(step_id="acquisition", experience_id="acquisition"),
                    RunExperienceStep(step_id="probe", experience_id="probe", commit_post_state=False),
                ),
            ),
        ),
    )
    plan = compile_learning_study(
        study_run_id="pump-p01-probe-runtime",
        spec=spec,
        resolve_task=resolve_pump_task_id,
    )
    binding = build_pump_p01_binding(
        run_root=tmp_path / "learner",
        world_run_root=tmp_path / "world",
        execution_condition=WorldLearningExecutionCondition(
            actor=_unused_actor,
            actor_binding_label="deterministic-reference",
        ),
        consolidation_operation=lambda _context: None,
    )
    execution = asyncio.run(run_learning_study(plan=plan, operations=binding.operations))
    arm = execution.arm_runs[0]
    assert len(arm.trial_records) == 2
    assert arm.trial_records[1].task_id == PUMP_RS2_TASK_ID
    assert not (tmp_path / "learner" / "learner-arms" / arm.arm_run_id / "states" / "probe").exists()
    learner_bytes = b"".join(path.read_bytes() for path in (tmp_path / "learner").rglob("*") if path.is_file())
    assert PUMP_RS2_PROFILE_ID.encode() not in learner_bytes


def _trial(task_id: str):
    from aec_bench.trials import PlannedTrial

    return PlannedTrial(
        trial_id="pump-trial",
        experiment_id="pump-experiment",
        task_id=task_id,
        agent=AgentConfig(name="fixed", adapter="fixed", model="reference", parameters={}),
        compute=ComputeConfig(backend="local"),
        repetition=1,
    )


async def _unused_actor(**_kwargs: object):  # type: ignore[no-untyped-def]
    raise AssertionError("deterministic runner must not invoke an actor")
