# ABOUTME: Tests the meta-harness prose-to-world process inside AEC-Bench.
# ABOUTME: Covers intake, governance, pauseable runtime, ledger records, and autonomy gates.

from __future__ import annotations

import copy
import json
from pathlib import Path

from aec_bench.meta_harness.autonomy import (
    AutonomyConfig,
    estimate_process_cost_usd,
    run_autonomous_process,
    score_process_result,
)
from aec_bench.meta_harness.ledger import read_ledger
from aec_bench.meta_harness.world_process import (
    apply_governance_decision,
    build_governance_review_packet,
    build_problem_brief_request,
    build_world_generation_request,
)
from aec_bench.meta_harness.world_runtime import run_process


def test_problem_brief_and_world_generation_requests_preserve_boundaries() -> None:
    intake = build_problem_brief_request(
        task_text="Create a calculation task that exposes verifier/artifact disagreement.",
        attachments=[{"path": "runs/demo/result.json", "kind": "run_artifact"}],
        process_id="process.demo",
    )
    world_generation = build_world_generation_request(
        brief=_brief(),
        source_world=_world(),
        process_id="process.demo",
    )

    assert intake["status"] == "awaiting_problem_space_brief"
    assert intake["payload"]["attachments"][0]["kind"] == "run_artifact"
    assert "brief" not in intake["payload"]
    assert world_generation["status"] == "awaiting_world_generation"
    assert world_generation["request"]["environment"]["environment_id"] == "world_generator"
    assert world_generation["request"]["payload"]["source_world"]["world_id"] == "world.base"


def test_governance_routes_accepted_schema_changes_back_to_world_generation() -> None:
    world = _world()
    original = copy.deepcopy(world)
    operation_run = {
        "execution": {
            "pending_orchestration_requests": [
                {
                    "step_id": "project_governance",
                    "request": {
                        "operation": {"operation": "projection", "axis": "governance"},
                        "issues": [{"code": "axis_not_declared"}],
                    },
                }
            ],
            "worlds": {
                "world_with_proposal": {
                    "world_id": "world.base",
                    "agentic_operation_proposals": [_proposal()],
                }
            },
        }
    }

    packet = build_governance_review_packet(
        brief=_brief(),
        source_world=world,
        operation_run=operation_run,
        process_id="process.demo",
    )
    outcome = apply_governance_decision(
        brief=_brief(),
        source_world=world,
        proposal=_proposal(),
        decision={
            "decision_id": "decision.accept-governance-axis",
            "status": "accepted",
            "scope": "world_schema",
            "decided_by": "human",
            "rationale": "Governance is now a recurring evaluation dimension.",
        },
        process_id="process.demo",
    )

    assert len(packet["candidates"]) == 2
    assert outcome["status"] == "accepted_for_world_generation"
    assert outcome["world_generation_request"]["status"] == "awaiting_world_generation"
    assert outcome["world_generation_request"]["request"]["payload"]["governance_directive"]["target"] == "world_schema"
    assert world == original


