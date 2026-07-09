# ABOUTME: Defines the prose intake, world generation, and governance contracts.
# ABOUTME: Routes accepted repair proposals back to generation without hidden mutation.

from __future__ import annotations

import copy
import json
import re
from typing import Any

from aec_bench.meta_harness.operation_profile import validate_operation_proposal

GOVERNANCE_STATUSES = {"accepted", "rejected", "needs_human_review"}
GOVERNANCE_SCOPES = {"run_only", "world_schema", "world_generator"}


def build_problem_brief_request(
    *,
    task_text: str,
    attachments: list[dict[str, Any]] | None = None,
    process_id: str | None = None,
) -> dict[str, Any]:
    if not _has_text(task_text):
        raise ValueError("task_text must be a non-empty string")

    payload = {
        "task_text": task_text.strip(),
        "attachments": copy.deepcopy(attachments or []),
    }
    resolved_process_id = process_id or _stable_id("process", task_text)
    return {
        "process_id": resolved_process_id,
        "stage": "problem_space_intake",
        "status": "awaiting_problem_space_brief",
        "payload": payload,
        "system_prompt": _problem_brief_system_prompt(),
        "user_prompt": _problem_brief_user_prompt(payload),
        "response_schema": problem_space_brief_schema(),
        "next_step": "submit problem_space_brief to build_world_generation_request",
    }


def build_world_generation_request(
    *,
    brief: dict[str, Any],
    source_world: dict[str, Any] | None = None,
    governance_directive: dict[str, Any] | None = None,
    process_id: str | None = None,
) -> dict[str, Any]:
    resolved_process_id = process_id or _stable_id("process", brief.get("brief_id"), brief.get("objective"))
    payload = {
        "brief": copy.deepcopy(brief),
        "source_world": _world_summary(source_world) if source_world else None,
        "governance_directive": copy.deepcopy(governance_directive),
    }
    environment = world_generator_environment()
    return {
        "process_id": resolved_process_id,
        "stage": "world_generation",
        "status": "awaiting_world_generation",
        "request": {
            "environment": environment,
            "payload": payload,
            "system_prompt": _world_generation_system_prompt(environment),
            "user_prompt": _world_generation_user_prompt(payload),
            "response_schema": world_card_response_schema(),
        },
    }


def build_governance_review_packet(
    *,
    brief: dict[str, Any],
    source_world: dict[str, Any],
    operation_run: dict[str, Any],
    process_id: str | None = None,
) -> dict[str, Any]:
    return {
        "process_id": process_id or _stable_id("process", brief.get("brief_id"), source_world.get("world_id")),
        "stage": "governance_review",
        "status": "awaiting_governance_decision",
        "brief": copy.deepcopy(brief),
        "source_world": _world_summary(source_world),
        "candidates": _governance_candidates(operation_run),
        "response_schema": governance_decision_schema(),
        "principles": [
            "Operation proposals are evidence, not mutations.",
            "Only governance may route accepted repairs back to world generation.",
            "Run-only acceptance creates a local directive, not generator evolution.",
            "Generator and schema changes must preserve provenance and source world refs.",
        ],
    }


def apply_governance_decision(
    *,
    brief: dict[str, Any],
    source_world: dict[str, Any],
    proposal: dict[str, Any],
    decision: dict[str, Any],
    process_id: str | None = None,
) -> dict[str, Any]:
    proposal_errors = validate_operation_proposal(proposal)
    decision_errors = validate_governance_decision(decision)
    if proposal_errors or decision_errors:
        return _governance_outcome(
            status="invalid_governance_decision",
            brief=brief,
            source_world=source_world,
            proposal=proposal,
            decision=decision,
            errors=proposal_errors + decision_errors,
            process_id=process_id,
        )

    if _requires_human_acceptance(proposal, decision):
        return _governance_outcome(
            status="blocked",
            brief=brief,
            source_world=source_world,
            proposal=proposal,
            decision=decision,
            errors=["proposal requires human approval before accepted governance action"],
            process_id=process_id,
        )

    status = decision["status"]
    if status == "rejected":
        return _governance_outcome(
            status="rejected",
            brief=brief,
            source_world=source_world,
            proposal=proposal,
            decision=decision,
            process_id=process_id,
        )
    if status == "needs_human_review":
        return _governance_outcome(
            status="awaiting_human_review",
            brief=brief,
            source_world=source_world,
            proposal=proposal,
            decision=decision,
            process_id=process_id,
        )

    if decision["scope"] == "run_only":
        return _governance_outcome(
            status="accepted_for_run",
            brief=brief,
            source_world=source_world,
            proposal=proposal,
            decision=decision,
            process_id=process_id,
            run_directive={
                "scope": "run_only",
                "mutation_allowed": False,
                "accepted_proposal": copy.deepcopy(proposal),
                "instruction": "Use as a local diagnostic directive only.",
            },
        )

    directive = _governance_directive(proposal, decision)
    world_generation_request = build_world_generation_request(
        brief=brief,
        source_world=source_world,
        governance_directive=directive,
        process_id=process_id,
    )
    return _governance_outcome(
        status="accepted_for_world_generation",
        brief=brief,
        source_world=source_world,
        proposal=proposal,
        decision=decision,
        process_id=process_id,
        world_generation_request=world_generation_request,
    )


