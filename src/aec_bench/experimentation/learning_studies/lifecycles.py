# ABOUTME: Binds runtime-neutral Learning Studies to complete local lifecycle trials.
# ABOUTME: Resolves exact lifecycle targets and keeps reset learner state separate from lifecycle evidence.

from __future__ import annotations

import json
import shutil
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import BaseModel

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.learning_study_evidence import FeedbackReleaseRecord, LearnerStateRef
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.experimentation.learning_studies.errors import LearningStudyFeatureUnsupported
from aec_bench.experimentation.learning_studies.learner_state import (
    LearnerTreeSnapshot,
    copy_learner_state,
    create_read_only_context_projection,
    initialise_learner_state,
    learner_tree_snapshot,
    memory_snapshot,
    require_only_channel_changed,
    validate_learner_state,
    validate_read_only_context_projection,
)
from aec_bench.experimentation.learning_studies.planning import PlannedArmRun
from aec_bench.experimentation.learning_studies.runtime import (
    ConsolidationRequest,
    ExecuteExperienceRequest,
    ExperienceExecutionResult,
    FeedbackHandle,
    FeedbackReleaseResult,
    LearnerStateHandle,
    LearnerTransitionResult,
    LearningStudyOperations,
    ReleaseFeedbackRequest,
)
from aec_bench.harness.lifecycle_local import run_local_lifecycle
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.lifecycles.application import run_lifecycle_trial
from aec_bench.lifecycles.catalogue import lifecycle_template_ids, lifecycle_variant_ids, verify_lifecycle
from aec_bench.lifecycles.compiled import compile_lifecycle
from aec_bench.lifecycles.runtime.episode import LifecycleExecutionMode, LifecycleVisibilityPolicy
from aec_bench.lifecycles.stormwater_design.drainage_learning import (
    DRAINAGE_ACQUISITION_TASK_ID,
    DRAINAGE_PROBE_TASK_ID,
    DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID,
    validate_drainage_staged_review_feedback,
)
from aec_bench.lifecycles.stormwater_design.drainage_model import CHECKPOINT_IDS
from aec_bench.lifecycles.values import LifecycleExecution, LifecycleTrial

_LIFECYCLE_NAMESPACE = "lifecycle"
_MAX_FEEDBACK_BYTES = 1_000_000
_MAX_RAW_HISTORY_FILE_BYTES = 1_000_000
_MAX_RAW_HISTORY_SNAPSHOT_BYTES = 4_000_000
_FORBIDDEN_FEEDBACK_KEYS = {"expected_answer", "gold", "private_path", "secret", "verifier_source"}
_FORBIDDEN_FEEDBACK_PATH_PARTS = ("/hidden/", "hidden/", "gold-submissions", "verifier-config")
_RAW_HISTORY_SCHEMA = "aec-bench/lifecycle/raw-history/1"
_RAW_HISTORY_FILENAME = f"acquisition__{DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID}.json"
_RAW_HISTORY_STATE_CHANNELS = frozenset({"history", "memory", "feedback"})
_RAW_HISTORY_CONTEXT_CHANNELS = frozenset({"history", "feedback"})


def lifecycle_record_uses_run(record: TrialRecord, expected_run: Path) -> bool:
    """Return whether a lifecycle record is attached to the expected run directory."""
    attached = [
        path.parent
        for path, _media_type, logical_path in record.pending_artifacts.values()
        if logical_path is not None and Path(logical_path).parts[-2:] == ("run", "state.json")
    ]
    if attached:
        return len(attached) == 1 and attached[0].resolve(strict=True) == expected_run.resolve(strict=True)
    output = record.output
    agent_output = None if output is None else output.agent_output
    if agent_output is None:
        return False
    run = Path(agent_output.output_path)
    return run.is_absolute() and run.resolve(strict=True) == expected_run.resolve(strict=True)


@dataclass(frozen=True, slots=True)
class LifecycleLearningTarget:
    task_id: str
    template_id: str
    variant_id: str | None


@dataclass(frozen=True, slots=True)
class LifecycleExecutionCondition:
    execution_mode: LifecycleExecutionMode
    visibility_policy: LifecycleVisibilityPolicy

    def __post_init__(self) -> None:
        if not isinstance(self.execution_mode, LifecycleExecutionMode) or not isinstance(
            self.visibility_policy, LifecycleVisibilityPolicy
        ):
            raise ValueError("lifecycle-condition-invalid: execution mode and visibility policy must be typed values")

    @property
    def adapter_id(self) -> str:
        return f"lifecycle-local:{self.execution_mode.value}:{self.visibility_policy.value}"


class LifecycleLearningTreatmentKind(StrEnum):
    RESET = "reset"
    STRUCTURED_MEMORY = "structured-memory"
    RAW_HISTORY = "raw-history"


@dataclass(frozen=True)
class LifecycleLearnerState:
    arm_run_id: str
    treatment_id: str
    root: Path


@dataclass(frozen=True)
class LifecycleFeedback:
    path: Path
    artifact: ArtifactRef


@dataclass(frozen=True)
class LifecycleConsolidationContext:
    state_root: Path
    memory_root: Path
    feedback: tuple[LifecycleFeedback, ...]


type LifecycleFeedbackProjector = Callable[[TrialRecord], bytes]
type LifecyclePhaseEvidenceExtractor = Callable[[TrialRecord], BaseModel | None]
type LifecycleConsolidationOperation = Callable[[LifecycleConsolidationContext], None]


@dataclass(frozen=True)
class LifecycleLearningBinding:
    operations: LearningStudyOperations[LifecycleLearnerState, LifecycleFeedback]
    snapshot_state: Callable[[LearnerStateHandle[LifecycleLearnerState]], Path]
    feedback_artifacts: Callable[[FeedbackHandle[LifecycleFeedback]], tuple[ArtifactRef, ...]]
    restore_state: Callable[[LearnerStateRef, Path], LearnerStateHandle[LifecycleLearnerState]]
    restore_feedback: Callable[
        [FeedbackReleaseRecord, LearnerStateHandle[LifecycleLearnerState]],
        FeedbackHandle[LifecycleFeedback],
    ]


def lifecycle_learning_task_id(*, template_id: str, variant_id: str | None) -> str:
    """Build and validate one exact lifecycle task identity."""

    _safe_component(template_id)
    if variant_id is not None:
        _safe_component(variant_id)
    return resolve_lifecycle_learning_target(_canonical_task_id(template_id=template_id, variant_id=variant_id)).task_id


