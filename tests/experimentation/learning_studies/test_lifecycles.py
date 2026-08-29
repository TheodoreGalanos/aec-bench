# ABOUTME: Tests the reset-only lifecycle Learning Studies adapter and exact target resolution.
# ABOUTME: Proves complete lifecycle trial reuse, isolated paths, cold execution, and resume.

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

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
from aec_bench.experimentation.learning_studies import lifecycles as lifecycle_adapter
from aec_bench.experimentation.learning_studies.errors import LearningStudyFeatureUnsupported
from aec_bench.experimentation.learning_studies.lifecycles import (
    LifecycleExecutionCondition,
    LifecycleLearningTreatmentKind,
    build_lifecycle_learning_operations,
    lifecycle_learning_task_id,
    resolve_lifecycle_learning_target,
)
from aec_bench.experimentation.learning_studies.planning import (
    CompiledConsolidationStep,
    CompiledExperienceStep,
    CompiledFeedbackStep,
    compile_learning_study,
)
from aec_bench.experimentation.learning_studies.recording import StudyRunRecorder
from aec_bench.experimentation.learning_studies.resume import load_resumable_study
from aec_bench.experimentation.learning_studies.runtime import (
    ArmRunStatus,
    ConsolidationRequest,
    ExecuteExperienceRequest,
    FeedbackHandle,
    LearnerStateHandle,
    ReleaseFeedbackRequest,
    run_learning_study,
)
from aec_bench.lifecycles.runtime.episode import LifecycleExecutionMode, LifecycleVisibilityPolicy
from tests.support.trial_record_factories import make_trial_record

_TEMPLATE_ID = "drainage-model-evidence-lifecycle-review"
_VARIANT_ID = "semantic_no_op_release"
_TASK_ID = f"lifecycle/{_TEMPLATE_ID}/{_VARIANT_ID}"
_CONDITION = LifecycleExecutionCondition(
    execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
    visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
)
_AGENT = AgentConfig(
    name="l01-test-agent",
    adapter="tool_loop",
    model="fixed-test-model",
    parameters={"max_turns_per_session": 5},
)
_COMPUTE = ComputeConfig(backend="local", resource_limits={"memory_mb": 512})


def _spec(*, repetitions: int = 1, two_arms: bool = False) -> LearningStudySpec:
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
        study_id="l01-cold-lifecycle",
        title="L01 cold lifecycle",
        research_question="Can one complete lifecycle run as one ordinary experience?",
        agent=_AGENT,
        compute=_COMPUTE,
        repetitions=repetitions,
        experiences=(LearningExperienceSpec(experience_id="probe", task_id=_TASK_ID, role=ExperienceRole.PROBE),),
        arms=tuple(arms),
    )


def _plan(*, repetitions: int = 1, two_arms: bool = False):  # noqa: ANN202
    return compile_learning_study(
        study_run_id="l01-b1-test",
        spec=_spec(repetitions=repetitions, two_arms=two_arms),
        resolve_task=resolve_lifecycle_learning_target,
    )


def _binding(tmp_path: Path, *, adapter_builder=None):  # noqa: ANN001, ANN202
    return build_lifecycle_learning_operations(
        run_root=tmp_path / "study",
        execution_condition=_CONDITION,
        treatment_kinds={"reset": LifecycleLearningTreatmentKind.RESET},
        adapter_builder=adapter_builder,
    )


def _initialise(binding, arm_run):  # noqa: ANN001, ANN202
    state = binding.operations.initialise_learner(arm_run)
    assert isinstance(state, LearnerStateHandle)
    return state


