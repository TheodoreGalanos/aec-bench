# ABOUTME: Tests for the AEC-Bench meta-harness CLI command group.
# ABOUTME: Verifies the command delegates to the library runtime and emits JSON envelopes.

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from aec_bench.cli.main import app

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[2]


def test_meta_harness_process_command_runs_supplied_artifacts(tmp_path: Path) -> None:
    brief = tmp_path / "brief.json"
    world = tmp_path / "world.json"
    task_run = tmp_path / "task-run.json"
    operation_plan = tmp_path / "operation-plan.json"
    proposal = tmp_path / "proposal.json"
    decision = tmp_path / "decision.json"
    output_dir = tmp_path / "process"
    ledger = tmp_path / "ledger.jsonl"
    _write_json(brief, _brief())
    _write_json(world, _world())
    _write_json(task_run, _task_run())
    _write_json(operation_plan, _operation_plan())
    _write_json(proposal, _proposal())
    _write_json(decision, _world_schema_decision())

    result = runner.invoke(
        app,
        [
            "--json",
            "meta-harness",
            "process",
            "Create a diagnostic task.",
            "--process-id",
            "process.demo",
            "--brief",
            str(brief),
            "--world",
            str(world),
            "--task-run",
            str(task_run),
            "--operation-plan",
            str(operation_plan),
            "--governance-proposal",
            str(proposal),
            "--governance-decision",
            str(decision),
            "--output-dir",
            str(output_dir),
            "--ledger",
            str(ledger),
        ],
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["command"] == "meta-harness process"
    assert envelope["data"]["status"] == "accepted_for_world_generation"
    assert envelope["data"]["logic_evaluation"]["overall_status"] == "certified"
    assert (output_dir / "harbor_task" / "result.json").exists()
    assert ledger.exists()


def test_meta_harness_logic_and_review_commands_emit_contract_packets(tmp_path: Path) -> None:
    world = tmp_path / "world.json"
    task_run = tmp_path / "task-run.json"
    review = tmp_path / "review.json"
    _write_json(world, _world())
    _write_json(task_run, _task_run())
    _write_json(review, _review_response())

    logic_result = runner.invoke(
        app,
        ["--json", "meta-harness", "logic-evaluate", "--world", str(world), "--run", str(task_run)],
    )
    review_request = runner.invoke(
        app,
        ["--json", "meta-harness", "review", "--world", str(world), "--run", str(task_run)],
    )
    reviewed = runner.invoke(
        app,
        [
            "--json",
            "meta-harness",
            "review",
            "--world",
            str(world),
            "--run",
            str(task_run),
            "--review-response",
            str(review),
        ],
    )

    assert logic_result.exit_code == 0, logic_result.output
    assert review_request.exit_code == 0, review_request.output
    assert reviewed.exit_code == 0, reviewed.output
    assert json.loads(logic_result.output)["data"]["overall_status"] == "certified"
    request_data = json.loads(review_request.output)["data"]
    assert request_data["payload"]["deterministic_evaluation"]["overall_status"] == "certified"
    assert "response_schema" in request_data
    assert json.loads(reviewed.output)["data"]["evaluation"]["overall_status"] == "certified"


def test_meta_harness_operation_commands_apply_and_materialize(tmp_path: Path) -> None:
    brief = tmp_path / "brief.json"
    world = tmp_path / "world.json"
    operation = tmp_path / "operation.json"
    operation_plan = tmp_path / "operation-plan.json"
    output_dir = tmp_path / "harbor-task"
    _write_json(brief, _brief())
    _write_json(world, _world())
    _write_json(operation, {"operation": "projection", "axis": "artifact_evidence"})
    _write_json(operation_plan, _operation_plan())

    applied = runner.invoke(
        app,
        [
            "--json",
            "meta-harness",
            "operation-apply",
            "--world",
            str(world),
            "--operation",
            str(operation),
        ],
    )
    orchestrated = runner.invoke(
        app,
        [
            "--json",
            "meta-harness",
            "operation-orchestrate",
            "--brief",
            str(brief),
            "--world",
            str(world),
            "--plan",
            str(operation_plan),
        ],
    )
    materialized = runner.invoke(
        app,
        [
            "--json",
            "meta-harness",
            "harbor-task",
            "--brief",
            str(brief),
            "--world",
            str(world),
            "--plan",
            str(operation_plan),
            "--output",
            str(output_dir),
        ],
    )

    assert applied.exit_code == 0, applied.output
    assert orchestrated.exit_code == 0, orchestrated.output
    assert materialized.exit_code == 0, materialized.output
    assert json.loads(applied.output)["data"]["status"] == "applied"
    assert json.loads(orchestrated.output)["data"]["status"] == "complete"
    assert json.loads(materialized.output)["data"]["status"] == "complete"
    assert (output_dir / "agent" / "input.json").exists()


def test_meta_harness_world_process_commands_emit_intake_generation_and_governance(tmp_path: Path) -> None:
    brief = tmp_path / "brief.json"
    world = tmp_path / "world.json"
    proposal = tmp_path / "proposal.json"
    decision = tmp_path / "decision.json"
    _write_json(brief, _brief())
    _write_json(world, _world())
    _write_json(proposal, _proposal())
    _write_json(decision, _world_schema_decision())

    intake = runner.invoke(
        app,
        ["--json", "meta-harness", "intake", "--task-text", "Create a diagnostic task."],
    )
    world_request = runner.invoke(
        app,
        ["--json", "meta-harness", "world-request", "--brief", str(brief), "--source-world", str(world)],
    )
    governed = runner.invoke(
        app,
        [
            "--json",
            "meta-harness",
            "govern",
            "--brief",
            str(brief),
            "--source-world",
            str(world),
            "--proposal",
            str(proposal),
            "--decision",
            str(decision),
        ],
    )

    assert intake.exit_code == 0, intake.output
    assert world_request.exit_code == 0, world_request.output
    assert governed.exit_code == 0, governed.output
    assert json.loads(intake.output)["data"]["status"] == "awaiting_problem_space_brief"
    assert json.loads(world_request.output)["data"]["status"] == "awaiting_world_generation"
    assert json.loads(governed.output)["data"]["status"] == "accepted_for_world_generation"


def test_meta_harness_model_plan_commands_share_endpoint_contract(tmp_path: Path) -> None:
    brief = tmp_path / "brief.json"
    world = tmp_path / "world.json"
    task_run = tmp_path / "task-run.json"
    _write_json(brief, _brief())
    _write_json(world, _world())
    _write_json(task_run, _task_run())

    commands = [
        [
            "review-models",
            "--world",
            str(world),
            "--run",
            str(task_run),
            "--model",
            "demo-model",
            "--emit-run-plan",
        ],
        [
            "intake-models",
            "--task-text",
            "Create a diagnostic task.",
            "--model",
            "demo-model",
            "--emit-run-plan",
        ],
        [
            "world-models",
            "--brief",
            str(brief),
            "--model",
            "demo-model",
            "--emit-run-plan",
        ],
        [
            "operation-models",
            "--brief",
            str(brief),
            "--world",
            str(world),
            "--model",
            "demo-model",
            "--emit-run-plan",
        ],
    ]

    for command in commands:
        result = runner.invoke(app, ["--json", "meta-harness", *command])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)["data"]
        assert data["models"][0]["model"] == "demo-model"


