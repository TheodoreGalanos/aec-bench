# ABOUTME: Tests persisted-plan reconciliation for Interactive World and lifecycle trials.
# ABOUTME: Proves family release checks, start ordering, canonical IDs, and plan ordering without providers.

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import aec_bench.lifecycles.application as lifecycle_application
from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.execution_policy import ExecutionPolicy
from aec_bench.contracts.execution_release import LifecycleExecutionRelease, WorldExecutionRelease
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
from aec_bench.contracts.run_plan import PlannedTrial, RunPlan, TaskPlanningProfile, plan_run
from aec_bench.contracts.task_definition import Difficulty, Lifecycle, TaskMetadata, Visibility
from aec_bench.contracts.task_snapshot import ArtifactTaskSnapshotRef
from aec_bench.contracts.trial_record import (
    AgentConfiguration,
    EvaluationStatus,
    EvidenceStatus,
    ExecutionEnvironmentRef,
    ExecutionStatus,
    PlannedTrialBinding,
    ProviderRoute,
    RunManifest,
    TimingRecord,
    TrialInput,
    TrialRecord,
    TrialTaskKind,
    UnresolvedSourceRef,
)
from aec_bench.harness.planned_trial_reconciliation import planned_trial_binding
from aec_bench.harness.world_trials import run_persisted_world_plan
from aec_bench.ledger.evidence_run_store import EvidenceRunStore
from aec_bench.lifecycles.application import LifecycleTrial, run_persisted_lifecycle_plan
from aec_bench.lifecycles.compiled import CompiledLifecycle, CompiledLifecycleEnvelope
from aec_bench.lifecycles.runtime.episode import LifecycleExecutionMode, LifecycleVisibilityPolicy
from aec_bench.trials import PlannedTrial as LegacyPlannedTrial
from aec_bench.worlds.tasks import WorldTask, build_world_task

_EXECUTION_POLICY = ExecutionPolicy(max_concurrency=1)


def _identity(kind: EntityKind, key: str, version: int = 1) -> EntityIdentity:
    return EntityIdentity(id=new_entity_id(kind), key=key, version=version)


def _world_task() -> tuple[WorldTask, WorldExecutionRelease, ArtifactTaskSnapshotRef]:
    world = WorldBuildRef(task_world_id="test-world", entry_point="tests.world:build", artifact_sha256="a" * 64)
    profile = InteractiveWorldProfileRef(
        task_world_id="test-world", profile_id="test-profile", profile_content_sha256="b" * 64
    )
    task = build_world_task(
        task_id="world/test",
        instruction="Inspect the world.",
        world=world,
        profile=profile,
        domain="test",
        category="test",
        difficulty=Difficulty.EASY,
        lifecycle=Lifecycle.ACTIVE,
        visibility=Visibility.PUBLIC,
        tags=("test",),
    )
    release_identity = _identity(EntityKind.TASK, task.task_id, version=1)
    release = WorldExecutionRelease(
        world_identity=_identity(EntityKind.WORLD, world.task_world_id, version=2),
        profile_identity=_identity(EntityKind.WORLD_PROFILE, profile.profile_id, version=3),
        world_build=world,
        profile=profile,
    )
    snapshot = ArtifactTaskSnapshotRef(
        task_id=task.task_id,
        task_identity=release_identity,
        artifact=ArtifactRef(
            artifact_id="artifacts/sha256/" + "c" * 64,
            sha256="c" * 64,
            size_bytes=1,
            media_type="application/vnd/aec-bench.task-snapshot+tar+zstd",
        ),
    )
    return task, release, snapshot


def _spec_and_plan(
    tmp_path: Path,
    *,
    family: TrialTaskKind = "world",
    conditions: int = 1,
    family_release: WorldExecutionRelease | LifecycleExecutionRelease | None = None,
) -> tuple[ResolvedRunSpec, RunPlan]:
    task, world_release, snapshot = _world_task()
    manifest = ExperimentManifest(
        experiment_id="family-plan",
        name="Family plan",
        tasks=TaskSelector(visibility_filter=[Visibility.PUBLIC]),
        agents=[AgentConfig(name=f"agent-{i}", adapter="direct", model=f"model-{i}") for i in range(conditions)],
        compute=ComputeConfig(backend="local"),
    )
    agent_conditions = tuple(
        AgentCondition(
            identity=_identity(EntityKind.AGENT_CONDITION, agent.name),
            adapter=agent.adapter,
            model=agent.model,
            client=agent.client,
            parameters=agent.parameters,
            system_prompt=agent.system_prompt,
        )
        for agent in manifest.agents
    )
    spec = resolve_run_spec(
        manifest,
        task_releases=[snapshot],
        agent_conditions=agent_conditions,
        experiment_identity=_identity(EntityKind.EXPERIMENT, manifest.experiment_id),
        run_identity=_identity(EntityKind.RUN, "family-run"),
        created_at=datetime(2026, 8, 30, 12, tzinfo=UTC),
        created_by="test",
        execution_policy=_EXECUTION_POLICY,
    )
    profile = TaskPlanningProfile(
        metadata=TaskMetadata(
            identity=snapshot.task_identity,
            lifecycle=Lifecycle.ACTIVE,
            visibility=Visibility.PUBLIC,
        ),
        execution_family=family,
        family_release=world_release if family == "world" else family_release,
    )
    plan = plan_run(
        spec,
        plan_identity=_identity(EntityKind.PLAN, "family-plan"),
        created_at=datetime(2026, 8, 30, 12, 1, tzinfo=UTC),
        task_profiles={snapshot.task_identity.id: profile},
        validate_combination=lambda task_release, condition, execution_family: None,
    )
    return spec, plan


