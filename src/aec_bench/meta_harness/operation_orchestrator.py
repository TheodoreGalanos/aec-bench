# ABOUTME: Defines an agentic environment for orchestrating operation-profile transformations.
# ABOUTME: Keeps agents in the planning/proposal role while harness tools apply or record changes.

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any

from aec_bench.meta_harness.operation_profile import (
    apply_world_operation,
    operation_proposal_schema,
    record_operation_proposal,
)

DEFAULT_ALLOWED_OPERATIONS = ["projection", "difference", "subset", "product"]
PLAN_STEP_KINDS = ["deterministic_operation", "agentic_operation_proposal"]


@dataclass(frozen=True)
class OperationOrchestrationRequest:
    system_prompt: str
    user_prompt: str
    response_schema: dict[str, Any]
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "response_schema": self.response_schema,
            "payload": self.payload,
        }


@dataclass(frozen=True)
class OperationPlanExecution:
    status: str
    plan_id: str | None
    brief_ref: str | None
    objective: str | None
    step_results: list[dict[str, Any]]
    worlds: dict[str, dict[str, Any]]
    pending_orchestration_requests: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "plan_id": self.plan_id,
            "brief_ref": self.brief_ref,
            "objective": self.objective,
            "step_results": self.step_results,
            "worlds": self.worlds,
            "pending_orchestration_requests": self.pending_orchestration_requests,
            "errors": self.errors,
        }


@dataclass(frozen=True)
class OperationOrchestratorRun:
    status: str
    request: dict[str, Any]
    execution: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "request": self.request,
            "execution": self.execution,
        }


def operation_orchestrator_environment(
    *,
    allowed_operations: list[str] | None = None,
) -> dict[str, Any]:
    operations = allowed_operations or list(DEFAULT_ALLOWED_OPERATIONS)
    return {
        "environment_id": "operation_orchestrator",
        "name": "Operation Orchestrator",
        "role": (
            "Plan and inspect operation-profile transformations over task worlds. "
            "The agent proposes plans and repairs; harness tools apply deterministic "
            "operations or record proposals."
        ),
        "allowed_operations": list(operations),
        "principles": [
            "Agents propose; harness applies or records.",
            "Do not mutate source worlds directly.",
            "Prefer deterministic operations when declared handles are complete.",
            "When deterministic operations are blocked, emit bounded proposals with evidence references.",
            "Keep problem briefs above operation primitives; records should use brief_ref "
            "rather than copying private context everywhere.",
        ],
        "guidelines": [
            "Start from the problem brief and identify the diagnostic question.",
            "Inspect available operation axes and handles before inventing new ones.",
            "Use projection to isolate one world dimension.",
            "Use difference to remove one affordance, evidence channel, policy, or verifier surface.",
            "Use subset to restrict declared list or object components.",
            "Use product only when both worlds declare the composition axis.",
            "Treat blocked operations as prompts for proposal artifacts, not as permission to mutate the world.",
        ],
        "tools": [
            {
                "name": "apply_world_operation",
                "execution_owner": "harness",
                "description": (
                    "Apply projection, difference, subset, or product to a world when declared handles make "
                    "the operation deterministic."
                ),
                "input_schema": {
                    "type": "object",
                    "required": ["world_ref", "operation"],
                    "properties": {
                        "world_ref": {"type": "string"},
                        "operation": {"type": "object"},
                    },
                },
                "output_contract": "OperationResult with status applied or needs_orchestration.",
            },
            {
                "name": "record_operation_proposal",
                "execution_owner": "harness",
                "description": "Validate and record an agentic proposal without applying its world_patch.",
                "input_schema": {
                    "type": "object",
                    "required": ["world_ref", "proposal"],
                    "properties": {
                        "world_ref": {"type": "string"},
                        "proposal": operation_proposal_schema(),
                    },
                },
                "output_contract": "World with agentic_operation_proposals appended.",
            },
            {
                "name": "inspect_operation_handles",
                "execution_owner": "agent",
                "description": "Read available axes, handles, and evidence references before planning operations.",
                "input_schema": {
                    "type": "object",
                    "required": ["world_ref"],
                    "properties": {"world_ref": {"type": "string"}},
                },
                "output_contract": "A summary of operation_profile and operation_handles.",
            },
        ],
        "expected_artifacts": [
            "operation_plan",
            "operation_execution",
            "agentic_operation_proposals",
        ],
        "stopping_conditions": [
            "All deterministic steps have operation_history.",
            "All blocked steps have orchestration requests or validated proposals.",
            "No source world mutation is performed outside harness-owned tools.",
        ],
        "examples": [
            {
                "id": "verifier_artifact_ablation",
                "brief": "Create diagnostic variants for verifier/artifact disagreement.",
                "plan_steps": [
                    {
                        "kind": "deterministic_operation",
                        "operation": {"operation": "projection", "axis": "artifact_evidence"},
                    },
                    {
                        "kind": "deterministic_operation",
                        "operation": {"operation": "difference", "axis": "artifact_evidence"},
                    },
                ],
            },
            {
                "id": "missing_governance_axis",
                "brief": "Probe whether governance should become an operation axis.",
                "plan_steps": [
                    {
                        "kind": "deterministic_operation",
                        "operation": {"operation": "projection", "axis": "governance"},
                        "fallback_policy": "propose_handle_if_missing",
                    }
                ],
            },
        ],
    }


