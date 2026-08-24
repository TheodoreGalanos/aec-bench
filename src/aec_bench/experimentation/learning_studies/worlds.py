# ABOUTME: Binds runtime-neutral Learning Studies to complete local Interactive World trials.
# ABOUTME: Resolves exact world/profile targets and keeps world evidence separate from learner state.

from __future__ import annotations

import json
import math
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Protocol

from aec_bench import worlds
from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.learning_study_evidence import FeedbackReleaseRecord, LearnerStateRef
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.experimentation.learning_studies.learner_state import (
    LearnerTreeSnapshot,
    copy_learner_state,
    initialise_learner_state,
    learner_tree_snapshot,
    memory_snapshot,
    require_only_channel_changed,
    validate_learner_state,
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
from aec_bench.harness.world_trials import WorldActorSessionRunner
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.trials import PlannedTrial
from aec_bench.worlds.tasks import WorldTask

_WORLD_NAMESPACE = "world"
_MAX_FEEDBACK_BYTES = 1_000_000
_FORBIDDEN_FEEDBACK_KEYS = {
    "expected_answer",
    "expected_response",
    "gold",
    "private_path",
    "secret",
    "verifier_source",
    "required_response",
    "instrument_condition",
    "visual_alert_conditions",
    "required_consecutive_alert_readings",
}
_FORBIDDEN_FEEDBACK_PATH_PARTS = ("/hidden/", "hidden/", "gold-submissions", "verifier-config")


@dataclass(frozen=True, slots=True)
class WorldLearningTarget:
    """One exact ``world/<world_id>/<profile_id>`` Learning Studies task identity."""

    task_id: str
    world_id: str
    profile_id: str


@dataclass(frozen=True, slots=True)
class WorldLearningExecutionCondition:
    """The actor binding a world learning arm treats as its fixed execution condition."""

    actor: WorldActorSessionRunner
    actor_binding_label: str

    def __post_init__(self) -> None:
        _safe_component(self.actor_binding_label)

    @property
    def adapter_id(self) -> str:
        return f"world-local:{self.actor_binding_label}"


class WorldLearningTreatmentKind(StrEnum):
    RESET = "reset"
    STRUCTURED_MEMORY = "structured-memory"


@dataclass(frozen=True)
class WorldLearnerState:
    arm_run_id: str
    treatment_id: str
    root: Path


@dataclass(frozen=True)
class WorldFeedback:
    path: Path
    artifact: ArtifactRef


@dataclass(frozen=True)
class WorldConsolidationContext:
    state_root: Path
    memory_root: Path
    feedback: tuple[WorldFeedback, ...]


type WorldFeedbackProjector = Callable[[TrialRecord], bytes]
type WorldConsolidationOperation = Callable[[WorldConsolidationContext], None]


class WorldLearningTrialRunner(Protocol):
    """The exact ``run_<world>_trial`` shape this adapter composes directly."""

    async def __call__(
        self,
        task: WorldTask,
        trial: PlannedTrial,
        *,
        actor: WorldActorSessionRunner,
        read_only_context_text: str | None = None,
    ) -> TrialRecord: ...


@dataclass(frozen=True)
class WorldLearningBinding:
    operations: LearningStudyOperations[WorldLearnerState, WorldFeedback]
    snapshot_state: Callable[[LearnerStateHandle[WorldLearnerState]], Path]
    feedback_artifacts: Callable[[FeedbackHandle[WorldFeedback]], tuple[ArtifactRef, ...]]
    restore_state: Callable[[LearnerStateRef, Path], LearnerStateHandle[WorldLearnerState]]
    restore_feedback: Callable[
        [FeedbackReleaseRecord, LearnerStateHandle[WorldLearnerState]],
        FeedbackHandle[WorldFeedback],
    ]


def world_learning_task_id(*, world_id: str, profile_id: str) -> str:
    """Build and validate one exact world Learning Studies task identity."""

    _safe_component(world_id)
    _safe_component(profile_id)
    return resolve_world_learning_target(_canonical_task_id(world_id=world_id, profile_id=profile_id)).task_id


def resolve_world_learning_target(task_id: str) -> WorldLearningTarget:
    """Resolve one exact namespaced world task through the existing worlds public API."""

    if not isinstance(task_id, str) or not task_id or "\\" in task_id:
        raise ValueError(f"world-task-id-invalid: {task_id!r}")
    parts = task_id.split("/")
    if len(parts) != 3 or parts[0] != _WORLD_NAMESPACE:
        raise ValueError(f"world-task-id-invalid: {task_id!r}")
    world_id, profile_id = parts[1], parts[2]
    try:
        _safe_component(world_id)
        _safe_component(profile_id)
    except ValueError as error:
        raise ValueError(f"world-task-id-invalid: {task_id!r}") from error

    try:
        info = worlds.get(world_id)
    except KeyError as error:
        raise ValueError(f"world-unknown: {world_id}") from error
    if profile_id not in {item.id for item in info.profiles}:
        raise ValueError(f"world-profile-unknown: {world_id}/{profile_id}")

    canonical = _canonical_task_id(world_id=world_id, profile_id=profile_id)
    if task_id != canonical:
        raise ValueError(f"world-task-id-invalid: task id is not canonical: {task_id!r}")
    return WorldLearningTarget(task_id=canonical, world_id=world_id, profile_id=profile_id)


def world_terminal_outcome_feedback(record: TrialRecord) -> bytes:
    """Project a small, generic terminal outcome reusable across future bounded worlds."""

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


def world_canonical_reward(record: TrialRecord) -> float:
    """Read the generic canonical reward, reusable unchanged by a future bounded world."""

    evaluation = record.evaluation
    if evaluation is None or not evaluation.validity.verifier_completed:
        raise ValueError("world-projection-ineligible: evaluation is unavailable or replay was invalid")
    value = evaluation.reward
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ValueError("world-projection-value-out-of-bounds: reward must be finite")
    selected = float(value)
    if not 0.0 <= selected <= 1.0:
        raise ValueError("world-projection-value-out-of-bounds: reward must be within [0, 1]")
    return selected


def build_world_learning_operations(
    *,
    run_root: Path,
    world_id: str,
    execution_condition: WorldLearningExecutionCondition,
    run_trial: WorldLearningTrialRunner,
    instructions: Mapping[str, str],
    treatment_kinds: Mapping[str, WorldLearningTreatmentKind],
    feedback_projectors: Mapping[str, WorldFeedbackProjector] | None = None,
    consolidation_operations: Mapping[str, WorldConsolidationOperation] | None = None,
    initial_memory_root: Path | None = None,
    resume_existing_run: bool = False,
) -> WorldLearningBinding:
    """Build the local Interactive World Learning Studies callback bundle."""

    _safe_component(world_id)
    selected_root = Path(run_root).resolve()
    if (
        not resume_existing_run
        and selected_root.exists()
        and (not selected_root.is_dir() or any(selected_root.iterdir()))
    ):
        raise ValueError(f"arm-isolation-failed: world learning run root must be empty: {selected_root}")
    if resume_existing_run and not selected_root.is_dir():
        raise ValueError(f"state-restore-invalid: world learning run root is unavailable: {selected_root}")
    coordinator = _WorldLearningCoordinator(
        run_root=selected_root,
        world_id=world_id,
        execution_condition=execution_condition,
        run_trial=run_trial,
        instructions=dict(instructions),
        treatment_kinds=treatment_kinds,
        feedback_projectors=feedback_projectors or {},
        consolidation_operations=consolidation_operations or {},
        initial_memory_root=initial_memory_root,
    )
    return WorldLearningBinding(
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


class _WorldLearningCoordinator:
    def __init__(
        self,
        *,
        run_root: Path,
        world_id: str,
        execution_condition: WorldLearningExecutionCondition,
        run_trial: WorldLearningTrialRunner,
        instructions: Mapping[str, str],
        treatment_kinds: Mapping[str, WorldLearningTreatmentKind],
        feedback_projectors: Mapping[str, WorldFeedbackProjector],
        consolidation_operations: Mapping[str, WorldConsolidationOperation],
        initial_memory_root: Path | None,
    ) -> None:
        self._run_root = run_root
        self._world_id = world_id
        self._execution_condition = execution_condition
        self._run_trial = run_trial
        self._instructions = dict(instructions)
        self._treatment_kinds = dict(treatment_kinds)
        self._feedback_projectors = dict(feedback_projectors)
        self._consolidation_operations = dict(consolidation_operations)
        self._initial_memory_root = None if initial_memory_root is None else Path(initial_memory_root).resolve()
        self._artifact_repository = ArtifactRepository(self._run_root / "_artifacts")
        for treatment_id, treatment_kind in self._treatment_kinds.items():
            if not treatment_id.strip():
                raise ValueError("world-treatment-unsupported: treatment ids must not be blank")
            if not isinstance(treatment_kind, WorldLearningTreatmentKind):
                raise ValueError(f"world-treatment-unsupported: {treatment_id}")

    def initialise_learner(self, arm_run: PlannedArmRun) -> LearnerStateHandle[WorldLearnerState]:
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
                if treatment_kind is WorldLearningTreatmentKind.STRUCTURED_MEMORY
                else None
            ),
        )
        return self._handle(arm_run.arm_run_id, arm_run.treatment_id, "initial", state_root)

    async def execute_experience(
        self,
        request: ExecuteExperienceRequest[WorldLearnerState],
    ) -> ExperienceExecutionResult[WorldLearnerState]:
        state = self._state_for_arm(request.state, request.arm_run)
        treatment_kind = self._treatment_kind(state.treatment_id)
        target = resolve_world_learning_target(request.step.trial.task_id)
        if target.world_id != self._world_id:
            raise ValueError(f"world-target-mismatch: {target.world_id} != {self._world_id}")
        instruction = self._instructions.get(target.task_id)
        if not instruction:
            raise ValueError(f"world-instruction-missing: {target.task_id}")

        candidate_root = self._candidate_root(request.arm_run.arm_run_id, request.step.step_id)
        try:
            copy_learner_state(state.root, candidate_root)
            context_snapshot: LearnerTreeSnapshot | None = None
            if treatment_kind is WorldLearningTreatmentKind.STRUCTURED_MEMORY:
                context_snapshot = memory_snapshot(state.root)

            task = worlds.task(
                target.world_id,
                profile=target.profile_id,
                instruction=instruction,
                task_id=target.task_id,
            )
            try:
                if context_snapshot is None:
                    record = await self._run_trial(task, request.step.trial, actor=self._execution_condition.actor)
                else:
                    read_only_context_text = _render_memory_context(context_snapshot)
                    record = await self._run_trial(
                        task,
                        request.step.trial,
                        actor=self._execution_condition.actor,
                        read_only_context_text=read_only_context_text,
                    )
            finally:
                if context_snapshot is not None and memory_snapshot(state.root) != context_snapshot:
                    raise ValueError("context-readonly-violation: learner memory changed during world execution")

            if record.trial_id != request.step.trial.trial_id or record.task_id != target.task_id:
                raise ValueError(
                    "world-trial-record-mismatch: returned trial identity does not match the planned target"
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
        request: ReleaseFeedbackRequest[WorldLearnerState],
    ) -> FeedbackReleaseResult[WorldLearnerState, WorldFeedback]:
        state = self._state_for_arm(request.state, request.arm_run)
        treatment_kind = self._treatment_kind(state.treatment_id)
        if treatment_kind is WorldLearningTreatmentKind.RESET:
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
                    value=WorldFeedback(path=feedback_path, artifact=artifact),
                ),
            )
        except Exception:
            shutil.rmtree(candidate_root, ignore_errors=True)
            raise

    def consolidate(
        self,
        request: ConsolidationRequest[WorldLearnerState, WorldFeedback],
    ) -> LearnerTransitionResult[WorldLearnerState]:
        state = self._state_for_arm(request.state, request.arm_run)
        treatment_kind = self._treatment_kind(state.treatment_id)
        if treatment_kind is not WorldLearningTreatmentKind.STRUCTURED_MEMORY:
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
                WorldFeedback(
                    path=candidate_root / "feedback" / item.path.name,
                    artifact=item.artifact,
                )
                for item in current_feedback
            )
            operation(
                WorldConsolidationContext(
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

    def discard_state(self, state: LearnerStateHandle[WorldLearnerState]) -> None:
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
    ) -> LearnerStateHandle[WorldLearnerState]:
        self._treatment_kind(reference.treatment_id)
        validate_learner_state(state_root)
        self._validate_state_location(reference.arm_run_id, state_root)
        return LearnerStateHandle(
            state_id=reference.state_id,
            value=WorldLearnerState(
                arm_run_id=reference.arm_run_id,
                treatment_id=reference.treatment_id,
                root=Path(state_root),
            ),
        )

    def restore_feedback(
        self,
        record: FeedbackReleaseRecord,
        state: LearnerStateHandle[WorldLearnerState],
    ) -> FeedbackHandle[WorldFeedback]:
        if state.value.arm_run_id != record.arm_run_id:
            raise ValueError("cross-arm-path-detected: feedback and restored state use different arms")
        treatment_kind = self._treatment_kind(state.value.treatment_id)
        if treatment_kind is WorldLearningTreatmentKind.RESET:
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
            value=WorldFeedback(path=candidates[0], artifact=reference),
        )

    @staticmethod
    def feedback_artifacts(feedback: FeedbackHandle[WorldFeedback]) -> tuple[ArtifactRef, ...]:
        return (feedback.value.artifact,)

    def _state_for_arm(
        self,
        handle: LearnerStateHandle[WorldLearnerState],
        arm_run: PlannedArmRun,
    ) -> WorldLearnerState:
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
        state: WorldLearnerState,
        feedback: tuple[FeedbackHandle[WorldFeedback], ...],
    ) -> tuple[WorldFeedback, ...]:
        selected: list[WorldFeedback] = []
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
            selected.append(WorldFeedback(path=current_path, artifact=handle.value.artifact))
        return tuple(selected)

    def _validate_state_location(self, arm_run_id: str, state_root: Path) -> None:
        resolved = Path(state_root).resolve()
        learner_arms = (self._run_root / "learner-arms").resolve()
        if learner_arms in resolved.parents:
            relative = resolved.relative_to(learner_arms)
            if len(relative.parts) != 3 or relative.parts[0] != arm_run_id or relative.parts[1] != "states":
                if relative.parts and relative.parts[0] != arm_run_id:
                    raise ValueError("cross-arm-path-detected: state path belongs to another arm")
                raise ValueError("learner-state-invalid: world evidence cannot be learner state")
            return
        if resolved.parent.name != arm_run_id:
            raise ValueError("state-restore-invalid: restored state path does not match its arm")

    def _treatment_kind(self, treatment_id: str) -> WorldLearningTreatmentKind:
        treatment_kind = self._treatment_kinds.get(treatment_id)
        if treatment_kind is None:
            raise ValueError(f"world-treatment-unsupported: {treatment_id}")
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
    ) -> LearnerStateHandle[WorldLearnerState]:
        return LearnerStateHandle(
            state_id=f"{arm_run_id}:state:{step_id}",
            value=WorldLearnerState(arm_run_id=arm_run_id, treatment_id=treatment_id, root=root),
        )


