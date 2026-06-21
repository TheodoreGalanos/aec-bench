# ABOUTME: Tests meta-harness operation-profile transformations inside AEC-Bench.
# ABOUTME: Pins deterministic operations and the agentic orchestration fallback contract.

from __future__ import annotations

import copy

from aec_bench.meta_harness.operation_orchestrator import (
    build_operation_orchestration_request,
    execute_operation_plan,
    operation_orchestrator_environment,
    run_operation_orchestrator,
    validate_operation_plan,
)
from aec_bench.meta_harness.operation_profile import (
    apply_world_operation,
    record_operation_proposal,
    validate_operation_proposal,
)


def test_projection_keeps_only_selected_axis_paths() -> None:
    world = _world()

    result = apply_world_operation(
        world,
        {"operation": "projection", "axis": "artifact_evidence"},
    ).to_dict()

    assert result["status"] == "applied"
    assert result["mode"] == "deterministic"
    projected = result["transformed_world"]
    assert projected["world_id"] == "world.base.projection.artifact_evidence"
    assert projected["logic_profile"]["construction_gates"] == world["logic_profile"]["construction_gates"]
    assert projected["evidence_profile"]["preserved_artifacts"] == [
        "logs/verifier/details.json",
        "logs/verifier/artifacts/report.json",
    ]
    assert "closure_gates" not in projected["logic_profile"]
    assert projected["operation_history"][0]["operation"] == "projection"


def test_difference_subset_and_product_transform_worlds_without_source_mutation() -> None:
    world = _world()
    original = copy.deepcopy(world)

    difference = apply_world_operation(
        world,
        {"operation": "difference", "axis": "artifact_evidence"},
    ).to_dict()
    subset = apply_world_operation(
        world,
        {"operation": "subset", "axis": "task_family", "include": ["calculation"]},
    ).to_dict()
    product = apply_world_operation(
        world,
        {
            "operation": "product",
            "axis": "verifier_family",
            "other_world": _world(world_id="world.other", name="Other World"),
        },
    ).to_dict()

    assert difference["status"] == "applied"
    assert "construction_gates" not in difference["transformed_world"]["logic_profile"]
    assert subset["transformed_world"]["families"] == ["calculation"]
    assert subset["transformed_world"]["family_components"] == {"calculation": {"difficulty": "easy"}}
    assert product["transformed_world"]["world_id"] == "world.base__product__world.other"
    assert product["transformed_world"]["product_components"]["left"]["world_id"] == "world.base"
    assert world == original


def test_blocked_operation_returns_agentic_orchestration_request() -> None:
    result = apply_world_operation(
        _world(),
        {"operation": "projection", "axis": "governance"},
    ).to_dict()

    assert result["status"] == "needs_orchestration"
    assert result["mode"] == "agentic_orchestration"
    assert result["issues"][0]["code"] == "axis_not_declared"
    assert result["orchestration_request"]["operation"]["axis"] == "governance"
    assert "propose_operation_handle" in result["orchestration_request"]["allowed_actions"]


def test_operation_proposal_validation_and_recording() -> None:
    world = _world()
    proposal = {
        "status": "complete",
        "operation": {"operation": "projection", "axis": "governance"},
        "proposed_action": "propose_operation_handle",
        "rationale": "Governance appears in reviewer findings but has no axis handle.",
        "evidence_refs": ["agentic_review.findings[0]"],
        "confidence": 0.82,
        "repair_targets": ["operation_profile", "world_schema"],
    }

    assert validate_operation_proposal(proposal) == []
    updated = record_operation_proposal(world, proposal)

    assert updated["agentic_operation_proposals"][0]["proposed_action"] == "propose_operation_handle"
    assert "agentic_operation_proposals" not in world


def test_operation_orchestrator_environment_and_request_keep_brief_above_primitives() -> None:
    brief = {
        "brief_id": "brief.verifier_artifact_ablation",
        "objective": "Create diagnostic variants for verifier/artifact disagreement.",
        "constraints": ["Do not mutate source worlds directly."],
    }

    environment = operation_orchestrator_environment(allowed_operations=["projection", "difference"])
    request = build_operation_orchestration_request(
        brief=brief,
        worlds=[_world()],
        allowed_operations=["projection", "difference"],
    ).to_dict()

    assert environment["environment_id"] == "operation_orchestrator"
    assert "Agents propose; harness applies or records." in environment["principles"]
    assert ["apply_world_operation", "record_operation_proposal"] == [tool["name"] for tool in environment["tools"][:2]]
    assert request["payload"]["brief"] == brief
    assert request["payload"]["environment"]["environment_id"] == "operation_orchestrator"
    assert "operation_plan" in request["response_schema"]["properties"]
    assert "Do not mutate source worlds directly" in request["system_prompt"]


