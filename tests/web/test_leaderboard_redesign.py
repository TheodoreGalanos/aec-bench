# ABOUTME: Tests for the leaderboard API endpoint with single-dataset and scorecard views.
# ABOUTME: Verifies dataset selector, model ranking, cross-dataset comparison, and URL params.

from pathlib import Path

from fastapi.testclient import TestClient

from aec_bench.contracts.dataset import (
    DatasetDescription,
    DatasetManifest,
    DatasetSource,
    DatasetTaskEntry,
)
from aec_bench.dataset.storage import write_manifest
from aec_bench.ledger.writer import write_trial_record
from aec_bench.web.app import create_app
from tests.support.trial_record_factories import make_trial_record


def _make_manifest(
    name: str = "electrical-only",
    version: str = "1.0.0",
    *,
    summary: str = "Electrical benchmark suite",
    domains: list[str] | None = None,
    difficulty_distribution: dict[str, int] | None = None,
    task_count: int = 2,
    tasks: list[DatasetTaskEntry] | None = None,
) -> DatasetManifest:
    """Build a minimal DatasetManifest for testing."""
    if tasks is None:
        tasks = [
            DatasetTaskEntry(
                task_id=f"{name}/task-{i}",
                task_path=f"tasks/{name}/task-{i}",
                content_hash=f"hash-{name}-{i}",
                domain=name.split("-")[0],
                difficulty="medium",
                tags=[],
            )
            for i in range(1, task_count + 1)
        ]
    return DatasetManifest(
        name=name,
        version=version,
        content_hash=f"sha256-{name}-{version}",
        description=DatasetDescription(
            summary=summary,
            domains=domains or ["electrical"],
            difficulty_distribution=difficulty_distribution or {"medium": task_count},
            task_count=task_count,
        ),
        created_at="2026-03-01T00:00:00Z",
        tasks=tasks,
        source=DatasetSource(method="manual"),
    )


