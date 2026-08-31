# ABOUTME: Tests Web API dataset views over semantic manifests and labelled exact references.
# ABOUTME: Ensures routine responses omit legacy versions and hashes while integrity stays fail closed.

from pathlib import Path

from fastapi.testclient import TestClient

from aec_bench.contracts.dataset import DatasetManifest, DatasetTaskEntry
from aec_bench.dataset.publication import publish_dataset
from aec_bench.dataset.storage import save_dataset
from aec_bench.web.app import create_app


def _make_client_with_dataset(tmp_path: Path) -> TestClient:
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    task = tasks / "electrical/voltage-drop/inst-0"
    task.mkdir(parents=True)
    (task / "task.toml").write_text(
        '[identity]\nid = "019c2c7a-5a33-7b8d-a702-8f7f3e8c21aa"\n'
        'key = "electrical/voltage-drop/inst-0"\nversion = 1\n\n'
        '[metadata]\nlifecycle = "active"\nvisibility = "public"\n',
        encoding="utf-8",
    )
    datasets = tmp_path / "datasets"
    manifest = DatasetManifest(
        dataset_id="test-ds",
        description="A test dataset",
        tasks=[
            DatasetTaskEntry(
                task_id="electrical/voltage-drop/inst-0",
                path="tasks/electrical/voltage-drop/inst-0",
                task_kind="artifact",
            )
        ],
    )
    save_dataset(datasets, manifest)
    publish_dataset(
        manifest=manifest,
        datasets_root=datasets,
        project_root=tmp_path,
        label="public-2026",
    )
    return TestClient(create_app(ledger_root=ledger, tasks_root=tasks, datasets_root=datasets))


def _make_client_empty(tmp_path: Path) -> TestClient:
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    datasets = tmp_path / "datasets"
    datasets.mkdir()
    return TestClient(create_app(ledger_root=ledger, tasks_root=tasks, datasets_root=datasets))


def test_datasets_list_api_uses_stable_identity_and_labels(tmp_path: Path) -> None:
    response = _make_client_with_dataset(tmp_path).get("/api/datasets")

    assert response.status_code == 200
    assert response.json() == {
        "datasets": [
            {
                "dataset_id": "test-ds",
                "description": "A test dataset",
                "task_count": 1,
                "labels": ["public-2026"],
            }
        ],
        "total_datasets": 1,
        "total_tasks": 1,
    }


def test_datasets_list_api_empty(tmp_path: Path) -> None:
    response = _make_client_empty(tmp_path).get("/api/datasets")

    assert response.status_code == 200
    assert response.json() == {"datasets": [], "total_datasets": 0, "total_tasks": 0}


def test_dataset_detail_api_resolves_label_to_exact_reference(tmp_path: Path) -> None:
    response = _make_client_with_dataset(tmp_path).get("/api/datasets/test-ds/public-2026")

    assert response.status_code == 200
    data = response.json()
    assert data["dataset_id"] == "test-ds"
    assert data["label"] == "public-2026"
    assert data["reference_kind"] == "bundle"
    assert data["tasks"] == [
        {
            "task_id": "electrical/voltage-drop/inst-0",
            "path": "tasks/electrical/voltage-drop/inst-0",
            "task_kind": "artifact",
        }
    ]
    assert not ({"version", "content_hash", "created_at"} & data.keys())


def test_dataset_detail_api_unknown_label_returns_404(tmp_path: Path) -> None:
    response = _make_client_with_dataset(tmp_path).get("/api/datasets/test-ds/nope")

    assert response.status_code == 404


def test_dataset_detail_api_reports_reference_integrity(tmp_path: Path) -> None:
    response = _make_client_with_dataset(tmp_path).get("/api/datasets/test-ds/public-2026?tab=integrity")

    assert response.status_code == 200
    assert response.json()["integrity_results"] == [{"task_id": "electrical/voltage-drop/inst-0", "status": "verified"}]
    assert response.json()["integrity_unexpected"] == []


def test_dataset_detail_api_reports_unexpected_material(tmp_path: Path) -> None:
    client = _make_client_with_dataset(tmp_path)
    extra = tmp_path / "tasks/electrical/voltage-drop/inst-0/extra.txt"
    extra.write_text("not in the published bundle", encoding="utf-8")

    response = client.get("/api/datasets/test-ds/public-2026?tab=integrity")

    assert response.status_code == 200
    assert response.json()["integrity_unexpected"] == ["tasks/electrical/voltage-drop/inst-0/extra.txt"]