def _store(tmp_path: Path, spec: ResolvedRunSpec, plan: RunPlan) -> EvidenceRunStore:
    store = EvidenceRunStore(tmp_path / "runs")
    store.create_run(spec)
    store.write_draft_plan(spec.run_identity, plan.model_copy(update={"state": "draft"}))
    store.promote_ready_plan(spec.run_identity, plan)
    return store


def _record(
    spec: ResolvedRunSpec,
    plan_trial: PlannedTrial,
    *,
    task_revision: str,
    adapter: str | None = None,
) -> TrialRecord:
    binding = planned_trial_binding(plan_trial, spec)
    record = TrialRecord(
        trial_id=str(plan_trial.trial_identity.id),
        run_id=str(spec.run_identity.id),
        task_id=plan_trial.task_release.task_id,
        planned_trial_binding=binding,
        execution_status=ExecutionStatus.FAILED,
        evaluation_status=EvaluationStatus.FAILED,
        evidence_status=EvidenceStatus.NOT_REQUIRED,
        started_at=datetime(2026, 8, 30, 12, 2, tzinfo=UTC),
        completed_at=datetime(2026, 8, 30, 12, 2, 1, tzinfo=UTC),
        input=TrialInput(
            instruction="Inspect the world.",
            task_revision=task_revision,
            task_kind=plan_trial.execution_family,
        ),
        timing=TimingRecord(total_seconds=1),
    )
    manifest = RunManifest(
        run_id=str(spec.run_identity.id),
        experiment_id=str(spec.experiment_identity.id),
        source=UnresolvedSourceRef(reason="test"),
        agent=AgentConfiguration(
            adapter=adapter or plan_trial.agent_condition.adapter,
            model=plan_trial.agent_condition.model,
        ),
        execution_environment=ExecutionEnvironmentRef(runtime_image="test", compute_backend=plan_trial.compute.backend),
        provider_route=ProviderRoute(provider="test", route="test"),
    )
    return record.bind_run_manifest(manifest)


def test_schema_one_planned_trial_binding_is_rejected_after_current_format_cutover(tmp_path: Path) -> None:
    spec, plan = _spec_and_plan(tmp_path)
    payload = planned_trial_binding(plan.trials[0], spec).model_dump(mode="json")
    payload["schema_version"] = 1
    payload.pop("compute")
    payload.pop("family_release")

    with pytest.raises(ValidationError):
        PlannedTrialBinding.model_validate(payload)


@pytest.mark.asyncio
async def test_world_plan_starts_before_runner_and_preserves_uuid_and_order(tmp_path: Path) -> None:
    task, release, _ = _world_task()
    extra = replace(task, task_id="world/extra")
    spec, plan = _spec_and_plan(tmp_path, conditions=2)
    store = _store(tmp_path, spec, plan)
    seen: list[str] = []

    async def runner(
        world_task: WorldTask,
        trial: LegacyPlannedTrial,
        binding: PlannedTrialBinding,
    ) -> TrialRecord:
        assert store.read_run(spec.run_identity).state.state == "started"
        assert binding.trial_identity.id == plan.trials[len(seen)].trial_identity.id
        seen.append(trial.trial_id)
        return _record(spec, plan.trials[len(seen) - 1], task_revision=world_task.task_revision)

    records = await run_persisted_world_plan(
        store=store,
        run_identity=spec.run_identity,
        tasks=[extra, task],
        run_trial=runner,
        started_at=datetime(2026, 8, 30, 12, 2, tzinfo=UTC),
    )
    assert [record.trial_id for record in records] == [str(trial.trial_identity.id) for trial in plan.trials]
    assert seen == [str(trial.trial_identity.id) for trial in plan.trials]
    assert release.world_build == task.world


@pytest.mark.asyncio
async def test_world_plan_rejects_adapter_drift_after_start(tmp_path: Path) -> None:
    task, _, _ = _world_task()
    spec, plan = _spec_and_plan(tmp_path)
    store = _store(tmp_path, spec, plan)

    async def runner(
        _task: WorldTask,
        _trial: LegacyPlannedTrial,
        _binding: PlannedTrialBinding,
    ) -> TrialRecord:
        return _record(spec, plan.trials[0], task_revision=task.task_revision, adapter="other-adapter")

    with pytest.raises(ValueError, match="agent condition"):
        await run_persisted_world_plan(
            store=store,
            run_identity=spec.run_identity,
            tasks=[task],
            run_trial=runner,
            started_at=datetime(2026, 8, 30, 12, 2, tzinfo=UTC),
        )


