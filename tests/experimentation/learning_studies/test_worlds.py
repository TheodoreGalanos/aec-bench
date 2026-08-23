# ABOUTME: Tests the reset-only Interactive World Learning Studies adapter and target resolution.
# ABOUTME: Proves complete dam trial reuse, isolated paths, and one cold probe through the common runtime.

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.learning_study import (
    ExperienceRole,
    LearningArmSpec,
    LearningExperienceSpec,
    LearningStudySpec,
    RunExperienceStep,
    StudyArmRole,
)
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.experimentation.learning_studies.errors import LearningStudyFeatureUnsupported
from aec_bench.experimentation.learning_studies.planning import (
    CompiledConsolidationStep,
    CompiledExperienceStep,
    CompiledFeedbackStep,
    compile_learning_study,
)
from aec_bench.experimentation.learning_studies.recording import StudyRunRecorder
from aec_bench.experimentation.learning_studies.runtime import (
    ArmRunStatus,
    ConsolidationRequest,
    ExecuteExperienceRequest,
    FeedbackHandle,
    LearnerStateHandle,
    ReleaseFeedbackRequest,
    run_learning_study,
)
from aec_bench.experimentation.learning_studies.worlds import (
    WorldLearningExecutionCondition,
    WorldLearningTreatmentKind,
    build_world_learning_operations,
    resolve_world_learning_target,
    world_learning_task_id,
)
from aec_bench.harness.dam_seepage_trial import run_dam_seepage_trial
from aec_bench.harness.prime_world_actor import run_prime_world_actor_session
from aec_bench.worlds.monitoring.dam_seepage.world import DAM_SEEPAGE_TASK_WORLD_ID, SeepageAction
from tests.support.trial_record_factories import make_trial_record

_WORLD_ID = DAM_SEEPAGE_TASK_WORLD_ID
_PROFILE_ID = "synthetic-rising-seepage"
_TASK_ID = f"world/{_WORLD_ID}/{_PROFILE_ID}"
_INSTRUCTION = "Monitor the dam and respond as conditions evolve."
_CONDITION = WorldLearningExecutionCondition(
    actor=run_prime_world_actor_session,
    actor_binding_label="prime-fake-executable",
)
_COMPUTE = ComputeConfig(backend="local")
_ESCALATION_ACTIONS = [
    {"action_name": SeepageAction.CHECK_MEASUREMENT_SYSTEM.value, "arguments": {}, "request_id": "check"},
    {"action_name": SeepageAction.RECORD_CONFIRMATION_READING.value, "arguments": {}, "request_id": "reading-2"},
    {"action_name": SeepageAction.RECORD_CONFIRMATION_READING.value, "arguments": {}, "request_id": "reading-3"},
    {"action_name": SeepageAction.INSPECT_DOWNSTREAM_AREA.value, "arguments": {}, "request_id": "inspect"},
    {
        "action_name": SeepageAction.ESCALATE_FOR_ENGINEERING_REVIEW.value,
        "arguments": {},
        "request_id": "submit",
    },
]


def _agent(tmp_path: Path, *, actions: list[dict[str, object]]) -> AgentConfig:
    from tests.prime_agent.test_acp import _fake_prime_agent

    return AgentConfig(
        name="prime",
        adapter="prime-agent",
        model="anthropic/test",
        parameters={
            "isolation": "development_same_user",
            "max_world_actions": 10,
            "max_model_calls": 10,
            "max_tokens": 1_000,
            "max_cost_usd": "10",
            "max_wall_seconds": 5,
            "executable": str(_fake_prime_agent(tmp_path)),
            "environment": {
                **os.environ,
                "FAKE_ACP_SCENARIO": "world",
                "FAKE_WORLD_ACTIONS": json.dumps(actions),
            },
        },
    )


