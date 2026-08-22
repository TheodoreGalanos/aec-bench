# ABOUTME: Tests the local artifact-task Learning Study adapter and filesystem isolation.
# ABOUTME: Proves copy-on-write state, channel permissions, and cross-arm rejection with real tasks.

from pathlib import Path

import pytest

from aec_bench.adapters.base import AdapterRequest, AdapterResult
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.experimentation.learning_studies.artifact_tasks import (
    ArtifactConsolidationContext,
    ArtifactLearningTreatment,
    ArtifactLearningTreatmentKind,
    build_artifact_learning_operations,
    terminal_outcome_feedback,
)
from aec_bench.experimentation.learning_studies.planning import CompiledExperienceStep, compile_learning_study
from aec_bench.experimentation.learning_studies.runtime import (
    ConsolidationRequest,
    ExecuteExperienceRequest,
    FeedbackReleaseResult,
    InitialiseLearnerRequest,
    LearnerStateHandle,
    ReleaseFeedbackRequest,
)
from aec_bench.experimentation.learning_studies.studies.a01_artifact_structural_transfer import (
    A01_CONSOLIDATION_OPERATION_ID,
    A01_FEEDBACK_VIEW_ID,
    build_a01_study_spec,
)
from aec_bench.tasks.loader import load_task_definition

from .support import HeatLoadStudyAdapter

_REPOSITORY_ROOT = Path(__file__).parents[3]
_TASKS_ROOT = _REPOSITORY_ROOT / "tasks"
_AGENT = AgentConfig(name="a01-test-agent", adapter="direct", model="fixed-test-model")
_COMPUTE = ComputeConfig(backend="local", resource_limits={"memory_mb": 512}, timeout_override=30)


def _resolve_task(task_id: str):  # noqa: ANN202
    return load_task_definition(_TASKS_ROOT / task_id, _TASKS_ROOT)


def _plan():  # noqa: ANN202
    return compile_learning_study(
        study_run_id="a01-adapter-test",
        spec=build_a01_study_spec(agent=_AGENT, compute=_COMPUTE),
        resolve_task=_resolve_task,
    )


def _binding(tmp_path: Path, *, adapter_builder, consolidation_operation=None):  # noqa: ANN001, ANN202
    def default_consolidation(context: ArtifactConsolidationContext) -> None:
        context.memory_root.mkdir(parents=True, exist_ok=True)
        (context.memory_root / "method.json").write_text('{"method":"heat-load"}\n', encoding="utf-8")

    return build_artifact_learning_operations(
        tasks_root=_TASKS_ROOT,
        run_root=tmp_path / "study",
        treatment_specs={
            "reset": ArtifactLearningTreatment("reset", ArtifactLearningTreatmentKind.RESET),
            "structured-memory": ArtifactLearningTreatment(
                "structured-memory", ArtifactLearningTreatmentKind.STRUCTURED_MEMORY
            ),
        },
        feedback_projectors={A01_FEEDBACK_VIEW_ID: terminal_outcome_feedback},
        consolidation_operations={A01_CONSOLIDATION_OPERATION_ID: consolidation_operation or default_consolidation},
        adapter_builder=adapter_builder,
    )


def _initialise(binding, arm_run):  # noqa: ANN001, ANN202
    result = binding.operations.initialise_learner(
        InitialiseLearnerRequest(
            study_run_id="a01-adapter-test",
            arm_run_id=arm_run.arm_run_id,
            arm_id=arm_run.arm_id,
            treatment_id=arm_run.treatment_id,
            repetition=arm_run.repetition,
            agent=_AGENT,
            compute=_COMPUTE,
            working_root=None,
        )
    )
    assert isinstance(result, LearnerStateHandle)
    return result


