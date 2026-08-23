# ABOUTME: Binds runtime-neutral Learning Studies to complete local Interactive World trials.
# ABOUTME: Resolves exact world/profile targets and keeps world evidence separate from learner state.

from __future__ import annotations

import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Protocol

from aec_bench import worlds
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.experimentation.learning_studies.errors import LearningStudyFeatureUnsupported
from aec_bench.experimentation.learning_studies.planning import PlannedArmRun
from aec_bench.experimentation.learning_studies.runtime import (
    ConsolidationRequest,
    ExecuteExperienceRequest,
    ExperienceExecutionResult,
    FeedbackReleaseResult,
    LearnerStateHandle,
    LearnerTransitionResult,
    LearningStudyOperations,
    ReleaseFeedbackRequest,
)
from aec_bench.harness.world_trials import WorldActorSessionRunner
from aec_bench.trials import PlannedTrial
from aec_bench.worlds.tasks import WorldTask

_WORLD_NAMESPACE = "world"


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


@dataclass(frozen=True, slots=True)
class WorldLearnerState:
    arm_run_id: str
    treatment_id: str
    root: Path


class WorldLearningTrialRunner(Protocol):
    """The exact ``run_<world>_trial`` shape this adapter composes directly."""

    async def __call__(
        self,
        task: WorldTask,
        trial: PlannedTrial,
        *,
        actor: WorldActorSessionRunner,
    ) -> TrialRecord: ...


@dataclass(frozen=True)
class WorldLearningBinding:
    operations: LearningStudyOperations[WorldLearnerState, object]
    snapshot_state: Callable[[LearnerStateHandle[WorldLearnerState]], Path]


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


def build_world_learning_operations(
    *,
    run_root: Path,
    world_id: str,
    execution_condition: WorldLearningExecutionCondition,
    run_trial: WorldLearningTrialRunner,
    instructions: Mapping[str, str],
    treatment_kinds: Mapping[str, WorldLearningTreatmentKind],
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
    ) -> None:
        self._run_root = run_root
        self._world_id = world_id
        self._execution_condition = execution_condition
        self._run_trial = run_trial
        self._instructions = dict(instructions)
        self._treatment_kinds = dict(treatment_kinds)
        for treatment_id, treatment_kind in self._treatment_kinds.items():
            if not treatment_id.strip():
                raise ValueError("world-treatment-unsupported: treatment ids must not be blank")
            if not isinstance(treatment_kind, WorldLearningTreatmentKind):
                raise ValueError(f"world-treatment-unsupported: {treatment_id}")
            if treatment_kind is not WorldLearningTreatmentKind.RESET:
                raise LearningStudyFeatureUnsupported(
                    f"world-treatment-unsupported: W1 supports only the reset treatment: {treatment_id}"
                )

    def initialise_learner(self, arm_run: PlannedArmRun) -> LearnerStateHandle[WorldLearnerState]:
        self._treatment_kind(arm_run.treatment_id)
        arm_root = self._arm_root(arm_run.arm_run_id)
        if arm_root.exists():
            raise ValueError(f"arm-isolation-failed: arm root already exists: {arm_root}")
        state_root = arm_root / "states" / "initial"
        state_root.mkdir(parents=True, exist_ok=False)
        return self._handle(arm_run.arm_run_id, arm_run.treatment_id, "initial", state_root)

    async def execute_experience(
        self,
        request: ExecuteExperienceRequest[WorldLearnerState],
    ) -> ExperienceExecutionResult[WorldLearnerState]:
        state = self._state_for_arm(request.state, request.arm_run)
        target = resolve_world_learning_target(request.step.trial.task_id)
        if target.world_id != self._world_id:
            raise ValueError(f"world-target-mismatch: {target.world_id} != {self._world_id}")
        instruction = self._instructions.get(target.task_id)
        if not instruction:
            raise ValueError(f"world-instruction-missing: {target.task_id}")

        arm_root = self._arm_root(request.arm_run.arm_run_id)
        step_component = _safe_component(request.step.step_id)
        candidate_root = arm_root / "states" / step_component
        if candidate_root.exists() or candidate_root.is_symlink():
            raise ValueError(f"arm-isolation-failed: state path already exists: {candidate_root}")

        task = worlds.task(
            target.world_id,
            profile=target.profile_id,
            instruction=instruction,
            task_id=target.task_id,
        )
        record = await self._run_trial(task, request.step.trial, actor=self._execution_condition.actor)
        if record.trial_id != request.step.trial.trial_id or record.task_id != target.task_id:
            raise ValueError(
                "world-trial-record-mismatch: returned trial identity does not match the planned target"
            )
        candidate_root.mkdir(parents=True, exist_ok=False)
        candidate = self._handle(
            request.arm_run.arm_run_id,
            state.treatment_id,
            request.step.step_id,
            candidate_root,
        )
        return ExperienceExecutionResult(trial_record=record, candidate_state=candidate)

    def release_feedback(
        self,
        request: ReleaseFeedbackRequest[WorldLearnerState],
    ) -> FeedbackReleaseResult[WorldLearnerState, object]:
        raise LearningStudyFeatureUnsupported("world-feedback-unsupported: W1 does not support feedback release")

    def consolidate(
        self,
        request: ConsolidationRequest[WorldLearnerState, object],
    ) -> LearnerTransitionResult[WorldLearnerState]:
        raise LearningStudyFeatureUnsupported("world-consolidation-unsupported: W1 does not support consolidation")

    def discard_state(self, state: LearnerStateHandle[WorldLearnerState]) -> None:
        value = state.value
        self._treatment_kind(value.treatment_id)
        states_root = (self._arm_root(value.arm_run_id) / "states").resolve()
        candidate_root = value.root.resolve()
        if candidate_root.parent != states_root or candidate_root.name == "initial":
            raise ValueError(f"state-discard-invalid: state is not a disposable candidate: {value.root}")
        shutil.rmtree(value.root, ignore_errors=False)

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
        return state

    def _treatment_kind(self, treatment_id: str) -> WorldLearningTreatmentKind:
        treatment_kind = self._treatment_kinds.get(treatment_id)
        if treatment_kind is None:
            raise ValueError(f"world-treatment-unsupported: {treatment_id}")
        return treatment_kind

    def _arm_root(self, arm_run_id: str) -> Path:
        return self._run_root / "learner-arms" / _safe_component(arm_run_id)

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


def _canonical_task_id(*, world_id: str, profile_id: str) -> str:
    return f"{_WORLD_NAMESPACE}/{world_id}/{profile_id}"


def _safe_component(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\\" in value:
        raise ValueError(f"world-task-id-invalid: unsafe identity component: {value!r}")
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or len(candidate.parts) != 1 or value in {".", ".."} or candidate.name != value:
        raise ValueError(f"world-task-id-invalid: unsafe identity component: {value!r}")
    return value


__all__ = (
    "WorldLearnerState",
    "WorldLearningBinding",
    "WorldLearningExecutionCondition",
    "WorldLearningTarget",
    "WorldLearningTreatmentKind",
    "WorldLearningTrialRunner",
    "build_world_learning_operations",
    "resolve_world_learning_target",
    "world_learning_task_id",
)