def _spec(agent: AgentConfig, *, repetitions: int = 1, two_arms: bool = False) -> LearningStudySpec:
    arms = [
        LearningArmSpec(
            arm_id="cold-reset",
            role=StudyArmRole.CONTROL,
            treatment_id="reset",
            steps=(RunExperienceStep(step_id="cold-probe", experience_id="probe", commit_post_state=False),),
        )
    ]
    if two_arms:
        arms.append(
            LearningArmSpec(
                arm_id="matched-reset",
                role=StudyArmRole.CONTROL,
                treatment_id="reset",
                steps=(RunExperienceStep(step_id="matched-probe", experience_id="probe", commit_post_state=False),),
            )
        )
    return LearningStudySpec(
        study_id="w01-cold-dam",
        title="W01 cold dam probe",
        research_question="Can one complete bounded dam episode run as one ordinary experience?",
        agent=agent,
        compute=_COMPUTE,
        repetitions=repetitions,
        experiences=(LearningExperienceSpec(experience_id="probe", task_id=_TASK_ID, role=ExperienceRole.PROBE),),
        arms=tuple(arms),
    )


def _plan(agent: AgentConfig, *, repetitions: int = 1, two_arms: bool = False):  # noqa: ANN202
    return compile_learning_study(
        study_run_id="w1-b1-test",
        spec=_spec(agent, repetitions=repetitions, two_arms=two_arms),
        resolve_task=resolve_world_learning_target,
    )


def _binding(tmp_path: Path):  # noqa: ANN202
    return build_world_learning_operations(
        run_root=tmp_path / "study",
        world_id=_WORLD_ID,
        execution_condition=_CONDITION,
        run_trial=run_dam_seepage_trial,
        instructions={_TASK_ID: _INSTRUCTION},
        treatment_kinds={"reset": WorldLearningTreatmentKind.RESET},
    )


def _initialise(binding, arm_run):  # noqa: ANN001, ANN202
    state = binding.operations.initialise_learner(arm_run)
    assert isinstance(state, LearnerStateHandle)
    return state


def test_world_learning_task_ids_resolve_exact_world_and_profile_targets() -> None:
    target = resolve_world_learning_target(_TASK_ID)

    assert target.task_id == _TASK_ID
    assert target.world_id == _WORLD_ID
    assert target.profile_id == _PROFILE_ID
    assert world_learning_task_id(world_id=_WORLD_ID, profile_id=_PROFILE_ID) == _TASK_ID


@pytest.mark.parametrize(
    ("task_id", "category"),
    (
        (f"{_WORLD_ID}/{_PROFILE_ID}", "world-task-id-invalid"),
        ("world", "world-task-id-invalid"),
        (f"world/{_WORLD_ID}", "world-task-id-invalid"),
        (f"world/unknown-world/{_PROFILE_ID}", "world-unknown"),
        (f"world/{_WORLD_ID}/unknown-profile", "world-profile-unknown"),
        (f"world/{_WORLD_ID}/../{_PROFILE_ID}", "world-task-id-invalid"),
        (f"world\\{_WORLD_ID}\\{_PROFILE_ID}", "world-task-id-invalid"),
        (f"/world/{_WORLD_ID}/{_PROFILE_ID}", "world-task-id-invalid"),
    ),
)
def test_world_learning_target_rejects_non_exact_or_unsafe_ids(task_id: str, category: str) -> None:
    with pytest.raises(ValueError, match=category):
        resolve_world_learning_target(task_id)


def test_world_target_compiles_to_deterministic_ordinary_planned_trials(tmp_path: Path) -> None:
    agent = _agent(tmp_path, actions=_ESCALATION_ACTIONS)
    first = _plan(agent, repetitions=2)
    second = _plan(agent, repetitions=2)

    first_trials = [
        step.trial for arm in first.arm_runs for step in arm.steps if isinstance(step, CompiledExperienceStep)
    ]
    second_trials = [
        step.trial for arm in second.arm_runs for step in arm.steps if isinstance(step, CompiledExperienceStep)
    ]

    assert first_trials == second_trials
    assert [trial.repetition for trial in first_trials] == [1, 2]
    assert all(trial.task_id == _TASK_ID for trial in first_trials)
    assert len({trial.trial_id for trial in first_trials}) == 2


