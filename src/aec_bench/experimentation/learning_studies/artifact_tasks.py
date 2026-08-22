# ABOUTME: Binds runtime-neutral Learning Studies to ordinary local artifact-task trials.
# ABOUTME: Carries only allowlisted learner artifacts through isolated copy-on-write arm state.

from __future__ import annotations

import json
import shutil
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.learning_study_evidence import FeedbackReleaseRecord, LearnerStateRef
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.experimentation.learning_studies.errors import LearningStudyFeatureUnsupported
from aec_bench.experimentation.learning_studies.runtime import (
    ConsolidationRequest,
    ExecuteExperienceRequest,
    ExperienceExecutionResult,
    FeedbackHandle,
    FeedbackReleaseResult,
    InitialiseLearnerRequest,
    LearnerStateHandle,
    LearnerTransitionResult,
    LearningStudyOperations,
    ReleaseFeedbackRequest,
)
from aec_bench.harness.artifact_tasks import AdapterBuilder, LocalTaskRuntime, run_trial, single_attempt
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.tasks.instance import ResolvedTaskInstance, resolve_instance_paths
from aec_bench.tasks.loader import load_task_definition

_LEARNER_NAMESPACE = ".aec-bench-learning"
_STATE_CHANNELS = frozenset({"history", "memory", "feedback"})
_MAX_FILE_BYTES = 1_000_000
_MAX_STATE_BYTES = 4_000_000
_ALLOWED_MEMORY_SUFFIXES = frozenset({".json", ".md", ".txt"})


class ArtifactLearningTreatmentKind(StrEnum):
    RESET = "reset"
    RAW_HISTORY = "raw-history"
    STRUCTURED_MEMORY = "structured-memory"


@dataclass(frozen=True)
class ArtifactLearnerState:
    arm_run_id: str
    treatment_id: str
    root: Path


@dataclass(frozen=True)
class ArtifactFeedback:
    path: Path
    artifact: ArtifactRef


@dataclass(frozen=True)
class ArtifactConsolidationContext:
    namespace_root: Path
    feedback: tuple[ArtifactFeedback, ...]

    @property
    def memory_root(self) -> Path:
        return self.namespace_root / "memory"


type ArtifactFeedbackProjector = Callable[[TrialRecord], bytes]
type ArtifactConsolidationOperation = Callable[[ArtifactConsolidationContext], None]


@dataclass(frozen=True)
class ArtifactLearningBinding:
    operations: LearningStudyOperations[ArtifactLearnerState, ArtifactFeedback]
    snapshot_state: Callable[[LearnerStateHandle[ArtifactLearnerState]], Path]
    feedback_artifacts: Callable[[FeedbackHandle[ArtifactFeedback]], tuple[ArtifactRef, ...]]
    restore_state: Callable[[LearnerStateRef, Path], LearnerStateHandle[ArtifactLearnerState]]
    restore_feedback: Callable[
        [FeedbackReleaseRecord, LearnerStateHandle[ArtifactLearnerState]],
        FeedbackHandle[ArtifactFeedback],
    ]


def build_artifact_learning_operations(
    *,
    tasks_root: Path,
    run_root: Path,
    treatment_kinds: Mapping[str, ArtifactLearningTreatmentKind],
    feedback_projectors: Mapping[str, ArtifactFeedbackProjector],
    consolidation_operations: Mapping[str, ArtifactConsolidationOperation],
    adapter_builder: AdapterBuilder | None = None,
) -> ArtifactLearningBinding:
    """Build one local-only callback bundle with explicit adapter-owned policy maps."""

    coordinator = _ArtifactLearningCoordinator(
        tasks_root=tasks_root,
        run_root=run_root,
        treatment_kinds=treatment_kinds,
        feedback_projectors=feedback_projectors,
        consolidation_operations=consolidation_operations,
        adapter_builder=adapter_builder,
    )
    return ArtifactLearningBinding(
        operations=LearningStudyOperations(
            initialise_learner=coordinator.initialise_learner,
            execute_experience=coordinator.execute_experience,
            release_feedback=coordinator.release_feedback,
            consolidate=coordinator.consolidate,
            discard_state=coordinator.discard_state,
            close_state=lambda _state: None,
        ),
        snapshot_state=lambda state: state.value.root,
        feedback_artifacts=lambda feedback: (feedback.value.artifact,),
        restore_state=coordinator.restore_state,
        restore_feedback=coordinator.restore_feedback,
    )