def test_lifecycle_learning_task_ids_resolve_variant_and_no_variant_targets() -> None:
    variant_target = resolve_lifecycle_learning_target(_TASK_ID)
    no_variant_id = lifecycle_learning_task_id(
        template_id="facade-submittal-review-lifecycle",
        variant_id=None,
    )
    no_variant_target = resolve_lifecycle_learning_target(no_variant_id)

    assert variant_target.task_id == _TASK_ID
    assert variant_target.template_id == _TEMPLATE_ID
    assert variant_target.variant_id == _VARIANT_ID
    assert no_variant_id == "lifecycle/facade-submittal-review-lifecycle"
    assert no_variant_target.variant_id is None
    assert lifecycle_learning_task_id(template_id=_TEMPLATE_ID, variant_id=_VARIANT_ID) == _TASK_ID


@pytest.mark.parametrize(
    ("task_id", "category"),
    (
        ("drainage-model-evidence-lifecycle-review/semantic_no_op_release", "lifecycle-task-id-invalid"),
        ("lifecycle", "lifecycle-task-id-invalid"),
        (f"lifecycle/{_TEMPLATE_ID}", "lifecycle-variant-required"),
        (f"lifecycle/{_TEMPLATE_ID}/unknown", "lifecycle-variant-unknown"),
        ("lifecycle/facade-submittal-review-lifecycle/default", "lifecycle-task-id-invalid"),
        ("lifecycle/unknown-template", "lifecycle-template-unknown"),
        (f"lifecycle/{_TEMPLATE_ID}/../{_VARIANT_ID}", "lifecycle-task-id-invalid"),
        (f"lifecycle\\{_TEMPLATE_ID}\\{_VARIANT_ID}", "lifecycle-task-id-invalid"),
        (f"/lifecycle/{_TEMPLATE_ID}/{_VARIANT_ID}", "lifecycle-task-id-invalid"),
    ),
)
def test_lifecycle_learning_target_rejects_non_exact_or_unsafe_ids(task_id: str, category: str) -> None:
    with pytest.raises(ValueError, match=category):
        resolve_lifecycle_learning_target(task_id)


def test_lifecycle_target_compiles_to_deterministic_ordinary_planned_trials() -> None:
    first = _plan(repetitions=2)
    second = _plan(repetitions=2)

    first_trials = [
        step.trial for arm in first.arm_runs for step in arm.steps if isinstance(step, CompiledExperienceStep)
    ]
    second_trials = [
        step.trial for arm in second.arm_runs for step in arm.steps if isinstance(step, CompiledExperienceStep)
    ]

    assert first_trials == second_trials
    assert [trial.repetition for trial in first_trials] == [1, 2]
    assert all(trial.task_id == _TASK_ID for trial in first_trials)
    assert all(trial.extensions == {} for trial in first_trials)
    assert len({trial.trial_id for trial in first_trials}) == 2


def test_b1_binding_fixes_the_lifecycle_execution_condition(tmp_path: Path) -> None:
    assert _CONDITION.adapter_id == "lifecycle-local:fresh_context:artifact_memory"
    unsupported = LifecycleExecutionCondition(
        execution_mode=LifecycleExecutionMode.PERSISTENT_CONTEXT,
        visibility_policy=LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
    )

    with pytest.raises(LearningStudyFeatureUnsupported, match="lifecycle-condition-invalid"):
        build_lifecycle_learning_operations(
            run_root=tmp_path / "study",
            execution_condition=unsupported,
            treatment_kinds={"reset": LifecycleLearningTreatmentKind.RESET},
        )


def test_lifecycle_learning_arms_reject_cross_arm_state(tmp_path: Path) -> None:
    plan = _plan(two_arms=True)
    binding = _binding(tmp_path)
    cold, matched = plan.arm_runs
    cold_state = _initialise(binding, cold)
    matched_state = _initialise(binding, matched)
    matched_step = matched.steps[0]
    assert isinstance(matched_step, CompiledExperienceStep)
    assert cold_state.value.root != matched_state.value.root

    with pytest.raises(ValueError, match="cross-arm-path-detected"):
        binding.operations.execute_experience(
            ExecuteExperienceRequest(arm_run=matched, step=matched_step, state=cold_state)
        )


