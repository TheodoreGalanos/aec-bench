# ABOUTME: Tests canonical local execution from a persisted resolved run plan.
# ABOUTME: Proves start ordering, exact task binding, planned trial selection, and result integrity.

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from aec_bench.adapters.base import AdapterRequest, AdapterResult
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.execution_policy import ExecutionPolicy
from aec_bench.contracts.experiment_manifest import (
    AgentCondition,
    AgentConfig,
    ComputeConfig,
    ExperimentManifest,
    TaskSelector,
)
from aec_bench.contracts.identity import EntityIdentity, EntityKind, new_entity_id
from aec_bench.contracts.resolved_run import ResolvedRunSpec, resolve_run_spec
from aec_bench.contracts.run_plan import BestOfAttemptRecipe, RunPlan, TaskPlanningProfile, plan_run
from aec_bench.contracts.task_definition import Lifecycle, TaskMetadata, Visibility
from aec_bench.contracts.task_snapshot import ArtifactTaskSnapshotRef
from aec_bench.harness.artifact_tasks import LocalTaskRuntime, run_persisted_artifact_plan
from aec_bench.ledger.evidence_run_store import EvidenceRunStore
from aec_bench.tasks.instance import ResolvedTaskInstance, resolve_instance_paths
from aec_bench.tasks.snapshot import TASK_SNAPSHOT_MEDIA_TYPE, build_task_snapshot_archive
from tests.support.task_factories import make_task_definition

_CREATED_AT = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
_EXECUTION_POLICY = ExecutionPolicy(max_concurrency=1)


def _identity(kind: EntityKind, key: str, version: int = 1) -> EntityIdentity:
    return EntityIdentity(id=new_entity_id(kind), key=key, version=version)


