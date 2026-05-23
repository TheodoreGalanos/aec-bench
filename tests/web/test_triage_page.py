# ABOUTME: Tests for the triage API endpoint with filters and trial list.
# ABOUTME: Verifies filter params, trial list data, and API response structure.

import json
from pathlib import Path

from fastapi.testclient import TestClient

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.trial_record import AgentReference, TaskReference
from aec_bench.ledger.writer import write_trial_record
from aec_bench.web.app import create_app
from tests.support.trial_record_factories import make_trial_record


def _make_client_with_trials(tmp_path: Path, n: int = 5) -> TestClient:
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    for i in range(n):
        write_trial_record(
            ledger_root=ledger,
            record=make_trial_record(experiment_id="exp-01", trial_id=f"trial-{i}"),
        )
    return TestClient(create_app(ledger_root=ledger, tasks_root=tasks))


def test_triage_api_returns_json(tmp_path: Path) -> None:
    """API endpoint returns JSON with required fields."""
    client = _make_client_with_trials(tmp_path)
    resp = client.get("/api/triage")
    assert resp.status_code == 200
    data = resp.json()
    assert "trials" in data
    assert "trial_count" in data
    assert "filters" in data
    assert "experiments" in data
    assert "models" in data


def test_triage_api_filters_by_experiment(tmp_path: Path) -> None:
    """API filters trials by experiment param and returns correct trial fields."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(experiment_id="experiment-001", trial_id="trial-a"),
    )
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(experiment_id="experiment-002", trial_id="trial-b"),
    )
    client = TestClient(create_app(ledger_root=ledger, tasks_root=tasks))
    resp = client.get("/api/triage?experiment=experiment-001")
    assert resp.status_code == 200
    data = resp.json()
    for trial in data["trials"]:
        assert trial["experiment_id"] == "experiment-001"
        assert "trial_id" in trial
        assert "reward" in trial
        assert "reward_class" in trial


def test_triage_api_with_experiment_filter(tmp_path: Path) -> None:
    """API returns trials for the filtered experiment."""
    client = _make_client_with_trials(tmp_path)
    resp = client.get("/api/triage?experiment=exp-01")
    assert resp.status_code == 200
    data = resp.json()
    assert any(t["trial_id"] == "trial-0" for t in data["trials"])


def test_triage_api_empty_results(tmp_path: Path) -> None:
    """API returns empty trials list with no records."""
    client = _make_client_with_trials(tmp_path, n=0)
    resp = client.get("/api/triage")
    assert resp.status_code == 200
    data = resp.json()
    assert data["trial_count"] == 0
    assert data["trials"] == []


def test_triage_api_reward_filter_zero(tmp_path: Path) -> None:
    """Filtering by reward=zero should only return trials with reward == 0.0."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(
            experiment_id="exp-rw",
            trial_id="t-zero",
            evaluation=EvaluationResult(
                reward=0.0,
                validity=ValidityCheck(
                    output_parseable=True,
                    schema_valid=True,
                    verifier_completed=True,
                ),
            ),
        ),
    )
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(
            experiment_id="exp-rw",
            trial_id="t-perfect",
            evaluation=EvaluationResult(
                reward=1.0,
                validity=ValidityCheck(
                    output_parseable=True,
                    schema_valid=True,
                    verifier_completed=True,
                ),
            ),
        ),
    )
    client = TestClient(create_app(ledger_root=ledger, tasks_root=tasks))
    resp = client.get("/api/triage?experiment=exp-rw&reward=zero")
    assert resp.status_code == 200
    data = resp.json()
    trial_ids = [t["trial_id"] for t in data["trials"]]
    assert "t-zero" in trial_ids
    assert "t-perfect" not in trial_ids


def test_triage_api_reward_filter_perfect(tmp_path: Path) -> None:
    """Filtering by reward=perfect should only return trials with reward == 1.0."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(
            experiment_id="exp-rw",
            trial_id="t-zero",
            evaluation=EvaluationResult(
                reward=0.0,
                validity=ValidityCheck(
                    output_parseable=True,
                    schema_valid=True,
                    verifier_completed=True,
                ),
            ),
        ),
    )
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(
            experiment_id="exp-rw",
            trial_id="t-perfect",
            evaluation=EvaluationResult(
                reward=1.0,
                validity=ValidityCheck(
                    output_parseable=True,
                    schema_valid=True,
                    verifier_completed=True,
                ),
            ),
        ),
    )
    client = TestClient(create_app(ledger_root=ledger, tasks_root=tasks))
    resp = client.get("/api/triage?experiment=exp-rw&reward=perfect")
    assert resp.status_code == 200
    data = resp.json()
    trial_ids = [t["trial_id"] for t in data["trials"]]
    assert "t-perfect" in trial_ids
    assert "t-zero" not in trial_ids


def test_triage_api_sort_reward_asc(tmp_path: Path) -> None:
    """Sorting by reward_asc should return lowest reward first."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(
            experiment_id="exp-sort",
            trial_id="t-high",
            evaluation=EvaluationResult(
                reward=1.0,
                validity=ValidityCheck(
                    output_parseable=True,
                    schema_valid=True,
                    verifier_completed=True,
                ),
            ),
        ),
    )
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(
            experiment_id="exp-sort",
            trial_id="t-low",
            evaluation=EvaluationResult(
                reward=0.0,
                validity=ValidityCheck(
                    output_parseable=True,
                    schema_valid=True,
                    verifier_completed=True,
                ),
            ),
        ),
    )
    client = TestClient(create_app(ledger_root=ledger, tasks_root=tasks))
    resp = client.get("/api/triage?experiment=exp-sort&sort=reward_asc")
    assert resp.status_code == 200
    data = resp.json()
    trial_ids = [t["trial_id"] for t in data["trials"]]
    assert trial_ids.index("t-low") < trial_ids.index("t-high")