def test_lifecycle_learning_rejects_non_local_compute_before_allocating_paths(tmp_path: Path) -> None:
    arm_run = _plan().arm_runs[0]
    binding = _binding(tmp_path)
    state = _initialise(binding, arm_run)
    step = arm_run.steps[0]
    assert isinstance(step, CompiledExperienceStep)
    remote_step = replace(step, trial=replace(step.trial, compute=ComputeConfig(backend="modal")))

    with pytest.raises(LearningStudyFeatureUnsupported, match="lifecycle-backend-unsupported: modal"):
        binding.operations.execute_experience(ExecuteExperienceRequest(arm_run=arm_run, step=remote_step, state=state))

    assert not (state.value.root.parents[1] / "lifecycle-experiences").exists()


def test_lifecycle_learning_rejects_preallocated_package_path(tmp_path: Path) -> None:
    arm_run = _plan().arm_runs[0]
    binding = _binding(tmp_path)
    state = _initialise(binding, arm_run)
    step = arm_run.steps[0]
    assert isinstance(step, CompiledExperienceStep)
    package = state.value.root.parents[1] / "lifecycle-experiences" / step.step_id / "package"
    package.mkdir(parents=True)

    with pytest.raises(ValueError, match="lifecycle-package-path-exists"):
        binding.operations.execute_experience(ExecuteExperienceRequest(arm_run=arm_run, step=step, state=state))


def test_reset_binding_rejects_feedback_and_consolidation(tmp_path: Path) -> None:
    arm_run = _plan().arm_runs[0]
    binding = _binding(tmp_path)
    state = _initialise(binding, arm_run)

    with pytest.raises(ValueError, match="feedback-view-unsupported"):
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

    with pytest.raises(ValueError, match="consolidation-operation-unsupported"):
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


def test_lifecycle_package_run_and_candidate_paths_are_isolated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_trials = []

    def compile_fake(template_id: str, package_dir: Path, *, variant_id: str | None = None):  # noqa: ANN202
        package_dir.mkdir(parents=True)
        return SimpleNamespace(
            package_dir=package_dir,
            envelope=SimpleNamespace(template_id=template_id, variant_id=variant_id),
        )

    def run_fake(*, trial, execute, verify, persist=None):  # noqa: ANN001, ANN202, ARG001
        trial.run_dir.mkdir(parents=True)
        captured_trials.append(trial)
        return make_trial_record(
            trial_id=trial.planned.trial_id,
            experiment_id=trial.planned.experiment_id,
            task_id=trial.planned.task_id,
            attempt=trial.planned.repetition,
        )

    monkeypatch.setattr(lifecycle_adapter, "compile_lifecycle", compile_fake)
    monkeypatch.setattr(lifecycle_adapter, "run_lifecycle_trial", run_fake)
    plan = _plan(repetitions=2, two_arms=True)
    binding = _binding(tmp_path)
    candidates = []

    for arm_run in plan.arm_runs:
        state = _initialise(binding, arm_run)
        step = arm_run.steps[0]
        assert isinstance(step, CompiledExperienceStep)
        result = binding.operations.execute_experience(
            ExecuteExperienceRequest(arm_run=arm_run, step=step, state=state)
        )
        candidates.append(result.candidate_state)

    package_paths = {trial.package_dir for trial in captured_trials}
    run_paths = {trial.run_dir for trial in captured_trials}
    candidate_paths = {state.value.root for state in candidates}
    assert len(package_paths) == len(run_paths) == len(candidate_paths) == 4
    assert package_paths.isdisjoint(run_paths)
    assert all({item.name for item in path.iterdir()} == {"memory", "feedback"} for path in candidate_paths)
    assert all(not any(item.is_file() for item in path.rglob("*")) for path in candidate_paths)
    assert all("lifecycle-experiences" not in path.parts for path in candidate_paths)
    assert all(trial.execution_mode is LifecycleExecutionMode.FRESH_CONTEXT for trial in captured_trials)
    assert all(trial.visibility_policy is LifecycleVisibilityPolicy.ARTIFACT_MEMORY for trial in captured_trials)


