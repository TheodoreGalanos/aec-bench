# ABOUTME: Defines the UUID-backed ordered plan and trial contracts for one resolved run.
# ABOUTME: Expands requested state into pure, validated work without persistence or execution.

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, PositiveInt, field_serializer, field_validator, model_validator

from aec_bench.contracts.evaluation_refs import EvaluationRegimeRef
from aec_bench.contracts.execution_release import (
    FamilyExecutionRelease,
    LifecycleExecutionRelease,
    WorldExecutionRelease,
)
from aec_bench.contracts.experiment_manifest import AgentCondition, ComputeConfig
from aec_bench.contracts.identity import EntityIdentity, EntityKey, EntityKind, new_entity_id
from aec_bench.contracts.resolved_run import ResolvedRunSpec
from aec_bench.contracts.task_definition import Lifecycle, TaskMetadata, Visibility
from aec_bench.contracts.task_snapshot import TaskSnapshotRef
from aec_bench.contracts.trial_extensions import (
    AdaptationProvenance,
)
from aec_bench.contracts.trial_record import TrialTaskKind
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr


class SingleAttemptRecipe(FrozenStrictModel):
    """Run one attempt for a planned trial."""

    kind: Literal["single_attempt"] = "single_attempt"


class BestOfAttemptRecipe(FrozenStrictModel):
    """Run a fixed number of attempts with one declared selector."""

    kind: Literal["best_of"] = "best_of"
    candidates: PositiveInt
    selector: Literal["self"] = "self"


type AttemptRecipe = Annotated[SingleAttemptRecipe | BestOfAttemptRecipe, Field(discriminator="kind")]


_EXTENSION_TYPES: Mapping[str, type[BaseModel]] = {
    "adaptation": AdaptationProvenance,
}


