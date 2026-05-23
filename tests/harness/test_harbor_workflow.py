# ABOUTME: Tests for the composed Harbor dispatch-and-import workflow in the harness.
# ABOUTME: Verifies job-dir detection and ledger import after synchronous Harbor execution.

import json
import shutil
from pathlib import Path

import pytest

from aec_bench.contracts.experiment_manifest import (
    AgentConfig,
    ComputeConfig,
    ExperimentManifest,
    TaskSelector,
)
from aec_bench.harness.harbor_workflow import HarborWorkflowError, SynchronousHarborWorkflow
from aec_bench.harness.progress_tracker import WorkflowProgressSnapshot

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


class MultiMatchExecutor:
    def __init__(
        self,
        *,
        source_job_dir: Path,
        jobs_root: Path,
        job_names: tuple[str, str] = ("run-a", "run-b"),
    ) -> None:
        self.source_job_dir = source_job_dir
        self.jobs_root = jobs_root
        self.job_names = job_names

    def execute(self, *, command: list[str], cwd: Path) -> int:
        del command, cwd
        for job_name in self.job_names:
            shutil.copytree(self.source_job_dir, self.jobs_root / job_name)
        return 0


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
    assert result.dispatch.command[:4] == ["uv", "run", "harbor", "run"]
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


@_skip_no_job_data
def test_synchronous_workflow_rejects_ambiguous_matching_job_dirs(tmp_path: Path) -> None:
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

    # Multiple matching dirs: workflow picks the latest instead of rejecting
    result = workflow.run(
        manifest=manifest,
        config_path=tmp_path / "generated-job.yaml",
        executor=MultiMatchExecutor(source_job_dir=HARBOR_JOB_DIR, jobs_root=jobs_root),
    )
    assert result.job_dir is not None
    assert result.import_result.imported_trials > 0


def _rewrite_job_result_id(job_dir: Path, new_id: str) -> None:
    result_path = job_dir / "result.json"
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    payload["id"] = new_id
    result_path.write_text(json.dumps(payload), encoding="utf-8")