def resolve_lifecycle_learning_target(task_id: str) -> LifecycleLearningTarget:
    """Resolve one exact namespaced lifecycle task through the existing catalogue."""

    if not isinstance(task_id, str) or not task_id or "\\" in task_id:
        raise ValueError(f"lifecycle-task-id-invalid: {task_id!r}")
    parts = task_id.split("/")
    if len(parts) not in {2, 3} or parts[0] != _LIFECYCLE_NAMESPACE:
        raise ValueError(f"lifecycle-task-id-invalid: {task_id!r}")
    template_id = parts[1]
    variant_id = parts[2] if len(parts) == 3 else None
    try:
        _safe_component(template_id)
        if variant_id is not None:
            _safe_component(variant_id)
    except ValueError as error:
        raise ValueError(f"lifecycle-task-id-invalid: {task_id!r}") from error

    if template_id not in lifecycle_template_ids():
        raise ValueError(f"lifecycle-template-unknown: {template_id}")
    variants = lifecycle_variant_ids(template_id)
    if variants and variant_id is None:
        raise ValueError(f"lifecycle-variant-required: {template_id}")
    if not variants and variant_id is not None:
        raise ValueError(f"lifecycle-task-id-invalid: lifecycle {template_id!r} does not declare variants")
    if variant_id is not None and variant_id not in variants:
        known = ", ".join(variants)
        raise ValueError(f"lifecycle-variant-unknown: {variant_id}. Known: {known}")

    canonical = _canonical_task_id(template_id=template_id, variant_id=variant_id)
    if task_id != canonical:
        raise ValueError(f"lifecycle-task-id-invalid: task id is not canonical: {task_id!r}")
    return LifecycleLearningTarget(
        task_id=canonical,
        template_id=template_id,
        variant_id=variant_id,
    )


def build_lifecycle_learning_operations(
    *,
    run_root: Path,
    execution_condition: LifecycleExecutionCondition,
    treatment_kinds: Mapping[str, LifecycleLearningTreatmentKind],
    feedback_projectors: Mapping[str, LifecycleFeedbackProjector] | None = None,
    phase_evidence_extractors: Mapping[str, Callable[[TrialRecord], BaseModel | None]] | None = None,
    consolidation_operations: Mapping[str, LifecycleConsolidationOperation] | None = None,
    initial_memory_root: Path | None = None,
    adapter_builder: Callable[..., Any] | None = None,
    resume_existing_run: bool = False,
) -> LifecycleLearningBinding:
    """Build the local lifecycle Learning Studies callback bundle."""

    if (
        execution_condition.execution_mode is not LifecycleExecutionMode.FRESH_CONTEXT
        or execution_condition.visibility_policy is not LifecycleVisibilityPolicy.ARTIFACT_MEMORY
    ):
        raise LearningStudyFeatureUnsupported(
            "lifecycle-condition-invalid: B1 supports only fresh_context with artifact_memory"
        )
    selected_root = Path(run_root).resolve()
    if (
        not resume_existing_run
        and selected_root.exists()
        and (not selected_root.is_dir() or any(selected_root.iterdir()))
    ):
        raise ValueError(f"arm-isolation-failed: lifecycle learning run root must be empty: {selected_root}")
    if resume_existing_run and not selected_root.is_dir():
        raise ValueError(f"state-restore-invalid: lifecycle learning run root is unavailable: {selected_root}")
    coordinator = _LifecycleLearningCoordinator(
        run_root=selected_root,
        execution_condition=execution_condition,
        treatment_kinds=treatment_kinds,
        feedback_projectors=feedback_projectors or {},
        phase_evidence_extractors=phase_evidence_extractors or {},
        consolidation_operations=consolidation_operations or {},
        initial_memory_root=initial_memory_root,
        adapter_builder=adapter_builder,
    )
    return LifecycleLearningBinding(
        operations=LearningStudyOperations(
            initialise_learner=coordinator.initialise_learner,
            execute_experience=coordinator.execute_experience,
            release_feedback=coordinator.release_feedback,
            consolidate=coordinator.consolidate,
            discard_state=coordinator.discard_state,
        ),
        snapshot_state=lambda state: state.value.root,
        feedback_artifacts=coordinator.feedback_artifacts,
        restore_state=coordinator.restore_state,
        restore_feedback=coordinator.restore_feedback,
    )


