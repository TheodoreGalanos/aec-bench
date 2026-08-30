# ABOUTME: Tests exact Harbor trial transport and planned-trial import reconciliation.
# ABOUTME: Uses provider-free TrialRecord fixtures to prove backend names never become canonical trial IDs.

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
import yaml

from aec_bench.contracts.execution_environment import HarborEnvironmentBinding
from aec_bench.contracts.experiment_manifest import AgentConfig, ExperimentManifest, TaskSelector
from aec_bench.contracts.identity import EntityIdentity, EntityKind, new_entity_id
from aec_bench.contracts.resolved_run import ResolvedRunSpec
from aec_bench.contracts.run_plan import RunPlan, plan_run
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trial_record import (
    AgentConfiguration,
    ExecutionEnvironmentRef,
    TrialRecord,
)
from aec_bench.harness.harbor_dispatch import HarborCommandExecutor, HarborDispatchError, HarborExperimentDispatcher
from aec_bench.harness.harbor_reconciliation import (
    HarborImportReconciliationError,
    build_harbor_trial_transport,
    read_harbor_trial_transport,
    reconcile_harbor_trial_records,
)
from tests.contracts.test_run_plan import _PLAN_CREATED_AT, _accept_combination, _resolved_run, _task_profiles
from tests.harness.test_persisted_artifact_plan import _ready_store, _spec, _task
from tests.support.trial_record_factories import make_trial_record


def _plan() -> tuple[ResolvedRunSpec, RunPlan]:
    spec = _resolved_run(repetitions=1)
    return spec, plan_run(
        spec,
        plan_identity=EntityIdentity(id=new_entity_id(EntityKind.PLAN), key="pump-study-plan", version=1),
        created_at=_PLAN_CREATED_AT,
        task_profiles=_task_profiles(spec, second_family="artifact"),
        validate_combination=_accept_combination,
    )


def _record(*, trial_name: str, task_id: str, model: str = "model-a") -> TrialRecord:
    return make_trial_record(
        trial_id=trial_name,
        task={"task_id": task_id, "task_revision": "a" * 64},
        agent=AgentConfiguration(
            adapter="direct",
            model=model,
            adapter_revision="adapter-revision",
            configuration={},
        ),
        environment=ExecutionEnvironmentRef(
            runtime_image="test-image",
            compute_backend="local",
            tool_versions={},
        ),
    )


def _manifest(spec: ResolvedRunSpec, plan: RunPlan) -> ExperimentManifest:
    agents = [
        AgentConfig(
            name=str(trial.agent_condition.identity.key),
            adapter=trial.agent_condition.adapter,
            model=trial.agent_condition.model,
            client=trial.agent_condition.client,
            parameters=trial.agent_condition.parameters,
            system_prompt=trial.agent_condition.system_prompt,
        )
        for trial in plan.trials
    ]
    return ExperimentManifest(
        experiment_id=str(spec.experiment_identity.key),
        name=spec.run_name,
        tasks=TaskSelector(visibility_filter=[Visibility.PUBLIC]),
        agents=agents,
        compute=spec.compute,
        repetitions=spec.repetitions,
        disable_verification=not spec.verification_enabled,
    )


class _InspectingExecutor(HarborCommandExecutor):
    def __init__(self, config_dir: Path, expected_count: int) -> None:
        self.config_dir = config_dir
        self.expected_count = expected_count
        self.calls: list[Path] = []

    def execute(self, *, command: list[str], cwd: Path) -> int:
        del cwd
        config_path = Path(command[-1])
        self.calls.append(config_path)
        assert len(tuple(self.config_dir.glob("*.trial-transport.json"))) == self.expected_count
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert config["n_attempts"] == 1
        assert len(config["tasks"]) == 1
        assert len(config["agents"]) == 1
        transport = json.loads(
            config_path.with_suffix(config_path.suffix + ".trial-transport.json").read_text(encoding="utf-8")
        )
        assert transport[0]["harbor_job_name"] == config["job_name"]
        return 0


