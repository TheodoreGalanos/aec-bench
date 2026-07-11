# ABOUTME: CLI tests for composite task-world template examples.
# ABOUTME: Verifies list, materialize-example, and verify-example commands use JSON envelopes.

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from aec_bench.cli.main import app
from aec_bench.meta_harness.evidence_lifecycle import run_evidence_lifecycle

runner = CliRunner()


def test_task_composite_template_list_command_emits_template_catalogue() -> None:
    result = runner.invoke(app, ["--json", "task", "composite-template", "list"])

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["command"] == "task composite-template list"
    assert envelope["data"]["count"] == 27
    assert envelope["data"]["templates"][0]["template_id"] == "stormwater-drainage-package"
    assert envelope["data"]["templates"][-1]["template_id"] == "drainage-model-evidence-lifecycle-review"


def test_task_composite_template_materialize_and_verify_commands(tmp_path: Path) -> None:
    output_dir = tmp_path / "example"

    materialized = runner.invoke(
        app,
        [
            "--json",
            "task",
            "composite-template",
            "materialize-example",
            "pump-station-duty-package",
            "--output",
            str(output_dir),
        ],
    )
    verified = runner.invoke(
        app,
        [
            "--json",
            "task",
            "composite-template",
            "verify-example",
            str(output_dir),
        ],
    )

    assert materialized.exit_code == 0, materialized.output
    assert verified.exit_code == 0, verified.output
    materialized_envelope = json.loads(materialized.output)
    verified_envelope = json.loads(verified.output)
    assert materialized_envelope["data"]["package_dir"] == str(output_dir)
    assert materialized_envelope["data"]["template_id"] == "pump-station-duty-package"
    assert verified_envelope["data"]["overall"] == "pass"
    assert verified_envelope["data"]["template_id"] == "pump-station-duty-package"


def test_task_composite_template_lifecycle_commands_materialize_and_verify(tmp_path: Path) -> None:
    package = tmp_path / "lifecycle-package"
    run_dir = tmp_path / "lifecycle-run"

    materialized = runner.invoke(
        app,
        [
            "--json",
            "task",
            "composite-template",
            "materialize-lifecycle",
            "drainage-model-evidence-lifecycle-review",
            "--output",
            str(package),
        ],
    )
    assert materialized.exit_code == 0, materialized.output
    gold = json.loads((package / "hidden" / "gold-submissions.json").read_text(encoding="utf-8"))

    def resolve(context: dict) -> dict:
        submission = Path(context["submission_path"])
        submission.parent.mkdir(parents=True, exist_ok=True)
        submission.write_text(json.dumps(gold[context["checkpoint_id"]]), encoding="utf-8")
        return {"status": "completed"}

    run_evidence_lifecycle(package, run_dir, episode_resolver=resolve)
    verified = runner.invoke(
        app,
        [
            "--json",
            "task",
            "composite-template",
            "verify-lifecycle",
            str(package),
            "--run-dir",
            str(run_dir),
        ],
    )

    assert verified.exit_code == 0, verified.output
    assert json.loads(materialized.output)["data"]["checkpoint_count"] == 3
    assert json.loads(verified.output)["data"]["overall"] == "pass"
    assert json.loads(verified.output)["data"]["reward"] == 1.0
