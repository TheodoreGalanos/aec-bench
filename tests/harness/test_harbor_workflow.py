# ABOUTME: Tests for the composed Harbor dispatch-and-import workflow in the harness.
# ABOUTME: Verifies job-dir detection and ledger import after synchronous Harbor execution.

import json
import shutil
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from aec_bench.contracts.experiment_manifest import (
    AgentConfig,
    ComputeConfig,
    ExperimentManifest,
    TaskSelector,
)
from aec_bench.harness.experiment_runner import ExperimentImportResult, HarborImportExperimentRunner
from aec_bench.harness.harbor_dispatch import HarborDispatchResult, HarborExperimentDispatcher
from aec_bench.harness.harbor_workflow import HarborWorkflowError, SynchronousHarborWorkflow
from aec_bench.harness.progress_tracker import WorkflowProgressSnapshot
from aec_bench.tasks.registry import TaskRegistry
from tests.support.task_factories import make_task_definition

REPO_ROOT = Path(__file__).resolve().parents[2]
HARBOR_JOB_DIR = REPO_ROOT / "jobs" / "2026-03-04__17-57-43"

_skip_no_job_data = pytest.mark.skipif(
    not HARBOR_JOB_DIR.exists(),
    reason="requires archived Harbor job data in jobs/",
)


class FakeExecutor:
    def __init__(self, *, source_job_dir: Path, jobs_root: Path, job_name: str = "run-001") -> None:
        self.source_job_dir = source_job_dir
        self.jobs_root = jobs_root
        self.job_name = job_name

    def execute(self, *, command: list[str], cwd: Path) -> int:
        del command, cwd
        destination = self.jobs_root / self.job_name
        shutil.copytree(self.source_job_dir, destination)
        return 0


class MultiJobExecutor:
    def __init__(
        self,
        *,
        source_job_dir: Path,
        jobs_root: Path,
        matching_job_name: str = "run-matching",
        other_job_name: str = "run-other",
    ) -> None:
        self.source_job_dir = source_job_dir
        self.jobs_root = jobs_root
        self.matching_job_name = matching_job_name
        self.other_job_name = other_job_name

    def execute(self, *, command: list[str], cwd: Path) -> int:
        del command, cwd
        matching_destination = self.jobs_root / self.matching_job_name
        other_destination = self.jobs_root / self.other_job_name
        shutil.copytree(self.source_job_dir, other_destination)
        _rewrite_job_result_id(other_destination, "some-other-experiment")
        shutil.copytree(self.source_job_dir, matching_destination)
        return 0


class EmptyJobExecutor:
    def __init__(self, jobs_root: Path) -> None:
        self.jobs_root = jobs_root

    def execute(self, *, command: list[str], cwd: Path) -> int:
        del command, cwd
        (self.jobs_root / "run-adaptive").mkdir()
        return 0


def test_synchronous_workflow_uses_exact_prevalidated_tasks_without_registry_reselection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    exact_task = make_task_definition(task_id="civil/calculation/exact")
    manifest = ExperimentManifest(
        experiment_id="adaptive-exact-run",
        name="Adaptive exact run",
        tasks=TaskSelector(include_patterns=[exact_task.task_id]),
        agents=[AgentConfig(name="agent", adapter="direct", model="test-model")],
        compute=ComputeConfig(backend="docker"),
    )
    jobs_root = tmp_path / "jobs"
    jobs_root.mkdir()
    captured: dict[str, object] = {}

    def reject_registry_reload(self):  # noqa: ANN001, ANN201
        del self
        raise AssertionError("exact task execution must not reload mutable registry state")

    def fake_dispatch(  # noqa: ANN001, ANN201
        self,
        *,
        manifest,
        tasks,
        config_path,
        task_path_overrides=None,
        environment_binding=None,
        executor=None,
        execute=True,
    ):
        del self, task_path_overrides, environment_binding, executor, execute
        captured["dispatch_tasks"] = tasks
        (jobs_root / "exact-job").mkdir()
        return HarborDispatchResult(
            config_path=config_path,
            command=["harbor"],
            selected_task_count=len(tasks),
            planned_trial_count=len(tasks),
            exit_code=0,
        )

    def fake_import(self, *, job_dir, manifest, record_transform=None, resolved_tasks=None):  # noqa: ANN001, ANN201
        del self, job_dir, record_transform
        captured["import_tasks"] = resolved_tasks
        return ExperimentImportResult(
            experiment_id=manifest.experiment_id,
            selected_task_count=len(resolved_tasks),
            planned_trial_count=len(resolved_tasks),
            discovered_trials=1,
            imported_trials=1,
            duplicate_trials=0,
            invalid_trials=0,
        )

    monkeypatch.setattr(TaskRegistry, "reload", reject_registry_reload)
    monkeypatch.setattr(HarborExperimentDispatcher, "dispatch", fake_dispatch)
    monkeypatch.setattr(HarborImportExperimentRunner, "import_harbor_job", fake_import)
    workflow = SynchronousHarborWorkflow(
        project_root=tmp_path,
        repo_root=REPO_ROOT,
        tasks_root=REPO_ROOT / "tasks",
        ledger_root=tmp_path / "ledger",
        jobs_root=jobs_root,
    )

    workflow.run(
        manifest=manifest,
        config_path=tmp_path / "adaptive.yaml",
        resolved_tasks=(exact_task,),
    )

    assert captured == {
        "dispatch_tasks": [exact_task],
        "import_tasks": (exact_task,),
    }