def validate_governance_decision(decision: Any) -> list[str]:
    if not isinstance(decision, dict):
        return ["governance decision must be a JSON object"]

    errors: list[str] = []
    if not _has_text(decision.get("decision_id")):
        errors.append("decision_id must be a non-empty string")
    if decision.get("status") not in GOVERNANCE_STATUSES:
        errors.append(f"status must be one of {sorted(GOVERNANCE_STATUSES)}")
    if decision.get("status") == "accepted" and decision.get("scope") not in GOVERNANCE_SCOPES:
        errors.append(f"scope must be one of {sorted(GOVERNANCE_SCOPES)} when accepted")
    if not _has_text(decision.get("decided_by")):
        errors.append("decided_by must be a non-empty string")
    if not _has_text(decision.get("rationale")):
        errors.append("rationale must be a non-empty string")
    return errors


def validate_problem_space_brief(brief: Any) -> list[str]:
    if not isinstance(brief, dict):
        return ["problem_space_brief must be a JSON object"]

    errors: list[str] = []
    for field_name in ["brief_id", "objective", "task_request"]:
        if not _has_text(brief.get(field_name)):
            errors.append(f"{field_name} must be a non-empty string")
    evidence_requirements = brief.get("evidence_requirements")
    if not _is_string_list(evidence_requirements) or not evidence_requirements:
        errors.append("evidence_requirements must be a non-empty list of strings")
    return errors


def validate_world_generation_response(response: Any) -> list[str]:
    if not isinstance(response, dict):
        return ["world generation response must be a JSON object"]

    world = response.get("world")
    if not isinstance(world, dict):
        return ["world must be a JSON object"]

    errors: list[str] = []
    for field_name in ["world_id", "task_unit"]:
        if not _has_text(world.get(field_name)):
            errors.append(f"world.{field_name} must be a non-empty string")
    for field_name in ["logic_profile", "operation_profile", "operation_handles"]:
        if not isinstance(world.get(field_name), dict):
            errors.append(f"world.{field_name} must be an object")
    return errors


def problem_space_brief_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["problem_space_brief"],
        "properties": {
            "problem_space_brief": {
                "type": "object",
                "required": ["brief_id", "objective", "task_request", "evidence_requirements"],
                "properties": {
                    "brief_id": {"type": "string", "minLength": 1},
                    "objective": {"type": "string", "minLength": 1},
                    "task_request": {"type": "string", "minLength": 1},
                    "constraints": {"type": "array", "items": {"type": "string"}},
                    "attachments": {"type": "array", "items": {"type": "object"}},
                    "expected_outputs": {"type": "array", "items": {"type": "string"}},
                    "evidence_requirements": {"type": "array", "items": {"type": "string"}},
                    "risk_notes": {"type": "array", "items": {"type": "string"}},
                },
            }
        },
    }


def world_generator_environment() -> dict[str, Any]:
    return {
        "environment_id": "world_generator",
        "name": "World Generator",
        "role": "Generate or revise task-world cards from problem briefs and governance directives.",
        "principles": [
            "Generate worlds; do not execute tasks.",
            "Preserve provenance from prose, briefs, source worlds, and governance directives.",
            "Declare logic_profile, operation_profile, and operation_handles explicitly.",
            "Do not mutate prior worlds; emit a replacement or derived world candidate.",
            "Treat accepted governance directives as constraints, not suggestions.",
        ],
        "tools": [
            {
                "name": "emit_world_card",
                "execution_owner": "agent",
                "description": "Return a task-world JSON object matching the response schema.",
            },
            {
                "name": "validate_world_profiles",
                "execution_owner": "harness",
                "description": "Validate logic, operation, evidence, and governance profile shape.",
            },
        ],
        "expected_artifacts": [
            "world_card",
            "world_generation_rationale",
            "profile_validation_report",
        ],
    }


def world_card_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["world"],
        "properties": {
            "world": {
                "type": "object",
                "required": [
                    "world_id",
                    "task_unit",
                    "logic_profile",
                    "operation_profile",
                    "operation_handles",
                ],
                "properties": {
                    "world_id": {"type": "string", "minLength": 1},
                    "name": {"type": "string"},
                    "task_unit": {"type": "string", "minLength": 1},
                    "logic_profile": {"type": "object"},
                    "operation_profile": {"type": "object"},
                    "operation_handles": {"type": "object"},
                    "evidence_profile": {"type": "object"},
                    "governance_profile": {"type": "object"},
                    "provenance": {"type": "object"},
                },
            },
            "world_generation_rationale": {"type": "string"},
        },
    }