def test_w1_binding_fixes_the_world_execution_condition() -> None:
    assert _CONDITION.adapter_id == "world-local:prime-fake-executable"


def test_world_learning_binding_rejects_untyped_treatment_kind_values(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="world-treatment-unsupported"):
        build_world_learning_operations(
            run_root=tmp_path / "study",
            world_id=_WORLD_ID,
            execution_condition=_CONDITION,
            run_trial=run_dam_seepage_trial,
            instructions={_TASK_ID: _INSTRUCTION},
            treatment_kinds={"reset": "reset"},  # type: ignore[dict-item]
        )


def test_world_learning_arms_reject_cross_arm_state(tmp_path: Path) -> None:
    agent = _agent(tmp_path, actions=_ESCALATION_ACTIONS)
    plan = _plan(agent, two_arms=True)
    binding = _binding(tmp_path)
    cold, matched = plan.arm_runs
    cold_state = _initialise(binding, cold)
    matched_state = _initialise(binding, matched)
    matched_step = matched.steps[0]
    assert isinstance(matched_step, CompiledExperienceStep)
    assert cold_state.value.root != matched_state.value.root

    with pytest.raises(ValueError, match="cross-arm-path-detected"):
        asyncio.run(
            binding.operations.execute_experience(
                ExecuteExperienceRequest(arm_run=matched, step=matched_step, state=cold_state)
            )
        )


def test_world_learning_rejects_missing_instruction(tmp_path: Path) -> None:
    agent = _agent(tmp_path, actions=_ESCALATION_ACTIONS)
    plan = _plan(agent)
    binding = build_world_learning_operations(
        run_root=tmp_path / "study",
        world_id=_WORLD_ID,
        execution_condition=_CONDITION,
        run_trial=run_dam_seepage_trial,
        instructions={},
        treatment_kinds={"reset": WorldLearningTreatmentKind.RESET},
    )
    arm_run = plan.arm_runs[0]
    state = _initialise(binding, arm_run)
    step = arm_run.steps[0]
    assert isinstance(step, CompiledExperienceStep)

    with pytest.raises(ValueError, match="world-instruction-missing"):
        asyncio.run(
            binding.operations.execute_experience(ExecuteExperienceRequest(arm_run=arm_run, step=step, state=state))
        )


def test_world_learning_rejects_preallocated_candidate_path(tmp_path: Path) -> None:
    agent = _agent(tmp_path, actions=_ESCALATION_ACTIONS)
    plan = _plan(agent)
    binding = _binding(tmp_path)
    arm_run = plan.arm_runs[0]
    state = _initialise(binding, arm_run)
    step = arm_run.steps[0]
    assert isinstance(step, CompiledExperienceStep)
    candidate = state.value.root.parent / step.step_id
    candidate.mkdir(parents=True)

    with pytest.raises(ValueError, match="arm-isolation-failed"):
        asyncio.run(
            binding.operations.execute_experience(ExecuteExperienceRequest(arm_run=arm_run, step=step, state=state))
        )


def test_reset_binding_rejects_feedback_and_consolidation(tmp_path: Path) -> None:
    agent = _agent(tmp_path, actions=_ESCALATION_ACTIONS)
    arm_run = _plan(agent).arm_runs[0]
    binding = _binding(tmp_path)
    state = _initialise(binding, arm_run)

    with pytest.raises(LearningStudyFeatureUnsupported, match="world-feedback-unsupported"):
        binding.operations.release_feedback(
            ReleaseFeedbackRequest(
                arm_run=arm_run,
                step=CompiledFeedbackStep(
                    step_id="feedback",
                    source_experience_id="probe",
                    feedback_view_id="terminal",
                ),
                state=state,
                source_trial_record=make_trial_record(),
            )
        )

    with pytest.raises(LearningStudyFeatureUnsupported, match="world-consolidation-unsupported"):
        binding.operations.consolidate(
            ConsolidationRequest(
                arm_run=arm_run,
                step=CompiledConsolidationStep(
                    step_id="consolidate",
                    feedback_step_ids=("feedback",),
                    operation_id="structured-memory",
                ),
                state=state,
                feedback=(
                    FeedbackHandle(
                        feedback_id="feedback",
                        source_experience_id="probe",
                        view_id="terminal",
                        value=None,
                    ),
                ),
            )
        )