def test_meta_harness_autonomous_command_runs_bounded_supervision(tmp_path: Path) -> None:
    brief = tmp_path / "brief.json"
    world = tmp_path / "world.json"
    output_dir = tmp_path / "autonomous"
    _write_json(brief, _brief())
    _write_json(world, _world())

    result = runner.invoke(
        app,
        [
            "--json",
            "meta-harness",
            "autonomous",
            "--task-text",
            "Create a diagnostic task.",
            "--brief",
            str(brief),
            "--world",
            str(world),
            "--output",
            str(output_dir),
            "--max-iterations",
            "1",
        ],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)["data"]
    assert data["config"]["max_iterations"] == 1
    assert data["status"] == "awaiting_task_run"
    assert (output_dir / "process_ledger.jsonl").exists()


def test_meta_harness_recipe_command_materializes_scriptable_workflow(tmp_path: Path) -> None:
    baseline_world = tmp_path / "baseline-world.json"
    candidate_world = tmp_path / "candidate-world.json"
    baseline_run = tmp_path / "baseline-run.json"
    candidate_run = tmp_path / "candidate-run.json"
    output_dir = tmp_path / "recipe"
    _write_json(baseline_world, _world())
    _write_json(candidate_world, _world())
    _write_json(baseline_run, _task_run())
    _write_json(candidate_run, _task_run())

    result = runner.invoke(
        app,
        [
            "--json",
            "meta-harness",
            "recipe",
            "--task-text",
            "Create a diagnostic task.",
            "--baseline-world",
            str(baseline_world),
            "--baseline-run",
            str(baseline_run),
            "--candidate-world",
            str(candidate_world),
            "--candidate-run",
            str(candidate_run),
            "--output",
            str(output_dir),
            "--command-prefix",
            "uv run aec-bench",
        ],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)["data"]
    recipe = json.loads((output_dir / "recipe.json").read_text(encoding="utf-8"))
    assert data["status"] == "materialized"
    assert data["files"]["run_script"].endswith("run_recipe.sh")
    assert (output_dir / "compare_candidate.py").exists()
    assert recipe["steps"][0]["command"][:3] == ["uv", "run", "aec-bench"]


