# ABOUTME: Tests for manifest-aware Harbor import orchestration in the harness layer.
# ABOUTME: Verifies selector validation, duplicate handling, and import progress accounting.

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.dataset import BundleDatasetRef
from aec_bench.contracts.experiment_manifest import (
    AgentConfig,
    ComputeConfig,
    ExperimentManifest,
    TaskSelector,
)
from aec_bench.contracts.trial_record import (
    AgentReference,
    EnvironmentSnapshot,
    TaskReference,
)
from aec_bench.harness import experiment_runner as experiment_runner_module
from aec_bench.harness.experiment_runner import (
    ExperimentImportMismatchError,
    HarborImportExperimentRunner,
)
from aec_bench.ledger.reader import read_trial_record
from tests.support.trial_record_factories import make_trial_record

REPO_ROOT = Path(__file__).resolve().parents[2]
TASKS_ROOT = REPO_ROOT / "tasks"
HARBOR_JOB_DIR = REPO_ROOT / "jobs" / "2026-03-04__17-57-43"

_skip_no_job_data = pytest.mark.skipif(
    not HARBOR_JOB_DIR.exists(),
    reason="requires archived Harbor job data in jobs/",
)


def test_runner_transforms_records_before_validation_and_persistence(tmp_path: Path, monkeypatch) -> None:
    task_id = "civil/calculation/adaptive"
    manifest = ExperimentManifest(
        experiment_id="adaptive-run",
        name="Adaptive run",
        tasks=TaskSelector(include_patterns=[task_id]),
        agents=[AgentConfig(name="agent", adapter="tool_loop", model="test-model")],
        compute=ComputeConfig(backend="docker"),
    )
    record = make_trial_record(
        experiment_id=manifest.experiment_id,
        task=TaskReference(task_id=task_id, task_revision="task-sha"),
        agent=AgentReference(
            adapter="tool_loop",
            model="test-model",
            adapter_revision="adapter-sha",
            configuration={},
        ),
        environment=EnvironmentSnapshot(
            runtime_image="task-image",
            compute_backend="docker",
            tool_versions={},
        ),
    )
    monkeypatch.setattr(
        experiment_runner_module,
        "import_harbor_job",
        lambda **_kwargs: [record],
    )
    monkeypatch.setattr(
        HarborImportExperimentRunner,
        "_selected_tasks",
        lambda _self, _manifest: [SimpleNamespace(task_id=task_id)],
    )
    transformed_trial_ids: list[str] = []

    def transform(imported):  # noqa: ANN001, ANN201
        transformed_trial_ids.append(imported.trial_id)
        return imported.model_copy(update={"attempt": 2})

    runner = HarborImportExperimentRunner(
        repo_root=tmp_path,
        tasks_root=tmp_path / "tasks",
        ledger_root=tmp_path / "ledger",
    )
    result = runner.import_harbor_job(
        job_dir=tmp_path / "job",
        manifest=manifest,
        record_transform=transform,
    )

    assert transformed_trial_ids == [record.trial_id]
    saved = json.loads(result.output_paths[0].read_text(encoding="utf-8"))
    assert saved["attempt"] == 2


def test_runner_passes_only_the_exact_dataset_reference_to_import(tmp_path: Path, monkeypatch) -> None:
    reference = BundleDatasetRef(
        dataset_id="core",
        artifact=ArtifactRef(
            artifact_id="sha256:" + "a" * 64,
            sha256="a" * 64,
            size_bytes=1,
            media_type="application/vnd.aec-bench.dataset-bundle+tar+gzip",
        ),
    )
    manifest = ExperimentManifest(
        experiment_id="exact-dataset-run",
        name="Exact dataset run",
        tasks=TaskSelector(dataset=reference),
        agents=[AgentConfig(name="agent", adapter="tool_loop", model="test-model")],
        compute=ComputeConfig(backend="docker"),
    )
    captured: dict[str, object] = {}

    def capture_import(**kwargs):  # noqa: ANN003, ANN202
        captured.update(kwargs)
        return []

    monkeypatch.setattr(experiment_runner_module, "import_harbor_job", capture_import)
    monkeypatch.setattr(HarborImportExperimentRunner, "_selected_tasks", lambda _self, _manifest: [])
    runner = HarborImportExperimentRunner(
        repo_root=tmp_path,
        tasks_root=tmp_path / "tasks",
        ledger_root=tmp_path / "ledger",
    )

    runner.import_harbor_job(job_dir=tmp_path / "job", manifest=manifest)

    assert captured["dataset"] == reference


def test_runner_returns_replayable_paths_for_identical_duplicate_records(
    tmp_path: Path,
    monkeypatch,
) -> None:
    task_id = "civil/calculation/replayable-import"
    manifest = ExperimentManifest(
        experiment_id="replayable-import",
        name="Replayable import",
        tasks=TaskSelector(include_patterns=[task_id]),
        agents=[AgentConfig(name="agent", adapter="tool_loop", model="test-model")],
        compute=ComputeConfig(backend="docker"),
    )
    record = make_trial_record(
        experiment_id=manifest.experiment_id,
        task=TaskReference(task_id=task_id, task_revision="task-sha"),
        agent=AgentReference(
            adapter="tool_loop",
            model="test-model",
            adapter_revision="adapter-sha",
            configuration={},
        ),
        environment=EnvironmentSnapshot(
            runtime_image="task-image",
            compute_backend="docker",
            tool_versions={},
        ),
    )
    monkeypatch.setattr(
        experiment_runner_module,
        "import_harbor_job",
        lambda **_kwargs: [record],
    )
    monkeypatch.setattr(
        HarborImportExperimentRunner,
        "_selected_tasks",
        lambda _self, _manifest: [SimpleNamespace(task_id=task_id)],
    )
    runner = HarborImportExperimentRunner(
        repo_root=tmp_path,
        tasks_root=tmp_path / "tasks",
        ledger_root=tmp_path / "ledger",
    )

    first = runner.import_harbor_job(
        job_dir=tmp_path / "job",
        manifest=manifest,
    )
    replay = runner.import_harbor_job(
        job_dir=tmp_path / "job",
        manifest=manifest,
    )

    assert first.imported_trials == 1
    assert first.duplicate_trials == 0
    assert replay.imported_trials == 0
    assert replay.duplicate_trials == 1
    assert replay.ledger_paths == first.output_paths
    replayed = read_trial_record(replay.ledger_paths[0], ledger_root=tmp_path / "ledger")
    assert replayed.model_dump(mode="json") == record.model_dump(mode="json")
    assert replayed.run_manifest == record.run_manifest

    conflicting_record = record.model_copy(update={"attempt": 2})
    monkeypatch.setattr(
        experiment_runner_module,
        "import_harbor_job",
        lambda **_kwargs: [conflicting_record],
    )
    with pytest.raises(
        ExperimentImportMismatchError,
        match="duplicate TrialRecord identity resolves to different ledger content",
    ):
        runner.import_harbor_job(
            job_dir=tmp_path / "job",
            manifest=manifest,
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