class _GoldAdapterBuilder:
    def __init__(self) -> None:
        self.executions = 0

    def __call__(self, **kwargs):  # noqa: ANN003, ANN202
        workspace = Path(kwargs["workspace"])
        package = workspace.parent.parent / "package"
        submissions = json.loads((package / "hidden" / "gold-submissions.json").read_text(encoding="utf-8"))
        builder = self

        class _Adapter:
            def execute(self, request):  # noqa: ANN001, ANN202
                builder.executions += 1
                output = Path(request.output_path)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(submissions[output.stem]), encoding="utf-8")
                return SimpleNamespace(
                    adapter_name="tool_loop",
                    resolved_model="fixed-test-model",
                    configuration_record={"model": "fixed-test-model", "source": "deterministic-test"},
                    agent_output=SimpleNamespace(status=SimpleNamespace(value="completed")),
                    transcript=[],
                    raw_output_text=None,
                    provider_error=None,
                    failure_kind=None,
                    usage_input_tokens=2,
                    usage_output_tokens=1,
                    usage_cache_read_tokens=0,
                    usage_cache_write_tokens=0,
                )

        return _Adapter()


def test_cold_lifecycle_probe_runs_as_one_record_and_resumes_without_rerun(tmp_path: Path) -> None:
    plan = _plan()
    run_root = tmp_path / "study"
    adapter_builder = _GoldAdapterBuilder()
    binding = _binding(tmp_path, adapter_builder=adapter_builder)
    recorder = StudyRunRecorder(
        root=run_root,
        plan=plan,
        snapshot_state=binding.snapshot_state,
        feedback_artifacts=binding.feedback_artifacts,
    )

    execution = asyncio.run(
        run_learning_study(
            plan=plan,
            operations=binding.operations,
            observer=recorder,
        )
    )

    assert len(execution.arm_runs) == 1
    arm_result = execution.arm_runs[0]
    assert arm_result.status is ArmRunStatus.COMPLETED
    assert len(arm_result.trial_records) == 1
    record = arm_result.trial_records[0]
    assert isinstance(record, TrialRecord)
    assert record.trial_id == plan.arm_runs[0].steps[0].trial.trial_id
    assert record.task_id == _TASK_ID
    assert record.attempt == 1
    assert record.evaluation is not None
    assert record.evaluation.reward == 1.0
    assert record.lifecycle_execution is not None
    assert record.lifecycle_execution.execution_mode == "fresh_context"
    assert record.lifecycle_execution.memory_visibility_policy == "artifact_memory"
    assert record.lifecycle_provenance is not None
    assert adapter_builder.executions == 3

    arm_root = run_root / "learner-arms" / plan.arm_runs[0].arm_run_id
    package = arm_root / "lifecycle-experiences" / "cold-probe" / "package"
    lifecycle_run = arm_root / "lifecycle-experiences" / "cold-probe" / "run"
    assert (package / "hidden" / "gold-submissions.json").is_file()
    assert (lifecycle_run / "state.json").is_file()
    assert not (arm_root / "states" / "cold-probe").exists()
    state_files = [path for path in (arm_root / "states").rglob("*") if path.is_file()]
    assert state_files == []
    assert (run_root / "study-plan.json").is_file()
    assert (run_root / "result.json").is_file()

    resumable = load_resumable_study(
        root=run_root,
        plan=plan,
        restore_root=tmp_path / "restored",
        snapshot_state=binding.snapshot_state,
        restore_state=binding.restore_state,
        restore_feedback=binding.restore_feedback,
        feedback_artifacts=binding.feedback_artifacts,
    )
    resumed = asyncio.run(
        run_learning_study(
            plan=plan,
            operations=binding.operations,
            observer=resumable.recorder,
            resume=resumable.resume,
        )
    )
    assert [item.arm_run_id for item in resumed.arm_runs] == [item.arm_run_id for item in execution.arm_runs]
    assert adapter_builder.executions == 3