def test_meta_harness_docs_examples_are_cli_consumable(tmp_path: Path) -> None:
    example_root = REPO_ROOT / "docs" / "examples" / "meta-harness"
    logic_world = example_root / "logic-profile" / "aecbench-verifier-event-world.json"
    logic_run = example_root / "logic-profile" / "aecbench-verifier-event-run.json"
    review_response = example_root / "logic-profile" / "aecbench-verifier-event-review-response.md"
    operation_world = example_root / "operation-profile" / "aecbench-world.json"
    operation_brief = example_root / "operation-profile" / "orchestrator-brief.json"
    operation_plan = example_root / "operation-profile" / "orchestrator-plan.json"
    reviewer_models = example_root / "logic-profile" / "reviewer-models.example.json"
    operation_models = example_root / "operation-profile" / "orchestrator-models.example.json"
    world_models = example_root / "world-process" / "world-process-models.example.json"
    process_brief = example_root / "world-process" / "problem-space-brief.json"
    task_run = example_root / "world-process" / "task-run.json"
    proposal = example_root / "world-process" / "governance-proposal.json"
    decision = example_root / "world-process" / "decision-accept-world-schema.json"
    output_dir = tmp_path / "example-process"

    logic_result = runner.invoke(
        app,
        ["--json", "meta-harness", "logic-evaluate", "--world", str(logic_world), "--run", str(logic_run)],
    )
    reviewed = runner.invoke(
        app,
        [
            "--json",
            "meta-harness",
            "review",
            "--world",
            str(logic_world),
            "--run",
            str(logic_run),
            "--review-response",
            str(review_response),
        ],
    )
    operation_result = runner.invoke(
        app,
        [
            "--json",
            "meta-harness",
            "operation-orchestrate",
            "--brief",
            str(operation_brief),
            "--world",
            str(operation_world),
            "--plan",
            str(operation_plan),
        ],
    )
    process_result = runner.invoke(
        app,
        [
            "--json",
            "meta-harness",
            "process",
            "Create diagnostic variants for verifier/artifact disagreement.",
            "--brief",
            str(process_brief),
            "--world",
            str(operation_world),
            "--task-run",
            str(task_run),
            "--operation-plan",
            str(operation_plan),
            "--governance-proposal",
            str(proposal),
            "--governance-decision",
            str(decision),
            "--output",
            str(output_dir),
        ],
    )
    review_plan = runner.invoke(
        app,
        [
            "--json",
            "meta-harness",
            "review-models",
            "--world",
            str(logic_world),
            "--run",
            str(logic_run),
            "--models-config",
            str(reviewer_models),
            "--emit-run-plan",
        ],
    )
    operation_plan_result = runner.invoke(
        app,
        [
            "--json",
            "meta-harness",
            "operation-models",
            "--brief",
            str(operation_brief),
            "--world",
            str(operation_world),
            "--models-config",
            str(operation_models),
            "--emit-run-plan",
        ],
    )
    intake_plan = runner.invoke(
        app,
        [
            "--json",
            "meta-harness",
            "intake-models",
            "--task-text",
            "Create diagnostic variants.",
            "--models-config",
            str(world_models),
            "--emit-run-plan",
        ],
    )
    world_plan = runner.invoke(
        app,
        [
            "--json",
            "meta-harness",
            "world-models",
            "--brief",
            str(process_brief),
            "--models-config",
            str(world_models),
            "--emit-run-plan",
        ],
    )

    assert logic_result.exit_code == 0, logic_result.output
    assert reviewed.exit_code == 0, reviewed.output
    assert operation_result.exit_code == 0, operation_result.output
    assert process_result.exit_code == 0, process_result.output
    assert review_plan.exit_code == 0, review_plan.output
    assert operation_plan_result.exit_code == 0, operation_plan_result.output
    assert intake_plan.exit_code == 0, intake_plan.output
    assert world_plan.exit_code == 0, world_plan.output
    assert json.loads(logic_result.output)["data"]["overall_status"] == "event_candidate"
    assert json.loads(reviewed.output)["data"]["evaluation"]["overall_status"] == "event_candidate"
    assert json.loads(operation_result.output)["data"]["status"] == "complete"
    assert json.loads(process_result.output)["data"]["status"] == "accepted_for_world_generation"
    assert len(json.loads(review_plan.output)["data"]["models"]) == 3
    assert len(json.loads(operation_plan_result.output)["data"]["models"]) == 2
    assert len(json.loads(intake_plan.output)["data"]["models"]) == 2
    assert len(json.loads(world_plan.output)["data"]["models"]) == 2


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _brief() -> dict:
    return {
        "brief_id": "brief.demo",
        "objective": "Create diagnostic variants.",
        "task_request": "Create a diagnostic task.",
        "evidence_requirements": ["preserve verifier artifacts"],
    }


