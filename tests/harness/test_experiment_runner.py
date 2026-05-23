# ABOUTME: Tests for manifest-aware Harbor import orchestration in the harness layer.
# ABOUTME: Verifies selector validation, duplicate handling, and import progress accounting.

from pathlib import Path

import pytest

from aec_bench.contracts.experiment_manifest import (
    AgentConfig,
    ComputeConfig,
    ExperimentManifest,
    TaskSelector,
)
from aec_bench.harness.experiment_runner import (
    ExperimentImportMismatchError,
    HarborImportExperimentRunner,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
TASKS_ROOT = REPO_ROOT / "tasks"
HARBOR_JOB_DIR = REPO_ROOT / "jobs" / "2026-03-04__17-57-43"

_skip_no_job_data = pytest.mark.skipif(
    not HARBOR_JOB_DIR.exists(),
    reason="requires archived Harbor job data in jobs/",
)


@_skip_no_job_data
def test_runner_imports_real_harbor_job_and_tracks_progress(tmp_path: Path) -> None:
    manifest = ExperimentManifest(
        experiment_id="6834bc30-3801-4a45-a114-afb2d3764b7d",
        name="Mechanical Harbor import",
        tasks=TaskSelector(domains=["mechanical"]),
        agents=[
            AgentConfig(
                name="tool-loop-sonnet-45",
                adapter="tool-loop-anthropic",
                model="claude-sonnet-4-6",
            )
        ],
        compute=ComputeConfig(backend="modal"),
    )
    runner = HarborImportExperimentRunner(
        repo_root=REPO_ROOT,
        tasks_root=TASKS_ROOT,
        ledger_root=tmp_path,
    )

    result = runner.import_harbor_job(job_dir=HARBOR_JOB_DIR, manifest=manifest)

    assert result.experiment_id == manifest.experiment_id
    assert result.selected_task_count > 0
    assert result.discovered_trials == 60
    assert result.imported_trials == 60
    assert result.duplicate_trials == 0
    assert result.unexpected_task_ids == []
    assert result.unexpected_agents == []
    assert result.unexpected_backends == []
    assert len(result.output_paths) == 60


@_skip_no_job_data
def test_runner_skips_duplicate_trial_records_on_repeat_import(tmp_path: Path) -> None:
    manifest = ExperimentManifest(
        experiment_id="6834bc30-3801-4a45-a114-afb2d3764b7d",
        name="Mechanical Harbor import",
        tasks=TaskSelector(domains=["mechanical"]),
        agents=[
            AgentConfig(
                name="tool-loop-sonnet-45",
                adapter="tool-loop-anthropic",
                model="claude-sonnet-4-6",
            )
        ],
        compute=ComputeConfig(backend="modal"),
    )
    runner = HarborImportExperimentRunner(
        repo_root=REPO_ROOT,
        tasks_root=TASKS_ROOT,
        ledger_root=tmp_path,
    )

    first = runner.import_harbor_job(job_dir=HARBOR_JOB_DIR, manifest=manifest)
    second = runner.import_harbor_job(job_dir=HARBOR_JOB_DIR, manifest=manifest)

    assert first.imported_trials == 60
    assert second.imported_trials == 0
    assert second.duplicate_trials == 60


@_skip_no_job_data
def test_runner_rejects_job_that_falls_outside_manifest_selector(tmp_path: Path) -> None:
    manifest = ExperimentManifest(
        experiment_id="6834bc30-3801-4a45-a114-afb2d3764b7d",
        name="Electrical only",
        tasks=TaskSelector(domains=["electrical"]),
        agents=[
            AgentConfig(
                name="tool-loop-sonnet-45",
                adapter="tool-loop-anthropic",
                model="claude-sonnet-4-6",
            )
        ],
        compute=ComputeConfig(backend="modal"),
    )
    runner = HarborImportExperimentRunner(
        repo_root=REPO_ROOT,
        tasks_root=TASKS_ROOT,
        ledger_root=tmp_path,
    )

    with pytest.raises(ExperimentImportMismatchError, match="unexpected task ids"):
        runner.import_harbor_job(job_dir=HARBOR_JOB_DIR, manifest=manifest)