@pytest.mark.asyncio
async def test_world_plan_rejects_release_drift_and_ignores_unplanned_tasks(tmp_path: Path) -> None:
    task, _, _ = _world_task()
    extra, _, _ = _world_task()
    extra = replace(extra, task_id="world/extra")
    spec, plan = _spec_and_plan(tmp_path)
    store = _store(tmp_path, spec, plan)
    drifted = replace(task, profile=InteractiveWorldProfileRef("test-world", "other", "d" * 64))
    with pytest.raises(ValueError, match="release"):
        await run_persisted_world_plan(
            store=store,
            run_identity=spec.run_identity,
            tasks=[extra, drifted],
            run_trial=lambda *_: None,
            started_at=datetime(2026, 8, 30, 12, 2, tzinfo=UTC),
        )


def test_lifecycle_plan_starts_before_runner_and_reconciles_exact_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hashes = {name: value * 64 for name, value in (("spec", "d"), ("package", "e"), ("executable", "f"))}
    envelope = CompiledLifecycleEnvelope(
        visibility="public",
        template_id="test-template",
        lifecycle_id="test-lifecycle",
        variant_id="test-variant",
        lifecycle_spec_sha256=hashes["spec"],
        package_sha256=hashes["package"],
        executable_artifact_sha256=hashes["executable"],
        operation_protocol_sha256=None,
    )
    lifecycle_release = LifecycleExecutionRelease(
        lifecycle_identity=_identity(EntityKind.LIFECYCLE, "test-lifecycle", version=2),
        variant_identity=_identity(EntityKind.VARIANT, "test-variant", version=3),
        visibility="public",
        template_id=envelope.template_id,
        lifecycle_id=envelope.lifecycle_id,
        variant_id=envelope.variant_id,
        lifecycle_spec_sha256=envelope.lifecycle_spec_sha256,
        package_sha256=envelope.package_sha256,
        executable_artifact_sha256=envelope.executable_artifact_sha256,
        operation_protocol_sha256=None,
    )
    spec, plan = _spec_and_plan(tmp_path, family="lifecycle", family_release=lifecycle_release)
    store = _store(tmp_path, spec, plan)
    compiled = object.__new__(CompiledLifecycle)
    object.__setattr__(compiled, "package_dir", tmp_path / "package")
    object.__setattr__(compiled, "envelope", envelope)
    legacy = LegacyPlannedTrial(
        trial_id=str(plan.trials[0].trial_identity.id),
        experiment_id=str(spec.experiment_identity.id),
        task_id=plan.trials[0].task_release.task_id,
        agent=AgentConfig(name="agent-0", adapter="direct", model="model-0"),
        compute=spec.compute,
        repetition=1,
    )
    lifecycle = LifecycleTrial(
        planned=legacy,
        compiled=compiled,
        run_dir=tmp_path / "lifecycle-run",
        execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
        visibility_policy=LifecycleVisibilityPolicy.RAW_EVIDENCE_ONLY,
    )
    seen: list[str] = []

    def fake_runner(**kwargs: Any) -> TrialRecord:
        assert store.read_run(spec.run_identity).state.state == "started"
        seen.append(kwargs["trial"].planned.trial_id)
        return _record(spec, plan.trials[0], task_revision=envelope.package_sha256)

    monkeypatch.setattr(lifecycle_application, "run_lifecycle_trial", fake_runner)
    drifted_envelope = envelope.model_copy(update={"variant_id": "other-variant"})
    drifted_compiled = object.__new__(CompiledLifecycle)
    object.__setattr__(drifted_compiled, "package_dir", tmp_path / "drifted-package")
    object.__setattr__(drifted_compiled, "envelope", drifted_envelope)
    with pytest.raises(ValueError, match="release"):
        run_persisted_lifecycle_plan(
            store=store,
            run_identity=spec.run_identity,
            trials=[replace(lifecycle, compiled=drifted_compiled)],
            execute=lambda _trial: None,
            verify=lambda _package, _run: {},
            started_at=datetime(2026, 8, 30, 12, 2, tzinfo=UTC),
        )
    assert store.read_run(spec.run_identity).state.state == "ready"

    drifted_compute = spec.compute.model_copy(update={"resource_limits": {"memory_mb": 1024}})
    with pytest.raises(ValueError, match="compute condition"):
        run_persisted_lifecycle_plan(
            store=store,
            run_identity=spec.run_identity,
            trials=[replace(lifecycle, planned=replace(legacy, compute=drifted_compute))],
            execute=lambda _trial: None,
            verify=lambda _package, _run: {},
            started_at=datetime(2026, 8, 30, 12, 2, tzinfo=UTC),
        )
    assert store.read_run(spec.run_identity).state.state == "ready"

    records = run_persisted_lifecycle_plan(
        store=store,
        run_identity=spec.run_identity,
        trials=[lifecycle],
        execute=lambda _trial: None,
        verify=lambda _package, _run: {},
        started_at=datetime(2026, 8, 30, 12, 2, tzinfo=UTC),
    )
    assert seen == [str(plan.trials[0].trial_identity.id)]
    assert [record.trial_id for record in records] == seen