class _ArtifactLearningCoordinator:
    def __init__(
        self,
        *,
        tasks_root: Path,
        run_root: Path,
        treatment_kinds: Mapping[str, ArtifactLearningTreatmentKind],
        feedback_projectors: Mapping[str, ArtifactFeedbackProjector],
        consolidation_operations: Mapping[str, ArtifactConsolidationOperation],
        adapter_builder: AdapterBuilder | None,
    ) -> None:
        self._tasks_root = tasks_root.resolve()
        self._run_root = run_root.resolve()
        self._treatment_kinds = dict(treatment_kinds)
        self._feedback_projectors = dict(feedback_projectors)
        self._consolidation_operations = dict(consolidation_operations)
        self._adapter_builder = adapter_builder
        if any(not treatment_id.strip() for treatment_id in self._treatment_kinds):
            raise ValueError("artifact learning treatment ids must not be blank")
        self._artifact_repository = ArtifactRepository(self._run_root / "_artifacts")

    def initialise_learner(
        self,
        request: InitialiseLearnerRequest,
    ) -> LearnerStateHandle[ArtifactLearnerState]:
        if request.compute.backend != "local":
            raise LearningStudyFeatureUnsupported(
                f"study {request.study_run_id} arm {request.arm_id}: "
                f"artifact-backend-unsupported: {request.compute.backend}"
            )
        self._treatment_kind(request.treatment_id)
        arm_root = self._arm_root(request.arm_run_id)
        if arm_root.exists():
            raise ValueError(f"arm-isolation-failed: arm root already exists: {arm_root}")
        state_root = arm_root / "states" / "initial"
        namespace = state_root / _LEARNER_NAMESPACE
        for channel in sorted(_STATE_CHANNELS):
            (namespace / channel).mkdir(parents=True, exist_ok=False)
        _validate_state_tree(state_root)
        return self._handle(request.arm_run_id, request.treatment_id, "initial", state_root)

    def execute_experience(
        self,
        request: ExecuteExperienceRequest[ArtifactLearnerState, ArtifactFeedback],
    ) -> ExperienceExecutionResult[ArtifactLearnerState]:
        state = self._state_for_arm(request.state, request.arm_run.arm_run_id)
        treatment_kind = self._treatment_kind(state.treatment_id)
        task = self._resolve_task(request.step.trial.task_id)
        if (task.instance_dir / _LEARNER_NAMESPACE).exists():
            raise ValueError("learner-path-unsafe: task uses the reserved learner namespace")

        arm_root = self._arm_root(request.arm_run.arm_run_id)
        step_component = _safe_component(request.step.step_id)
        export = arm_root / "selected-workspaces" / step_component
        candidate_root = arm_root / "states" / step_component
        if export.exists() or candidate_root.exists():
            raise ValueError(f"arm-isolation-failed: step storage already exists: {request.step.step_id}")

        runtime = LocalTaskRuntime(
            work_root=arm_root / "task-workspaces" / step_component,
            # Trial evidence is host-owned and append-only. It is not learner state,
            # so all arms can publish ordinary record artifacts to the study ledger.
            artifact_root=self._run_root / "ledger" / "_artifacts",
            adapter_builder=self._adapter_builder,
            agent_files=self._agent_files(state, treatment_kind),
        )
        record = run_trial(
            runtime=runtime,
            task=task,
            trial=request.step.trial,
            recipe=single_attempt(),
            selected_workspace_export=export,
        )
        try:
            self._validate_experience_namespace(
                state=state,
                treatment_kind=treatment_kind,
                exported_workspace=export,
            )
            _copy_state(state.root, candidate_root)
            candidate = self._handle(
                request.arm_run.arm_run_id,
                state.treatment_id,
                request.step.step_id,
                candidate_root,
            )
            return ExperienceExecutionResult(
                trial_record=record,
                candidate_state=candidate,
                changed_channels=(),
            )
        except Exception:
            shutil.rmtree(candidate_root, ignore_errors=True)
            raise

    def release_feedback(
        self,
        request: ReleaseFeedbackRequest[ArtifactLearnerState],
    ) -> FeedbackReleaseResult[ArtifactLearnerState, ArtifactFeedback]:
        state = self._state_for_arm(request.state, request.arm_run.arm_run_id)
        treatment_kind = self._treatment_kind(state.treatment_id)
        if treatment_kind is ArtifactLearningTreatmentKind.RESET:
            raise ValueError("feedback-view-unsupported: reset treatment cannot retain feedback")
        projector = self._feedback_projectors.get(request.step.feedback_view_id)
        if projector is None:
            raise ValueError(f"feedback-view-unsupported: {request.step.feedback_view_id}")
        try:
            projected_data = projector(request.source_trial_record)
            _validate_feedback_projection(projected_data)
        except Exception as error:
            raise ValueError(f"feedback-projection-failed: {error}") from error
        if len(projected_data) > _MAX_FILE_BYTES:
            raise ValueError("feedback-projection-failed: projected feedback is too large")

        candidate_root = self._candidate_root(request.arm_run.arm_run_id, request.step.step_id)
        try:
            _copy_state(state.root, candidate_root)
            feedback_id = f"{request.arm_run.arm_run_id}:feedback:{request.step.step_id}"
            feedback_path = (
                candidate_root / _LEARNER_NAMESPACE / "feedback" / f"{_safe_component(request.step.step_id)}.json"
            )
            feedback_path.write_bytes(projected_data)
            changed_channels = ["feedback"]
            if treatment_kind is ArtifactLearningTreatmentKind.RAW_HISTORY:
                history_path = (
                    candidate_root / _LEARNER_NAMESPACE / "history" / f"{_safe_component(request.step.step_id)}.json"
                )
                history_path.write_bytes(
                    _raw_history_entry(
                        source_experience_id=request.step.source_experience_id,
                        feedback_view_id=request.step.feedback_view_id,
                        public_feedback=projected_data,
                    )
                )
                changed_channels.append("history")
            _validate_state_tree(candidate_root)
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
                    feedback_id=feedback_id,
                    source_experience_id=request.step.source_experience_id,
                    view_id=request.step.feedback_view_id,
                    value=ArtifactFeedback(path=feedback_path, artifact=artifact),
                ),
                changed_channels=tuple(changed_channels),
            )
        except Exception:
            shutil.rmtree(candidate_root, ignore_errors=True)
            raise

    def consolidate(
        self,
        request: ConsolidationRequest[ArtifactLearnerState, ArtifactFeedback],
    ) -> LearnerTransitionResult[ArtifactLearnerState]:
        state = self._state_for_arm(request.state, request.arm_run.arm_run_id)
        treatment_kind = self._treatment_kind(state.treatment_id)
        if treatment_kind is not ArtifactLearningTreatmentKind.STRUCTURED_MEMORY:
            raise ValueError(f"consolidation-operation-unsupported: treatment {treatment_kind.value}")
        operation = self._consolidation_operations.get(request.step.operation_id)
        if operation is None:
            raise ValueError(f"consolidation-operation-unsupported: {request.step.operation_id}")

        candidate_root = self._candidate_root(request.arm_run.arm_run_id, request.step.step_id)
        before = _channel_contents(state.root)
        try:
            _copy_state(state.root, candidate_root)
            operation(
                ArtifactConsolidationContext(
                    namespace_root=candidate_root / _LEARNER_NAMESPACE,
                    feedback=tuple(item.value for item in request.feedback),
                )
            )
            _validate_state_tree(candidate_root)
            after = _channel_contents(candidate_root)
            changed = tuple(sorted(channel for channel in after if after[channel] != before[channel]))
            forbidden = set(changed) - {"memory"}
            if forbidden:
                raise ValueError(f"consolidation-output-invalid: forbidden channels changed: {sorted(forbidden)}")
            if "memory" not in changed:
                raise ValueError("consolidation-output-invalid: structured memory did not change")
            candidate = self._handle(
                request.arm_run.arm_run_id,
                state.treatment_id,
                request.step.step_id,
                candidate_root,
            )
            return LearnerTransitionResult(candidate_state=candidate, changed_channels=("memory",))
        except Exception:
            shutil.rmtree(candidate_root, ignore_errors=True)
            raise

    @staticmethod
    def discard_state(state: LearnerStateHandle[ArtifactLearnerState]) -> None:
        shutil.rmtree(state.value.root, ignore_errors=False)

    def restore_state(
        self,
        reference: LearnerStateRef,
        state_root: Path,
    ) -> LearnerStateHandle[ArtifactLearnerState]:
        self._treatment_kind(reference.treatment_id)
        _validate_state_tree(state_root)
        return LearnerStateHandle(
            state_id=reference.state_id,
            value=ArtifactLearnerState(
                arm_run_id=reference.arm_run_id,
                treatment_id=reference.treatment_id,
                root=state_root,
            ),
        )

    def restore_feedback(
        self,
        record: FeedbackReleaseRecord,
        state: LearnerStateHandle[ArtifactLearnerState],
    ) -> FeedbackHandle[ArtifactFeedback]:
        if state.value.arm_run_id != record.arm_run_id:
            raise ValueError("cross-arm-path-detected: feedback and restored state use different arms")
        candidates = tuple(
            sorted(
                (state.value.root / _LEARNER_NAMESPACE / "feedback").glob(
                    f"{_safe_component(record.release_step_id)}.*"
                )
            )
        )
        if len(candidates) != 1 or len(record.public_artifact_refs) != 1:
            raise ValueError(f"feedback-leak-detected: could not restore exact feedback {record.feedback_id}")
        reference = record.public_artifact_refs[0]
        payload = self._artifact_repository.read_bytes(reference)
        if candidates[0].read_bytes() != payload:
            raise ValueError(f"feedback-leak-detected: state feedback differs from evidence {record.feedback_id}")
        return FeedbackHandle(
            feedback_id=record.feedback_id,
            source_experience_id=record.source_experience_id,
            view_id=record.view_id,
            value=ArtifactFeedback(path=candidates[0], artifact=reference),
        )

    def _resolve_task(self, task_id: str) -> ResolvedTaskInstance:
        instance_dir = (self._tasks_root / task_id).resolve()
        if instance_dir == self._tasks_root or self._tasks_root not in instance_dir.parents:
            raise ValueError(f"learner-path-unsafe: task id escapes tasks root: {task_id}")
        task = load_task_definition(instance_dir, self._tasks_root)
        if task.task_id != task_id:
            raise ValueError(f"resolved task identity differs from plan: {task.task_id} != {task_id}")
        return resolve_instance_paths(task, instance_dir)

    def _agent_files(
        self,
        state: ArtifactLearnerState,
        treatment_kind: ArtifactLearningTreatmentKind,
    ) -> dict[str, Path]:
        if treatment_kind is ArtifactLearningTreatmentKind.RESET:
            return {}
        files: dict[str, Path] = {}
        namespace = state.root / _LEARNER_NAMESPACE
        for channel in _readable_channels(treatment_kind):
            for source in sorted((namespace / channel).rglob("*")):
                if source.is_file():
                    relative = source.relative_to(state.root).as_posix()
                    files[relative] = source
        return files

    def _validate_experience_namespace(
        self,
        *,
        state: ArtifactLearnerState,
        treatment_kind: ArtifactLearningTreatmentKind,
        exported_workspace: Path,
    ) -> None:
        exported_namespace = exported_workspace / _LEARNER_NAMESPACE
        if treatment_kind is ArtifactLearningTreatmentKind.RESET:
            if exported_namespace.exists():
                raise ValueError("learner-channel-write-forbidden: reset experience created learner artifacts")
            return
        expected = {
            path.relative_to(state.root / _LEARNER_NAMESPACE).as_posix(): path.read_bytes()
            for channel in _readable_channels(treatment_kind)
            for path in sorted((state.root / _LEARNER_NAMESPACE / channel).rglob("*"))
            if path.is_file()
        }
        actual = (
            {}
            if not exported_namespace.exists()
            else {
                path.relative_to(exported_namespace).as_posix(): path.read_bytes()
                for path in sorted(exported_namespace.rglob("*"))
                if path.is_file()
            }
        )
        if actual != expected:
            raise ValueError("learner-channel-write-forbidden: task execution changed learner artifacts")

    def _treatment_kind(self, treatment_id: str) -> ArtifactLearningTreatmentKind:
        treatment_kind = self._treatment_kinds.get(treatment_id)
        if treatment_kind is None:
            raise ValueError(f"artifact treatment is unsupported: {treatment_id}")
        return treatment_kind

    def _state_for_arm(
        self,
        handle: LearnerStateHandle[ArtifactLearnerState],
        arm_run_id: str,
    ) -> ArtifactLearnerState:
        state: ArtifactLearnerState = handle.value
        if state.arm_run_id != arm_run_id:
            raise ValueError(f"cross-arm-path-detected: state belongs to {state.arm_run_id}, requested by {arm_run_id}")
        _validate_state_tree(state.root)
        return state

    def _arm_root(self, arm_run_id: str) -> Path:
        return self._run_root / "learner-arms" / _safe_component(arm_run_id)

    def _candidate_root(self, arm_run_id: str, step_id: str) -> Path:
        candidate = self._arm_root(arm_run_id) / "states" / _safe_component(step_id)
        if candidate.exists():
            raise ValueError(f"arm-isolation-failed: state path already exists: {candidate}")
        return candidate

    @staticmethod
    def _handle(
        arm_run_id: str,
        treatment_id: str,
        step_id: str,
        root: Path,
    ) -> LearnerStateHandle[ArtifactLearnerState]:
        return LearnerStateHandle(
            state_id=f"{arm_run_id}:state:{step_id}",
            value=ArtifactLearnerState(
                arm_run_id=arm_run_id,
                treatment_id=treatment_id,
                root=root,
            ),
        )