def test_operation_plan_execution_records_pending_requests_and_proposals() -> None:
    world = _world()
    blocked_plan = {
        "plan_id": "plan.governance_probe",
        "brief_ref": "brief.governance_projection",
        "objective": "Probe whether governance should become an operation axis.",
        "steps": [
            {
                "id": "project_governance",
                "kind": "deterministic_operation",
                "world_ref": "world.base",
                "operation": {"operation": "projection", "axis": "governance"},
                "fallback_policy": "propose_handle_if_missing",
            }
        ],
        "acceptance_checks": ["blocked steps produce orchestration requests"],
    }
    proposal_plan = {
        "plan_id": "plan.record_proposal",
        "brief_ref": "brief.governance_projection",
        "objective": "Record a proposed governance operation handle.",
        "steps": [
            {
                "id": "record_governance_handle",
                "kind": "agentic_operation_proposal",
                "world_ref": "world.base",
                "output_ref": "world_with_governance_proposal",
                "proposal": {
                    "status": "complete",
                    "operation": {"operation": "projection", "axis": "governance"},
                    "proposed_action": "propose_operation_handle",
                    "rationale": "Governance is visible in review findings but absent as a handle.",
                    "evidence_refs": ["agentic_review.findings[0]"],
                    "confidence": 0.84,
                    "repair_targets": ["operation_profile", "world_schema"],
                    "world_patch": {"operation_handles": {"governance": {"paths": ["governance_profile"]}}},
                },
            }
        ],
        "acceptance_checks": ["proposal is recorded, not applied"],
    }

    blocked = execute_operation_plan(blocked_plan, {"world.base": world}).to_dict()
    recorded = execute_operation_plan(proposal_plan, {"world.base": world}).to_dict()

    assert blocked["status"] == "needs_orchestration"
    assert blocked["pending_orchestration_requests"][0]["step_id"] == "project_governance"
    assert recorded["status"] == "complete"
    updated = recorded["worlds"]["world_with_governance_proposal"]
    assert updated["agentic_operation_proposals"][0]["proposed_action"] == "propose_operation_handle"
    assert "governance" not in updated["operation_handles"]
    assert "agentic_operation_proposals" not in world


def test_run_operation_orchestrator_waits_for_agent_plan_and_validates_plan_shape() -> None:
    brief = {
        "brief_id": "brief.verifier_artifact_ablation",
        "objective": "Create diagnostic variants for verifier/artifact disagreement.",
    }

    run = run_operation_orchestrator(
        brief=brief,
        worlds=[_world()],
        allowed_operations=["projection", "difference"],
    ).to_dict()
    errors = validate_operation_plan({"plan_id": "", "steps": []}, {"world.base"})

    assert run["status"] == "awaiting_agent_plan"
    assert run["request"]["payload"]["brief"] == brief
    assert run["execution"] is None
    assert "plan_id must be a non-empty string" in errors
    assert "objective must be a non-empty string" in errors
    assert "steps must be a non-empty list" in errors


def _world(
    *,
    world_id: str = "world.base",
    name: str = "Base World",
) -> dict:
    return {
        "world_id": world_id,
        "name": name,
        "task_unit": "Complete a calculation with verifier-visible artifacts.",
        "families": ["calculation", "review"],
        "family_components": {
            "calculation": {"difficulty": "easy"},
            "review": {"difficulty": "hard"},
        },
        "logic_profile": {
            "closure_gates": [{"id": "verifier_passed", "evidence_key": "score.passed", "expected": True}],
            "construction_gates": [{"id": "artifact_witnessed", "construction_required": ["artifacts.report.path"]}],
            "containment_gates": [],
            "event_triggers": [],
            "agentic_review": {"required": True},
        },
        "evidence_profile": {
            "preserved_artifacts": [
                "logs/verifier/details.json",
                "logs/verifier/artifacts/report.json",
            ],
            "process_metrics": ["tool_count", "duration"],
        },
        "operation_profile": {
            "subset_axes": ["task_family"],
            "difference_axes": ["artifact_evidence", "trace_channel"],
            "projection_axes": ["artifact_evidence", "verifier_authority"],
            "product_axes": ["verifier_family"],
            "extension_policy": "Escalate missing handles to agentic orchestration.",
            "agentic_orchestration": {
                "allowed_actions": [
                    "propose_operation_handle",
                    "propose_component_transform",
                    "request_schema_extension",
                ],
                "guidance": "Prefer deterministic operations; propose repairs when handles are incomplete.",
            },
        },
        "operation_handles": {
            "artifact_evidence": {
                "paths": [
                    "logic_profile.construction_gates",
                    "evidence_profile.preserved_artifacts",
                ],
            },
            "task_family": {"paths": ["families", "family_components"]},
            "verifier_authority": {"paths": ["logic_profile.closure_gates"]},
            "verifier_family": {"paths": ["logic_profile.closure_gates"]},
        },
    }