def _setup_env(
    tmp_path: Path,
    *,
    manifests: list[DatasetManifest] | None = None,
    trial_kwargs_list: list[dict] | None = None,
) -> TestClient:
    """Create a test client with optional datasets and trial records."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    datasets = tmp_path / "datasets"
    datasets.mkdir()

    if manifests:
        for manifest in manifests:
            write_manifest(datasets, manifest)

    if trial_kwargs_list:
        for kwargs in trial_kwargs_list:
            write_trial_record(
                ledger_root=ledger,
                record=make_trial_record(**kwargs),
            )

    return TestClient(
        create_app(
            ledger_root=ledger,
            tasks_root=tasks,
            datasets_root=datasets,
        )
    )


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


def test_leaderboard_api_returns_json(tmp_path: Path) -> None:
    """GET /api/leaderboard should return a JSON response with expected keys."""
    client = _setup_env(tmp_path, manifests=[_make_manifest()])
    resp = client.get("/api/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "model_rows" in data
    assert "is_scorecard" in data
    assert "scorecard_rows" in data
    assert "datasets" in data
    assert "selected_dataset" in data


def test_leaderboard_api_datasets_list(tmp_path: Path) -> None:
    """datasets list in API response should include available manifests."""
    m = _make_manifest(name="electrical-only")
    client = _setup_env(tmp_path, manifests=[m])
    resp = client.get("/api/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["datasets"]) == 1
    assert data["datasets"][0]["name"] == "electrical-only"


def test_leaderboard_api_empty_ledger(tmp_path: Path) -> None:
    """API should return empty model_rows when no trials match the dataset."""
    client = _setup_env(tmp_path, manifests=[_make_manifest()])
    resp = client.get("/api/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["model_rows"], list)


def test_leaderboard_api_with_first_dataset(tmp_path: Path) -> None:
    """API returns selected_dataset matching the first available dataset."""
    client = _setup_env(tmp_path, manifests=[_make_manifest()])
    resp = client.get("/api/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["selected_dataset"] is not None
    assert "electrical-only" in data["selected_dataset"]


def test_leaderboard_api_multiple_datasets(tmp_path: Path) -> None:
    """API datasets list includes all available manifests."""
    client = _setup_env(
        tmp_path,
        manifests=[_make_manifest(), _make_manifest(name="civil-basic")],
    )
    resp = client.get("/api/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["datasets"]) == 2
    dataset_names = [d["name"] for d in data["datasets"]]
    assert "electrical-only" in dataset_names
    assert "civil-basic" in dataset_names


def test_leaderboard_api_dataset_url_param(tmp_path: Path) -> None:
    """?dataset= param should select the matching dataset."""
    client = _setup_env(
        tmp_path,
        manifests=[
            _make_manifest(),
            _make_manifest(name="civil-basic", summary="Civil benchmark suite"),
        ],
    )
    resp = client.get("/api/leaderboard?dataset=civil-basic@1.0.0")
    assert resp.status_code == 200
    data = resp.json()
    assert "civil-basic" in data["selected_dataset"]


def test_leaderboard_api_model_ranking(tmp_path: Path) -> None:
    """Models should be ranked by mean reward descending in model_rows."""
    manifest = _make_manifest()
    ds_id = f"{manifest.name}@{manifest.version}"
    client = _setup_env(
        tmp_path,
        manifests=[manifest],
        trial_kwargs_list=[
            {
                "trial_id": "t1",
                "experiment_id": "exp-01",
                "dataset_id": ds_id,
                "agent": {
                    "adapter": "tool_loop",
                    "model": "anthropic:claude-sonnet-4-20250514",
                    "adapter_revision": "rev1",
                    "configuration": {},
                },
                "evaluation": {
                    "reward": 0.8,
                    "validity": {
                        "output_parseable": True,
                        "schema_valid": True,
                        "verifier_completed": True,
                    },
                },
            },
            {
                "trial_id": "t2",
                "experiment_id": "exp-01",
                "dataset_id": ds_id,
                "agent": {
                    "adapter": "pydantic_ai",
                    "model": "openai:gpt-4.1-mini",
                    "adapter_revision": "rev2",
                    "configuration": {},
                },
                "evaluation": {
                    "reward": 1.0,
                    "validity": {
                        "output_parseable": True,
                        "schema_valid": True,
                        "verifier_completed": True,
                    },
                },
            },
        ],
    )
    resp = client.get("/api/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    rows = data["model_rows"]
    assert len(rows) >= 2
    # First row should be the higher reward model
    assert rows[0]["mean_reward"] >= rows[1]["mean_reward"]


def test_leaderboard_api_no_datasets(tmp_path: Path) -> None:
    """API handles empty datasets gracefully."""
    client = _setup_env(tmp_path)
    resp = client.get("/api/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["datasets"] == []
    assert data["selected_dataset"] is None


def test_leaderboard_api_scorecard_view(tmp_path: Path) -> None:
    """?view=scorecard should set is_scorecard=True in the response."""
    client = _setup_env(
        tmp_path,
        manifests=[_make_manifest(), _make_manifest(name="civil-basic")],
    )
    resp = client.get("/api/leaderboard?view=scorecard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_scorecard"] is True


def test_leaderboard_api_scorecard_includes_datasets(tmp_path: Path) -> None:
    """Scorecard view should include all datasets in the response."""
    client = _setup_env(
        tmp_path,
        manifests=[
            _make_manifest(name="electrical-only"),
            _make_manifest(name="civil-basic"),
        ],
    )
    resp = client.get("/api/leaderboard?view=scorecard")
    assert resp.status_code == 200
    data = resp.json()
    dataset_names = [d["name"] for d in data["datasets"]]
    assert "electrical-only" in dataset_names
    assert "civil-basic" in dataset_names


def test_leaderboard_api_dataset_with_no_trials(tmp_path: Path) -> None:
    """Dataset exists but no trials — model_rows should be empty."""
    client = _setup_env(tmp_path, manifests=[_make_manifest()])
    resp = client.get("/api/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["model_rows"] == []