class PlannedTrialExtension(FrozenStrictModel):
    """One supported typed extension retained with a planned trial."""

    extension_kind: EntityKey
    value: BaseModel

    @model_validator(mode="before")
    @classmethod
    def parse_typed_value(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        expected = _EXTENSION_TYPES.get(str(value.get("extension_kind")))
        raw_extension = value.get("value")
        if expected is not None and isinstance(raw_extension, Mapping):
            parsed = dict(value)
            parsed["value"] = expected.model_validate(raw_extension)
            return parsed
        return value

    @field_serializer("value")
    def serialize_typed_value(self, value: BaseModel) -> object:
        return value.model_dump(mode="json")

    @model_validator(mode="after")
    def validate_supported_type(self) -> Self:
        expected = _EXTENSION_TYPES.get(str(self.extension_kind))
        if expected is None:
            raise ValueError(f"unsupported planned trial extension: {self.extension_kind}")
        if not isinstance(self.value, expected):
            raise ValueError(
                f"planned trial extension {self.extension_kind} requires {expected.__name__}, "
                f"got {type(self.value).__name__}"
            )
        return self


class PlannedTrial(FrozenStrictModel):
    """One exact ordered unit of work in a run plan."""

    trial_identity: EntityIdentity
    ordinal: PositiveInt
    run_identity: EntityIdentity
    task_release: TaskSnapshotRef
    task_metadata: TaskMetadata
    agent_condition: AgentCondition
    compute: ComputeConfig
    repetition: PositiveInt
    seed: Annotated[int, Field(strict=True, ge=0)] | None = None
    execution_family: TrialTaskKind
    family_release: FamilyExecutionRelease | None = None
    attempt_recipe: AttemptRecipe
    evaluation_profile: EvaluationRegimeRef | None = None
    extensions: tuple[PlannedTrialExtension, ...] = ()

    @property
    def trial_id(self) -> UUID:
        """Return the UUID-backed trial identity."""

        return self.trial_identity.id

    @property
    def trial_key(self) -> EntityKey:
        """Return the readable key from the authoritative trial identity."""

        return self.trial_identity.key

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        if self.task_release.task_identity is None:
            raise ValueError("planned trial task release must include task identity")
        if self.task_metadata.identity != self.task_release.task_identity:
            raise ValueError("planned trial task metadata must match the task release")
        if self.task_metadata.lifecycle not in {Lifecycle.ACTIVE, Lifecycle.DEPRECATED}:
            raise ValueError("planned trial requires an active or deprecated task release")
        if self.trial_identity.version < 1:
            raise ValueError("planned trial identity version must be positive")
        if self.run_identity.version < 1:
            raise ValueError("planned trial run identity version must be positive")
        extension_kinds = [str(extension.extension_kind) for extension in self.extensions]
        if len(extension_kinds) != len(set(extension_kinds)):
            raise ValueError("planned trial extension kinds must be unique")
        return self


class RunPlanSummary(FrozenStrictModel):
    """Counts that describe a plan without enumerating its trials."""

    selected_task_count: PositiveInt
    agent_condition_count: PositiveInt
    repetitions: PositiveInt
    total_trials: PositiveInt
    trials_by_execution_family: dict[TrialTaskKind, PositiveInt]
    trials_by_backend: dict[NonEmptyStr, PositiveInt]
    visibility_policy: tuple[Visibility, ...]
    tasks_by_visibility: dict[Visibility, PositiveInt]
    deprecated_task_count: NonNegativeInt

    @field_validator("visibility_policy")
    @classmethod
    def validate_visibility_policy(cls, value: tuple[Visibility, ...]) -> tuple[Visibility, ...]:
        if not value:
            raise ValueError("run plan visibility policy must not be empty")
        if len(value) != len(set(value)):
            raise ValueError("run plan visibility policy must be unique")
        return value


class RunPlan(FrozenStrictModel):
    """One UUID-backed, ordered plan for a resolved run."""

    schema_version: Literal[1, 2] = 1
    plan_identity: EntityIdentity
    run_identity: EntityIdentity
    created_at: datetime
    state: Literal["draft", "ready", "started", "closed"] = "draft"
    trials: tuple[PlannedTrial, ...]
    summary: RunPlanSummary

    @property
    def plan_id(self) -> UUID:
        """Return the UUID-backed plan identity."""

        return self.plan_identity.id

    @property
    def plan_key(self) -> EntityKey:
        """Return the readable key from the authoritative plan identity."""

        return self.plan_identity.key

    @property
    def plan_version(self) -> int:
        """Return the version from the authoritative plan identity."""

        return self.plan_identity.version

    @property
    def run_id(self) -> UUID:
        """Return the UUID-backed run identity."""

        return self.run_identity.id

    @field_validator("created_at")
    @classmethod
    def validate_created_at_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("run plan created_at must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        if self.plan_identity.id == self.run_identity.id:
            raise ValueError("run plan and run identities must be distinct")
        if not self.trials:
            raise ValueError("run plan must include at least one planned trial")
        if self.state == "ready":
            self._validate_ready_trials()
        return self

    def _validate_ready_trials(self) -> None:
        if tuple(trial.ordinal for trial in self.trials) != tuple(range(1, len(self.trials) + 1)):
            raise ValueError("ready run plan trial ordinals must be contiguous from 1")
        trial_ids = [trial.trial_identity.id for trial in self.trials]
        if len(trial_ids) != len(set(trial_ids)):
            raise ValueError("ready run plan trial identities must be unique")
        trial_keys = [str(trial.trial_key) for trial in self.trials]
        if len(trial_keys) != len(set(trial_keys)):
            raise ValueError("ready run plan trial keys must be unique")
        if any(trial.run_identity != self.run_identity for trial in self.trials):
            raise ValueError("ready run plan trials must reference the plan run identity")
        if self.schema_version == 2:
            for trial in self.trials:
                if trial.execution_family == "artifact" and trial.family_release is not None:
                    raise ValueError("ready artifact trial must not have a family release")
                if trial.execution_family == "world" and not isinstance(
                    trial.family_release,
                    WorldExecutionRelease,
                ):
                    raise ValueError("ready world trial requires a world release")
                if trial.execution_family == "lifecycle" and not isinstance(
                    trial.family_release,
                    LifecycleExecutionRelease,
                ):
                    raise ValueError("ready lifecycle trial requires a lifecycle release")
        task_ids = {trial.task_release.task_id for trial in self.trials}
        agent_ids = {trial.agent_condition.identity.id for trial in self.trials}
        if self.summary.selected_task_count != len(task_ids):
            raise ValueError("run plan summary task count does not match trials")
        if self.summary.agent_condition_count != len(agent_ids):
            raise ValueError("run plan summary agent count does not match trials")
        if self.summary.total_trials != len(self.trials):
            raise ValueError("run plan summary total does not match trials")
        if self.summary.repetitions != max(trial.repetition for trial in self.trials):
            raise ValueError("run plan summary repetitions do not match trials")
        family_counts = {
            family: sum(trial.execution_family == family for trial in self.trials)
            for family in {trial.execution_family for trial in self.trials}
        }
        if self.summary.trials_by_execution_family != family_counts:
            raise ValueError("run plan summary execution-family counts do not match trials")
        backend_counts = {
            backend: sum(trial.compute.backend == backend for trial in self.trials)
            for backend in {trial.compute.backend for trial in self.trials}
        }
        if self.summary.trials_by_backend != backend_counts:
            raise ValueError("run plan summary backend counts do not match trials")
        task_metadata: dict[UUID, TaskMetadata] = {}
        for trial in self.trials:
            task_identity = trial.task_metadata.identity.id
            existing = task_metadata.setdefault(task_identity, trial.task_metadata)
            if existing != trial.task_metadata:
                raise ValueError("ready run plan task metadata must be consistent")
        visibility_counts = Counter(metadata.visibility for metadata in task_metadata.values())
        if self.summary.tasks_by_visibility != dict(visibility_counts):
            raise ValueError("run plan summary visibility counts do not match trials")
        deprecated_count = sum(metadata.lifecycle is Lifecycle.DEPRECATED for metadata in task_metadata.values())
        if self.summary.deprecated_task_count != deprecated_count:
            raise ValueError("run plan summary deprecated task count does not match trials")
        if any(metadata.visibility not in self.summary.visibility_policy for metadata in task_metadata.values()):
            raise ValueError("ready run plan task visibility is outside the plan policy")


class TaskPlanningProfile(FrozenStrictModel):
    """Validated task metadata needed to make one release ready for planning."""

    metadata: TaskMetadata
    execution_family: TrialTaskKind
    family_release: FamilyExecutionRelease | None = None

    @model_validator(mode="after")
    def validate_runnable_lifecycle(self) -> Self:
        if self.metadata.lifecycle not in {Lifecycle.ACTIVE, Lifecycle.DEPRECATED}:
            raise ValueError("run planning requires an active or deprecated task release")
        if self.execution_family == "artifact" and self.family_release is not None:
            raise ValueError("artifact planning profile must not have a family release")
        if self.execution_family == "world" and not isinstance(self.family_release, WorldExecutionRelease):
            raise ValueError("world planning profile requires a world release")
        if self.execution_family == "lifecycle" and not isinstance(
            self.family_release,
            LifecycleExecutionRelease,
        ):
            raise ValueError("lifecycle planning profile requires a lifecycle release")
        return self


TrialIdentityFactory = Callable[[str], EntityIdentity]
CombinationValidator = Callable[[TaskSnapshotRef, AgentCondition, TrialTaskKind], None]


def plan_run(
    spec: ResolvedRunSpec,
    *,
    plan_identity: EntityIdentity,
    created_at: datetime,
    task_profiles: Mapping[UUID, TaskPlanningProfile],
    validate_combination: CombinationValidator,
    attempt_recipe: AttemptRecipe | None = None,
    trial_identity_factory: TrialIdentityFactory | None = None,
    extensions: Sequence[PlannedTrialExtension] = (),
) -> RunPlan:
    """Expand one resolved run into an ordered, ready plan without external effects."""

    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("run plan created_at must include a timezone")
    if created_at < spec.created_at:
        raise ValueError("run plan created_at must not precede the resolved run specification")
    release_ids = {release.task_identity.id for release in spec.task_releases if release.task_identity is not None}
    if set(task_profiles) != release_ids:
        raise ValueError("task planning profiles must exactly match the resolved task releases")
    make_trial_identity = trial_identity_factory or _new_trial_identity
    selected_attempt_recipe = attempt_recipe or SingleAttemptRecipe()
    trials: list[PlannedTrial] = []
    ordinal = 1
    for task_release in spec.task_releases:
        assert task_release.task_identity is not None
        profile = task_profiles[task_release.task_identity.id]
        if profile.metadata.identity != task_release.task_identity:
            raise ValueError("task planning profile identity must match the task release")
        if profile.metadata.visibility not in spec.visibility:
            raise ValueError("task planning profile visibility is outside the resolved run policy")
        for condition in spec.agent_conditions:
            validate_combination(task_release, condition, profile.execution_family)
            for repetition in range(1, spec.repetitions + 1):
                trial_key = EntityKey(f"{task_release.task_id}__{condition.identity.key}__rep-{repetition:02d}")
                trial_identity = make_trial_identity(str(trial_key))
                if trial_identity.key != trial_key:
                    raise ValueError("trial identity factory must preserve the requested trial key")
                trials.append(
                    PlannedTrial(
                        trial_identity=trial_identity,
                        ordinal=ordinal,
                        run_identity=spec.run_identity,
                        task_release=task_release,
                        task_metadata=profile.metadata,
                        agent_condition=condition,
                        compute=spec.compute,
                        repetition=repetition,
                        seed=spec.randomization_seed,
                        execution_family=profile.execution_family,
                        family_release=profile.family_release,
                        attempt_recipe=selected_attempt_recipe,
                        evaluation_profile=spec.evaluation_regime,
                        extensions=tuple(extensions),
                    )
                )
                ordinal += 1
    family_counts = Counter(trial.execution_family for trial in trials)
    visibility_counts = Counter(profile.metadata.visibility for profile in task_profiles.values())
    summary = RunPlanSummary(
        selected_task_count=len(spec.task_releases),
        agent_condition_count=len(spec.agent_conditions),
        repetitions=spec.repetitions,
        total_trials=len(trials),
        trials_by_execution_family=dict(family_counts),
        trials_by_backend={spec.compute.backend: len(trials)},
        visibility_policy=spec.visibility,
        tasks_by_visibility=dict(visibility_counts),
        deprecated_task_count=sum(
            profile.metadata.lifecycle is Lifecycle.DEPRECATED for profile in task_profiles.values()
        ),
    )
    return RunPlan(
        schema_version=2,
        plan_identity=plan_identity,
        run_identity=spec.run_identity,
        created_at=created_at,
        state="ready",
        trials=tuple(trials),
        summary=summary,
    )


def _new_trial_identity(key: str) -> EntityIdentity:
    return EntityIdentity(id=new_entity_id(EntityKind.TRIAL), key=EntityKey(key), version=1)


__all__ = (
    "AttemptRecipe",
    "BestOfAttemptRecipe",
    "CombinationValidator",
    "FamilyExecutionRelease",
    "LifecycleExecutionRelease",
    "PlannedTrial",
    "PlannedTrialExtension",
    "RunPlan",
    "RunPlanSummary",
    "SingleAttemptRecipe",
    "TaskPlanningProfile",
    "TrialIdentityFactory",
    "WorldExecutionRelease",
    "plan_run",
)