def terminal_outcome_feedback(record: TrialRecord) -> bytes:
    """Project a small public terminal outcome without arbitrary evaluator breakdowns."""

    evaluation = record.evaluation
    data = {
        "trial_id": record.trial_id,
        "task_id": record.task_id,
        "execution_status": record.execution_status.value,
        "reward": None if evaluation is None else evaluation.reward,
        "validity": None
        if evaluation is None
        else {
            "output_parseable": evaluation.validity.output_parseable,
            "schema_valid": evaluation.validity.schema_valid,
            "verifier_completed": evaluation.validity.verifier_completed,
        },
    }
    return (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def public_episode_feedback(record: TrialRecord) -> bytes:
    """Project public instruction, selected output, and terminal outcome for one episode."""

    data = {
        "instruction": record.input.instruction,
        "selected_output": _selected_output_text(record),
        "terminal_outcome": json.loads(terminal_outcome_feedback(record)),
    }
    return (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def public_actor_episode(record: TrialRecord) -> bytes:
    """Project only the public task identity, instruction, and selected actor output."""

    data = {
        "task_id": record.task_id,
        "instruction": record.input.instruction,
        "selected_output": _selected_output_text(record),
    }
    return (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _selected_output_text(record: TrialRecord) -> str:
    output_path = None if record.output is None else record.output.raw_output_path
    if output_path is None:
        raise ValueError("public episode has no selected output")
    try:
        return Path(output_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ValueError("public episode selected output is unavailable or not UTF-8 text") from error


def _raw_history_entry(
    *,
    source_experience_id: str,
    feedback_view_id: str,
    public_feedback: bytes,
) -> bytes:
    data = {
        "source_experience_id": source_experience_id,
        "feedback_view_id": feedback_view_id,
        "public_feedback": json.loads(public_feedback),
    }
    return (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _readable_channels(treatment_kind: ArtifactLearningTreatmentKind) -> tuple[str, ...]:
    if treatment_kind is ArtifactLearningTreatmentKind.RESET:
        return ()
    if treatment_kind is ArtifactLearningTreatmentKind.RAW_HISTORY:
        return ("history", "feedback")
    return ("memory", "feedback")


def _validate_feedback_projection(data: bytes) -> None:
    if not isinstance(data, bytes) or not data:
        raise ValueError("artifact feedback projection must be a non-empty JSON object")
    try:
        decoded = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("artifact feedback projection must be a non-empty JSON object") from error
    if not isinstance(decoded, dict):
        raise ValueError("artifact feedback projection must be a non-empty JSON object")


def _copy_state(source: Path, destination: Path) -> None:
    _validate_state_tree(source)
    if destination.exists():
        raise ValueError(f"arm-isolation-failed: state destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    _validate_state_tree(destination)


def _validate_state_tree(root: Path) -> None:
    namespace = root / _LEARNER_NAMESPACE
    if not namespace.is_dir():
        raise ValueError("learner-namespace-missing")
    total = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"learner-path-unsafe: symbolic link: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"learner-path-unsafe: special file: {path}")
        if root not in path.resolve().parents:
            raise ValueError(f"learner-path-unsafe: path escapes state root: {path}")
        size = path.stat().st_size
        if size > _MAX_FILE_BYTES:
            raise ValueError(f"learner-path-unsafe: file exceeds limit: {path}")
        total += size
        if total > _MAX_STATE_BYTES:
            raise ValueError("learner-path-unsafe: state exceeds total byte limit")
        if path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
            raise ValueError(f"learner-path-unsafe: executable file: {path}")
        relative = path.relative_to(namespace)
        if not relative.parts or relative.parts[0] not in _STATE_CHANNELS:
            raise ValueError(f"learner-path-unsafe: file is outside a declared channel: {path}")
        if relative.parts[0] == "history" and path.suffix.lower() != ".json":
            raise ValueError(f"raw-history-output-invalid: unsupported history file type: {path.suffix}")
        if relative.parts[0] == "memory" and path.suffix.lower() not in _ALLOWED_MEMORY_SUFFIXES:
            raise ValueError(f"consolidation-output-invalid: unsupported memory file type: {path.suffix}")


def _channel_contents(root: Path) -> dict[str, dict[str, bytes]]:
    namespace = root / _LEARNER_NAMESPACE
    return {
        channel: {
            path.relative_to(namespace / channel).as_posix(): path.read_bytes()
            for path in sorted((namespace / channel).rglob("*"))
            if path.is_file()
        }
        for channel in sorted(_STATE_CHANNELS)
    }


def _safe_component(value: str) -> str:
    candidate = PurePosixPath(value)
    if not value.strip() or candidate.is_absolute() or len(candidate.parts) != 1 or value in {".", ".."}:
        raise ValueError(f"learner-path-unsafe: unsafe identity: {value!r}")
    return value


__all__ = (
    "ArtifactConsolidationContext",
    "ArtifactConsolidationOperation",
    "ArtifactFeedback",
    "ArtifactFeedbackProjector",
    "ArtifactLearnerState",
    "ArtifactLearningBinding",
    "ArtifactLearningTreatmentKind",
    "build_artifact_learning_operations",
    "public_actor_episode",
    "public_episode_feedback",
    "terminal_outcome_feedback",
)