def test_synchronous_workflow_forwards_record_transform_before_import(tmp_path: Path, monkeypatch) -> None:
    manifest = ExperimentManifest(
        experiment_id="adaptive-run",
        name="Adaptive run",
        tasks=TaskSelector(include_patterns=["electrical/voltage-drop"]),
        agents=[AgentConfig(name="agent", adapter="direct", model="test-model")],
        compute=ComputeConfig(backend="docker"),
    )
    jobs_root = tmp_path / "jobs"
    jobs_root.mkdir()
    captured: list[object] = []

    def fake_import(self, *, job_dir, manifest, record_transform=None, resolved_tasks=None):  # noqa: ANN001, ANN201
        del self, job_dir, resolved_tasks
        captured.append(record_transform)
        return ExperimentImportResult(
            experiment_id=manifest.experiment_id,
            selected_task_count=1,
            planned_trial_count=1,
            discovered_trials=1,
            imported_trials=1,
            duplicate_trials=0,
            invalid_trials=0,
        )

    monkeypatch.setattr(HarborImportExperimentRunner, "import_harbor_job", fake_import)
    workflow = SynchronousHarborWorkflow(
        project_root=tmp_path,
        repo_root=REPO_ROOT,
        tasks_root=REPO_ROOT / "tasks",
        ledger_root=tmp_path / "ledger",
        jobs_root=jobs_root,
    )

    def transform(record):  # noqa: ANN001, ANN201
        return record

    workflow.run(
        manifest=manifest,
        config_path=tmp_path / "adaptive.yaml",
        executor=EmptyJobExecutor(jobs_root),
        record_transform=transform,
        resolved_tasks=(make_task_definition(task_id="electrical/voltage-drop"),),
    )

    assert captured == [transform]