_LOCAL_ENVIRONMENT = HarborEnvironmentBinding(
    backend="local",
    import_path="tests.support.harbor_local_environment:LocalFilesystemHarborEnvironment",
)


def test_persisted_dispatch_prepares_all_exact_one_trial_jobs_before_effect(tmp_path: Path) -> None:
    task = _task(tmp_path)
    spec = _spec(task, condition_count=2)
    store, plan = _ready_store(tmp_path, spec)
    config_dir = tmp_path / "configs"
    executor = _InspectingExecutor(config_dir, expected_count=2)

    result = HarborExperimentDispatcher(project_root=tmp_path, jobs_dir=tmp_path / "jobs").dispatch_persisted_plan(
        store=store,
        run_identity=spec.run_identity,
        manifest=_manifest(spec, plan),
        tasks=[task],
        config_dir=config_dir,
        started_at=datetime(2026, 8, 30, 12, 2, tzinfo=UTC),
        environment_binding=_LOCAL_ENVIRONMENT,
        executor=executor,
    )

    assert store.read_run(spec.run_identity).state.state == "started"
    assert len(result.dispatches) == 2
    assert len(executor.calls) == 2
    assert all(dispatch.exit_code == 0 for dispatch in result.dispatches)
    assert [dispatch.planned_trial_ids[0] for dispatch in result.dispatches] == [
        trial.trial_identity.id for trial in plan.trials
    ]


def test_persisted_dispatch_rejects_task_drift_before_effect(tmp_path: Path) -> None:
    task = _task(tmp_path)
    spec = _spec(task)
    store, plan = _ready_store(tmp_path, spec)
    (task.instance_dir / "instruction.md").write_text("drifted\n", encoding="utf-8")
    executor = _InspectingExecutor(tmp_path / "configs", expected_count=0)

    with pytest.raises(HarborDispatchError, match="task bytes"):
        HarborExperimentDispatcher(project_root=tmp_path).dispatch_persisted_plan(
            store=store,
            run_identity=spec.run_identity,
            manifest=_manifest(spec, plan),
            tasks=[task],
            config_dir=tmp_path / "configs",
            started_at=datetime(2026, 8, 30, 12, 2, tzinfo=UTC),
            environment_binding=_LOCAL_ENVIRONMENT,
            executor=executor,
        )

    assert executor.calls == []
    assert store.read_run(spec.run_identity).state.state == "ready"


def test_transport_uses_safe_names_and_exact_planned_uuids() -> None:
    _, plan = _plan()

    transport = build_harbor_trial_transport(plan.trials[:2])

    assert [item.planned_trial_id for item in transport] == [trial.trial_id for trial in plan.trials[:2]]
    assert [item.harbor_job_name for item in transport] == [
        f"aec-planned-{trial.trial_id.hex}" for trial in plan.trials[:2]
    ]
    assert all(item.harbor_trial_name is None for item in transport)


def test_transport_sidecar_fixture_is_strict_and_readable() -> None:
    path = Path(__file__).parents[1] / "fixtures" / "harbor" / "planned_trial_transport.json"

    transport = read_harbor_trial_transport(path)

    assert transport[0].harbor_job_name.startswith("aec-planned-")
    assert transport[0].harbor_trial_name is None


def test_reconciliation_binds_records_in_plan_order_and_keeps_backend_ids() -> None:
    spec, plan = _plan()
    transport = build_harbor_trial_transport(plan.trials[:2], ["harbor-task-a", "harbor-task-b"])
    records = [
        _record(
            trial_name="harbor-task-b",
            task_id=plan.trials[1].task_release.task_id,
            model=plan.trials[1].agent_condition.model,
        ),
        _record(
            trial_name="harbor-task-a",
            task_id=plan.trials[0].task_release.task_id,
            model=plan.trials[0].agent_condition.model,
        ),
    ]
    records[0].output.agent_result["harbor_job_id"] = "job-123"

    reconciled, report = reconcile_harbor_trial_records(
        records=records,
        run_spec=spec,
        run_plan=plan,
        transport=transport,
    )

    assert [record.trial_id for record in reconciled] == [str(item.planned_trial_id) for item in transport]
    assert [record.planned_trial_binding.ordinal for record in reconciled] == [1, 2]
    assert reconciled[0].output.agent_result["harbor_trial_name"] == "harbor-task-a"
    assert reconciled[0].output.agent_result.get("harbor_job_id") is None
    assert reconciled[1].output.agent_result["harbor_job_id"] == "job-123"
    assert report.observed_trial_ids == tuple(item.planned_trial_id for item in transport)
    assert report.accepted_trial_ids == tuple(UUID(record.trial_id) for record in reconciled)
    assert all(record.trial_id != "job-123" for record in reconciled)