def test_world_target_mismatch_is_rejected(tmp_path: Path) -> None:
    agent = _agent(tmp_path, actions=_ESCALATION_ACTIONS)
    plan = _plan(agent)
    binding = build_world_learning_operations(
        run_root=tmp_path / "study",
        world_id="another-world",
        execution_condition=_CONDITION,
        run_trial=run_dam_seepage_trial,
        instructions={_TASK_ID: _INSTRUCTION},
        treatment_kinds={"reset": WorldLearningTreatmentKind.RESET},
    )
    arm_run = plan.arm_runs[0]
    state = _initialise(binding, arm_run)
    step = arm_run.steps[0]
    assert isinstance(step, CompiledExperienceStep)

    with pytest.raises(ValueError, match="world-target-mismatch"):
        asyncio.run(
            binding.operations.execute_experience(ExecuteExperienceRequest(arm_run=arm_run, step=step, state=state))
        )


def test_cold_dam_probe_runs_as_one_record_through_the_common_runtime(tmp_path: Path) -> None:
    agent = _agent(tmp_path, actions=_ESCALATION_ACTIONS)
    plan = _plan(agent)
    run_root = tmp_path / "study"
    binding = _binding(tmp_path)
    recorder = StudyRunRecorder(root=run_root, plan=plan, snapshot_state=binding.snapshot_state)

    execution = asyncio.run(run_learning_study(plan=plan, operations=binding.operations, observer=recorder))

    assert len(execution.arm_runs) == 1
    arm_result = execution.arm_runs[0]
    assert arm_result.status is ArmRunStatus.COMPLETED
    assert len(arm_result.trial_records) == 1
    record = arm_result.trial_records[0]
    assert isinstance(record, TrialRecord)
    assert record.trial_id == plan.arm_runs[0].steps[0].trial.trial_id
    assert record.task_id == _TASK_ID
    assert record.evaluation is not None
    assert record.evaluation.reward == 1.0
    assert record.input.instruction == _INSTRUCTION

    arm_root = run_root / "learner-arms" / plan.arm_runs[0].arm_run_id
    assert not (arm_root / "states" / "cold-probe").exists()
    state_files = [path for path in (arm_root / "states").rglob("*") if path.is_file()]
    assert state_files == []
    assert (run_root / "study-plan.json").is_file()
    assert (run_root / "result.json").is_file()


def test_world_learning_rejects_returned_identity_mismatch(tmp_path: Path) -> None:
    agent = _agent(tmp_path, actions=_ESCALATION_ACTIONS)
    plan = _plan(agent)
    arm_run = plan.arm_runs[0]
    step = arm_run.steps[0]
    assert isinstance(step, CompiledExperienceStep)

    async def wrong_identity_trial(task, trial, *, actor):  # noqa: ANN001, ANN202
        record = await run_dam_seepage_trial(task, trial, actor=actor)
        return record.model_copy(update={"trial_id": "not-the-planned-trial-id"})

    binding = build_world_learning_operations(
        run_root=tmp_path / "study",
        world_id=_WORLD_ID,
        execution_condition=_CONDITION,
        run_trial=wrong_identity_trial,
        instructions={_TASK_ID: _INSTRUCTION},
        treatment_kinds={"reset": WorldLearningTreatmentKind.RESET},
    )
    state = _initialise(binding, arm_run)

    with pytest.raises(ValueError, match="world-trial-record-mismatch"):
        asyncio.run(
            binding.operations.execute_experience(ExecuteExperienceRequest(arm_run=arm_run, step=step, state=state))
        )