def governance_decision_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["decision_id", "status", "decided_by", "rationale"],
        "properties": {
            "decision_id": {"type": "string", "minLength": 1},
            "status": {"enum": sorted(GOVERNANCE_STATUSES)},
            "scope": {"enum": sorted(GOVERNANCE_SCOPES)},
            "decided_by": {"type": "string", "minLength": 1},
            "rationale": {"type": "string", "minLength": 1},
            "conditions": {"type": "array", "items": {"type": "string"}},
        },
    }


def _governance_candidates(operation_run: dict[str, Any]) -> list[dict[str, Any]]:
    execution = operation_run.get("execution") if isinstance(operation_run, dict) else {}
    execution = execution or {}
    candidates: list[dict[str, Any]] = []

    for index, item in enumerate(execution.get("pending_orchestration_requests", [])):
        candidates.append(
            {
                "candidate_id": f"pending.{index}",
                "kind": "blocked_operation",
                "step_id": item.get("step_id"),
                "fallback_policy": item.get("fallback_policy"),
                "orchestration_request": copy.deepcopy(item.get("request")),
            }
        )

    worlds = execution.get("worlds", {})
    if isinstance(worlds, dict):
        for world_ref, world in worlds.items():
            proposals = world.get("agentic_operation_proposals", []) if isinstance(world, dict) else []
            for index, proposal in enumerate(proposals):
                candidates.append(
                    {
                        "candidate_id": f"{world_ref}.proposal.{index}",
                        "kind": "agentic_operation_proposal",
                        "world_ref": world_ref,
                        "proposal": copy.deepcopy(proposal),
                    }
                )
    return candidates


def _governance_outcome(
    *,
    status: str,
    brief: dict[str, Any],
    source_world: dict[str, Any],
    proposal: dict[str, Any],
    decision: dict[str, Any],
    errors: list[str] | None = None,
    process_id: str | None = None,
    run_directive: dict[str, Any] | None = None,
    world_generation_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "process_id": process_id or _stable_id("process", brief.get("brief_id"), source_world.get("world_id")),
        "stage": "governance_application",
        "status": status,
        "brief_ref": brief.get("brief_id"),
        "source_world_ref": source_world.get("world_id"),
        "decision": copy.deepcopy(decision),
        "proposal": copy.deepcopy(proposal),
        "errors": errors or [],
        "run_directive": copy.deepcopy(run_directive),
        "world_generation_request": copy.deepcopy(world_generation_request),
    }


def _governance_directive(
    proposal: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    return {
        "target": decision["scope"],
        "decision": copy.deepcopy(decision),
        "accepted_proposal": copy.deepcopy(proposal),
        "requested_changes": {
            "repair_targets": copy.deepcopy(proposal.get("repair_targets", [])),
            "new_operation_handles": copy.deepcopy(proposal.get("new_operation_handles", {})),
            "world_patch": copy.deepcopy(proposal.get("world_patch", {})),
        },
        "mutation_policy": "regenerate_or_patch_after_governance_only",
    }


def _requires_human_acceptance(
    proposal: dict[str, Any],
    decision: dict[str, Any],
) -> bool:
    return (
        proposal.get("requires_human_approval") is True
        and decision.get("status") == "accepted"
        and decision.get("decided_by") != "human"
    )


def _problem_brief_system_prompt() -> str:
    return (
        "You are the problem-space intake agent. Convert user prose and attachments "
        "into a structured problem_space_brief. Do not invent source facts; preserve "
        "uncertainty and evidence requirements."
    )


def _problem_brief_user_prompt(payload: dict[str, Any]) -> str:
    return (
        "Create a problem_space_brief for this task request.\n\n"
        "Payload:\n"
        "```json\n"
        f"{json.dumps(payload, indent=2, sort_keys=True)}\n"
        "```"
    )


def _world_generation_system_prompt(environment: dict[str, Any]) -> str:
    principles = "\n".join(f"- {item}" for item in environment["principles"])
    return (
        "You are the World Generator environment for a meta-harness. "
        "Return a world card; do not execute the task.\n\n"
        "Principles:\n"
        f"{principles}"
    )


def _world_generation_user_prompt(payload: dict[str, Any]) -> str:
    return (
        "Generate or revise a task world for this brief and governance context.\n"
        "Return only JSON matching the response schema.\n\n"
        "Payload:\n"
        "```json\n"
        f"{json.dumps(payload, indent=2, sort_keys=True)}\n"
        "```"
    )


def _world_summary(world: dict[str, Any] | None) -> dict[str, Any] | None:
    if world is None:
        return None
    return {
        "world_id": world.get("world_id"),
        "name": world.get("name"),
        "task_unit": world.get("task_unit"),
        "logic_profile": copy.deepcopy(world.get("logic_profile", {})),
        "operation_profile": copy.deepcopy(world.get("operation_profile", {})),
        "operation_handles": copy.deepcopy(world.get("operation_handles", {})),
        "evidence_profile": copy.deepcopy(world.get("evidence_profile", {})),
    }


def _stable_id(prefix: str, *parts: Any) -> str:
    seed = ".".join(str(part) for part in parts if part)
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", seed.strip()).strip("-").lower()
    return f"{prefix}.{slug or 'default'}"


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)