def test_single_job_transport_binds_the_observed_generated_harbor_name() -> None:
    spec, plan = _plan()
    transport = build_harbor_trial_transport(plan.trials[:1])
    record = _record(
        trial_name="task-name__backend-generated-id",
        task_id=plan.trials[0].task_release.task_id,
    )

    reconciled, report = reconcile_harbor_trial_records(
        records=[record],
        run_spec=spec,
        run_plan=plan,
        transport=transport,
    )

    assert reconciled[0].trial_id == str(transport[0].planned_trial_id)
    assert report.observed_trial_names == ("task-name__backend-generated-id",)


def test_reconciliation_reports_duplicate_mapped_harbor_name() -> None:
    spec, plan = _plan()
    transport = build_harbor_trial_transport(plan.trials[:1], ["harbor-task-a"])
    records = [
        _record(trial_name="harbor-task-a", task_id=plan.trials[0].task_release.task_id),
        _record(trial_name="harbor-task-a", task_id=plan.trials[0].task_release.task_id),
    ]

    with pytest.raises(HarborImportReconciliationError, match="duplicates=1") as error:
        reconcile_harbor_trial_records(
            records=records,
            run_spec=spec,
            run_plan=plan,
            transport=transport,
        )

    assert error.value.report.duplicate_trial_names == ("harbor-task-a",)
    assert error.value.report.duplicate_trial_ids == (transport[0].planned_trial_id,)


def test_single_job_reconciliation_reports_a_missing_planned_uuid() -> None:
    spec, plan = _plan()
    transport = build_harbor_trial_transport(plan.trials[:1])

    with pytest.raises(HarborImportReconciliationError, match="missing=1") as error:
        reconcile_harbor_trial_records(
            records=[],
            run_spec=spec,
            run_plan=plan,
            transport=transport,
        )

    assert error.value.report.observed_trial_ids == ()
    assert error.value.report.missing_trial_ids == (transport[0].planned_trial_id,)


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        (["missing"], "missing=2"),
        (["unexpected", "unexpected"], "unexpected=1"),
    ],
)
def test_reconciliation_reports_exact_membership_failures(names: list[str], expected: str) -> None:
    spec, plan = _plan()
    transport = build_harbor_trial_transport(plan.trials[:2], ["harbor-task-a", "harbor-task-b"])
    records = [_record(trial_name=name, task_id=plan.trials[0].task_release.task_id) for name in names]

    with pytest.raises(HarborImportReconciliationError, match=expected) as error:
        reconcile_harbor_trial_records(
            records=records,
            run_spec=spec,
            run_plan=plan,
            transport=transport,
        )

    report = error.value.report
    assert report.missing_trial_ids
    if names == ["missing"]:
        assert report.unexpected_trial_names == ("missing",)
    else:
        assert report.unexpected_trial_names == ("unexpected",)


def test_reconciliation_rejects_record_drift_even_when_transport_name_matches() -> None:
    spec, plan = _plan()
    transport = build_harbor_trial_transport(plan.trials[:1], ["harbor-task-a"])
    drifted = _record(
        trial_name="harbor-task-a",
        task_id=plan.trials[0].task_release.task_id,
        model="different-model",
    )

    with pytest.raises(ValueError, match="agent condition"):
        reconcile_harbor_trial_records(
            records=[drifted],
            run_spec=spec,
            run_plan=plan,
            transport=transport,
        )
