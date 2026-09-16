# ABOUTME: Verifies Harbor model usage survives import without root-model repricing.
# ABOUTME: Covers cached input, partial costs, reported zero, and ledger retention.

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from aec_bench.contracts.trajectory import read_trajectory
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.harness.harbor_contract import HarborAgentResult
from aec_bench.harness.harbor_importing.core import import_harbor_trial
from aec_bench.ledger.reader import read_trial_record
from aec_bench.ledger.writer import write_trial_record
from aec_bench.trajectory.writer import TrajectoryWriter
from tests.harness.test_harbor_import import _write_current_entrypoint_trial


def _import_usage(tmp_path: Path, agent_result: dict[str, Any], *, current: bool = False) -> TrialRecord:
    repo_root, trial_dir = _write_current_entrypoint_trial(tmp_path)
    if not current:
        (trial_dir / "artifacts/agent/agent_result.json").unlink()
    result_path = trial_dir / "result.json"
    payload = json.loads(result_path.read_text())
    payload["agent_result"] = agent_result
    payload["config"]["agent"]["model_name"] = "gpt-4.1"
    result_path.write_text(json.dumps(payload))
    return import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)


def test_import_retains_model_usage_and_native_inclusive_cached_input(tmp_path: Path) -> None:
    record = _import_usage(
        tmp_path,
        {
            "n_input_tokens": 300,
            "n_output_tokens": 30,
            "n_cache_tokens": 70,
            "cost_usd": 9.0,
            "model_usage": {
                "provider/root": {"n_input_tokens": 100, "n_output_tokens": 10, "n_cache_tokens": 20, "cost_usd": 0.2},
                "provider/child": {"n_input_tokens": 200, "n_output_tokens": 20, "n_cache_tokens": 50, "cost_usd": 0.3},
            },
        },
    )
    assert record.cost is not None
    assert record.cost.tokens_in == 300
    assert record.cost.cache_read_tokens == 70
    assert record.cost.estimated_cost_usd == 9.0
    assert record.cost.model_usage is not None
    assert set(record.cost.model_usage) == {"provider/root", "provider/child"}
    child = record.cost.model_usage["provider/child"]
    assert (child.tokens_in, child.tokens_out, child.cache_read_tokens) == (200, 20, 50)
    assert child.reported_cost_usd == 0.3
    assert child.estimated_cost_usd is None
    ledger = tmp_path / "ledger"
    path = write_trial_record(ledger_root=ledger, record=record)
    loaded = read_trial_record(path, ledger_root=ledger)
    assert loaded.cost == record.cost


def test_import_estimates_each_model_at_its_own_rate(tmp_path: Path) -> None:
    record = _import_usage(
        tmp_path,
        {
            "model_usage": {
                "gpt-4.1": {"n_input_tokens": 1000, "n_output_tokens": 100, "n_cache_tokens": 200},
                "gpt-4.1-mini": {"n_input_tokens": 2000, "n_output_tokens": 200, "n_cache_tokens": 0},
            }
        },
    )
    assert record.cost is not None
    assert record.cost.tokens_in == 3000
    assert record.cost.tokens_out == 300
    assert record.cost.cache_read_tokens == 200
    assert record.cost.estimated_cost_usd == pytest.approx(0.0025 + 0.00112)
    assert record.cost.model_usage is not None
    assert record.cost.model_usage["gpt-4.1"].reported_cost_usd is None
    assert record.cost.model_usage["gpt-4.1-mini"].estimated_cost_usd == pytest.approx(0.00112)


@pytest.mark.parametrize(
    "missing",
    [
        None,
        {},
        {"n_input_tokens": 10},
        {
            "n_input_tokens": 10,
            "n_output_tokens": 2,
            "n_cache_tokens": 0,
        },
    ],
)
def test_unknown_child_cost_prevents_root_model_fallback(tmp_path: Path, missing: Any) -> None:
    child = {} if missing is None else missing
    record = _import_usage(
        tmp_path,
        {
            "n_input_tokens": 100,
            "n_output_tokens": 20,
            "model_usage": {"unknown-child": child},
        },
    )
    assert record.cost is not None
    assert record.cost.estimated_cost_usd is None
    assert record.cost.model_usage is not None
    assert record.cost.model_usage["unknown-child"].cost_usd is None


def test_partial_breakdown_does_not_price_unattributed_usage(tmp_path: Path) -> None:
    record = _import_usage(
        tmp_path,
        {
            "n_input_tokens": 200,
            "n_output_tokens": 20,
            "model_usage": {
                "gpt-4.1": {
                    "n_input_tokens": 100,
                    "n_output_tokens": 10,
                    "n_cache_tokens": 0,
                    "cost_usd": 0.5,
                }
            },
        },
    )
    assert record.cost is not None
    assert record.cost.tokens_in == 200
    assert record.cost.estimated_cost_usd is None
    assert record.cost.model_usage is not None
    assert record.cost.model_usage["gpt-4.1"].reported_cost_usd == 0.5


