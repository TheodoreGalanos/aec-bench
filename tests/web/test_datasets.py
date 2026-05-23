# ABOUTME: Tests for the datasets API endpoints showing versioned benchmark datasets.
# ABOUTME: Verifies list view, detail view with tabs, and 404 handling via JSON API.

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from aec_bench.web.app import create_app


def _make_client_with_dataset(tmp_path: Path) -> TestClient:
    """Create a client with a minimal dataset in storage."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    datasets = tmp_path / "datasets" / "test-ds" / "1.0.0"
    datasets.mkdir(parents=True)
    manifest = {
        "name": "test-ds",
        "version": "1.0.0",
        "content_hash": "abc123",
        "description": {
            "summary": "A test dataset",
            "purpose": "testing",
            "standards": ["AS3008"],
            "domains": ["electrical"],
            "difficulty_distribution": {"medium": 1},
            "template_count": 1,
            "task_count": 1,
        },
        "created_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
        "tasks": [
            {
                "task_id": "electrical/voltage-drop/inst-0",
                "task_path": "tasks/electrical/voltage-drop/inst-0",
                "content_hash": "hash-0001",
                "domain": "electrical",
                "difficulty": "medium",
                "tags": ["voltage"],
            }
        ],
        "source": {"method": "manual"},
    }
    (datasets / "manifest.json").write_text(json.dumps(manifest))
    return TestClient(create_app(ledger_root=ledger, tasks_root=tasks, datasets_root=tmp_path / "datasets"))


def _make_client_empty(tmp_path: Path) -> TestClient:
    """Create a client with no datasets."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    datasets = tmp_path / "datasets"
    datasets.mkdir()
    return TestClient(create_app(ledger_root=ledger, tasks_root=tasks, datasets_root=datasets))


# ---------------------------------------------------------------------------
# API: list endpoint
# ---------------------------------------------------------------------------


def test_datasets_list_api_returns_json(tmp_path: Path) -> None:
    """GET /api/datasets should return JSON with expected keys."""
    client = _make_client_with_dataset(tmp_path)
    resp = client.get("/api/datasets")
    assert resp.status_code == 200
    data = resp.json()
    assert "datasets" in data
    assert "total_datasets" in data
    assert "total_tasks" in data


def test_datasets_list_api_includes_dataset(tmp_path: Path) -> None:
    """Datasets list should include the test dataset."""
    client = _make_client_with_dataset(tmp_path)
    resp = client.get("/api/datasets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_datasets"] == 1
    assert data["datasets"][0]["name"] == "test-ds"
    assert data["datasets"][0]["version"] == "1.0.0"


def test_datasets_list_api_empty(tmp_path: Path) -> None:
    """Empty datasets directory should return zero counts."""
    client = _make_client_empty(tmp_path)
    resp = client.get("/api/datasets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_datasets"] == 0
    assert data["total_tasks"] == 0


def test_datasets_api_shows_summary(tmp_path: Path) -> None:
    """Dataset entry should include the summary description."""
    client = _make_client_with_dataset(tmp_path)
    resp = client.get("/api/datasets")
    assert resp.status_code == 200
    data = resp.json()
    ds = data["datasets"][0]
    assert ds["summary"] == "A test dataset"


def test_datasets_api_shows_domain(tmp_path: Path) -> None:
    """Dataset entry should include domain information."""
    client = _make_client_with_dataset(tmp_path)
    resp = client.get("/api/datasets")
    assert resp.status_code == 200
    data = resp.json()
    ds = data["datasets"][0]
    assert "electrical" in ds["domains"]


def test_datasets_api_shows_task_count(tmp_path: Path) -> None:
    """Dataset entry should include task count."""
    client = _make_client_with_dataset(tmp_path)
    resp = client.get("/api/datasets")
    assert resp.status_code == 200
    data = resp.json()
    ds = data["datasets"][0]
    assert ds["task_count"] >= 1


# ---------------------------------------------------------------------------
# API: detail endpoint
# ---------------------------------------------------------------------------


def test_dataset_detail_api_returns_json(tmp_path: Path) -> None:
    """GET /api/datasets/{name}/{version} should return JSON with expected keys."""
    client = _make_client_with_dataset(tmp_path)
    resp = client.get("/api/datasets/test-ds/1.0.0")
    assert resp.status_code == 200
    data = resp.json()
    assert "name" in data
    assert "version" in data
    assert "tasks" in data
    assert "experiment_results" in data
    assert "integrity_results" in data


def test_dataset_detail_api_correct_name(tmp_path: Path) -> None:
    """Detail endpoint should return the correct dataset name and version."""
    client = _make_client_with_dataset(tmp_path)
    resp = client.get("/api/datasets/test-ds/1.0.0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "test-ds"
    assert data["version"] == "1.0.0"


def test_dataset_detail_api_shows_task_id(tmp_path: Path) -> None:
    """Detail endpoint should include task_id values from the manifest."""
    client = _make_client_with_dataset(tmp_path)
    resp = client.get("/api/datasets/test-ds/1.0.0")
    assert resp.status_code == 200
    data = resp.json()
    task_ids = [t["task_id"] for t in data["tasks"]]
    assert any("voltage-drop" in tid for tid in task_ids)


def test_dataset_detail_api_shows_difficulty(tmp_path: Path) -> None:
    """Detail endpoint should include difficulty for each task."""
    client = _make_client_with_dataset(tmp_path)
    resp = client.get("/api/datasets/test-ds/1.0.0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tasks"][0]["difficulty"] == "medium"


def test_dataset_detail_api_shows_domain(tmp_path: Path) -> None:
    """Detail endpoint should include domain for each task."""
    client = _make_client_with_dataset(tmp_path)
    resp = client.get("/api/datasets/test-ds/1.0.0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tasks"][0]["domain"] == "electrical"


def test_dataset_detail_api_unknown_returns_404(tmp_path: Path) -> None:
    """Detail endpoint should return 404 for a non-existent dataset."""
    client = _make_client_with_dataset(tmp_path)
    resp = client.get("/api/datasets/nope/9.9.9")
    assert resp.status_code == 404


def test_dataset_detail_api_integrity_results(tmp_path: Path) -> None:
    """Integrity results should be present in the detail response."""
    client = _make_client_with_dataset(tmp_path)
    resp = client.get("/api/datasets/test-ds/1.0.0")
    assert resp.status_code == 200
    data = resp.json()
    # integrity_results should be a list of per-task integrity entries
    assert isinstance(data["integrity_results"], list)
