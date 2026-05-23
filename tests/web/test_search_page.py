# ABOUTME: Tests for search across templates, datasets, trials, experiments, and workspaces.
# ABOUTME: Verifies result shape, empty states, ranking, and group caps via JSON API.

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.trial_record import AgentReference
from aec_bench.ledger.reader import _reset_cache_for_testing
from aec_bench.ledger.writer import write_trial_record
from aec_bench.web.app import create_app
from tests.support.trial_record_factories import make_trial_record


def _make_client(tmp_path: Path) -> TestClient:
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    return TestClient(create_app(ledger_root=ledger, tasks_root=tasks))


def test_search_api_returns_json(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    resp = client.get("/api/search?q=voltage")
    assert resp.status_code == 200
    data = resp.json()
    assert "query" in data
    assert "template_results" in data
    assert "dataset_results" in data
    assert "total_results" in data


def test_search_finds_templates(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    resp = client.get("/api/search?q=voltage-drop")
    assert resp.status_code == 200
    data = resp.json()
    template_names = [t["name"] for t in data["template_results"]]
    assert any("voltage-drop" in name for name in template_names)
    first = data["template_results"][0]
    assert first["name"] == "voltage-drop"
    assert first["task_id"] == f"{first['discipline']}/voltage-drop"


def test_search_empty_query(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    resp = client.get("/api/search?q=")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_results"] == 0


def test_search_no_results(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    resp = client.get("/api/search?q=xyznonexistent12345")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_results"] == 0


def test_search_results_have_discipline(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    resp = client.get("/api/search?q=voltage")
    assert resp.status_code == 200
    data = resp.json()
    for result in data["template_results"]:
        assert "discipline" in result


# ---------------------------------------------------------------------------
# Helpers for ledger-based search tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_ledger_cache() -> None:
    """Clear the module-level ledger cache before every test in this module."""
    _reset_cache_for_testing()


def _valid_evaluation(reward: float) -> EvaluationResult:
    return EvaluationResult(
        reward=reward,
        validity=ValidityCheck(
            output_parseable=True,
            schema_valid=True,
            verifier_completed=True,
        ),
    )


# ---------------------------------------------------------------------------
# Trial search tests
# ---------------------------------------------------------------------------


def test_search_returns_trial_matches_by_trial_id(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    tasks = tmp_path / "tasks"
    ledger.mkdir()
    tasks.mkdir()
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(trial_id="qv-droop__abc", experiment_id="exp-a"),
    )
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(trial_id="pf-droop__xyz", experiment_id="exp-a"),
    )

    app = create_app(ledger_root=ledger, tasks_root=tasks)
    client = TestClient(app)
    resp = client.get("/api/search?q=qv-droop")
    assert resp.status_code == 200
    data = resp.json()
    trials = data["trial_results"]
    assert len(trials) == 1
    assert trials[0]["trial_id"] == "qv-droop__abc"
    assert trials[0]["experiment_id"] == "exp-a"
    assert "model" in trials[0]
    assert "task_id" in trials[0]
    assert "reward" in trials[0]


def test_search_matches_trials_by_model_substring(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    tasks = tmp_path / "tasks"
    ledger.mkdir()
    tasks.mkdir()
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(
            trial_id="t1",
            agent=AgentReference(
                adapter="rlm",
                model="anthropic:claude-haiku-4-5",
                adapter_revision="x",
                configuration={},
            ),
        ),
    )
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(
            trial_id="t2",
            agent=AgentReference(
                adapter="rlm",
                model="anthropic:claude-sonnet-4-6",
                adapter_revision="x",
                configuration={},
            ),
        ),
    )

    app = create_app(ledger_root=ledger, tasks_root=tasks)
    client = TestClient(app)
    resp = client.get("/api/search?q=haiku")
    data = resp.json()
    assert [t["trial_id"] for t in data["trial_results"]] == ["t1"]


def test_search_caps_trial_results_at_ten(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    tasks = tmp_path / "tasks"
    ledger.mkdir()
    tasks.mkdir()
    for i in range(15):
        write_trial_record(
            ledger_root=ledger,
            record=make_trial_record(trial_id=f"matchme-{i:02d}", experiment_id="exp-a"),
        )

    app = create_app(ledger_root=ledger, tasks_root=tasks)
    client = TestClient(app)
    resp = client.get("/api/search?q=matchme")
    data = resp.json()
    assert len(data["trial_results"]) == 10


def test_search_returns_experiment_aggregates(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    tasks = tmp_path / "tasks"
    ledger.mkdir()
    tasks.mkdir()
    # Two trials in exp-alpha with rewards 1.0 and 0.5 → mean 0.75.
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(
            trial_id="t1",
            experiment_id="exp-alpha",
            evaluation=_valid_evaluation(1.0),
        ),
    )
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(
            trial_id="t2",
            experiment_id="exp-alpha",
            evaluation=_valid_evaluation(0.5),
        ),
    )
    # One trial in exp-beta that shouldn't match "alpha".
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(trial_id="t3", experiment_id="exp-beta"),
    )

    app = create_app(ledger_root=ledger, tasks_root=tasks)
    client = TestClient(app)
    resp = client.get("/api/search?q=alpha")
    data = resp.json()
    exps = data["experiment_results"]
    assert len(exps) == 1
    assert exps[0]["experiment_id"] == "exp-alpha"
    assert exps[0]["trial_count"] == 2
    assert exps[0]["mean_reward"] == pytest.approx(0.75)


def test_search_returns_empty_workspace_results_when_no_workspaces_root(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    tasks = tmp_path / "tasks"
    ledger.mkdir()
    tasks.mkdir()
    app = create_app(ledger_root=ledger, tasks_root=tasks)
    client = TestClient(app)
    resp = client.get("/api/search?q=voltage")
    data = resp.json()
    assert data["workspace_results"] == []


def test_search_empty_query_returns_empty_groups(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    tasks = tmp_path / "tasks"
    ledger.mkdir()
    tasks.mkdir()
    write_trial_record(ledger_root=ledger, record=make_trial_record())
    app = create_app(ledger_root=ledger, tasks_root=tasks)
    client = TestClient(app)
    resp = client.get("/api/search?q=")
    data = resp.json()
    assert data["trial_results"] == []
    assert data["experiment_results"] == []
    assert data["workspace_results"] == []
    assert data["total_results"] == 0
