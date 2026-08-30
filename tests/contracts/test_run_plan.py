# ABOUTME: Tests pure expansion of a resolved run into UUID-backed ordered work.
# ABOUTME: Covers plan summaries, identity factories, readiness validation, and typed extensions.

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.execution_release import WorldExecutionRelease
from aec_bench.contracts.experiment_manifest import (
    AgentCondition,
    AgentConfig,
    ComputeConfig,
    ExperimentManifest,
    TaskSelector,
)
from aec_bench.contracts.identity import EntityIdentity, EntityKind, new_entity_id
from aec_bench.contracts.interactive_world import InteractiveWorldProfileRef, WorldBuildRef
from aec_bench.contracts.resolved_run import ResolvedRunSpec, resolve_run_spec
from aec_bench.contracts.run_plan import (
    PlannedTrialExtension,
    RunPlan,
    SingleAttemptRecipe,
    TaskPlanningProfile,
    plan_run,
)
from aec_bench.contracts.task_definition import Lifecycle, TaskMetadata, Visibility
from aec_bench.contracts.task_snapshot import ArtifactTaskSnapshotRef, TaskSnapshotRef
from aec_bench.contracts.trial_extensions import AdaptationProvenance
from aec_bench.contracts.trial_record import TrialTaskKind

_PLAN_CREATED_AT = datetime(2026, 8, 30, 12, 1, tzinfo=UTC)


def _identity(kind: EntityKind, key: str, version: int = 1) -> EntityIdentity:
    return EntityIdentity(id=new_entity_id(kind), key=key, version=version)


def _snapshot(task_id: str, version: int = 1) -> ArtifactTaskSnapshotRef:
    digest = "a" * 64
    return ArtifactTaskSnapshotRef(
        task_id=task_id,
        task_identity=_identity(EntityKind.TASK, task_id, version),
        artifact=ArtifactRef(
            artifact_id=f"artifacts/sha256/{digest}",
            sha256=digest,
            size_bytes=1,
            media_type="application/vnd.aec-bench.task-snapshot+tar+zstd",
        ),
    )


def _resolved_run(*, repetitions: int = 2) -> ResolvedRunSpec:
    manifest = ExperimentManifest(
        experiment_id="pump-study",
        name="Pump study",
        tasks=TaskSelector(visibility_filter=[Visibility.PUBLIC]),
        agents=[
            AgentConfig(name="baseline", adapter="direct", model="model-a"),
            AgentConfig(name="candidate", adapter="direct", model="model-b"),
        ],
        compute=ComputeConfig(backend="local", resource_limits={"cpu": 2}),
        repetitions=repetitions,
    )
    conditions = tuple(
        AgentCondition(
            identity=_identity(EntityKind.AGENT_CONDITION, agent.name),
            adapter=agent.adapter,
            model=agent.model,
            client=agent.client,
            system_prompt=agent.system_prompt,
            parameters=agent.parameters,
        )
        for agent in manifest.agents
    )
    return resolve_run_spec(
        manifest,
        task_releases=[_snapshot("civil/pump-sizing", 2), _snapshot("civil/pipe-loss", 3)],
        agent_conditions=conditions,
        experiment_identity=_identity(EntityKind.EXPERIMENT, "pump-study", 2),
        run_identity=_identity(EntityKind.RUN, "pump-study-run"),
        created_at=datetime(2026, 8, 30, 12, 0, tzinfo=UTC),
        created_by="theo",
        randomization_seed=42,
    )


def _task_profiles(
    spec: ResolvedRunSpec,
    *,
    second_family: TrialTaskKind = "world",
) -> dict[UUID, TaskPlanningProfile]:
    profiles: dict[UUID, TaskPlanningProfile] = {}
    for index, release in enumerate(spec.task_releases):
        assert release.task_identity is not None
        profiles[release.task_identity.id] = TaskPlanningProfile(
            metadata=TaskMetadata(
                identity=release.task_identity,
                lifecycle=Lifecycle.ACTIVE if index == 0 else Lifecycle.DEPRECATED,
                visibility=Visibility.PUBLIC,
            ),
            execution_family="artifact" if index == 0 else second_family,
            family_release=(
                None
                if index == 0 and second_family != "artifact"
                else (
                    WorldExecutionRelease(
                        world_identity=_identity(EntityKind.WORLD, release.task_id),
                        profile_identity=_identity(EntityKind.WORLD_PROFILE, f"{release.task_id}-profile"),
                        world_build=WorldBuildRef(
                            task_world_id=release.task_id,
                            entry_point="aec_bench.tests.world:build",
                            artifact_sha256="b" * 64,
                        ),
                        profile=InteractiveWorldProfileRef(
                            task_world_id=release.task_id,
                            profile_id=f"{release.task_id}-profile",
                            profile_content_sha256="c" * 64,
                        ),
                    )
                    if index != 0 and second_family == "world"
                    else None
                )
            ),
        )
    return profiles