def build_operation_orchestration_request(
    *,
    brief: dict[str, Any],
    worlds: list[dict[str, Any]],
    allowed_operations: list[str] | None = None,
) -> OperationOrchestrationRequest:
    environment = operation_orchestrator_environment(allowed_operations=allowed_operations)
    payload = {
        "brief": copy.deepcopy(brief),
        "worlds": [_world_summary(world) for world in worlds],
        "allowed_operations": environment["allowed_operations"],
        "environment": environment,
    }
    return OperationOrchestrationRequest(
        system_prompt=_system_prompt(brief, environment),
        user_prompt=_user_prompt(payload),
        response_schema=operation_plan_response_schema(),
        payload=payload,
    )


def run_operation_orchestrator(
    *,
    brief: dict[str, Any],
    worlds: list[dict[str, Any]],
    allowed_operations: list[str] | None = None,
    operation_plan: dict[str, Any] | None = None,
) -> OperationOrchestratorRun:
    request = build_operation_orchestration_request(
        brief=brief,
        worlds=worlds,
        allowed_operations=allowed_operations,
    ).to_dict()
    if operation_plan is None:
        return OperationOrchestratorRun(
            status="awaiting_agent_plan",
            request=request,
            execution=None,
        )
    world_map = {_world_ref(world): world for world in worlds}
    execution = execute_operation_plan(operation_plan, world_map).to_dict()
    return OperationOrchestratorRun(
        status=execution["status"],
        request=request,
        execution=execution,
    )


def validate_operation_plan(
    plan: Any,
    available_world_refs: set[str],
) -> list[str]:
    if not isinstance(plan, dict):
        return ["operation plan must be a JSON object"]

    errors: list[str] = []
    if not _has_text(plan.get("plan_id")):
        errors.append("plan_id must be a non-empty string")
    if not _has_text(plan.get("objective")):
        errors.append("objective must be a non-empty string")
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("steps must be a non-empty list")
        return errors

    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            errors.append(f"steps[{index}] must be an object")
            continue
        errors.extend(_validate_step(index, step, available_world_refs))
    return errors


def execute_operation_plan(
    plan: dict[str, Any],
    worlds: dict[str, dict[str, Any]],
) -> OperationPlanExecution:
    errors = validate_operation_plan(plan, set(worlds))
    if errors:
        return OperationPlanExecution(
            status="invalid_plan",
            plan_id=plan.get("plan_id") if isinstance(plan, dict) else None,
            brief_ref=plan.get("brief_ref") if isinstance(plan, dict) else None,
            objective=plan.get("objective") if isinstance(plan, dict) else None,
            step_results=[],
            worlds={},
            errors=errors,
        )

    step_results: list[dict[str, Any]] = []
    output_worlds: dict[str, dict[str, Any]] = {}
    pending_requests: list[dict[str, Any]] = []

    for step in plan["steps"]:
        world_ref = step["world_ref"]
        source_world = worlds[world_ref]
        kind = step["kind"]
        if kind == "deterministic_operation":
            result = apply_world_operation(source_world, step["operation"]).to_dict()
            step_result = {
                "step_id": step["id"],
                "kind": kind,
                "world_ref": world_ref,
                "status": result["status"],
                "operation_result": result,
            }
            if result["status"] == "applied":
                output_ref = step.get("output_ref") or step["id"]
                output_worlds[output_ref] = result["transformed_world"]
                step_result["output_ref"] = output_ref
            else:
                pending_requests.append(
                    {
                        "step_id": step["id"],
                        "fallback_policy": step.get("fallback_policy"),
                        "request": result["orchestration_request"],
                    }
                )
            step_results.append(step_result)
        elif kind == "agentic_operation_proposal":
            output_ref = step.get("output_ref") or step["id"]
            updated_world = record_operation_proposal(source_world, step["proposal"])
            output_worlds[output_ref] = updated_world
            step_results.append(
                {
                    "step_id": step["id"],
                    "kind": kind,
                    "world_ref": world_ref,
                    "status": "recorded",
                    "output_ref": output_ref,
                }
            )

    status = "needs_orchestration" if pending_requests else "complete"
    return OperationPlanExecution(
        status=status,
        plan_id=plan.get("plan_id"),
        brief_ref=plan.get("brief_ref"),
        objective=plan.get("objective"),
        step_results=step_results,
        worlds=output_worlds,
        pending_orchestration_requests=pending_requests,
    )