def test_triage_api_annotated_filter(tmp_path: Path) -> None:
    """Filtering by annotated=yes should only return annotated trials."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(experiment_id="exp-ann", trial_id="t-ann"),
    )
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(experiment_id="exp-ann", trial_id="t-noann"),
    )
    ann_dir = ledger / "exp-ann" / "_annotations"
    ann_dir.mkdir(parents=True)
    (ann_dir / "t-ann.json").write_text(
        json.dumps({"verdict": "pass", "notes": "", "timestamp": "2026-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    client = TestClient(create_app(ledger_root=ledger, tasks_root=tasks))
    resp = client.get("/api/triage?experiment=exp-ann&annotated=yes")
    assert resp.status_code == 200
    data = resp.json()
    trial_ids = [t["trial_id"] for t in data["trials"]]
    assert "t-ann" in trial_ids
    assert "t-noann" not in trial_ids


def test_triage_api_annotated_filter_no(tmp_path: Path) -> None:
    """Filtering by annotated=no should only return unannotated trials."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(experiment_id="exp-ann", trial_id="t-ann"),
    )
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(experiment_id="exp-ann", trial_id="t-noann"),
    )
    ann_dir = ledger / "exp-ann" / "_annotations"
    ann_dir.mkdir(parents=True)
    (ann_dir / "t-ann.json").write_text(
        json.dumps({"verdict": "pass", "notes": "", "timestamp": "2026-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    client = TestClient(create_app(ledger_root=ledger, tasks_root=tasks))
    resp = client.get("/api/triage?experiment=exp-ann&annotated=no")
    assert resp.status_code == 200
    data = resp.json()
    trial_ids = [t["trial_id"] for t in data["trials"]]
    assert "t-noann" in trial_ids
    assert "t-ann" not in trial_ids


def test_triage_api_model_dropdown_populated(tmp_path: Path) -> None:
    """The models list should be populated with discovered models."""
    client = _make_client_with_trials(tmp_path)
    resp = client.get("/api/triage?experiment=exp-01")
    assert resp.status_code == 200
    data = resp.json()
    # Default factory model is "anthropic:claude-sonnet-4-20250514"
    assert "anthropic:claude-sonnet-4-20250514" in data["models"]


def test_triage_api_trial_count_correct(tmp_path: Path) -> None:
    """The response should show total trial count."""
    client = _make_client_with_trials(tmp_path, n=3)
    resp = client.get("/api/triage?experiment=exp-01")
    assert resp.status_code == 200
    data = resp.json()
    assert data["trial_count"] == 3


def test_triage_api_filter_by_adapter(tmp_path: Path) -> None:
    """API should filter trials by adapter name."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(
            experiment_id="exp-01",
            trial_id="t-loop",
            agent=AgentReference(adapter="tool_loop", model="sonnet", adapter_revision="r1", configuration={}),
        ),
    )
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(
            experiment_id="exp-01",
            trial_id="t-pydantic",
            agent=AgentReference(adapter="pydantic_ai", model="sonnet", adapter_revision="r1", configuration={}),
        ),
    )
    client = TestClient(create_app(ledger_root=ledger, tasks_root=tasks))
    resp = client.get("/api/triage?adapter=tool_loop")
    assert resp.status_code == 200
    data = resp.json()
    trial_ids = [t["trial_id"] for t in data["trials"]]
    assert "t-loop" in trial_ids
    assert "t-pydantic" not in trial_ids


def test_triage_api_filter_by_task_type(tmp_path: Path) -> None:
    """API should filter trials by task type prefix."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(
            experiment_id="exp-01",
            trial_id="t-vd",
            task=TaskReference(task_id="electrical/voltage-drop/inst-0", task_revision="r1"),
        ),
    )
    write_trial_record(
        ledger_root=ledger,
        record=make_trial_record(
            experiment_id="exp-01",
            trial_id="t-cs",
            task=TaskReference(task_id="electrical/cable-sizing/inst-0", task_revision="r1"),
        ),
    )
    client = TestClient(create_app(ledger_root=ledger, tasks_root=tasks))
    resp = client.get("/api/triage?task_type=voltage-drop")
    assert resp.status_code == 200
    data = resp.json()
    trial_ids = [t["trial_id"] for t in data["trials"]]
    assert "t-vd" in trial_ids
    assert "t-cs" not in trial_ids