def _accept_combination(
    task_release: TaskSnapshotRef,
    condition: AgentCondition,
    execution_family: TrialTaskKind,
) -> None:
    del task_release, condition, execution_family


def test_plan_run_expands_exact_order_and_summary() -> None:
    spec = _resolved_run()
    plan = plan_run(
        spec,
        plan_identity=_identity(EntityKind.PLAN, "pump-study-plan"),
        created_at=_PLAN_CREATED_AT,
        task_profiles=_task_profiles(spec),
        validate_combination=_accept_combination,
        attempt_recipe=SingleAttemptRecipe(),
    )

    assert plan.state == "ready"
    assert plan.summary.selected_task_count == 2
    assert plan.summary.agent_condition_count == 2
    assert plan.summary.repetitions == 2
    assert plan.summary.total_trials == 8
    assert plan.summary.trials_by_execution_family == {"artifact": 4, "world": 4}
    assert plan.summary.trials_by_backend == {"local": 8}
    assert plan.summary.tasks_by_visibility == {Visibility.PUBLIC: 2}
    assert plan.summary.deprecated_task_count == 1
    assert [trial.ordinal for trial in plan.trials] == list(range(1, 9))
    assert [trial.repetition for trial in plan.trials[:4]] == [1, 2, 1, 2]
    assert all(trial.task_release.task_identity is not None for trial in plan.trials)
    assert all(trial.seed == 42 for trial in plan.trials)
    assert RunPlan.model_validate_json(plan.model_dump_json()) == plan


def test_repeated_planning_creates_fresh_trial_uuids() -> None:
    spec = _resolved_run(repetitions=1)
    first = plan_run(
        spec,
        plan_identity=_identity(EntityKind.PLAN, "pump-study-plan-a"),
        created_at=_PLAN_CREATED_AT,
        task_profiles=_task_profiles(spec),
        validate_combination=_accept_combination,
    )
    second = plan_run(
        spec,
        plan_identity=_identity(EntityKind.PLAN, "pump-study-plan-b"),
        created_at=_PLAN_CREATED_AT,
        task_profiles=_task_profiles(spec),
        validate_combination=_accept_combination,
    )

    assert {trial.trial_id for trial in first.trials}.isdisjoint({trial.trial_id for trial in second.trials})


def test_plan_run_accepts_supported_typed_extensions() -> None:
    extension = PlannedTrialExtension(
        extension_kind="adaptation",
        value=AdaptationProvenance(
            family_id="family-1",
            seed_task_id="civil/pump-sizing",
            variation_key="variant-1",
            variation={"axis": "value"},
        ),
    )
    spec = _resolved_run(repetitions=1)
    plan = plan_run(
        spec,
        plan_identity=_identity(EntityKind.PLAN, "pump-study-plan"),
        created_at=_PLAN_CREATED_AT,
        task_profiles=_task_profiles(spec),
        validate_combination=_accept_combination,
        extensions=[extension],
    )

    assert all(trial.extensions == (extension,) for trial in plan.trials)
    assert RunPlan.model_validate_json(plan.model_dump_json()) == plan


def test_schema_one_ready_plan_is_rejected_after_current_format_cutover() -> None:
    spec = _resolved_run(repetitions=1)
    plan = plan_run(
        spec,
        plan_identity=_identity(EntityKind.PLAN, "pump-study-plan"),
        created_at=_PLAN_CREATED_AT,
        task_profiles=_task_profiles(spec),
        validate_combination=_accept_combination,
    )
    payload = plan.model_dump(mode="json")
    payload["schema_version"] = 1
    for trial in payload["trials"]:
        trial.pop("family_release", None)
    with pytest.raises(ValidationError):
        RunPlan.model_validate(payload)