def _task(tmp_path: Path, *, name: str = "one") -> ResolvedTaskInstance:
    task_dir = tmp_path / name
    task_dir.mkdir()
    (task_dir / "instruction.md").write_text("Write /workspace/deliverables/result.md\n", encoding="utf-8")
    (task_dir / "remove-me.txt").write_text("stale\n", encoding="utf-8")
    environment = task_dir / "environment"
    environment.mkdir()
    (environment / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    tests = task_dir / "tests"
    tests.mkdir()
    (tests / "verify.py").write_text("# private\n", encoding="utf-8")
    definition = make_task_definition(
        task_id=f"test/artifact/{name}",
        identity=_identity(EntityKind.TASK, f"test/artifact/{name}", version=2),
        environment={"dockerfile": "environment/Dockerfile"},
        verifier={
            "script": "tests/verify.py",
            "expected_output_path": "/workspace/deliverables/result.md",
            "reward_path": "logs/verifier/reward.json",
            "details_path": "logs/verifier/details.json",
        },
    )
    return resolve_instance_paths(definition, task_dir)


def _release(task: ResolvedTaskInstance) -> ArtifactTaskSnapshotRef:
    identity = task.task.identity
    assert identity is not None
    archive = build_task_snapshot_archive(task.instance_dir)
    digest = hashlib.sha256(archive).hexdigest()
    return ArtifactTaskSnapshotRef(
        task_id=task.task.task_id,
        task_identity=identity,
        artifact=ArtifactRef(
            artifact_id=f"task-snapshots/{digest}.tar.zst",
            sha256=digest,
            size_bytes=len(archive),
            media_type=TASK_SNAPSHOT_MEDIA_TYPE,
        ),
    )


def _spec(task: ResolvedTaskInstance, *, condition_count: int = 1) -> ResolvedRunSpec:
    agents = tuple(
        AgentConfig(name=f"agent-{index}", adapter="direct", model=f"model-{index}") for index in range(condition_count)
    )
    manifest = ExperimentManifest(
        experiment_id="artifact-plan-test",
        name="Artifact plan test",
        tasks=TaskSelector(visibility_filter=[Visibility.PUBLIC]),
        agents=list(agents),
        compute=ComputeConfig(backend="local", resource_limits={"memory_mb": 512}),
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
        for agent in agents
    )
    return resolve_run_spec(
        manifest,
        task_releases=[_release(task)],
        agent_conditions=conditions,
        experiment_identity=_identity(EntityKind.EXPERIMENT, manifest.experiment_id),
        run_identity=_identity(EntityKind.RUN, "artifact-plan-run"),
        created_at=_CREATED_AT,
        created_by="test",
        execution_policy=_EXECUTION_POLICY,
    )


def _ready_store(
    tmp_path: Path, spec: ResolvedRunSpec, *, attempt_recipe: BestOfAttemptRecipe | None = None
) -> tuple[EvidenceRunStore, RunPlan]:
    plan = plan_run(
        spec,
        plan_identity=_identity(EntityKind.PLAN, "artifact-plan"),
        created_at=datetime(2026, 8, 30, 12, 1, tzinfo=UTC),
        task_profiles={
            spec.task_releases[0].task_identity.id: TaskPlanningProfile(
                metadata=TaskMetadata(
                    identity=spec.task_releases[0].task_identity,
                    lifecycle=Lifecycle.ACTIVE,
                    visibility=Visibility.PUBLIC,
                ),
                execution_family="artifact",
            )
        },
        validate_combination=lambda task_release, condition, execution_family: None,
        attempt_recipe=attempt_recipe,
    )
    store = EvidenceRunStore(tmp_path / "runs")
    store.create_run(spec)
    store.write_draft_plan(spec.run_identity, plan.model_copy(update={"state": "draft"}))
    store.promote_ready_plan(spec.run_identity, plan)
    return store, plan


class _Adapter:
    def __init__(
        self,
        model: str,
        workspace: Path,
        calls: list[str],
        state: EvidenceRunStore,
        run_identity: EntityIdentity,
        adapter_name: str = "direct",
    ) -> None:
        self.model = model
        self.adapter_name = adapter_name
        self.workspace = workspace
        self.calls = calls
        self.state = state
        self.run_identity = run_identity

    def execute(self, request: AdapterRequest) -> AdapterResult:
        assert self.state.read_run(self.run_identity).state.state == "started"
        self.calls.append(self.model)
        output = self.workspace / "deliverables" / "result.md"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("Complete\n", encoding="utf-8")
        return AdapterResult(
            adapter_name=self.adapter_name,
            resolved_model=self.model,
            configuration_record={},
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path=request.output_path,
                output_format=request.output_format,
            ),
            transcript=[],
        )


def _runtime(
    store: EvidenceRunStore,
    spec: ResolvedRunSpec,
    calls: list[str],
    *,
    drift: bool = False,
    adapter_drift: bool = False,
) -> LocalTaskRuntime:
    def build(**kwargs: Any) -> _Adapter:
        model = "wrong-model" if drift else kwargs["model_name"]
        adapter_name = "wrong-adapter" if adapter_drift else "direct"
        return _Adapter(model, Path(kwargs["workspace"]), calls, store, spec.run_identity, adapter_name)

    return LocalTaskRuntime(
        work_root=store.root / "work",
        adapter_builder=build,
        normalise=False,
    )


def test_persisted_artifact_plan_starts_before_effect_and_binds_record(tmp_path: Path) -> None:
    task = _task(tmp_path)
    spec = _spec(task)
    store, plan = _ready_store(tmp_path, spec)
    calls: list[str] = []

    records = run_persisted_artifact_plan(
        store=store,
        run_identity=spec.run_identity,
        runtime=_runtime(store, spec, calls),
        tasks=[task],
        started_at=datetime(2026, 8, 30, 12, 2, tzinfo=UTC),
        verify=False,
    )

    assert calls == ["model-0"]
    assert [record.trial_id for record in records] == [str(plan.trials[0].trial_identity.id)]
    binding = records[0].planned_trial_binding
    assert binding is not None
    assert binding.run_identity == spec.run_identity
    assert binding.trial_identity == plan.trials[0].trial_identity
    assert binding.task_release == plan.trials[0].task_release
    assert binding.ordinal == plan.trials[0].ordinal
    assert binding.repetition == plan.trials[0].repetition
    assert records[0].attempt == 1