def _render_memory_context(snapshot: LearnerTreeSnapshot) -> str:
    """Render committed memory files into one deterministic, delimited text block."""

    sections = tuple(
        f"--- {relative} ---\n{content.decode('utf-8')}" for relative, kind, content in snapshot if kind == "file"
    )
    return "\n\n".join(sections)


def _canonical_task_id(*, world_id: str, profile_id: str) -> str:
    return f"{_WORLD_NAMESPACE}/{world_id}/{profile_id}"


def _validate_feedback_projection(data: bytes, *, source_record: TrialRecord) -> None:
    if not isinstance(data, bytes) or not data:
        raise ValueError("feedback-projection-invalid-json: world feedback must be non-empty bytes")
    if len(data) > _MAX_FEEDBACK_BYTES:
        raise ValueError("feedback-projection-too-large: world feedback exceeds the file limit")
    try:
        decoded = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("feedback-projection-invalid-json: world feedback must be UTF-8 JSON") from error
    if not isinstance(decoded, dict):
        raise ValueError("feedback-projection-invalid-json: world feedback must be a JSON object")
    forbidden_roots: tuple[str, ...] = ()
    output = source_record.output
    if output is not None and output.agent_output is not None:
        run_root = Path(output.agent_output.output_path)
        forbidden_roots = (str(run_root), str(run_root.parent))
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
        raise ValueError("feedback-hidden-path-detected: hidden world path detected")
    if any(root and root in value for root in forbidden_roots):
        raise ValueError("feedback-projection-unsafe: world execution root detected")


def _safe_component(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\\" in value:
        raise ValueError(f"world-task-id-invalid: unsafe identity component: {value!r}")
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or len(candidate.parts) != 1 or value in {".", ".."} or candidate.name != value:
        raise ValueError(f"world-task-id-invalid: unsafe identity component: {value!r}")
    return value


__all__ = (
    "WorldConsolidationContext",
    "WorldConsolidationOperation",
    "WorldFeedback",
    "WorldFeedbackProjector",
    "WorldLearnerState",
    "WorldLearningBinding",
    "WorldLearningExecutionCondition",
    "WorldLearningTarget",
    "WorldLearningTreatmentKind",
    "WorldLearningTrialRunner",
    "build_world_learning_operations",
    "resolve_world_learning_target",
    "world_canonical_reward",
    "world_learning_task_id",
    "world_terminal_outcome_feedback",
)