def test_synchronous_workflow_dispatch_only_never_opens_the_trial_record_importer(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manifest = ExperimentManifest(
        experiment_id="adaptive-stage-run",
        name="Adaptive declared-stage run",
        tasks=TaskSelector(include_patterns=["civil/calculation/exact"]),
        agents=[AgentConfig(name="agent", adapter="direct", model="test-model")],
        compute=ComputeConfig(backend="docker"),
        disable_verification=True,
    )
    exact_task = make_task_definition(task_id="civil/calculation/exact")
    jobs_root = tmp_path / "jobs"
    jobs_root.mkdir()

    def reject_import(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        del args, kwargs
        raise AssertionError("intermediate stage dispatch must not create TrialRecord evidence")

    monkeypatch.setattr(HarborImportExperimentRunner, "import_harbor_job", reject_import)
    workflow = SynchronousHarborWorkflow(
        project_root=tmp_path,
        repo_root=REPO_ROOT,
        tasks_root=REPO_ROOT / "tasks",
        ledger_root=tmp_path / "ledger",
        jobs_root=jobs_root,
    )

    result = workflow.dispatch_only(
        manifest=manifest,
        config_path=tmp_path / "adaptive-stage.yaml",
        executor=EmptyJobExecutor(jobs_root),
        resolved_tasks=(exact_task,),
    )

    assert result.job_dir == jobs_root / "run-adaptive"
    assert result.dispatch.exit_code == 0
    assert not (tmp_path / "ledger").exists()


def test_synchronous_workflow_imports_an_existing_dispatch_without_redispatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    exact_task = make_task_definition(task_id="civil/calculation/import-existing")
    manifest = ExperimentManifest(
        experiment_id="adaptive-import-existing",
        name="Adaptive import existing",
        tasks=TaskSelector(include_patterns=[exact_task.task_id]),
        agents=[AgentConfig(name="agent", adapter="direct", model="test-model")],
        compute=ComputeConfig(backend="docker"),
        disable_verification=True,
    )
    jobs_root = tmp_path / "jobs"
    jobs_root.mkdir()
    imported_jobs: list[Path] = []

    def fake_import(self, *, job_dir, manifest, record_transform=None, resolved_tasks=None):  # noqa: ANN001, ANN201
        del self, record_transform
        imported_jobs.append(job_dir)
        return ExperimentImportResult(
            experiment_id=manifest.experiment_id,
            selected_task_count=len(resolved_tasks),
            planned_trial_count=len(resolved_tasks),
            discovered_trials=1,
            imported_trials=1,
            duplicate_trials=0,
            invalid_trials=0,
        )

    monkeypatch.setattr(HarborImportExperimentRunner, "import_harbor_job", fake_import)
    workflow = SynchronousHarborWorkflow(
        project_root=tmp_path,
        repo_root=REPO_ROOT,
        tasks_root=REPO_ROOT / "tasks",
        ledger_root=tmp_path / "ledger",
        jobs_root=jobs_root,
    )
    dispatched = workflow.dispatch_only(
        manifest=manifest,
        config_path=tmp_path / "adaptive-import-existing.yaml",
        executor=EmptyJobExecutor(jobs_root),
        resolved_tasks=(exact_task,),
    )

    result = workflow.import_dispatched(
        manifest=manifest,
        dispatched=dispatched,
    )

    assert imported_jobs == [dispatched.job_dir]
    assert result.dispatch == dispatched.dispatch
    assert result.job_dir == dispatched.job_dir
    assert result.import_result.imported_trials == 1


def test_synchronous_workflow_dispatches_exact_external_task_path(
    tmp_path: Path,
) -> None:
    exact_task = make_task_definition(task_id="civil/proposal-session/source-free")
    task_path = tmp_path / "derived-task"
    task_path.mkdir()
    manifest = ExperimentManifest(
        experiment_id="proposal-session-path",
        name="Proposal session external task",
        tasks=TaskSelector(include_patterns=[exact_task.task_id]),
        agents=[AgentConfig(name="agent", adapter="direct", model="test-model")],
        compute=ComputeConfig(backend="docker"),
        disable_verification=True,
    )
    jobs_root = tmp_path / "jobs"
    jobs_root.mkdir()
    config_path = tmp_path / "proposal-session.yaml"
    workflow = SynchronousHarborWorkflow(
        project_root=tmp_path,
        repo_root=REPO_ROOT,
        tasks_root=REPO_ROOT / "tasks",
        ledger_root=tmp_path / "ledger",
        jobs_root=jobs_root,
    )

    workflow.dispatch_only(
        manifest=manifest,
        config_path=config_path,
        executor=EmptyJobExecutor(jobs_root),
        resolved_tasks=(exact_task,),
        task_path_overrides={exact_task.task_id: task_path},
    )

    written = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert written["tasks"] == [{"path": str(task_path.resolve())}]


@_skip_no_job_data
def test_synchronous_workflow_dispatches_and_imports_real_job(tmp_path: Path) -> None:
    manifest = ExperimentManifest(
        experiment_id="6834bc30-3801-4a45-a114-afb2d3764b7d",
        name="Mechanical Harbor run",
        tasks=TaskSelector(domains=["mechanical"]),
        agents=[
            AgentConfig(
                name="tool-loop-sonnet-45",
                adapter="tool_loop",
                model="claude-sonnet-4-6",
                parameters={"harbor_import_path": ("agents.tool_loop_anthropic:ToolLoopAnthropicAgent")},
            )
        ],
        compute=ComputeConfig(backend="modal"),
    )
    jobs_root = tmp_path / "jobs"
    jobs_root.mkdir()
    workflow = SynchronousHarborWorkflow(
        project_root=tmp_path,
        repo_root=REPO_ROOT,
        tasks_root=REPO_ROOT / "tasks",
        ledger_root=tmp_path / "ledger",
        jobs_root=jobs_root,
    )
    progress_events: list[WorkflowProgressSnapshot] = []

    result = workflow.run(
        manifest=manifest,
        config_path=tmp_path / "generated-job.yaml",
        executor=FakeExecutor(source_job_dir=HARBOR_JOB_DIR, jobs_root=jobs_root),
        progress_callback=progress_events.append,
    )

    assert result.job_dir.name == "run-001"
    assert result.dispatch.command[:5] == ["uv", "run", "python", "-m", "aec_bench.harness.harbor_job"]
    assert result.import_result.imported_trials == 60
    assert result.import_result.duplicate_trials == 0
    assert [event.stage for event in progress_events] == [
        "dispatch_started",
        "dispatch_completed",
        "job_dir_identified",
        "import_started",
        "import_completed",
    ]
    assert progress_events[-1].imported_trials == 60


def test_synchronous_workflow_rejects_missing_new_job_dir(tmp_path: Path) -> None:
    manifest = ExperimentManifest(
        experiment_id="experiment-001",
        name="Mechanical Harbor run",
        tasks=TaskSelector(include_patterns=["mechanical/heat-load/*"]),
        agents=[
            AgentConfig(
                name="tool-loop-sonnet-45",
                adapter="tool_loop",
                model="claude-sonnet-4-6",
                parameters={"harbor_import_path": ("agents.tool_loop_anthropic:ToolLoopAnthropicAgent")},
            )
        ],
        compute=ComputeConfig(backend="modal"),
    )
    jobs_root = tmp_path / "jobs"
    jobs_root.mkdir()
    workflow = SynchronousHarborWorkflow(
        project_root=tmp_path,
        repo_root=REPO_ROOT,
        tasks_root=REPO_ROOT / "tasks",
        ledger_root=tmp_path / "ledger",
        jobs_root=jobs_root,
    )

    class NoopExecutor:
        def execute(self, *, command: list[str], cwd: Path) -> int:
            del command, cwd
            return 0

    with pytest.raises(HarborWorkflowError, match="no new Harbor job directory found"):
        workflow.run(
            manifest=manifest,
            config_path=tmp_path / "generated-job.yaml",
            executor=NoopExecutor(),
            resolved_tasks=(make_task_definition(task_id="mechanical/heat-load/demo-instance"),),
        )


@_skip_no_job_data
def test_synchronous_workflow_selects_matching_job_when_multiple_new_dirs_appear(
    tmp_path: Path,
) -> None:
    manifest = ExperimentManifest(
        experiment_id="6834bc30-3801-4a45-a114-afb2d3764b7d",
        name="Mechanical Harbor run",
        tasks=TaskSelector(domains=["mechanical"]),
        agents=[
            AgentConfig(
                name="tool-loop-sonnet-45",
                adapter="tool_loop",
                model="claude-sonnet-4-6",
                parameters={"harbor_import_path": ("agents.tool_loop_anthropic:ToolLoopAnthropicAgent")},
            )
        ],
        compute=ComputeConfig(backend="modal"),
    )
    jobs_root = tmp_path / "jobs"
    jobs_root.mkdir()
    workflow = SynchronousHarborWorkflow(
        project_root=tmp_path,
        repo_root=REPO_ROOT,
        tasks_root=REPO_ROOT / "tasks",
        ledger_root=tmp_path / "ledger",
        jobs_root=jobs_root,
    )

    result = workflow.run(
        manifest=manifest,
        config_path=tmp_path / "generated-job.yaml",
        executor=MultiJobExecutor(source_job_dir=HARBOR_JOB_DIR, jobs_root=jobs_root),
    )

    assert result.job_dir.name == "run-matching"
    assert result.import_result.imported_trials == 60


def test_synchronous_workflow_rejects_ambiguous_matching_job_dirs(tmp_path: Path) -> None:
    manifest = ExperimentManifest(
        experiment_id="ambiguous-job-run",
        name="Ambiguous Harbor job run",
        tasks=TaskSelector(domains=["electrical"]),
        agents=[AgentConfig(name="agent", adapter="direct", model="test-model")],
        compute=ComputeConfig(backend="modal"),
    )
    jobs_root = tmp_path / "jobs"
    jobs_root.mkdir()
    workflow = SynchronousHarborWorkflow(
        project_root=tmp_path,
        repo_root=REPO_ROOT,
        tasks_root=REPO_ROOT / "tasks",
        ledger_root=tmp_path / "ledger",
        jobs_root=jobs_root,
    )

    matching_dirs = {jobs_root / "run-a", jobs_root / "run-b"}
    for job_dir in matching_dirs:
        job_dir.mkdir()
        (job_dir / "result.json").write_text(
            json.dumps({"id": manifest.experiment_id}),
            encoding="utf-8",
        )

    with pytest.raises(
        HarborWorkflowError,
        match="multiple job directories without one exact experiment match",
    ):
        workflow._resolve_job_dir(
            manifest=manifest,
            before=set(),
            after=matching_dirs,
        )


def _rewrite_job_result_id(job_dir: Path, new_id: str) -> None:
    result_path = job_dir / "result.json"
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    payload["id"] = new_id
    result_path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize("observer_fails", [False, True])
def test_completion_observes_persisted_final_records_and_isolates_callback_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, observer_fails: bool
) -> None:
    from aec_bench.harness.harbor_workflow import HarborDispatchOnlyResult, HarborWorkflowResult
    from tests.support.trial_record_factories import make_trial_record

    task = make_task_definition()
    record = make_trial_record(task={"task_id": task.task_id, "task_revision": "test"})
    failed = make_trial_record(
        trial_id="trial-002",
        task={"task_id": task.task_id, "task_revision": "test"},
        execution_status="failed",
        evaluation=None,
    )
    manifest = ExperimentManifest(
        experiment_id=record.experiment_id,
        name="Completion callback",
        tasks=TaskSelector(include_patterns=[task.task_id]),
        agents=[AgentConfig(name="agent", adapter=record.agent.adapter, model=record.agent.model)],
        compute=ComputeConfig(backend=record.environment.compute_backend),
        repetitions=2,
    )
    monkeypatch.setattr("aec_bench.harness.experiment_runner.import_harbor_job", lambda **kwargs: [record, failed])
    workflow = SynchronousHarborWorkflow(
        project_root=tmp_path,
        repo_root=REPO_ROOT,
        tasks_root=tmp_path / "tasks",
        ledger_root=tmp_path / "ledger",
        jobs_root=tmp_path / "jobs",
    )
    dispatched = HarborDispatchOnlyResult(
        dispatch=HarborDispatchResult(
            config_path=tmp_path / "job.yaml", command=[], selected_task_count=1, planned_trial_count=2, exit_code=0
        ),
        job_dir=tmp_path / "jobs" / "job",
        resolved_tasks=(task,),
    )
    snapshots: list[WorkflowProgressSnapshot] = []
    completions: list[HarborWorkflowResult] = []
    observed_records: list[dict[str, object]] = []
    stages_at_completion: list[str] = []

    def observe_progress(snapshot: WorkflowProgressSnapshot) -> None:
        snapshots.append(snapshot)
        if observer_fails:
            raise RuntimeError("progress consumer failed")

    def on_complete(result: HarborWorkflowResult) -> None:
        completions.append(result)
        observed_records.extend(json.loads(path.read_text()) for path in result.import_result.ledger_paths)
        stages_at_completion.append(snapshots[-1].stage)
        if observer_fails:
            raise RuntimeError("completion consumer failed")

    result = workflow.import_dispatched(
        manifest=manifest, dispatched=dispatched, progress_callback=observe_progress, completion_callback=on_complete
    )
    assert completions == [result]
    assert observed_records == [record.model_dump(mode="json"), failed.model_dump(mode="json")]
    assert stages_at_completion == ["import_completed"]
    assert result.import_result.execution_status_counts == {"completed": 1, "failed": 1}
    assert result.import_result.imported_trials == 2
    assert result.import_result.invalid_trials == 0
    if observer_fails:
        assert "Harbor completion callback failed (RuntimeError)" in caplog.text
        assert "Workflow progress callback failed (RuntimeError)" in caplog.text

    duplicate = workflow.import_dispatched(manifest=manifest, dispatched=dispatched)
    assert duplicate.import_result.imported_trials == 0
    assert duplicate.import_result.duplicate_trials == 2
    assert duplicate.import_result.execution_status_counts == result.import_result.execution_status_counts
    assert duplicate.import_result.ledger_paths == result.import_result.ledger_paths


def test_completion_is_not_called_when_import_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from aec_bench.harness.harbor_workflow import HarborDispatchOnlyResult, HarborWorkflowResult

    task = make_task_definition()
    manifest = ExperimentManifest(
        experiment_id="import-failure",
        name="Import failure",
        tasks=TaskSelector(include_patterns=[task.task_id]),
        agents=[AgentConfig(name="agent", adapter="direct", model="test")],
        compute=ComputeConfig(backend="docker"),
    )

    def fail_import(**kwargs: object) -> None:
        raise ValueError("invalid source trial")

    monkeypatch.setattr("aec_bench.harness.experiment_runner.import_harbor_job", fail_import)
    workflow = SynchronousHarborWorkflow(
        project_root=tmp_path,
        repo_root=REPO_ROOT,
        tasks_root=tmp_path / "tasks",
        ledger_root=tmp_path / "ledger",
        jobs_root=tmp_path / "jobs",
    )
    dispatched = HarborDispatchOnlyResult(
        dispatch=HarborDispatchResult(
            config_path=tmp_path / "job.yaml", command=[], selected_task_count=1, planned_trial_count=1, exit_code=0
        ),
        job_dir=tmp_path / "jobs" / "job",
        resolved_tasks=(task,),
    )
    completions: list[HarborWorkflowResult] = []
    with pytest.raises(ValueError, match="invalid source trial"):
        workflow.import_dispatched(manifest=manifest, dispatched=dispatched, completion_callback=completions.append)
    assert completions == []
    assert not workflow.ledger_root.exists()


def test_trial_progress_does_not_import_attempts_or_complete_a_failed_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import UTC, datetime
    from uuid import uuid4

    from aec_bench.harness.harbor_dispatch import SubprocessHarborExecutor
    from aec_bench.harness.harbor_workflow import HarborWorkflowResult
    from aec_bench.harness.progress_tracker import HarborTrialProgress

    task = make_task_definition()
    manifest = ExperimentManifest(
        experiment_id="failed-dispatch",
        name="Failed dispatch",
        tasks=TaskSelector(include_patterns=[task.task_id]),
        agents=[AgentConfig(name="agent", adapter="direct", model="test")],
        compute=ComputeConfig(backend="docker"),
    )
    event = HarborTrialProgress(
        event="end",
        timestamp=datetime.now(UTC),
        harbor_trial_id=uuid4(),
        trial_name="attempt",
        task_name=task.task_id,
        agent_name="agent",
        model_name="test",
        trial_dir=tmp_path / "jobs/job/attempt",
        exception_type="RuntimeError",
    )

    def dispatch(self: object, **kwargs: object) -> HarborDispatchResult:
        executor = kwargs["executor"]
        assert isinstance(executor, SubprocessHarborExecutor)
        assert executor.progress_callback is not None
        executor.progress_callback(event)
        return HarborDispatchResult(
            config_path=tmp_path / "job.yaml", command=[], selected_task_count=1, planned_trial_count=1, exit_code=7
        )

    monkeypatch.setattr(HarborExperimentDispatcher, "dispatch", dispatch)
    workflow = SynchronousHarborWorkflow(
        project_root=tmp_path,
        repo_root=REPO_ROOT,
        tasks_root=tmp_path / "tasks",
        ledger_root=tmp_path / "ledger",
        jobs_root=tmp_path / "jobs",
    )
    snapshots: list[WorkflowProgressSnapshot] = []
    completions: list[HarborWorkflowResult] = []
    with pytest.raises(HarborWorkflowError, match="exit code 7"):
        workflow.run(
            manifest=manifest,
            config_path=tmp_path / "job.yaml",
            resolved_tasks=(task,),
            progress_callback=snapshots.append,
            completion_callback=completions.append,
        )
    assert [snapshot.stage for snapshot in snapshots] == ["dispatch_started", "trial_event", "dispatch_completed"]
    assert snapshots[1].trial == event
    assert snapshots[1].imported_trials == snapshots[1].discovered_trials == 0
    assert completions == []
    assert not workflow.ledger_root.exists()