def _world() -> dict:
    return {
        "world_id": "world.base",
        "name": "Base World",
        "task_unit": "Complete a calculation.",
        "logic_profile": {
            "closure_gates": [{"id": "verifier_passed", "evidence_key": "score.passed", "expected": True}],
            "construction_gates": [{"id": "artifact_witnessed", "construction_required": ["artifacts.report.path"]}],
            "containment_gates": [],
            "event_triggers": [],
            "agentic_review": {"required": True, "review_modes": ["verifier_result"]},
        },
        "operation_profile": {"projection_axes": ["artifact_evidence"]},
        "operation_handles": {"artifact_evidence": {"paths": ["logic_profile.construction_gates"]}},
        "evidence_profile": {"artifacts": ["logs/verifier/details.json"]},
    }


def _task_run() -> dict:
    return {
        "run_id": "run.demo",
        "evidence": {
            "score": {"passed": True},
            "artifacts": {"report": {"path": "logs/verifier/artifacts/report.json"}},
            "agentic_review": {
                "status": "complete",
                "reviewed_modes": ["verifier_result"],
                "findings": [],
            },
        },
    }


def _review_response() -> dict:
    return {
        "status": "complete",
        "reviewed_modes": ["verifier_result"],
        "findings": [],
    }


def _operation_plan() -> dict:
    return {
        "plan_id": "plan.demo",
        "objective": "Create diagnostic variants.",
        "steps": [
            {
                "id": "project_artifacts",
                "kind": "deterministic_operation",
                "world_ref": "world.base",
                "operation": {"operation": "projection", "axis": "artifact_evidence"},
            }
        ],
        "acceptance_checks": ["projection has operation_history"],
    }


def _proposal() -> dict:
    return {
        "status": "complete",
        "operation": {"operation": "projection", "axis": "governance"},
        "proposed_action": "request_schema_extension",
        "rationale": "Governance appears in review findings but has no operation handle.",
        "evidence_refs": ["agentic_review.findings[0]"],
        "confidence": 0.87,
        "repair_targets": ["world_schema", "world_generator"],
    }


def _world_schema_decision() -> dict:
    return {
        "decision_id": "decision.accept-governance-axis",
        "status": "accepted",
        "scope": "world_schema",
        "decided_by": "human",
        "rationale": "Governance is now a recurring evaluation dimension.",
    }
