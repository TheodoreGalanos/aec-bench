# ABOUTME: Tests for the /api/analyze pivot endpoint across dims, metrics, and filters.
# ABOUTME: Uses an in-memory ledger fixture; exercises every rows/cols/metric combination.

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.trial_record import AgentReference, TaskReference
from aec_bench.ledger.reader import _reset_cache_for_testing
from aec_bench.ledger.writer import write_trial_record
from aec_bench.web.app import create_app
from tests.support.trial_record_factories import make_trial_record


@pytest.fixture(autouse=True)
def _reset_ledger_cache() -> None:
    _reset_cache_for_testing()


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    ledger = tmp_path / "ledger"
    tasks = tmp_path / "tasks"
    ledger.mkdir()
    tasks.mkdir()
    app = create_app(ledger_root=ledger, tasks_root=tasks)
    return TestClient(app)


def _valid_evaluation(reward: float) -> EvaluationResult:
    return EvaluationResult(
        reward=reward,
        validity=ValidityCheck(
            output_parseable=True,
            schema_valid=True,
            verifier_completed=True,
        ),
    )


def _write(ledger_root: Path, **overrides) -> None:
    record = make_trial_record(**overrides)
    write_trial_record(ledger_root=ledger_root, record=record)


def test_analyze_adapter_by_task_type_mean_reward(client: TestClient, tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    _write(
        ledger,
        trial_id="t1",
        agent=AgentReference(
            adapter="rlm", model="anthropic:claude-sonnet-4-20250514", adapter_revision="x", configuration={}
        ),
        task=TaskReference(task_id="electrical/voltage-drop/easy", task_revision="x"),
        evaluation=_valid_evaluation(1.0),
    )
    _write(
        ledger,
        trial_id="t2",
        agent=AgentReference(
            adapter="rlm", model="anthropic:claude-sonnet-4-20250514", adapter_revision="x", configuration={}
        ),
        task=TaskReference(task_id="electrical/string-sizing/easy", task_revision="x"),
        evaluation=_valid_evaluation(0.5),
    )
    _write(
        ledger,
        trial_id="t3",
        agent=AgentReference(
            adapter="tool_loop", model="anthropic:claude-sonnet-4-20250514", adapter_revision="x", configuration={}
        ),
        task=TaskReference(task_id="electrical/voltage-drop/easy", task_revision="x"),
        evaluation=_valid_evaluation(0.0),
    )

    resp = client.get("/api/analyze?rows=adapter&cols=task_type&metrics=mean_reward")
    assert resp.status_code == 200
    data = resp.json()
    assert data["rows_dim"] == "adapter"
    assert data["cols_dim"] == "task_type"
    assert data["metrics"] == ["mean_reward"]
    assert sorted(data["row_labels"]) == ["rlm", "tool_loop"]
    assert sorted(data["col_labels"]) == ["string-sizing", "voltage-drop"]
    # rlm × voltage-drop = 1.0
    assert data["cells"]["rlm|voltage-drop"]["mean_reward"] == pytest.approx(1.0)
    assert data["cells"]["rlm|voltage-drop"]["count"] == 1
    # tool_loop × voltage-drop = 0.0
    assert data["cells"]["tool_loop|voltage-drop"]["mean_reward"] == pytest.approx(0.0)
    # Row total rlm = mean(1.0, 0.5) = 0.75
    assert data["row_totals"]["rlm"]["mean_reward"] == pytest.approx(0.75)
    assert data["row_totals"]["rlm"]["count"] == 2
    # Grand total = mean(1.0, 0.5, 0.0) = 0.5
    assert data["grand_total"]["mean_reward"] == pytest.approx(0.5)
    assert data["grand_total"]["count"] == 3


def test_analyze_rows_only_multi_metric(client: TestClient, tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    for i, reward in enumerate([1.0, 0.5, 0.0]):
        _write(
            ledger,
            trial_id=f"t{i}",
            agent=AgentReference(
                adapter="rlm", model="anthropic:claude-sonnet-4-20250514", adapter_revision="x", configuration={}
            ),
            task=TaskReference(task_id="electrical/voltage-drop/easy", task_revision="x"),
            evaluation=_valid_evaluation(reward),
        )

    resp = client.get("/api/analyze?rows=model&cols=none&metrics=mean_reward,perfect_pct,zero_pct,count")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cols_dim"] == "none"
    assert data["col_labels"] == []
    assert data["metrics"] == ["mean_reward", "perfect_pct", "zero_pct", "count"]
    rt = data["row_totals"]["anthropic:claude-sonnet-4-20250514"]
    assert rt["mean_reward"] == pytest.approx(0.5)
    assert rt["perfect_pct"] == pytest.approx(1 / 3)
    assert rt["zero_pct"] == pytest.approx(1 / 3)
    assert rt["count"] == 3


def test_analyze_delta_column_mean_reward(client: TestClient, tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    # task_type voltage-drop has two models; haiku performs worse than sonnet.
    _write(
        ledger,
        trial_id="a1",
        agent=AgentReference(adapter="rlm", model="claude-haiku", adapter_revision="x", configuration={}),
        task=TaskReference(task_id="electrical/voltage-drop/easy", task_revision="x"),
        evaluation=_valid_evaluation(0.4),
    )
    _write(
        ledger,
        trial_id="a2",
        agent=AgentReference(adapter="rlm", model="claude-sonnet", adapter_revision="x", configuration={}),
        task=TaskReference(task_id="electrical/voltage-drop/easy", task_revision="x"),
        evaluation=_valid_evaluation(0.9),
    )

    resp = client.get(
        "/api/analyze?rows=task_type&cols=model&metrics=mean_reward&delta=true",
    )
    data = resp.json()
    assert data["delta_enabled"] is True
    # col_labels are alphabetically sorted; haiku first, sonnet last.
    assert data["col_labels"] == ["claude-haiku", "claude-sonnet"]
    # delta = last_col - first_col = 0.9 - 0.4 = 0.5
    assert data["row_deltas"]["voltage-drop"] == pytest.approx(0.5)


def test_analyze_rejects_same_dim_for_rows_and_cols(client: TestClient) -> None:
    resp = client.get("/api/analyze?rows=adapter&cols=adapter")
    assert resp.status_code == 400
    assert "must differ" in resp.json()["detail"]


def test_analyze_rejects_multi_metric_when_cols_is_set(client: TestClient) -> None:
    resp = client.get(
        "/api/analyze?rows=adapter&cols=task_type&metrics=mean_reward,perfect_pct",
    )
    assert resp.status_code == 400
    assert "Multiple metrics" in resp.json()["detail"]


def test_analyze_respects_experiment_filter(client: TestClient, tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    _write(ledger, trial_id="e1", experiment_id="exp-a", evaluation=_valid_evaluation(1.0))
    _write(ledger, trial_id="e2", experiment_id="exp-b", evaluation=_valid_evaluation(0.0))

    resp = client.get("/api/analyze?rows=adapter&cols=task_type&metrics=mean_reward&experiment=exp-a")
    data = resp.json()
    assert data["grand_total"]["count"] == 1
    assert data["grand_total"]["mean_reward"] == pytest.approx(1.0)


def test_analyze_cost_metric_reads_record_cost(client: TestClient, tmp_path: Path) -> None:
    from aec_bench.contracts.trial_record import CostRecord

    ledger = tmp_path / "ledger"
    # Two trials with cost set, one without.
    _write(ledger, trial_id="c1", cost=CostRecord(estimated_cost_usd=0.10))
    _write(ledger, trial_id="c2", cost=CostRecord(estimated_cost_usd=0.30))
    _write(ledger, trial_id="c3")  # no cost override → factory default (cost=None)

    resp = client.get("/api/analyze?rows=adapter&cols=none&metrics=cost,count")
    assert resp.status_code == 200
    data = resp.json()
    row = data["row_totals"][next(iter(data["row_totals"]))]
    # Only the two explicit-cost trials contribute; the third has cost=None and is skipped.
    # Mean of 0.10 and 0.30 = 0.20.
    assert row["cost"] == pytest.approx(0.20)
    assert row["count"] == 3