def test_persisted_artifact_plan_rejects_missing_or_unstarted_plan(tmp_path: Path) -> None:
    task = _task(tmp_path)
    spec = _spec(task)
    store = EvidenceRunStore(tmp_path / "runs")
    store.create_run(spec)
    with pytest.raises(ValueError, match="persisted ready plan"):
        run_persisted_artifact_plan(
            store=store,
            run_identity=spec.run_identity,
            runtime=_runtime(store, spec, []),
            tasks=[task],
            started_at=datetime(2026, 8, 30, 12, 2, tzinfo=UTC),
            verify=False,
        )


def test_persisted_artifact_plan_rejects_release_drift_and_does_not_start(tmp_path: Path) -> None:
    task = _task(tmp_path)
    spec = _spec(task)
    store, _ = _ready_store(tmp_path, spec)
    (task.instance_dir / "instruction.md").write_text("changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="planned snapshot"):
        run_persisted_artifact_plan(
            store=store,
            run_identity=spec.run_identity,
            runtime=_runtime(store, spec, []),
            tasks=[task],
            started_at=datetime(2026, 8, 30, 12, 2, tzinfo=UTC),
            verify=False,
        )
    assert store.read_run(spec.run_identity).state.state == "ready"


def test_persisted_artifact_plan_ignores_unplanned_tasks(tmp_path: Path) -> None:
    task = _task(tmp_path)
    extra = _task(tmp_path, name="extra")
    spec = _spec(task)
    store, _ = _ready_store(tmp_path, spec)
    calls: list[str] = []

    records = run_persisted_artifact_plan(
        store=store,
        run_identity=spec.run_identity,
        runtime=_runtime(store, spec, calls),
        tasks=[extra, task],
        started_at=datetime(2026, 8, 30, 12, 2, tzinfo=UTC),
        verify=False,
    )

    assert len(records) == 1
    assert calls == ["model-0"]


def test_persisted_artifact_plan_rejects_result_identity_drift(tmp_path: Path) -> None:
    task = _task(tmp_path)
    spec = _spec(task)
    store, _ = _ready_store(tmp_path, spec)
    with pytest.raises(ValueError, match="resolved model"):
        run_persisted_artifact_plan(
            store=store,
            run_identity=spec.run_identity,
            runtime=_runtime(store, spec, [], drift=True),
            tasks=[task],
            started_at=datetime(2026, 8, 30, 12, 2, tzinfo=UTC),
            verify=False,
        )


def test_persisted_artifact_plan_rejects_adapter_identity_drift(tmp_path: Path) -> None:
    task = _task(tmp_path)
    spec = _spec(task)
    store, _ = _ready_store(tmp_path, spec)
    with pytest.raises(ValueError, match="adapter result"):
        run_persisted_artifact_plan(
            store=store,
            run_identity=spec.run_identity,
            runtime=_runtime(store, spec, [], adapter_drift=True),
            tasks=[task],
            started_at=datetime(2026, 8, 30, 12, 2, tzinfo=UTC),
            verify=False,
        )


def test_persisted_artifact_plan_returns_plan_order_for_multiple_conditions(tmp_path: Path) -> None:
    task = _task(tmp_path)
    spec = _spec(task, condition_count=2)
    store, plan = _ready_store(tmp_path, spec)
    calls: list[str] = []
    records = run_persisted_artifact_plan(
        store=store,
        run_identity=spec.run_identity,
        runtime=_runtime(store, spec, calls),
        tasks=[task],
        started_at=datetime(2026, 8, 30, 12, 2, tzinfo=UTC),
        verify=False,
    )

    assert [record.trial_id for record in records] == [str(trial.trial_identity.id) for trial in plan.trials]
    assert calls == ["model-0", "model-1"]