class _LifecycleLearningCoordinator:
    def __init__(
        self,
        *,
        run_root: Path,
        execution_condition: LifecycleExecutionCondition,
        treatment_kinds: Mapping[str, LifecycleLearningTreatmentKind],
        feedback_projectors: Mapping[str, LifecycleFeedbackProjector],
        phase_evidence_extractors: Mapping[str, LifecyclePhaseEvidenceExtractor],
        consolidation_operations: Mapping[str, LifecycleConsolidationOperation],
        initial_memory_root: Path | None,
        adapter_builder: Callable[..., Any] | None,
    ) -> None:
        self._run_root = run_root
        self._execution_condition = execution_condition
        self._treatment_kinds = dict(treatment_kinds)
        self._feedback_projectors = dict(feedback_projectors)
        self._phase_evidence_extractors = dict(phase_evidence_extractors)
        self._consolidation_operations = dict(consolidation_operations)
        self._initial_memory_root = None if initial_memory_root is None else Path(initial_memory_root).resolve()
        self._adapter_builder = adapter_builder
        self._artifact_repository = ArtifactRepository(self._run_root / "_artifacts")
        for treatment_id, treatment_kind in self._treatment_kinds.items():
            if not treatment_id.strip():
                raise ValueError("lifecycle-treatment-unsupported: treatment ids must not be blank")
            if not isinstance(treatment_kind, LifecycleLearningTreatmentKind):
                raise ValueError(f"lifecycle-treatment-unsupported: {treatment_id}")

    def initialise_learner(
        self,
        arm_run: PlannedArmRun,
    ) -> LearnerStateHandle[LifecycleLearnerState]:
        treatment_kind = self._treatment_kind(arm_run.treatment_id)
        arm_root = self._arm_root(arm_run.arm_run_id)
        if arm_root.exists():
            raise ValueError(f"arm-isolation-failed: arm root already exists: {arm_root}")
        state_root = arm_root / "states" / "initial"
        state_root.parent.mkdir(parents=True, exist_ok=False)
        if treatment_kind is LifecycleLearningTreatmentKind.RAW_HISTORY:
            _initialise_raw_history_state(state_root)
        else:
            initialise_learner_state(
                state_root,
                memory_seed_root=(
                    self._initial_memory_root
                    if treatment_kind is LifecycleLearningTreatmentKind.STRUCTURED_MEMORY
                    else None
                ),
            )
        return self._handle(arm_run.arm_run_id, arm_run.treatment_id, "initial", state_root)

    def execute_experience(
        self,
        request: ExecuteExperienceRequest[LifecycleLearnerState],
    ) -> ExperienceExecutionResult[LifecycleLearnerState]:
        if request.step.trial.compute.backend != "local":
            raise LearningStudyFeatureUnsupported(
                f"lifecycle-backend-unsupported: {request.step.trial.compute.backend}"
            )
        state = self._state_for_arm(request.state, request.arm_run)
        treatment_kind = self._treatment_kind(state.treatment_id)
        target = resolve_lifecycle_learning_target(request.step.trial.task_id)
        arm_root = self._arm_root(request.arm_run.arm_run_id)
        step_component = _safe_component(request.step.step_id)
        experience_root = arm_root / "lifecycle-experiences" / step_component
        package_dir = experience_root / "package"
        run_dir = experience_root / "run"
        context_root = experience_root / "context"
        candidate_root = arm_root / "states" / step_component
        if package_dir.exists():
            raise ValueError(f"lifecycle-package-path-exists: {package_dir}")
        if run_dir.exists():
            raise ValueError(f"lifecycle-run-path-exists: {run_dir}")
        if experience_root.exists() or candidate_root.exists():
            raise ValueError(f"arm-isolation-failed: step storage already exists: {request.step.step_id}")
        experience_root.mkdir(parents=True, exist_ok=False)

        try:
            compiled = compile_lifecycle(
                target.template_id,
                package_dir,
                variant_id=target.variant_id,
            )
        except Exception as error:
            raise ValueError(f"lifecycle-compile-failed: {error}") from error
        if (
            compiled.package_dir.resolve() != package_dir.resolve()
            or compiled.envelope.template_id != target.template_id
            or compiled.envelope.variant_id != target.variant_id
        ):
            raise ValueError("lifecycle-target-mismatch: compiled lifecycle differs from the planned target")
        try:
            self._copy_state(state.root, candidate_root, treatment_kind)
            context_snapshot: LearnerTreeSnapshot | None = None
            selected_context: Path | None = None
            if treatment_kind is LifecycleLearningTreatmentKind.STRUCTURED_MEMORY:
                context_snapshot = create_read_only_context_projection(state.root, context_root)
                selected_context = context_root
            elif treatment_kind is LifecycleLearningTreatmentKind.RAW_HISTORY:
                context_snapshot = _create_raw_history_context_projection(state.root, context_root)
                selected_context = context_root

            lifecycle_trial = LifecycleTrial(
                planned=request.step.trial,
                compiled=compiled,
                run_dir=run_dir,
                execution_mode=self._execution_condition.execution_mode,
                visibility_policy=self._execution_condition.visibility_policy,
            )

            def execute(trial: LifecycleTrial) -> LifecycleExecution:
                try:
                    return run_local_lifecycle(
                        trial,
                        adapter_builder=self._adapter_builder,
                        read_only_context_root=selected_context,
                    )
                except Exception as error:
                    raise RuntimeError(f"lifecycle-execution-failed: {error}") from error

            try:
                record = run_lifecycle_trial(
                    trial=lifecycle_trial,
                    execute=execute,
                    verify=verify_lifecycle,
                )
            except RuntimeError as error:
                if str(error).startswith("lifecycle-execution-failed:"):
                    raise
                raise ValueError(f"lifecycle-recording-failed: {error}") from error
            except Exception as error:
                raise ValueError(f"lifecycle-recording-failed: {error}") from error
            finally:
                if context_snapshot is not None:
                    if treatment_kind is LifecycleLearningTreatmentKind.RAW_HISTORY:
                        _validate_raw_history_context_projection(context_root, context_snapshot)
                    else:
                        validate_read_only_context_projection(context_root, context_snapshot)

            extractor = self._phase_evidence_extractors.get(target.template_id)
            if extractor is not None:
                try:
                    evidence = extractor(record)
                except Exception:
                    evidence = None
                if evidence is not None:
                    record.attach_extension("lifecycle_learning_evidence", evidence)

            expected_identity = (
                request.step.trial.trial_id,
                request.step.trial.task_id,
                request.step.trial.repetition,
            )
            actual_identity = (record.trial_id, record.task_id, record.attempt)
            if actual_identity != expected_identity:
                raise ValueError(
                    f"lifecycle-trial-record-mismatch: returned {actual_identity!r}, expected {expected_identity!r}"
                )

            candidate = self._handle(
                request.arm_run.arm_run_id,
                state.treatment_id,
                request.step.step_id,
                candidate_root,
            )
            return ExperienceExecutionResult(trial_record=record, candidate_state=candidate)
        except Exception:
            shutil.rmtree(candidate_root, ignore_errors=True)
            raise

    def release_feedback(
        self,
        request: ReleaseFeedbackRequest[LifecycleLearnerState],
    ) -> FeedbackReleaseResult[LifecycleLearnerState, LifecycleFeedback]:
        state = self._state_for_arm(request.state, request.arm_run)
        treatment_kind = self._treatment_kind(state.treatment_id)
        if treatment_kind is LifecycleLearningTreatmentKind.RESET:
            raise ValueError("feedback-view-unsupported: reset treatment cannot retain feedback")
        projector = self._feedback_projectors.get(request.step.feedback_view_id)
        if projector is None:
            if treatment_kind is LifecycleLearningTreatmentKind.RAW_HISTORY:
                raise ValueError(
                    f"raw-history-feedback-invalid: unsupported feedback view {request.step.feedback_view_id}"
                )
            raise ValueError(f"feedback-view-unsupported: {request.step.feedback_view_id}")
        try:
            projected_data = projector(request.source_trial_record)
            _validate_feedback_projection(projected_data, source_record=request.source_trial_record)
            history_entry = (
                _raw_history_entry(
                    source_experience_id=request.step.source_experience_id,
                    source_record=request.source_trial_record,
                    feedback_view_id=request.step.feedback_view_id,
                    public_feedback=projected_data,
                )
                if treatment_kind is LifecycleLearningTreatmentKind.RAW_HISTORY
                else None
            )
        except Exception as error:
            if treatment_kind is LifecycleLearningTreatmentKind.RAW_HISTORY:
                message = str(error)
                if message.startswith("raw-history-"):
                    raise
                raise ValueError(f"raw-history-selection-invalid: {message}") from error
            raise ValueError(f"feedback-projection-failed: {error}") from error

        candidate_root = self._candidate_root(request.arm_run.arm_run_id, request.step.step_id)
        before = (
            _raw_history_tree_snapshot(state.root)
            if treatment_kind is LifecycleLearningTreatmentKind.RAW_HISTORY
            else learner_tree_snapshot(state.root)
        )
        try:
            self._copy_state(state.root, candidate_root, treatment_kind)
            release_component = _safe_component(request.step.step_id)
            feedback_path = candidate_root / "feedback" / f"{release_component}.json"
            feedback_path.write_bytes(projected_data)
            if treatment_kind is LifecycleLearningTreatmentKind.RAW_HISTORY:
                assert history_entry is not None
                history_path = candidate_root / "history" / _RAW_HISTORY_FILENAME
                if history_path.exists():
                    raise ValueError("raw-history-selection-invalid: history entry already exists")
                history_path.write_bytes(history_entry)
                _validate_raw_history_state(candidate_root)
                _require_raw_release_channels_changed(before, _raw_history_tree_snapshot(candidate_root))
            else:
                validate_learner_state(candidate_root)
                require_only_channel_changed(
                    before,
                    learner_tree_snapshot(candidate_root),
                    allowed="feedback",
                    category="feedback-state-mismatch",
                )
            artifact = self._artifact_repository.publish_bytes(
                data=projected_data,
                media_type="application/json",
            )
            candidate = self._handle(
                request.arm_run.arm_run_id,
                state.treatment_id,
                request.step.step_id,
                candidate_root,
            )
            return FeedbackReleaseResult(
                candidate_state=candidate,
                feedback=FeedbackHandle(
                    feedback_id=f"{request.arm_run.arm_run_id}:feedback:{request.step.step_id}",
                    source_experience_id=request.step.source_experience_id,
                    view_id=request.step.feedback_view_id,
                    value=LifecycleFeedback(path=feedback_path, artifact=artifact),
                ),
            )
        except Exception:
            shutil.rmtree(candidate_root, ignore_errors=True)
            raise

    def consolidate(
        self,
        request: ConsolidationRequest[LifecycleLearnerState, LifecycleFeedback],
    ) -> LearnerTransitionResult[LifecycleLearnerState]:
        state = self._state_for_arm(request.state, request.arm_run)
        treatment_kind = self._treatment_kind(state.treatment_id)
        if treatment_kind is LifecycleLearningTreatmentKind.RAW_HISTORY:
            raise ValueError("raw-history-consolidation-forbidden: raw history has no consolidation operation")
        if treatment_kind is not LifecycleLearningTreatmentKind.STRUCTURED_MEMORY:
            raise ValueError(f"consolidation-operation-unsupported: treatment {treatment_kind.value}")
        if not request.feedback:
            raise ValueError("consolidation-input-invalid: at least one feedback handle is required")
        operation = self._consolidation_operations.get(request.step.operation_id)
        if operation is None:
            raise ValueError(f"consolidation-operation-unsupported: {request.step.operation_id}")
        current_feedback = self._consolidation_feedback(state, request.feedback)

        candidate_root = self._candidate_root(request.arm_run.arm_run_id, request.step.step_id)
        before_tree = learner_tree_snapshot(state.root)
        before_memory = memory_snapshot(state.root)
        try:
            self._copy_state(state.root, candidate_root, treatment_kind)
            candidate_feedback = tuple(
                LifecycleFeedback(
                    path=candidate_root / "feedback" / item.path.name,
                    artifact=item.artifact,
                )
                for item in current_feedback
            )
            operation(
                LifecycleConsolidationContext(
                    state_root=candidate_root,
                    memory_root=candidate_root / "memory",
                    feedback=candidate_feedback,
                )
            )
            validate_learner_state(candidate_root)
            after_tree = learner_tree_snapshot(candidate_root)
            require_only_channel_changed(
                before_tree,
                after_tree,
                allowed="memory",
                category="consolidation-forbidden-state-change",
            )
            if memory_snapshot(candidate_root) == before_memory:
                raise ValueError("consolidation-memory-unchanged: structured memory did not change")
            return LearnerTransitionResult(
                candidate_state=self._handle(
                    request.arm_run.arm_run_id,
                    state.treatment_id,
                    request.step.step_id,
                    candidate_root,
                )
            )
        except Exception as error:
            shutil.rmtree(candidate_root, ignore_errors=True)
            if isinstance(error, ValueError) and str(error).startswith("consolidation-"):
                raise
            raise ValueError(f"consolidation-output-invalid: {error}") from error

    def discard_state(self, state: LearnerStateHandle[LifecycleLearnerState]) -> None:
        value = state.value
        treatment_kind = self._treatment_kind(value.treatment_id)
        self._validate_state(value.root, treatment_kind)
        states_root = (self._arm_root(value.arm_run_id) / "states").resolve()
        candidate_root = value.root.resolve()
        if candidate_root.parent != states_root or candidate_root.name == "initial":
            raise ValueError(f"state-discard-invalid: state is not a disposable candidate: {value.root}")
        shutil.rmtree(value.root, ignore_errors=False)

    def restore_state(
        self,
        reference: LearnerStateRef,
        state_root: Path,
    ) -> LearnerStateHandle[LifecycleLearnerState]:
        treatment_kind = self._treatment_kind(reference.treatment_id)
        self._validate_state(state_root, treatment_kind)
        self._validate_state_location(reference.arm_run_id, state_root)
        return LearnerStateHandle(
            state_id=reference.state_id,
            value=LifecycleLearnerState(
                arm_run_id=reference.arm_run_id,
                treatment_id=reference.treatment_id,
                root=Path(state_root),
            ),
        )

    def restore_feedback(
        self,
        record: FeedbackReleaseRecord,
        state: LearnerStateHandle[LifecycleLearnerState],
    ) -> FeedbackHandle[LifecycleFeedback]:
        if state.value.arm_run_id != record.arm_run_id:
            raise ValueError("cross-arm-path-detected: feedback and restored state use different arms")
        treatment_kind = self._treatment_kind(state.value.treatment_id)
        if treatment_kind is LifecycleLearningTreatmentKind.RESET:
            raise ValueError("feedback-view-unsupported: reset treatment has no feedback to restore")
        self._validate_state(state.value.root, treatment_kind)
        release_component = _safe_component(record.release_step_id)
        candidates = tuple(sorted((state.value.root / "feedback").glob(f"{release_component}.*")))
        if len(candidates) != 1 or candidates[0].suffix != ".json" or len(record.public_artifact_refs) != 1:
            raise ValueError(f"feedback-leak-detected: could not restore exact feedback {record.feedback_id}")
        reference = record.public_artifact_refs[0]
        payload = self._artifact_repository.read_bytes(reference)
        if candidates[0].read_bytes() != payload:
            raise ValueError(f"feedback-state-mismatch: state feedback differs from evidence {record.feedback_id}")
        if treatment_kind is LifecycleLearningTreatmentKind.RAW_HISTORY:
            feedback = validate_drainage_staged_review_feedback(payload)
            if (
                feedback["trial_id"] != record.source_trial_id
                or feedback["task_id"] != DRAINAGE_ACQUISITION_TASK_ID
                or feedback["feedback_view_id"] != record.view_id
                or record.view_id != DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID
            ):
                raise ValueError("raw-history-state-mismatch: feedback identity differs from release evidence")
            history_files = tuple((state.value.root / "history").glob("*.json"))
            if len(history_files) != 1:
                raise ValueError("raw-history-state-mismatch: history entry is missing or ambiguous")
            history = _decode_canonical_json(history_files[0].read_bytes(), category="raw-history-state-mismatch")
            if (
                history["source_experience_id"] != record.source_experience_id
                or history["source_trial_id"] != record.source_trial_id
                or history["source_task_id"] != DRAINAGE_ACQUISITION_TASK_ID
                or history["feedback_view_id"] != record.view_id
            ):
                raise ValueError("raw-history-state-mismatch: history identity differs from release evidence")
        return FeedbackHandle(
            feedback_id=record.feedback_id,
            source_experience_id=record.source_experience_id,
            view_id=record.view_id,
            value=LifecycleFeedback(path=candidates[0], artifact=reference),
        )

    @staticmethod
    def feedback_artifacts(feedback: FeedbackHandle[LifecycleFeedback]) -> tuple[ArtifactRef, ...]:
        return (feedback.value.artifact,)

    def _state_for_arm(
        self,
        handle: LearnerStateHandle[LifecycleLearnerState],
        arm_run: PlannedArmRun,
    ) -> LifecycleLearnerState:
        state = handle.value
        if state.arm_run_id != arm_run.arm_run_id:
            raise ValueError(
                f"cross-arm-path-detected: state belongs to {state.arm_run_id}, requested by {arm_run.arm_run_id}"
            )
        if state.treatment_id != arm_run.treatment_id:
            raise ValueError("learner-state-invalid: state treatment does not match the planned arm")
        self._treatment_kind(state.treatment_id)
        self._validate_state(state.root, self._treatment_kind(state.treatment_id))
        self._validate_state_location(arm_run.arm_run_id, state.root)
        return state

    def _consolidation_feedback(
        self,
        state: LifecycleLearnerState,
        feedback: tuple[FeedbackHandle[LifecycleFeedback], ...],
    ) -> tuple[LifecycleFeedback, ...]:
        selected: list[LifecycleFeedback] = []
        seen: set[str] = set()
        for handle in feedback:
            expected_prefix = f"{state.arm_run_id}:feedback:"
            if not handle.feedback_id.startswith(expected_prefix) or handle.feedback_id in seen:
                raise ValueError("consolidation-input-invalid: feedback identity does not belong to this arm")
            seen.add(handle.feedback_id)
            release_step_id = handle.feedback_id.removeprefix(expected_prefix)
            if not release_step_id or handle.value.path.name != f"{_safe_component(release_step_id)}.json":
                raise ValueError("consolidation-input-invalid: feedback path does not match its identity")
            current_path = state.root / "feedback" / handle.value.path.name
            if not current_path.is_file():
                raise ValueError(f"feedback-state-mismatch: current state lacks {handle.feedback_id}")
            published = self._artifact_repository.read_bytes(handle.value.artifact)
            if current_path.read_bytes() != published:
                raise ValueError(f"feedback-state-mismatch: current state differs from {handle.feedback_id}")
            selected.append(LifecycleFeedback(path=current_path, artifact=handle.value.artifact))
        return tuple(selected)

    @staticmethod
    def _validate_state(root: Path, treatment_kind: LifecycleLearningTreatmentKind) -> None:
        if treatment_kind is LifecycleLearningTreatmentKind.RAW_HISTORY:
            _validate_raw_history_state(root)
        else:
            validate_learner_state(root)

    @staticmethod
    def _copy_state(
        source: Path,
        destination: Path,
        treatment_kind: LifecycleLearningTreatmentKind,
    ) -> None:
        if treatment_kind is not LifecycleLearningTreatmentKind.RAW_HISTORY:
            copy_learner_state(source, destination)
            return
        _validate_raw_history_state(source)
        if destination.exists() or destination.is_symlink():
            raise ValueError("arm-isolation-failed: state destination already exists")
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copytree(source, destination)
            _validate_raw_history_state(destination)
        except Exception:
            shutil.rmtree(destination, ignore_errors=True)
            raise

    def _validate_state_location(self, arm_run_id: str, state_root: Path) -> None:
        resolved = Path(state_root).resolve()
        learner_arms = (self._run_root / "learner-arms").resolve()
        if learner_arms in resolved.parents:
            relative = resolved.relative_to(learner_arms)
            if len(relative.parts) != 3 or relative.parts[0] != arm_run_id or relative.parts[1] != "states":
                if relative.parts and relative.parts[0] != arm_run_id:
                    raise ValueError("cross-arm-path-detected: state path belongs to another arm")
                raise ValueError("learner-state-invalid: lifecycle evidence cannot be learner state")
            return
        if resolved.parent.name != arm_run_id:
            raise ValueError("state-restore-invalid: restored state path does not match its arm")

    def _treatment_kind(self, treatment_id: str) -> LifecycleLearningTreatmentKind:
        treatment_kind = self._treatment_kinds.get(treatment_id)
        if treatment_kind is None:
            if treatment_id == "raw-history":
                raise ValueError("raw-history-treatment-unsupported: caller did not map raw-history")
            raise ValueError(f"lifecycle-treatment-unsupported: {treatment_id}")
        return treatment_kind

    def _arm_root(self, arm_run_id: str) -> Path:
        return self._run_root / "learner-arms" / _safe_component(arm_run_id)

    def _candidate_root(self, arm_run_id: str, step_id: str) -> Path:
        candidate = self._arm_root(arm_run_id) / "states" / _safe_component(step_id)
        if candidate.exists() or candidate.is_symlink():
            raise ValueError(f"arm-isolation-failed: state path already exists: {candidate}")
        return candidate

    @staticmethod
    def _handle(
        arm_run_id: str,
        treatment_id: str,
        step_id: str,
        root: Path,
    ) -> LearnerStateHandle[LifecycleLearnerState]:
        return LearnerStateHandle(
            state_id=f"{arm_run_id}:state:{step_id}",
            value=LifecycleLearnerState(
                arm_run_id=arm_run_id,
                treatment_id=treatment_id,
                root=root,
            ),
        )


