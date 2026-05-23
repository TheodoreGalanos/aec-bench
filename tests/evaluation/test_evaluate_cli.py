# ABOUTME: Integration tests for the aec-bench evaluate CLI command.
# ABOUTME: Uses fixture trial records in tmp_path to test all output modes.

import json
from pathlib import Path

from typer.testing import CliRunner

from aec_bench.cli.main import app
from aec_bench.ledger.writer import write_trial_record
from tests.support.trial_record_factories import make_trial_record

runner = CliRunner()


def _populate_ledger(ledger_root: Path, n_trials: int = 3) -> str:
    """Write n trial records to a ledger and return the experiment ID."""
    experiment_id = "test-experiment"
    for i in range(n_trials):
        record = make_trial_record(
            trial_id=f"trial-{i:03d}",
            experiment_id=experiment_id,
        )
        write_trial_record(ledger_root=ledger_root, record=record)
    return experiment_id


def test_evaluate_table_output(tmp_path: Path) -> None:
    """--text should print Rich tables with experiment stats."""
    exp_id = _populate_ledger(tmp_path)
    result = runner.invoke(
        app,
        ["--text", "evaluate", "--experiment", exp_id, "--ledger-root", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert exp_id in result.output
    assert "Mean Reward" in result.output or "mean" in result.output.lower()


def test_evaluate_json_output(tmp_path: Path) -> None:
    """--json should produce valid JSON envelope with expected keys."""
    exp_id = _populate_ledger(tmp_path)
    result = runner.invoke(
        app,
        ["--json", "evaluate", "--experiment", exp_id, "--ledger-root", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["command"] == "evaluate"
    assert envelope["status"] == "success"
    assert "evaluation_id" in envelope["data"]
    assert "summary" in envelope["data"]


def test_evaluate_persists_artifact(tmp_path: Path) -> None:
    """After running, _evaluations/ should have a new artifact file."""
    exp_id = _populate_ledger(tmp_path)
    runner.invoke(
        app,
        ["--text", "evaluate", "--experiment", exp_id, "--ledger-root", str(tmp_path)],
    )
    eval_dir = tmp_path / exp_id / "_evaluations"
    assert eval_dir.exists()
    artifacts = list(eval_dir.glob("*.json"))
    assert len(artifacts) == 1


def test_evaluate_with_report_flag(tmp_path: Path) -> None:
    """--report should create an HTML file with experiment content."""
    exp_id = _populate_ledger(tmp_path)
    report_path = tmp_path / "report.html"
    result = runner.invoke(
        app,
        [
            "--text",
            "evaluate",
            "--experiment",
            exp_id,
            "--ledger-root",
            str(tmp_path),
            "--report",
            str(report_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert report_path.exists()
    content = report_path.read_text()
    assert exp_id in content
    assert "<html" in content.lower()


def test_evaluate_nonexistent_experiment(tmp_path: Path) -> None:
    """Unknown experiment should error with exit code 1."""
    result = runner.invoke(
        app,
        ["--json", "evaluate", "--experiment", "nonexistent", "--ledger-root", str(tmp_path)],
    )
    assert result.exit_code == 1
    envelope = json.loads(result.output)
    assert envelope["status"] == "error"
    assert len(envelope["errors"]) > 0


def test_evaluate_empty_results(tmp_path: Path) -> None:
    """Experiment with zero matching trials should error."""
    _populate_ledger(tmp_path)
    result = runner.invoke(
        app,
        [
            "--json",
            "evaluate",
            "--experiment",
            "test-experiment",
            "--ledger-root",
            str(tmp_path),
            "--adapter",
            "nonexistent-adapter",
        ],
    )
    assert result.exit_code == 1
    envelope = json.loads(result.output)
    assert envelope["status"] == "error"