def test_reported_zero_is_preserved(tmp_path: Path) -> None:
    record = _import_usage(
        tmp_path,
        {
            "model_usage": {
                "unknown-free-model": {
                    "n_input_tokens": 0,
                    "n_output_tokens": 0,
                    "n_cache_tokens": 0,
                    "cost_usd": 0.0,
                }
            }
        },
    )
    assert record.cost is not None
    assert record.cost.tokens_in == 0
    assert record.cost.estimated_cost_usd == 0.0
    assert record.cost.model_usage is not None
    assert record.cost.model_usage["unknown-free-model"].reported_cost_usd == 0.0


@pytest.mark.parametrize("agent_result", [{}, {"model_usage": {}}, {"n_input_tokens": 100}])
def test_missing_usage_does_not_become_free_or_partially_priced(tmp_path: Path, agent_result: Any) -> None:
    record = _import_usage(tmp_path, agent_result)
    assert record.cost is not None
    assert record.cost.estimated_cost_usd is None


@pytest.mark.parametrize("value", [-1, float("inf"), float("nan")])
def test_invalid_model_cost_is_rejected(value: float) -> None:
    with pytest.raises(ValidationError):
        HarborAgentResult.model_validate({"model_usage": {"model": {"cost_usd": value}}})


def test_invalid_model_identity_and_tokens_are_rejected() -> None:
    invalid_cases: tuple[dict[str, dict[str, int]], ...] = ({" ": {}}, {"model": {"n_input_tokens": -1}})
    for model_usage in invalid_cases:
        with pytest.raises(ValidationError):
            HarborAgentResult.model_validate({"model_usage": model_usage})


def test_native_harbor_accounting_includes_child_models_once(tmp_path: Path) -> None:
    pytest.importorskip("harbor")
    from harbor.utils.trajectory_utils import compute_model_usage

    from aec_bench.harness.atif import to_atif

    source = tmp_path / "trajectory.jsonl"
    writer = TrajectoryWriter(str(source))
    writer.user("Check the design.")
    writer.new_step()
    writer.model_response(
        {
            "source": "test",
            "model_name": "gpt-4.1",
            "usage": {
                "input_tokens": 1000,
                "output_tokens": 100,
                "cache_read_tokens": 200,
            },
        }
    )
    writer.tool_call("advisor", "", tool_call_id="child-call")
    child = writer.subagent(parent_tool_call_id="child-call", agent_name="advisor", model_name="gpt-4.1-mini")
    child.user("Check the units.")
    child.new_step()
    child.model_response(
        {
            "source": "test",
            "model_name": "gpt-4.1-mini",
            "usage": {
                "input_tokens": 2000,
                "output_tokens": 200,
                "cache_read_tokens": 0,
            },
        }
    )
    child.assistant("The units match.")
    child.close()
    writer.tool_result("advisor", "The units match.", tool_call_id="child-call")
    writer.close()
    trajectory = to_atif(read_trajectory(source), agent_name="tool_loop", agent_version="1")
    model_usage = compute_model_usage(trajectory)
    assert set(model_usage) == {"gpt-4.1", "gpt-4.1-mini"}
    record = _import_usage(
        tmp_path,
        {
            "n_input_tokens": 3000,
            "n_output_tokens": 300,
            "n_cache_tokens": 200,
            "model_usage": {model: usage.model_dump() for model, usage in model_usage.items()},
        },
    )
    assert record.cost is not None
    assert record.cost is not None
    assert record.cost.tokens_in == 3000
    assert record.cost.tokens_out == 300
    assert record.cost.estimated_cost_usd == pytest.approx(0.00362)


def test_current_agent_usage_remains_aggregate_authority(tmp_path: Path) -> None:
    record = _import_usage(
        tmp_path,
        {
            "n_input_tokens": 999,
            "n_output_tokens": 999,
            "model_usage": {"child": {"n_input_tokens": 10, "n_output_tokens": 20, "cost_usd": 0.1}},
        },
        current=True,
    )
    assert record.cost is not None
    assert (record.cost.tokens_in, record.cost.tokens_out) == (101, 202)
    assert (record.cost.cache_read_tokens, record.cost.cache_write_tokens) == (33, 44)
    assert record.cost is not None
    assert record.cost.advisor_calls == 2
    assert record.cost.estimated_cost_usd is None


def test_model_estimate_requires_complete_token_usage(tmp_path: Path) -> None:
    record = _import_usage(
        tmp_path,
        {
            "model_usage": {
                "gpt-4.1": {"n_input_tokens": 100, "n_output_tokens": 10},
            }
        },
    )
    assert record.cost is not None
    assert record.cost is not None
    assert record.cost.model_usage is not None
    assert record.cost.model_usage is not None
    assert record.cost.model_usage["gpt-4.1"].cache_read_tokens is None
    assert record.cost.estimated_cost_usd is None


def test_historical_artifact_cached_input_is_normalized_once(tmp_path: Path) -> None:
    record = _import_usage(
        tmp_path,
        {
            "metadata": {
                "input_tokens": 80,
                "output_tokens": 10,
                "cache_read_input_tokens": 20,
                "cache_creation_input_tokens": 0,
            }
        },
    )
    assert record.cost is not None
    assert record.cost is not None
    assert record.cost.tokens_in == 100
    assert record.cost.cache_read_tokens == 20
    assert record.cost.estimated_cost_usd == pytest.approx(0.00025)