def test_schema_two_ready_plan_requires_matching_family_releases() -> None:
    spec = _resolved_run(repetitions=1)
    plan = plan_run(
        spec,
        plan_identity=_identity(EntityKind.PLAN, "pump-study-plan"),
        created_at=_PLAN_CREATED_AT,
        task_profiles=_task_profiles(spec),
        validate_combination=_accept_combination,
    )
    trials = list(plan.trials)
    trials[-1] = trials[-1].model_copy(update={"family_release": None})
    with pytest.raises(ValidationError, match="world release"):
        RunPlan(
            schema_version=2,
            plan_identity=plan.plan_identity,
            run_identity=plan.run_identity,
            created_at=plan.created_at,
            state=plan.state,
            trials=tuple(trials),
            summary=plan.summary,
        )


def test_plan_run_rejects_duplicate_trial_id_from_factory() -> None:
    identity = _identity(EntityKind.TRIAL, "placeholder")

    def duplicate_identity(key: str) -> EntityIdentity:
        return identity.model_copy(update={"key": key})

    with pytest.raises(ValidationError, match="trial identities must be unique"):
        spec = _resolved_run(repetitions=1)
        plan_run(
            spec,
            plan_identity=_identity(EntityKind.PLAN, "pump-study-plan"),
            created_at=_PLAN_CREATED_AT,
            task_profiles=_task_profiles(spec),
            validate_combination=_accept_combination,
            trial_identity_factory=duplicate_identity,
        )


def test_ready_plan_rejects_non_contiguous_ordinals() -> None:
    spec = _resolved_run(repetitions=1)
    plan = plan_run(
        spec,
        plan_identity=_identity(EntityKind.PLAN, "pump-study-plan"),
        created_at=_PLAN_CREATED_AT,
        task_profiles=_task_profiles(spec),
        validate_combination=_accept_combination,
    )
    changed_trial = plan.trials[1].model_copy(update={"ordinal": 99})
    with pytest.raises(ValidationError, match="ordinals must be contiguous"):
        RunPlan(
            plan_identity=plan.plan_identity,
            run_identity=plan.run_identity,
            created_at=plan.created_at,
            state=plan.state,
            trials=(plan.trials[0], changed_trial, *plan.trials[2:]),
            summary=plan.summary,
        )


def test_plan_run_requires_exact_runnable_task_profiles() -> None:
    spec = _resolved_run(repetitions=1)
    profiles = _task_profiles(spec)
    profiles.pop(next(iter(profiles)))
    with pytest.raises(ValueError, match="exactly match"):
        plan_run(
            spec,
            plan_identity=_identity(EntityKind.PLAN, "pump-study-plan"),
            created_at=_PLAN_CREATED_AT,
            task_profiles=profiles,
            validate_combination=_accept_combination,
        )

    profiles = _task_profiles(spec)
    task_id = next(iter(profiles))
    profiles[task_id] = profiles[task_id].model_copy(
        update={"metadata": profiles[task_id].metadata.model_copy(update={"visibility": Visibility.HOLDOUT})}
    )
    with pytest.raises(ValueError, match="outside the resolved run policy"):
        plan_run(
            spec,
            plan_identity=_identity(EntityKind.PLAN, "pump-study-plan"),
            created_at=_PLAN_CREATED_AT,
            task_profiles=profiles,
            validate_combination=_accept_combination,
        )


def test_ready_plan_rejects_inaccurate_visibility_summary() -> None:
    spec = _resolved_run(repetitions=1)
    plan = plan_run(
        spec,
        plan_identity=_identity(EntityKind.PLAN, "pump-study-plan"),
        created_at=_PLAN_CREATED_AT,
        task_profiles=_task_profiles(spec),
        validate_combination=_accept_combination,
    )
    changed_summary = plan.summary.model_copy(update={"tasks_by_visibility": {Visibility.PRIVATE: 2}})
    with pytest.raises(ValidationError, match="visibility counts"):
        RunPlan(
            plan_identity=plan.plan_identity,
            run_identity=plan.run_identity,
            created_at=plan.created_at,
            state=plan.state,
            trials=plan.trials,
            summary=changed_summary,
        )


def test_plan_run_rejects_invalid_creation_time() -> None:
    spec = _resolved_run(repetitions=1)
    inputs = {
        "spec": spec,
        "plan_identity": _identity(EntityKind.PLAN, "pump-study-plan"),
        "task_profiles": _task_profiles(spec),
        "validate_combination": _accept_combination,
    }
    with pytest.raises(ValueError, match="timezone"):
        plan_run(created_at=datetime(2026, 8, 30, 12, 1), **inputs)
    with pytest.raises(ValueError, match="must not precede"):
        plan_run(created_at=datetime(2026, 8, 30, 11, 59, tzinfo=UTC), **inputs)
