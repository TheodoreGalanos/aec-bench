# ABOUTME: Binds runtime-neutral Learning Studies to complete local lifecycle trials.
# ABOUTME: Resolves exact lifecycle targets and keeps reset learner state separate from lifecycle evidence.

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any

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
from aec_bench.lifecycles.values import LifecycleExecution, LifecycleTrial

_LIFECYCLE_NAMESPACE = "lifecycle"
_MAX_FEEDBACK_BYTES = 1_000_000
_FORBIDDEN_FEEDBACK_KEYS = {"expected_answer", "gold", "private_path", "secret", "verifier_source"}
_FORBIDDEN_FEEDBACK_PATH_PARTS = ("/hidden/", "hidden/", "gold-submissions", "verifier-config")


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
        consolidation_operations: Mapping[str, LifecycleConsolidationOperation],
        initial_memory_root: Path | None,
        adapter_builder: Callable[..., Any] | None,
    ) -> None:
        self._run_root = run_root
        self._execution_condition = execution_condition
        self._treatment_kinds = dict(treatment_kinds)
        self._feedback_projectors = dict(feedback_projectors)
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
            copy_learner_state(state.root, candidate_root)
            context_snapshot: LearnerTreeSnapshot | None = None
            selected_context: Path | None = None
            if treatment_kind is LifecycleLearningTreatmentKind.STRUCTURED_MEMORY:
                context_snapshot = create_read_only_context_projection(state.root, context_root)
                selected_context = context_root

            lifecycle_trial = LifecycleTrial(
                planned=request.step.trial,
                package_dir=compiled.package_dir,
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
                    validate_read_only_context_projection(context_root, context_snapshot)

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
            raise ValueError(f"feedback-view-unsupported: {request.step.feedback_view_id}")
        try:
            projected_data = projector(request.source_trial_record)
            _validate_feedback_projection(projected_data, source_record=request.source_trial_record)
        except Exception as error:
            raise ValueError(f"feedback-projection-failed: {error}") from error

        candidate_root = self._candidate_root(request.arm_run.arm_run_id, request.step.step_id)
        before = learner_tree_snapshot(state.root)
        try:
            copy_learner_state(state.root, candidate_root)
            release_component = _safe_component(request.step.step_id)
            feedback_path = candidate_root / "feedback" / f"{release_component}.json"
            feedback_path.write_bytes(projected_data)
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
            copy_learner_state(state.root, candidate_root)
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
        self._treatment_kind(value.treatment_id)
        validate_learner_state(value.root)
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
        self._treatment_kind(reference.treatment_id)
        validate_learner_state(state_root)
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
        validate_learner_state(state.value.root)
        release_component = _safe_component(record.release_step_id)
        candidates = tuple(sorted((state.value.root / "feedback").glob(f"{release_component}.*")))
        if len(candidates) != 1 or candidates[0].suffix != ".json" or len(record.public_artifact_refs) != 1:
            raise ValueError(f"feedback-leak-detected: could not restore exact feedback {record.feedback_id}")
        reference = record.public_artifact_refs[0]
        payload = self._artifact_repository.read_bytes(reference)
        if candidates[0].read_bytes() != payload:
            raise ValueError(f"feedback-state-mismatch: state feedback differs from evidence {record.feedback_id}")
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
        validate_learner_state(state.root)
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
    "resolve_lifecycle_learning_target",
)
