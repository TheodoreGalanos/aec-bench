# ABOUTME: Tests persisted run plan, inspection, diff, and reconciliation CLI views.
# ABOUTME: Proves reviewer commands use stored contracts without starting execution.

import json
from pathlib import Path

from typer.testing import CliRunner

from aec_bench.cli.main import app
from aec_bench.contracts.identity import EntityIdentity, EntityKey, EntityKind, new_entity_id
from tests.harness.test_persisted_artifact_plan import _ready_store, _spec, _task

runner = CliRunner()


def _write_identity_task(tasks_root: Path) -> str:
    task_id = "electrical/voltage-drop/demo-instance"
    task_dir = tasks_root / task_id
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "instruction.md").write_text(
        "Calculate the answer and write it to /workspace/output.jsonl.\n",
        encoding="utf-8",
    )
    (task_dir / "task.toml").write_text(
        f'''[identity]\nid = "{new_entity_id(EntityKind.TASK)}"\nkey = "{task_id}"\nversion = 1\n\n'''
        '[metadata]\nvisibility = "public"\nlifecycle = "active"\n\n[agent]\ntimeout_sec = 60\n',
        encoding="utf-8",
    )
    (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    return task_id


def test_run_inspect_resolves_human_readable_key(tmp_path: Path) -> None:
    task = _task(tmp_path)
    spec = _spec(task)
    store, plan = _ready_store(tmp_path, spec)

    result = runner.invoke(
        app, ["--json", "run", "inspect", str(spec.run_identity.key), "--store-root", str(store.root)]
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["data"]["run_identity"]["id"] == str(spec.run_identity.id)
    assert payload["data"]["plan_trial_count"] == len(plan.trials)
    assert payload["data"]["plan_readiness"] == "ready"
    assert payload["data"]["accounting"] is None


def test_run_plan_resolves_uuid_and_returns_persisted_bytes(tmp_path: Path) -> None:
    task = _task(tmp_path)
    spec = _spec(task)
    store, plan = _ready_store(tmp_path, spec)

    result = runner.invoke(app, ["--json", "run", "plan", str(spec.run_identity.id), "--store-root", str(store.root)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["data"]["plan"]["plan_identity"]["id"] == str(plan.plan_identity.id)
    assert payload["data"]["plan"]["state"] == "ready"


def test_run_plan_config_persists_resolved_spec_and_ready_plan(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_id = _write_identity_task(tasks_root)
    config = tmp_path / "experiment.yaml"
    config.write_text(
        f"""experiment_id: cli-plan-test
name: CLI plan test
tasks:
  include_patterns: [{task_id}]
agents:
  - name: baseline
    adapter: direct
    model: test-model
compute:
  backend: local
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--json",
            "run",
            "plan",
            "--config",
            str(config),
            "--tasks-root",
            str(tasks_root),
            "--store-root",
            str(tmp_path / "runs"),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["data"]["run"]["run_identity"]["key"].startswith("cli-plan-test-run-")
    assert payload["data"]["state"]["state"] == "ready"
    assert payload["data"]["plan"]["state"] == "ready"
    assert payload["data"]["plan"]["summary"]["total_trials"] == 1
    assert not (tmp_path / "jobs").exists()


def test_run_diff_reports_semantic_field_changes(tmp_path: Path) -> None:
    first_task = _task(tmp_path, name="one")
    first_spec = _spec(first_task)
    store, _ = _ready_store(tmp_path, first_spec)
    second_task = _task(tmp_path, name="two")
    second_spec = _spec(second_task).model_copy(
        update={
            "run_identity": EntityIdentity(
                id=new_entity_id(EntityKind.RUN),
                key=EntityKey("artifact-plan-run-two"),
                version=1,
            ),
            "run_name": "Changed run name",
        }
    )
    _ready_store(tmp_path, second_spec)

    result = runner.invoke(
        app,
        [
            "--json",
            "run",
            "diff",
            str(first_spec.run_identity.key),
            str(second_spec.run_identity.key),
            "--store-root",
            str(store.root),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    paths = {change["path"] for change in payload["data"]["changes"]}
    assert "condition.run_name" in paths
    assert all("identity.id" not in path for path in paths)


def test_run_diff_reports_unchanged_condition_fields_without_occurrence_noise(tmp_path: Path) -> None:
    task = _task(tmp_path)
    first_spec = _spec(task)
    store, _ = _ready_store(tmp_path, first_spec)
    second_spec = first_spec.model_copy(
        update={
            "run_identity": EntityIdentity(
                id=new_entity_id(EntityKind.RUN),
                key=EntityKey("artifact-plan-run-second"),
                version=1,
            )
        }
    )
    _ready_store(tmp_path, second_spec)

    result = runner.invoke(
        app,
        [
            "--json",
            "run",
            "diff",
            str(first_spec.run_identity.key),
            str(second_spec.run_identity.key),
            "--store-root",
            str(store.root),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["data"]["changes"] == []
    assert "condition.repetitions" in payload["data"]["unchanged"]


def test_run_reconcile_requires_explicit_observation_file(tmp_path: Path) -> None:
    task = _task(tmp_path)
    spec = _spec(task)
    store, plan = _ready_store(tmp_path, spec)
    observations = tmp_path / "observations.json"
    observations.write_text("[]", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--json",
            "run",
            "reconcile",
            str(spec.run_identity.key),
            "--observations",
            str(observations),
            "--store-root",
            str(store.root),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["data"]["status"] == "incomplete"
    assert payload["data"]["counts"]["planned"] == len(plan.trials)
    assert payload["data"]["counts"]["missing"] == len(plan.trials)
    assert payload["data"]["accepted_record_count"] == 0


def test_run_reconcile_does_not_invent_observations(tmp_path: Path) -> None:
    task = _task(tmp_path)
    spec = _spec(task)
    store, _ = _ready_store(tmp_path, spec)

    result = runner.invoke(
        app, ["--json", "run", "reconcile", str(spec.run_identity.key), "--store-root", str(store.root)]
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert "requires --observations" in payload["errors"][0]
