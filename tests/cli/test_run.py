# ABOUTME: Tests for the manifest and inline aec-bench run CLI entry point.
# ABOUTME: Verifies backend planning output and Harbor-backed Morph routing.

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from aec_bench import worlds
from aec_bench.cli.main import app
from aec_bench.contracts.dataset import DatasetManifest, DatasetTaskEntry
from aec_bench.contracts.run_bundle import PublishedRunPackage
from aec_bench.dataset.publication import publish_dataset
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.ledger.run_package import publish_run_package
from aec_bench.worlds.tasks import WorldTask
from tests.support.adaptive_harness import build_adaptive_bundle, write_adaptive_task

runner = CliRunner()


def _write_world_task(tasks_root: Path) -> tuple[Path, WorldTask]:
    task_dir = tasks_root / "civil" / "dam-monitoring"
    task_dir.mkdir(parents=True)
    task = worlds.task(
        "dam-seepage-monitoring",
        profile="synthetic-rising-seepage",
        instruction="Monitor the dam.",
        task_id="civil/dam-monitoring",
    )
    (task_dir / "instruction.md").write_text(task.instruction, encoding="utf-8")
    (task_dir / "world.toml").write_text(
        f'''[world]
task_world_id = "{task.world.task_world_id}"
entry_point = "{task.world.entry_point}"
artifact_sha256 = "{task.world.artifact_sha256}"

[profile]
task_world_id = "{task.profile.task_world_id}"
profile_id = "{task.profile.profile_id}"
profile_content_sha256 = "{task.profile.profile_content_sha256}"

[metadata]
domain = "civil"
category = "monitoring"
difficulty = "medium"
lifecycle = "active"
visibility = "public"
tags = ["dam", "monitoring", "seepage", "synthetic"]
''',
        encoding="utf-8",
    )
    return task_dir, task


def _write_minimal_task(tasks_root: Path) -> Path:
    task_dir = tasks_root / "electrical" / "voltage-drop" / "demo-instance"
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "instruction.md").write_text(
        "Calculate the answer and write it to /workspace/output.jsonl.\n",
        encoding="utf-8",
    )
    (task_dir / "task.toml").write_text(
        '[identity]\nid = "019c2c7a-5a33-7b8d-a702-8f7f3e8c21aa"\n'
        'key = "electrical/voltage-drop/demo-instance"\nversion = 1\n\n'
        '[metadata]\nlifecycle = "active"\nvisibility = "public"\n\n[agent]\ntimeout_sec = 60\n',
        encoding="utf-8",
    )
    (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    return task_dir


def test_run_dry_run_reports_selected_backend(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_minimal_task(tasks_root)

    result = runner.invoke(
        app,
        [
            "--json",
            "run",
            str(task_dir),
            "--model",
            "test-model",
            "--tasks-root",
            str(tasks_root),
            "--backend",
            "modal",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["data"]["backend"] == "modal"


def test_run_dry_run_accepts_morph_backend(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_minimal_task(tasks_root)

    result = runner.invoke(
        app,
        [
            "--json",
            "run",
            str(task_dir),
            "--model",
            "test-model",
            "--tasks-root",
            str(tasks_root),
            "--backend",
            "morph",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["data"]["backend"] == "morph"


def test_run_dry_run_reports_reviewer_plan_from_config(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_minimal_task(tasks_root)
    reviewer_config = tmp_path / "reviewer.json"
    reviewer_config.write_text(
        json.dumps(
            {
                "enabled": True,
                "models": [
                    {"name": "primary", "model": "openai:gpt-5.2"},
                    {"name": "secondary", "model": "anthropic:claude-opus-4-8"},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--json",
            "run",
            str(task_dir),
            "--model",
            "test-model",
            "--tasks-root",
            str(tasks_root),
            "--backend",
            "modal",
            "--reviewer-models-config",
            str(reviewer_config),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["data"]["reviewer"]["enabled"] is True
    assert envelope["data"]["reviewer"]["models"] == ["primary", "secondary"]


def test_run_config_resolves_dataset_label_before_planning(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_minimal_task(tasks_root)
    task_path = task_dir.relative_to(tmp_path).as_posix()
    manifest = DatasetManifest(
        dataset_id="core",
        description="Core benchmark tasks",
        tasks=(
            DatasetTaskEntry(task_id=task_dir.relative_to(tasks_root).as_posix(), path=task_path, task_kind="artifact"),
        ),
    )
    publish_dataset(
        manifest=manifest,
        datasets_root=tmp_path / "artefacts" / "datasets",
        project_root=tmp_path,
        label="public-2026",
    )
    config = tmp_path / "experiment.yaml"
    config.write_text(
        """\
experiment_id: exact-dataset
name: Exact dataset run
tasks:
  dataset: core@public-2026
agents:
  - name: test-agent
    adapter: tool_loop
    model: test-model
compute:
  backend: modal
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--json",
            "run",
            "--config",
            str(config),
            "--tasks-root",
            str(tasks_root),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["data"]["selected_tasks"] == 1


def test_run_dry_run_loads_world_task_from_dataset_entry(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir, task = _write_world_task(tasks_root)
    manifest = DatasetManifest(
        dataset_id="worlds",
        description="World benchmark tasks",
        tasks=(
            DatasetTaskEntry(
                task_id=task.task_id,
                path=task_dir.relative_to(tmp_path).as_posix(),
                task_kind="world",
            ),
        ),
    )
    publish_dataset(
        manifest=manifest,
        datasets_root=tmp_path / "artefacts" / "datasets",
        project_root=tmp_path,
        label="public-2026",
    )
    config = tmp_path / "world-experiment.yaml"
    config.write_text(
        """experiment_id: world-dataset
name: World dataset run
tasks:
  dataset: worlds@public-2026
agents:
  - name: prime
    adapter: prime-agent
    model: test-model
compute:
  backend: local
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["--json", "run", "--config", str(config), "--tasks-root", str(tasks_root), "--dry-run"],
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["data"]["selected_tasks"] == 1
    assert envelope["data"]["trials"][0]["task_id"] == task.task_id


def test_run_export_and_import_transfer_one_published_package(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root)
    source_ledger = tmp_path / "source-ledger"
    plan = build_adaptive_bundle(
        tasks_root=tasks_root,
        artifact_repository=ArtifactRepository(source_ledger / "_artifacts"),
    )
    published = publish_run_package(
        ledger_root=source_ledger,
        package=PublishedRunPackage(run_plan=plan),
    )
    archive = tmp_path / "run-package.tar.zst"

    exported = runner.invoke(
        app,
        [
            "--json",
            "run",
            "export",
            plan.run_manifest.run_id,
            "--output",
            str(archive),
            "--ledger-root",
            str(source_ledger),
        ],
    )

    assert exported.exit_code == 0, exported.output
    assert archive.read_bytes() == ArtifactRepository(source_ledger / "_artifacts").read_bytes(published)
    destination_ledger = tmp_path / "destination-ledger"
    imported = runner.invoke(
        app,
        [
            "--json",
            "run",
            "import",
            str(archive),
            "--ledger-root",
            str(destination_ledger),
        ],
    )

    assert imported.exit_code == 0, imported.output
    envelope = json.loads(imported.output)
    assert envelope["data"]["run_id"] == plan.run_manifest.run_id
    assert ArtifactRepository(destination_ledger / "_artifacts").read_bytes(published) == archive.read_bytes()