def _canonical_task_id(*, template_id: str, variant_id: str | None) -> str:
    suffix = template_id if variant_id is None else f"{template_id}/{variant_id}"
    return f"{_LIFECYCLE_NAMESPACE}/{suffix}"


def _validate_feedback_projection(data: bytes, *, source_record: TrialRecord) -> None:
    if not isinstance(data, bytes) or not data:
        raise ValueError("feedback-projection-invalid-json: lifecycle feedback must be non-empty bytes")
    if len(data) > _MAX_FEEDBACK_BYTES:
        raise ValueError("feedback-projection-too-large: lifecycle feedback exceeds the file limit")
    try:
        decoded = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("feedback-projection-invalid-json: lifecycle feedback must be UTF-8 JSON") from error
    if not isinstance(decoded, dict):
        raise ValueError("feedback-projection-invalid-json: lifecycle feedback must be a JSON object")
    forbidden_roots: tuple[str, ...] = ()
    output = source_record.output
    if output is not None and output.agent_output is not None:
        run_root = Path(output.agent_output.output_path)
        if run_root.is_absolute():
            forbidden_roots = (str(run_root), str(run_root.parent / "package"))
    _validate_feedback_value(decoded, forbidden_roots=forbidden_roots)


def _validate_feedback_value(value: object, *, forbidden_roots: tuple[str, ...]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = key.lower().replace("-", "_")
            if normalized in _FORBIDDEN_FEEDBACK_KEYS:
                raise ValueError(f"feedback-projection-unsafe: forbidden key: {key}")
            _validate_feedback_value(item, forbidden_roots=forbidden_roots)
        return
    if isinstance(value, list):
        for item in value:
            _validate_feedback_value(item, forbidden_roots=forbidden_roots)
        return
    if not isinstance(value, str):
        return
    lowered = value.lower().replace("\\", "/")
    if value.startswith("/") or (len(value) >= 3 and value[0].isalpha() and value[1:3] in {":/", ":\\"}):
        raise ValueError("feedback-projection-unsafe: absolute path string detected")
    if any(part in lowered for part in _FORBIDDEN_FEEDBACK_PATH_PARTS):
        raise ValueError("feedback-hidden-path-detected: hidden lifecycle path detected")
    if any(root and root in value for root in forbidden_roots):
        raise ValueError("feedback-projection-unsafe: lifecycle package or run root detected")


def _initialise_raw_history_state(root: Path) -> None:
    selected = Path(root)
    selected.mkdir(parents=True, exist_ok=False)
    try:
        for channel in sorted(_RAW_HISTORY_STATE_CHANNELS):
            (selected / channel).mkdir()
        _validate_raw_history_state(selected)
    except Exception:
        shutil.rmtree(selected, ignore_errors=True)
        raise


def _raw_history_entry(
    *,
    source_experience_id: str,
    source_record: TrialRecord,
    feedback_view_id: str,
    public_feedback: bytes,
) -> bytes:
    if source_record.task_id != DRAINAGE_ACQUISITION_TASK_ID:
        raise ValueError("raw-history-source-task-mismatch: source task is not the declared acquisition")
    if (
        source_record.execution_status.value != "completed"
        or source_record.evaluation_status.value != "completed"
        or source_record.evaluation is None
        or not source_record.evaluation.validity.verifier_completed
    ):
        raise ValueError("raw-history-source-trial-missing: source lifecycle trial is not verifier-complete")
    if feedback_view_id != DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID:
        raise ValueError("raw-history-feedback-invalid: feedback view is not the drainage public view")
    if not isinstance(source_experience_id, str) or not source_experience_id:
        raise ValueError("raw-history-selection-invalid: source experience identity is missing")
    instruction = source_record.input.instruction
    if not isinstance(instruction, str) or not instruction.strip():
        raise ValueError("raw-history-selection-invalid: public instruction is missing")
    _validate_public_text(instruction)
    feedback = _decode_canonical_json(public_feedback, category="raw-history-feedback-invalid")
    try:
        validate_drainage_staged_review_feedback(public_feedback)
    except Exception as error:
        raise ValueError(f"raw-history-feedback-invalid: {error}") from error
    if feedback.get("task_id") != source_record.task_id or feedback.get("trial_id") != source_record.trial_id:
        raise ValueError("raw-history-feedback-invalid: feedback source identity does not match the trial")
    if feedback.get("feedback_view_id") != feedback_view_id:
        raise ValueError("raw-history-feedback-invalid: feedback view identity does not match the release")
    outputs = feedback.get("checkpoint_submissions")
    if not isinstance(outputs, dict) or tuple(outputs) != tuple(sorted(CHECKPOINT_IDS)):
        raise ValueError("raw-history-selection-invalid: checkpoint submissions are not the declared output set")
    _validate_raw_public_value(outputs)
    entry = {
        "history_schema": _RAW_HISTORY_SCHEMA,
        "source_experience_id": source_experience_id,
        "source_task_id": source_record.task_id,
        "source_trial_id": source_record.trial_id,
        "feedback_view_id": feedback_view_id,
        "public_input": {"instruction": instruction},
        "public_outputs": outputs,
        "released_feedback": feedback,
    }
    return _canonical_json_bytes(entry, category="raw-history-state-invalid")


def _validate_public_text(value: str) -> None:
    lowered = value.lower().replace("\\", "/")
    if value.startswith("/") or (len(value) >= 3 and value[0].isalpha() and value[1:3] in {":/", ":\\"}):
        raise ValueError("raw-history-forbidden-material: public instruction contains a host path")
    if any(part in lowered for part in _FORBIDDEN_FEEDBACK_PATH_PARTS):
        raise ValueError("raw-history-forbidden-material: public instruction contains protected material")


def _validate_raw_public_value(value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("raw-history-forbidden-material: output key is invalid")
            _validate_raw_public_value(item)
    elif isinstance(value, list):
        for item in value:
            _validate_raw_public_value(item)
    elif isinstance(value, str):
        lowered = value.lower().replace("\\", "/")
        forbidden = (
            "/hidden/",
            "hidden/",
            "gold-submissions",
            "verifier-config",
            "metrics.json",
            "verification.json",
            "experiment-manifest.json",
            DRAINAGE_PROBE_TASK_ID.lower(),
        )
        if value.startswith("/") or (len(value) >= 3 and value[0].isalpha() and value[1:3] in {":/", ":\\"}):
            raise ValueError("raw-history-forbidden-material: output contains a host path")
        if any(token in lowered for token in forbidden):
            raise ValueError("raw-history-forbidden-material: output contains protected material")


def _canonical_json_bytes(value: object, *, category: str) -> bytes:
    try:
        text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n"
    except (TypeError, ValueError) as error:
        raise ValueError(f"{category}: JSON is not canonical") from error
    return text.encode("utf-8")


def _decode_canonical_json(data: bytes, *, category: str) -> dict[str, Any]:
    if not isinstance(data, bytes) or not data:
        raise ValueError(f"{category}: JSON bytes are missing")
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{category}: JSON is invalid UTF-8") from error
    if not isinstance(payload, dict) or _canonical_json_bytes(payload, category=category) != data:
        raise ValueError(f"{category}: JSON bytes are not canonical")
    return payload


def _raw_history_tree_snapshot(root: Path) -> LearnerTreeSnapshot:
    _validate_raw_history_state(root)
    return _tree_snapshot(Path(root))


def _require_raw_release_channels_changed(before: LearnerTreeSnapshot, after: LearnerTreeSnapshot) -> None:
    before_map = {(path, kind): content for path, kind, content in before}
    after_map = {(path, kind): content for path, kind, content in after}
    changed = {key[0] for key in before_map.keys() | after_map.keys() if before_map.get(key) != after_map.get(key)}
    changed_roots = {PurePosixPath(path).parts[0] for path in changed}
    if changed_roots != {"history", "feedback"}:
        raise ValueError("raw-history-channel-write-forbidden: release must change only history/ and feedback/")


def _tree_snapshot(root: Path) -> LearnerTreeSnapshot:
    entries: list[tuple[str, str, bytes]] = []
    for path in sorted(Path(root).rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ValueError("raw-history-path-unsafe: symbolic link in learner state")
        if path.is_dir():
            entries.append((relative, "directory", b""))
        elif path.is_file():
            entries.append((relative, "file", path.read_bytes()))
        else:
            raise ValueError("raw-history-path-unsafe: special file in learner state")
    return tuple(entries)


def _validate_raw_history_state(root: Path) -> None:
    selected = Path(root)
    _require_safe_directory(selected, "raw-history-state-invalid")
    top_level = {path.name: path for path in selected.iterdir()}
    if set(top_level) != _RAW_HISTORY_STATE_CHANNELS or any(not path.is_dir() for path in top_level.values()):
        raise ValueError("raw-history-state-invalid: state root must contain history/, memory/, and feedback/")
    _validate_raw_channel(selected / "history", channel="history")
    _validate_raw_channel(selected / "feedback", channel="feedback")
    history_entries = tuple((selected / "history").iterdir())
    if any(path.is_dir() for path in history_entries):
        raise ValueError("raw-history-selection-invalid: history entries must be files")
    if len(history_entries) > 1 or (history_entries and history_entries[0].name != _RAW_HISTORY_FILENAME):
        raise ValueError("raw-history-selection-invalid: history entry is ambiguous")
    if any(path.is_dir() for path in (selected / "feedback").iterdir()):
        raise ValueError("raw-history-selection-invalid: feedback entries must be files")
    memory = selected / "memory"
    if any(memory.rglob("*")):
        raise ValueError("raw-history-channel-write-forbidden: raw history memory must remain empty")
    total = sum(path.stat().st_size for path in selected.rglob("*") if path.is_file() and not path.is_symlink())
    if total > _MAX_RAW_HISTORY_SNAPSHOT_BYTES:
        raise ValueError("raw-history-snapshot-too-large: raw history snapshot exceeds 4 MiB")


def _create_raw_history_context_projection(state_root: Path, destination: Path) -> LearnerTreeSnapshot:
    _validate_raw_history_state(state_root)
    target = Path(destination)
    if target.exists() or target.is_symlink():
        raise ValueError("raw-history-path-unsafe: context path already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.mkdir()
        for channel in sorted(_RAW_HISTORY_CONTEXT_CHANNELS):
            shutil.copytree(Path(state_root) / channel, target / channel)
        _validate_raw_history_context_projection(target, ())
        for path in sorted(target.rglob("*"), reverse=True):
            path.chmod(0o500 if path.is_dir() else 0o400)
        target.chmod(0o500)
        return _tree_snapshot(target)
    except Exception as error:
        shutil.rmtree(target, ignore_errors=True)
        if isinstance(error, ValueError) and str(error).startswith("raw-history-"):
            raise
        raise ValueError(f"raw-history-state-invalid: context projection failed: {error}") from error


def _validate_raw_history_context_projection(root: Path, expected: LearnerTreeSnapshot) -> None:
    try:
        selected = Path(root)
        _require_safe_directory(selected, "raw-history-context-mutated")
        top_level = {path.name: path for path in selected.iterdir()}
        if set(top_level) != _RAW_HISTORY_CONTEXT_CHANNELS or any(not path.is_dir() for path in top_level.values()):
            raise ValueError("raw-history-context-mutated: context channels differ")
        _validate_raw_channel(selected / "history", channel="history")
        _validate_raw_channel(selected / "feedback", channel="feedback")
        actual = _tree_snapshot(selected)
    except Exception as error:
        if isinstance(error, ValueError) and str(error).startswith("raw-history-"):
            raise
        raise ValueError(f"raw-history-context-mutated: {error}") from error
    if expected and actual != expected:
        raise ValueError("raw-history-context-mutated: projected context bytes changed")


def _validate_raw_channel(root: Path, *, channel: str) -> None:
    _require_safe_directory(root, "raw-history-state-invalid")
    seen: set[str] = set()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        relative = path.relative_to(root)
        _validate_raw_relative_path(relative)
        key = relative.as_posix().casefold()
        if key in seen:
            raise ValueError("raw-history-path-unsafe: case-insensitive path collision")
        seen.add(key)
        if path.is_symlink():
            raise ValueError("raw-history-path-unsafe: symbolic link in learner state")
        if path.is_dir():
            continue
        if not path.is_file() or path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
            raise ValueError("raw-history-path-unsafe: unsupported learner file")
        if path.suffix.lower() != ".json":
            raise ValueError("raw-history-selection-invalid: history and feedback must be JSON")
        if path.stat().st_size > _MAX_RAW_HISTORY_FILE_BYTES:
            raise ValueError("raw-history-file-too-large: learner state file exceeds 1 MiB")
        data = path.read_bytes()
        if channel == "history":
            _validate_history_entry(data)
        else:
            payload = _decode_canonical_json(data, category="raw-history-state-invalid")
            try:
                validate_drainage_staged_review_feedback(data)
            except Exception as error:
                raise ValueError(f"raw-history-feedback-invalid: {error}") from error
            if payload.get("feedback_view_id") != DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID:
                raise ValueError("raw-history-feedback-invalid: feedback view identity is invalid")


def _validate_history_entry(data: bytes) -> None:
    payload = _decode_canonical_json(data, category="raw-history-state-invalid")
    expected = {
        "history_schema",
        "source_experience_id",
        "source_task_id",
        "source_trial_id",
        "feedback_view_id",
        "public_input",
        "public_outputs",
        "released_feedback",
    }
    if set(payload) != expected or payload["history_schema"] != _RAW_HISTORY_SCHEMA:
        raise ValueError("raw-history-selection-invalid: history entry fields do not match the allowlist")
    if payload["source_task_id"] != DRAINAGE_ACQUISITION_TASK_ID:
        raise ValueError("raw-history-source-task-mismatch: history source task is not the acquisition")
    if payload["feedback_view_id"] != DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID:
        raise ValueError("raw-history-feedback-invalid: history feedback view is invalid")
    if any(
        not isinstance(payload[item], str) or not payload[item]
        for item in ("source_experience_id", "source_task_id", "source_trial_id")
    ):
        raise ValueError("raw-history-selection-invalid: history source identity is invalid")
    public_input = payload["public_input"]
    if (
        not isinstance(public_input, dict)
        or set(public_input) != {"instruction"}
        or not isinstance(public_input["instruction"], str)
    ):
        raise ValueError("raw-history-selection-invalid: public instruction is invalid")
    _validate_public_text(public_input["instruction"])
    outputs = payload["public_outputs"]
    if not isinstance(outputs, dict) or tuple(outputs) != tuple(sorted(CHECKPOINT_IDS)):
        raise ValueError("raw-history-selection-invalid: public outputs are invalid")
    if any(not isinstance(outputs[item], dict) for item in CHECKPOINT_IDS):
        raise ValueError("raw-history-selection-invalid: public output is not an archived submission")
    _validate_raw_public_value(outputs)
    feedback = payload["released_feedback"]
    if not isinstance(feedback, dict):
        raise ValueError("raw-history-feedback-invalid: released feedback is invalid")
    feedback_bytes = _canonical_json_bytes(feedback, category="raw-history-feedback-invalid")
    try:
        validate_drainage_staged_review_feedback(feedback_bytes)
    except Exception as error:
        raise ValueError(f"raw-history-feedback-invalid: {error}") from error
    if feedback.get("task_id") != payload["source_task_id"] or feedback.get("trial_id") != payload["source_trial_id"]:
        raise ValueError("raw-history-state-mismatch: history feedback source identity differs")
    if feedback.get("feedback_view_id") != payload["feedback_view_id"]:
        raise ValueError("raw-history-state-mismatch: history feedback view differs")
    if feedback.get("checkpoint_submissions") != outputs:
        raise ValueError("raw-history-state-mismatch: history outputs differ from released feedback")


def _require_safe_directory(path: Path, category: str) -> None:
    if path.is_symlink() or not path.is_dir():
        raise ValueError(f"{category}: learner state directory is invalid")
    try:
        path.resolve(strict=True)
    except OSError as error:
        raise ValueError(f"{category}: learner state directory is unreadable") from error


def _validate_raw_relative_path(path: Path) -> None:
    pure = PurePosixPath(path.as_posix())
    if (
        pure.is_absolute()
        or not pure.parts
        or any(part in {".", ".."} or part.startswith(".") or "\\" in part for part in pure.parts)
    ):
        raise ValueError("raw-history-path-unsafe: unsafe learner path")


def _safe_component(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\\" in value:
        raise ValueError(f"lifecycle-task-id-invalid: unsafe identity component: {value!r}")
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or len(candidate.parts) != 1 or value in {".", ".."} or candidate.name != value:
        raise ValueError(f"lifecycle-task-id-invalid: unsafe identity component: {value!r}")
    return value


__all__ = (
    "LifecycleConsolidationContext",
    "LifecycleConsolidationOperation",
    "LifecycleExecutionCondition",
    "LifecycleFeedback",
    "LifecycleFeedbackProjector",
    "LifecycleLearnerState",
    "LifecycleLearningBinding",
    "LifecycleLearningTarget",
    "LifecycleLearningTreatmentKind",
    "build_lifecycle_learning_operations",
    "lifecycle_learning_task_id",
    "lifecycle_record_uses_run",
    "resolve_lifecycle_learning_target",
)