def operation_plan_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["operation_plan"],
        "properties": {
            "operation_plan": {
                "type": "object",
                "required": ["plan_id", "objective", "steps", "acceptance_checks"],
                "properties": {
                    "plan_id": {"type": "string", "minLength": 1},
                    "brief_ref": {"type": "string"},
                    "objective": {"type": "string", "minLength": 1},
                    "steps": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["id", "kind", "world_ref"],
                            "properties": {
                                "id": {"type": "string", "minLength": 1},
                                "kind": {"enum": PLAN_STEP_KINDS},
                                "world_ref": {"type": "string", "minLength": 1},
                                "output_ref": {"type": "string"},
                                "operation": {"type": "object"},
                                "proposal": operation_proposal_schema(),
                                "fallback_policy": {"type": "string"},
                            },
                        },
                    },
                    "acceptance_checks": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            }
        },
    }


def _validate_step(
    index: int,
    step: dict[str, Any],
    available_world_refs: set[str],
) -> list[str]:
    errors: list[str] = []
    if not _has_text(step.get("id")):
        errors.append(f"steps[{index}].id must be a non-empty string")
    kind = step.get("kind")
    if kind not in PLAN_STEP_KINDS:
        errors.append(f"steps[{index}].kind must be one of {PLAN_STEP_KINDS}")
    world_ref = step.get("world_ref")
    if not _has_text(world_ref):
        errors.append(f"steps[{index}].world_ref must be a non-empty string")
    elif world_ref not in available_world_refs:
        errors.append(f"steps[{index}].world_ref is not available: {world_ref}")

    if kind == "deterministic_operation" and not isinstance(step.get("operation"), dict):
        errors.append(f"steps[{index}].operation must be an object")
    if kind == "agentic_operation_proposal" and not isinstance(step.get("proposal"), dict):
        errors.append(f"steps[{index}].proposal must be an object")
    return errors


def _system_prompt(
    brief: dict[str, Any],
    environment: dict[str, Any],
) -> str:
    constraints = brief.get("constraints", [])
    constraint_text = "\n".join(f"- {item}" for item in constraints) if isinstance(constraints, list) else ""
    principles = "\n".join(f"- {item}" for item in environment["principles"])
    return (
        "You are the Operation Orchestrator environment for a meta-harness. "
        "Produce an operation_plan; do not execute hidden mutations.\n\n"
        "Principles:\n"
        f"{principles}\n\n"
        "Brief constraints:\n"
        f"{constraint_text or '- No extra constraints supplied.'}"
    )


def _user_prompt(payload: dict[str, Any]) -> str:
    tools = ", ".join(tool["name"] for tool in payload["environment"]["tools"])
    return (
        "Plan operation-profile transformations for the supplied problem brief and worlds.\n"
        f"Available harness tools: {tools}.\n"
        "Return only JSON matching the response schema. Use deterministic operations where possible; "
        "use agentic_operation_proposal steps when a missing handle or schema extension is needed.\n\n"
        "Payload:\n"
        "```json\n"
        f"{json.dumps(payload, indent=2, sort_keys=True)}\n"
        "```"
    )


def _world_summary(world: dict[str, Any]) -> dict[str, Any]:
    return {
        "world_id": world.get("world_id"),
        "name": world.get("name"),
        "task_unit": world.get("task_unit"),
        "operation_profile": copy.deepcopy(world.get("operation_profile", {})),
        "operation_handles": copy.deepcopy(world.get("operation_handles", {})),
        "logic_profile": copy.deepcopy(world.get("logic_profile", {})),
        "evidence_profile": copy.deepcopy(world.get("evidence_profile", {})),
    }


def _world_ref(world: dict[str, Any]) -> str:
    value = world.get("world_id")
    if not _has_text(value):
        raise ValueError("world must have a non-empty world_id")
    return value


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