def test_artifact_learning_arms_have_disjoint_roots_and_reject_cross_arm_state(tmp_path: Path) -> None:
    plan = _plan()
    binding = _binding(
        tmp_path,
        adapter_builder=lambda **kwargs: HeatLoadStudyAdapter(Path(kwargs["workspace"]), []),
    )
    cold, exposed = plan.arm_runs
    cold_state = _initialise(binding, cold)
    exposed_state = _initialise(binding, exposed)

    assert cold_state.value.root != exposed_state.value.root
    assert cold_state.value.root.stat().st_ino != exposed_state.value.root.stat().st_ino
    cold_step = cold.steps[0]
    assert isinstance(cold_step, CompiledExperienceStep)
    with pytest.raises(ValueError, match="cross-arm-path-detected"):
        binding.operations.execute_experience(
            ExecuteExperienceRequest(
                arm_run=cold,
                step=cold_step,
                state=exposed_state,
                completed_trial_records=(),
                released_feedback=(),
            )
        )


def test_task_cannot_write_structured_memory_during_experience(tmp_path: Path) -> None:
    plan = _plan()
    exposed = plan.arm_runs[1]

    class WritingAdapter(HeatLoadStudyAdapter):
        def execute(self, request: AdapterRequest) -> AdapterResult:
            result = super().execute(request)
            memory = self.workspace / ".aec-bench-learning" / "memory"
            memory.mkdir(parents=True, exist_ok=True)
            (memory / "forbidden.md").write_text("task write\n", encoding="utf-8")
            return result

    binding = _binding(
        tmp_path,
        adapter_builder=lambda **kwargs: WritingAdapter(Path(kwargs["workspace"]), []),
    )
    initial = _initialise(binding, exposed)
    acquisition = exposed.steps[0]
    assert isinstance(acquisition, CompiledExperienceStep)
    before = tuple(initial.value.root.rglob("*"))

    with pytest.raises(ValueError, match="learner-channel-write-forbidden"):
        binding.operations.execute_experience(
            ExecuteExperienceRequest(
                arm_run=exposed,
                step=acquisition,
                state=initial,
                completed_trial_records=(),
                released_feedback=(),
            )
        )

    assert tuple(initial.value.root.rglob("*")) == before
    assert not (initial.value.root.parent / acquisition.step_id).exists()


def test_forbidden_consolidation_write_rolls_back_to_released_feedback_state(tmp_path: Path) -> None:
    plan = _plan()
    exposed = plan.arm_runs[1]

    def invalid_consolidation(context: ArtifactConsolidationContext) -> None:
        (context.namespace_root / "feedback" / "injected.json").write_text("{}\n", encoding="utf-8")

    binding = _binding(
        tmp_path,
        adapter_builder=lambda **kwargs: HeatLoadStudyAdapter(Path(kwargs["workspace"]), []),
        consolidation_operation=invalid_consolidation,
    )
    initial = _initialise(binding, exposed)
    acquisition_step = exposed.steps[0]
    feedback_step = exposed.steps[1]
    consolidation_step = exposed.steps[2]
    assert isinstance(acquisition_step, CompiledExperienceStep)
    acquisition = binding.operations.execute_experience(
        ExecuteExperienceRequest(
            arm_run=exposed,
            step=acquisition_step,
            state=initial,
            completed_trial_records=(),
            released_feedback=(),
        )
    )
    feedback = binding.operations.release_feedback(
        ReleaseFeedbackRequest(
            arm_run=exposed,
            step=feedback_step,
            state=acquisition.candidate_state,
            source_trial_record=acquisition.trial_record,
        )
    )
    assert isinstance(feedback, FeedbackReleaseResult)
    before = {
        path.relative_to(feedback.candidate_state.value.root): path.read_bytes()
        for path in feedback.candidate_state.value.root.rglob("*")
        if path.is_file()
    }

    with pytest.raises(ValueError, match="forbidden channels changed"):
        binding.operations.consolidate(
            ConsolidationRequest(
                arm_run=exposed,
                step=consolidation_step,
                state=feedback.candidate_state,
                feedback=(feedback.feedback,),
            )
        )

    assert {
        path.relative_to(feedback.candidate_state.value.root): path.read_bytes()
        for path in feedback.candidate_state.value.root.rglob("*")
        if path.is_file()
    } == before
    assert not (feedback.candidate_state.value.root.parent / consolidation_step.step_id).exists()