def test_runtime_pauses_and_records_ledger_entries(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.jsonl"

    intake_only = run_process(
        task_text="Create a diagnostic task.",
        process_id="process.demo",
        ledger_path=ledger_path,
    )
    with_brief = run_process(
        task_text="Create a diagnostic task.",
        process_id="process.demo",
        problem_space_brief=_brief(),
    )

    entries = read_ledger(ledger_path)

    assert intake_only["status"] == "awaiting_problem_space_brief"
    assert [entry["stage"] for entry in entries] == ["problem_space_intake"]
    assert with_brief["status"] == "awaiting_world_generation"
    assert with_brief["world_generation_request"]["request"]["environment"]["environment_id"] == "world_generator"


def test_runtime_reaches_governed_world_generation_with_supplied_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "process"
    ledger_path = output_dir / "process_ledger.jsonl"

    result = run_process(
        task_text="Create a diagnostic task.",
        process_id="process.demo",
        problem_space_brief=_brief(),
        world=_world(),
        task_run=_task_run(),
        operation_plan=_operation_plan(),
        governance_proposal=_proposal(),
        governance_decision=_world_schema_decision(),
        output_dir=output_dir,
        ledger_path=ledger_path,
    )
    entries = read_ledger(ledger_path)
    result_json = json.loads((output_dir / "harbor_task" / "result.json").read_text(encoding="utf-8"))

    assert result["status"] == "accepted_for_world_generation"
    assert result["logic_evaluation"]["overall_status"] == "certified"
    assert result["operation_run"]["status"] == "complete"
    assert result_json["task_type"] == "operation_orchestrator"
    assert [entry["stage"] for entry in entries] == [
        "problem_space_intake",
        "problem_space_brief",
        "world_generation_request",
        "world",
        "harbor_task_package",
        "task_run",
        "logic_evaluation",
        "operation_orchestration",
        "governance_review",
        "governance_application",
    ]


def test_autonomy_scores_runs_and_human_gates_world_schema_governance() -> None:
    config = AutonomyConfig(max_iterations=3)
    runtime_result = run_process(
        task_text="Create a diagnostic task.",
        process_id="process.demo",
        problem_space_brief=_brief(),
        world=_world(),
        task_run=_task_run(),
        operation_plan=_operation_plan(),
        governance_proposal=_proposal(),
        governance_decision=_world_schema_decision(),
    )
    machine_decision = _world_schema_decision()
    machine_decision["decided_by"] = "governance-agent"

    score = score_process_result(runtime_result)
    autonomous = run_autonomous_process(
        task_text="Create a diagnostic task.",
        process_id="process.autonomy-human-gate",
        config=config,
        problem_space_brief=_brief(),
        world=_world(),
        task_run_resolver=lambda _runtime: copy.deepcopy(_task_run()),
        operation_plan_resolver=lambda _runtime: copy.deepcopy(_operation_plan()),
        governance_resolver=lambda _runtime: {
            "proposal": copy.deepcopy(_proposal()),
            "decision": machine_decision,
        },
    )

    assert score["components"]["verifier_reward"] == 1.0
    assert score["components"]["logic_certified"] == 1.0
    assert score["components"]["review_complete"] == 1.0
    assert autonomous["status"] == "awaiting_human_governance"
    assert autonomous["pending_decision"]["scope"] == "world_schema"


def test_autonomy_cost_estimate_counts_model_stage_costs() -> None:
    result = {
        "cost_usd": 0.01,
        "intake_model_run": {"cost": {"estimated_cost_usd": 0.02}},
        "world_generation_model_run": {"cost": {"estimated_cost_usd": 0.03}},
        "review_model_run": {"cost": {"estimated_cost_usd": 0.04}},
        "operation_run": {"model_run": {"cost": {"estimated_cost_usd": 0.05}}},
        "task_run": {"cost": {"estimated_cost_usd": 0.06}},
    }

    assert estimate_process_cost_usd(result) == 0.21


def _brief() -> dict:
    return {
        "brief_id": "brief.demo",
        "objective": "Create diagnostic variants for verifier/artifact disagreement.",
        "task_request": "Create a diagnostic task.",
        "constraints": ["Do not mutate source worlds directly."],
        "evidence_requirements": ["verifier reward", "artifact evidence"],
    }


def _world() -> dict:
    return {
        "world_id": "world.base",
        "name": "Base World",
        "task_unit": "Complete a calculation with verifier-visible artifacts.",
        "operation_profile": {
            "projection_axes": ["artifact_evidence"],
            "difference_axes": ["artifact_evidence"],
        },
        "operation_handles": {"artifact_evidence": {"paths": ["logic_profile.construction_gates"]}},
        "logic_profile": {
            "closure_gates": [{"id": "verifier_passed", "evidence_key": "score.passed", "expected": True}],
            "construction_gates": [{"id": "artifact_witnessed", "construction_required": ["artifacts.report.path"]}],
            "containment_gates": [],
            "event_triggers": [],
            "agentic_review": {
                "required": True,
                "review_modes": [
                    "verifier_result",
                    "output_artifacts",
                    "trace",
                    "source_authority",
                    "rubric_scores",
                    "contradiction_ledger",
                ],
            },
        },
        "evidence_profile": {"preserved_artifacts": ["logs/verifier/artifacts/report.json"]},
    }


def _operation_plan() -> dict:
    return {
        "plan_id": "plan.artifact_projection",
        "brief_ref": "brief.demo",
        "objective": "Create diagnostic variants for verifier/artifact disagreement.",
        "steps": [
            {
                "id": "project_artifacts",
                "kind": "deterministic_operation",
                "world_ref": "world.base",
                "output_ref": "artifact_projection",
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
        "new_operation_handles": {"governance": {"paths": ["governance_profile"]}},
        "requires_human_approval": True,
    }


def _world_schema_decision() -> dict:
    return {
        "decision_id": "decision.accept-governance-axis",
        "status": "accepted",
        "scope": "world_schema",
        "decided_by": "human",
        "rationale": "Governance is now a recurring evaluation dimension.",
    }


def _task_run() -> dict:
    return {
        "run_id": "run.demo",
        "evidence": {
            "score": {"passed": True},
            "artifacts": {"report": {"path": "logs/verifier/artifacts/report.json"}},
            "agentic_review": {
                "status": "complete",
                "reviewed_modes": [
                    "verifier_result",
                    "output_artifacts",
                    "trace",
                    "source_authority",
                    "rubric_scores",
                    "contradiction_ledger",
                ],
                "findings": [],
            },
        },
    }
