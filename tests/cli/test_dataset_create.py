# ABOUTME: Tests the schema-2 dataset create, publish, and config CLI workflow.
# ABOUTME: Ensures human labels resolve to exact references before experiment YAML is written.

from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime
from pathlib import Path

import yaml
from typer.testing import CliRunner

from aec_bench.cli.main import app
from aec_bench.contracts.dataset import BundleDatasetRef, DatasetManifest, DatasetPublication, DatasetTaskEntry
from aec_bench.dataset.porter import DATASET_BUNDLE_MEDIA_TYPE, build_dataset_bundle
from aec_bench.dataset.storage import write_publication
from aec_bench.ledger.artifact_repository import ArtifactRepository

runner = CliRunner()


def _make_task(project_root: Path, task_id: str, difficulty: str) -> None:
    task_dir = project_root / "tasks" / task_id
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text(
        '[identity]\nid = "019c2c7a-5a33-7b8d-a702-8f7f3e8c21aa"\n'
        f'key = "{task_id.lower()}"\nversion = 1\n\n'
        "[metadata]\n"
        'lifecycle = "active"\n'
        'visibility = "public"\n'
        f'difficulty = "{difficulty}"\n'
        'category = "reasoning"\n'
        'tags = ["dataset-test"]\n\n'
        "[agent]\n"
        "timeout_sec = 600\n",
        encoding="utf-8",
    )
    (task_dir / "instruction.md").write_text("Solve the task.\n", encoding="utf-8")
    tests_dir = task_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")


def _prepare_project(tmp_path: Path) -> None:
    (tmp_path / "aec-bench.toml").write_text(
        '[paths]\ntasks = "tasks"\ndatasets = "artefacts/datasets"\n',
        encoding="utf-8",
    )
    _make_task(tmp_path, "electrical/example/easy", "easy")
    _make_task(tmp_path, "electrical/example/medium", "medium")
    _make_task(tmp_path, "mechanical/example/hard", "hard")


def _write_suite_output(project_root: Path) -> Path:
    suite_output = project_root / "tasks" / "generation-manifest.json"
    suite_output.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "suite_id": "generated-suite",
                "source": {
                    "kind": "git",
                    "revision": "a" * 40,
                    "template_root": "src/aec_bench/templates/builtin",
                },
                "config_ref": "generation-config.json",
                "instances": [
                    {
                        "task_id": "electrical/example/easy",
                        "task_kind": "artifact",
                        "template_id": "electrical/example",
                        "seed": 20260508,
                        "instance_index": 0,
                        "difficulty": "easy",
                        "tool_mode": "with-tool",
                        "task_lifecycle": "active",
                        "task_visibility": "public",
                        "task_identity_id": "019c2c7a-5a33-7b8d-a702-8f7f3e8c21aa",
                    },
                    {
                        "task_id": "mechanical/example/hard",
                        "task_kind": "artifact",
                        "template_id": "mechanical/example",
                        "seed": 20260509,
                        "instance_index": 1,
                        "difficulty": "hard",
                        "tool_mode": "with-tool",
                        "task_lifecycle": "active",
                        "task_visibility": "public",
                        "task_identity_id": "019c2c7a-5a33-7b8d-a702-8f7f3e8c21ab",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return suite_output


def test_dataset_create_uses_stable_id_and_schema_2(tmp_path: Path, monkeypatch) -> None:
    _prepare_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["dataset", "create", "easy-only", "--difficulty", "easy"])

    assert result.exit_code == 0, result.output
    manifest_path = tmp_path / "artefacts/datasets/manifests/easy-only/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 2
    assert manifest["dataset_id"] == "easy-only"
    assert [task["task_id"] for task in manifest["tasks"]] == ["electrical/example/easy"]
    assert not ({"version", "content_hash", "created_at"} & manifest.keys())


def test_dataset_create_cannot_overwrite_stable_id(tmp_path: Path, monkeypatch) -> None:
    _prepare_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["dataset", "create", "core"]).exit_code == 0

    result = runner.invoke(app, ["dataset", "create", "core"])

    assert result.exit_code == 1
    assert "already exists" in result.output


def test_dataset_create_from_suite_output_keeps_only_replay_inputs(tmp_path: Path, monkeypatch) -> None:
    _prepare_project(tmp_path)
    suite_output = _write_suite_output(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["dataset", "create", "from-suite", "--from-suite-output", str(suite_output)])

    assert result.exit_code == 0, result.output
    manifest = json.loads(
        (tmp_path / "artefacts/datasets/manifests/from-suite/manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["generation"] == {"seed": 20260508, "config_ref": "generation-config.json"}
    assert [task["task_id"] for task in manifest["tasks"]] == [
        "electrical/example/easy",
        "mechanical/example/hard",
    ]


def test_dataset_publish_then_config_persists_exact_reference(tmp_path: Path, monkeypatch) -> None:
    _prepare_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["dataset", "create", "core", "--difficulty", "easy"]).exit_code == 0
    published = runner.invoke(app, ["dataset", "publish", "core", "--label", "public-2026"])
    output = tmp_path / "experiment.yaml"

    configured = runner.invoke(
        app,
        ["dataset", "config", "core@public-2026", "--model", "gpt-5", "--output", str(output)],
    )

    assert published.exit_code == 0, published.output
    assert configured.exit_code == 0, configured.output
    dataset = yaml.safe_load(output.read_text(encoding="utf-8"))["tasks"]["dataset"]
    assert dataset["kind"] == "bundle"
    assert dataset["dataset_id"] == "core"
    assert dataset["artifact"]["sha256"]
    assert "latest" not in output.read_text(encoding="utf-8")


def test_dataset_publish_rejects_latest_label(tmp_path: Path, monkeypatch) -> None:
    _prepare_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["dataset", "create", "core"]).exit_code == 0

    result = runner.invoke(app, ["dataset", "publish", "core", "--label", "latest"])

    assert result.exit_code == 1
    assert "latest is a mutable selector" in result.output


def test_dataset_export_preserves_exact_detached_bundle_bytes(tmp_path: Path, monkeypatch) -> None:
    _prepare_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    manifest = DatasetManifest(
        dataset_id="core",
        description="Core tasks",
        tasks=(
            DatasetTaskEntry(
                task_id="electrical/example/easy",
                path="tasks/electrical/example/easy",
                task_kind="artifact",
            ),
        ),
    )
    normal = build_dataset_bundle(manifest=manifest, project_root=tmp_path)
    noncanonical = gzip.compress(gzip.decompress(normal), mtime=7)
    datasets_root = tmp_path / "artefacts" / "datasets"
    artifact = ArtifactRepository(datasets_root / "artifacts").publish_bytes(
        data=noncanonical,
        media_type=DATASET_BUNDLE_MEDIA_TYPE,
    )
    reference = BundleDatasetRef(dataset_id="core", artifact=artifact)
    write_publication(
        datasets_root,
        DatasetPublication(dataset_ref=reference, label="imported", published_at=datetime.now(UTC)),
    )
    output = tmp_path / "export.tar.gz"

    result = runner.invoke(app, ["dataset", "export", "core@imported", "--output", str(output)])

    assert result.exit_code == 0, result.output
    assert output.read_bytes() == noncanonical
