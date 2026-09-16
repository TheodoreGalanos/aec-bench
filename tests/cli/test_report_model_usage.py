# ABOUTME: Tests model usage reporting through the real ledger and CLI summary.
# ABOUTME: Checks JSON fields, cost sources, and readable unknown-cost output.

import json
from pathlib import Path

from typer.testing import CliRunner

from aec_bench.cli.main import app
from aec_bench.ledger.writer import write_trial_record
from tests.support.trial_record_factories import make_trial_record


def test_report_summary_reads_model_usage_from_ledger(tmp_path: Path) -> None:
    record = make_trial_record(
        cost={
            "model_usage": {
                "root": {"tokens_in": 100, "tokens_out": 20, "cache_read_tokens": 10, "reported_cost_usd": 0.5},
                "child": {"tokens_in": 50},
            }
        }
    )
    write_trial_record(ledger_root=tmp_path, record=record)
    runner = CliRunner()
    command = ["report", "summary", "--ledger-root", str(tmp_path)]
    result = runner.invoke(app, ["--json", *command])
    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)["data"]
    assert summary["by_model_usage"]["root"]["total_cost_usd"] == 0.5
    assert summary["by_model_usage"]["root"]["n_reported_cost"] == 1
    assert summary["by_model_usage"]["child"]["total_cost_usd"] is None
    assert summary["n_trials_without_model_usage"] == 0
    human = runner.invoke(app, ["--text", *command])
    assert human.exit_code == 0, human.output
    assert "Model Usage" in human.output
    assert "Unknown" in human.output
    assert "Trials without model usage: 0" in human.output
