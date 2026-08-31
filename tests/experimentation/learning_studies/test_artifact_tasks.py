# ABOUTME: Tests the local artifact-task Learning Study adapter and filesystem isolation.
# ABOUTME: Proves copy-on-write state, channel permissions, and cross-arm rejection with real tasks.

from dataclasses import replace
from pathlib import Path

import pytest

from aec_bench.adapters.base import AdapterRequest, AdapterResult
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.experimentation.learning_studies.artifact_tasks import (
    ArtifactConsolidationContext,
    ArtifactLearningTreatmentKind,
    build_artifact_learning_operations,
    terminal_outcome_feedback,
)
from aec_bench.experimentation.learning_studies.errors import LearningStudyFeatureUnsupported
from aec_bench.experimentation.learning_studies.planning import CompiledExperienceStep, compile_learning_study
from aec_bench.experimentation.learning_studies.protocol_collection import (
    BUILTIN_LEARNING_STUDY_PROTOCOLS,
    load_learning_study_protocol,
)
from aec_bench.experimentation.learning_studies.runtime import (
    ConsolidationRequest,
    ExecuteExperienceRequest,
    FeedbackReleaseResult,
    LearnerStateHandle,
    ReleaseFeedbackRequest,
)
from aec_bench.tasks.loader import load_task_definition

from .support import HeatLoadStudyAdapter, resolve_learning_task_dir

_REPOSITORY_ROOT = Path(__file__).parents[3]
_TASKS_ROOT = _REPOSITORY_ROOT / "tasks"
_AGENT = AgentConfig(name="a01-test-agent", adapter="direct", model="fixed-test-model")
_COMPUTE = ComputeConfig(backend="local", resource_limits={"memory_mb": 512}, timeout_override=30)
_PROTOCOL_PATH = BUILTIN_LEARNING_STUDY_PROTOCOLS / "a01-artifact-structural-transfer"
_FEEDBACK_VIEW_ID = "heat-load-public-evaluation"
_CONSOLIDATION_OPERATION_ID = "update-structured-memory"


def _resolve_task(task_id: str):  # noqa: ANN202
    return load_task_definition(resolve_learning_task_dir(_TASKS_ROOT, task_id), _TASKS_ROOT)


def _plan():  # noqa: ANN202
    return compile_learning_study(
        study_run_id="a01-adapter-test",
        spec=load_learning_study_protocol(_PROTOCOL_PATH, agent=_AGENT, compute=_COMPUTE),
        resolve_task=_resolve_task,
    )


def _binding(  # noqa: ANN001, ANN202
    tmp_path: Path,
    *,
    adapter_builder,
    consolidation_operation=None,
    feedback_projector=terminal_outcome_feedback,
):
    def default_consolidation(context: ArtifactConsolidationContext) -> None:
        context.memory_root.mkdir(parents=True, exist_ok=True)
        (context.memory_root / "method.json").write_text('{"method":"heat-load"}\n', encoding="utf-8")

    return build_artifact_learning_operations(
        tasks_root=_TASKS_ROOT,
        run_root=tmp_path / "study",
        treatment_kinds={
            "reset": ArtifactLearningTreatmentKind.RESET,
            "structured-memory": ArtifactLearningTreatmentKind.STRUCTURED_MEMORY,
        },
        feedback_projectors={_FEEDBACK_VIEW_ID: feedback_projector},
        consolidation_operations={_CONSOLIDATION_OPERATION_ID: consolidation_operation or default_consolidation},
        adapter_builder=adapter_builder,
    )


def _initialise(binding, arm_run):  # noqa: ANN001, ANN202
    result = binding.operations.initialise_learner(arm_run)
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
            )
        )


def test_artifact_learning_rejects_non_local_compute_before_creating_task_workspace(tmp_path: Path) -> None:
    exposed = _plan().arm_runs[1]
    binding = _binding(
        tmp_path,
        adapter_builder=lambda **kwargs: HeatLoadStudyAdapter(Path(kwargs["workspace"]), []),
    )

    initial = _initialise(binding, exposed)
    acquisition = exposed.steps[0]
    assert isinstance(acquisition, CompiledExperienceStep)
    modal_step = replace(acquisition, trial=replace(acquisition.trial, compute=ComputeConfig(backend="modal")))

    with pytest.raises(LearningStudyFeatureUnsupported, match="artifact-backend-unsupported: modal"):
        binding.operations.execute_experience(ExecuteExperienceRequest(arm_run=exposed, step=modal_step, state=initial))

    assert not (tmp_path / "study" / "learner-arms" / exposed.arm_run_id / "task-workspaces").exists()


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
            )
        )

    assert tuple(initial.value.root.rglob("*")) == before
    assert not (initial.value.root.parent / acquisition.step_id).exists()


@pytest.mark.parametrize("data", [b"not JSON", b"[]"])
def test_invalid_feedback_projection_does_not_create_candidate_state(tmp_path: Path, data: bytes) -> None:
    exposed = _plan().arm_runs[1]
    binding = _binding(
        tmp_path,
        adapter_builder=lambda **kwargs: HeatLoadStudyAdapter(Path(kwargs["workspace"]), []),
        feedback_projector=lambda _record: data,
    )
    initial = _initialise(binding, exposed)
    acquisition_step = exposed.steps[0]
    feedback_step = exposed.steps[1]
    assert isinstance(acquisition_step, CompiledExperienceStep)
    acquisition = binding.operations.execute_experience(
        ExecuteExperienceRequest(
            arm_run=exposed,
            step=acquisition_step,
            state=initial,
        )
    )

    with pytest.raises(ValueError, match="feedback-projection-failed"):
        binding.operations.release_feedback(
            ReleaseFeedbackRequest(
                arm_run=exposed,
                step=feedback_step,
                state=acquisition.candidate_state,
                source_trial_record=acquisition.trial_record,
            )
        )

    assert not (acquisition.candidate_state.value.root.parent / feedback_step.step_id).exists()


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
