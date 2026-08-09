# ABOUTME: Defines the current pump-station actor action catalogue and exact task argument schemas.
# ABOUTME: Parses installed actor payloads once into task-owned actions for the functional core.

from __future__ import annotations

from dataclasses import fields
from typing import Any, cast

from pydantic import JsonValue, TypeAdapter, ValidationError

from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.contracts.world_interface import (
    WorldActorActionCapability,
    WorldActorActionRequest,
    WorldActorCapabilityCatalogue,
    WorldInterfaceError,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_models import (
    CancelProcess,
    ContinueOperation,
    PumpStationAction,
    RequestConditionCheck,
    RequestDependencyWaiver,
    RequestDutyAssignment,
    RequestFunctionalCheck,
    RequestInspection,
    RequestObstructionClearance,
    RequestProvisionalClosure,
    RequestProvisionalReturn,
    RequestVerification,
    ResumeProcess,
)

PUMP_STATION_ACTOR_WORKSPACE_TOOL_ID = "pump-station-actor-interface"
PUMP_STATION_TEMPORAL_EVIDENCE_ACTION_NAMES = (
    "search_evidence",
    "fetch_evidence",
)
PUMP_STATION_ACTOR_ACTION_NAMES = (
    "continue_operation",
    "request_duty_assignment",
    "request_inspection",
    "request_obstruction_clearance",
    "request_functional_check",
    "request_provisional_return",
    "request_provisional_closure",
    "request_post_maintenance_verification",
    "resume_process",
    "cancel_process",
    "request_dependency_waiver",
    "request_condition_check",
    *PUMP_STATION_TEMPORAL_EVIDENCE_ACTION_NAMES,
)


_ACTION_TYPES: dict[str, type[object]] = {
    "continue_operation": ContinueOperation,
    "request_duty_assignment": RequestDutyAssignment,
    "request_inspection": RequestInspection,
    "request_obstruction_clearance": RequestObstructionClearance,
    "request_functional_check": RequestFunctionalCheck,
    "request_provisional_return": RequestProvisionalReturn,
    "request_provisional_closure": RequestProvisionalClosure,
    "request_post_maintenance_verification": RequestVerification,
    "resume_process": ResumeProcess,
    "cancel_process": CancelProcess,
    "request_dependency_waiver": RequestDependencyWaiver,
    "request_condition_check": RequestConditionCheck,
}

_TEMPORAL_ARGUMENT_SCHEMAS: dict[str, dict[str, JsonValue]] = {
    "search_evidence": {
        "additionalProperties": False,
        "description": "Actor-visible arguments for one bounded documentary search.",
        "properties": {
            "limit": {"default": 5, "title": "Limit", "type": "integer"},
            "query": {"title": "Query", "type": "string"},
            "scope": {"default": "all", "title": "Scope", "type": "string"},
        },
        "required": ["query"],
        "title": "TemporalEvidenceSearchArguments",
        "type": "object",
    },
    "fetch_evidence": {
        "additionalProperties": False,
        "description": "Actor-visible arguments for one opaque-reference fetch.",
        "properties": {"reference": {"title": "Reference", "type": "string"}},
        "required": ["reference"],
        "title": "TemporalEvidenceFetchArguments",
        "type": "object",
    },
}

_ACTION_DESCRIPTIONS = {
    "continue_operation": "Continue the permitted mode to the next declared decision event.",
    "request_duty_assignment": "Request an ordered assignment of eligible pumps to declared service.",
    "request_inspection": "Request a scheduled inspection of one named pump.",
    "request_obstruction_clearance": "Request clearance against named inspection evidence.",
    "request_functional_check": "Request one controlled test for a pump in the test-only boundary.",
    "request_provisional_return": "Request return against accepted functional-check evidence.",
    "request_provisional_closure": "Request administrative closure while duties remain open.",
    "request_post_maintenance_verification": "Request independent post-maintenance verification.",
    "resume_process": "Resume blocked or suspended work after dependency checks.",
    "cancel_process": "Cancel live work and release unused reservations.",
    "request_dependency_waiver": "Request one narrow dependency waiver with named evidence.",
    "request_condition_check": "Request one sensor-based condition check for a named pump.",
    "search_evidence": "Search the documentary evidence available to this tenure now.",
    "fetch_evidence": "Fetch content through an opaque reference from an earlier search.",
}


def pump_station_actor_capabilities(
    *,
    task_world_id: str,
    temporal_repository_verified: bool,
) -> WorldActorCapabilityCatalogue:
    """Return the current closed action catalogue when its evidence tools are usable."""

    if not temporal_repository_verified:
        from aec_bench.worlds.stewardship.wastewater_pump_station.reference_system import (
            PumpStationReferenceSystemError,
        )

        raise PumpStationReferenceSystemError(
            "temporal-capability",
            "actor interface requires a verified temporal-evidence repository",
        )
    return WorldActorCapabilityCatalogue(
        task_world_id=task_world_id,
        actions=tuple(
            WorldActorActionCapability(
                name=name,
                description=_ACTION_DESCRIPTIONS[name],
                input_schema=(
                    _TEMPORAL_ARGUMENT_SCHEMAS[name]
                    if name in _TEMPORAL_ARGUMENT_SCHEMAS
                    else cast(dict[str, JsonValue], TypeAdapter(_ACTION_TYPES[name]).json_schema())
                ),
            )
            for name in PUMP_STATION_ACTOR_ACTION_NAMES
        ),
    )


def parse_pump_station_action(
    action_name: str,
    arguments: dict[str, object],
) -> PumpStationAction:
    """Parse one installed action payload into the task-owned action union."""

    action_type = _ACTION_TYPES.get(action_name)
    if action_type is None:
        raise WorldInterfaceError("unknown-actor-action", action_name)
    expected = {field.name for field in fields(cast(Any, action_type))}
    unexpected = set(arguments) - expected
    if unexpected:
        names = ", ".join(sorted(unexpected))
        raise WorldInterfaceError("actor-action-arguments", f"unexpected arguments for {action_name}: {names}")
    try:
        validated = TypeAdapter(action_type).validate_python(arguments)
    except (ValidationError, ValueError) as error:
        raise WorldInterfaceError(
            "actor-action-arguments",
            f"invalid arguments for {action_name}: {error}",
        ) from error
    return cast(PumpStationAction, validated)


def pump_station_temporal_access_arguments(
    request: WorldActorActionRequest,
) -> tuple[NonEmptyStr, NonEmptyStr, int] | NonEmptyStr:
    """Validate one temporal access request without creating a world transition."""

    if request.action_name not in PUMP_STATION_TEMPORAL_EVIDENCE_ACTION_NAMES:
        raise WorldInterfaceError("actor-action-unavailable", request.action_name)
    expected = {"query", "scope", "limit"} if request.action_name == "search_evidence" else {"reference"}
    unexpected = set(request.arguments) - expected
    if unexpected:
        names = ", ".join(sorted(unexpected))
        raise WorldInterfaceError("actor-action-arguments", f"unexpected arguments for {request.action_name}: {names}")

    if request.action_name == "fetch_evidence":
        reference = request.arguments.get("reference")
        if not isinstance(reference, str) or not reference:
            raise WorldInterfaceError("actor-action-arguments", "reference must be a non-empty string")
        return reference

    query = request.arguments.get("query")
    scope = request.arguments.get("scope", "all")
    limit = request.arguments.get("limit", 5)
    if not isinstance(query, str) or not query:
        raise WorldInterfaceError("actor-action-arguments", "query must be a non-empty string")
    if not isinstance(scope, str) or not scope:
        raise WorldInterfaceError("actor-action-arguments", "scope must be a non-empty string")
    if type(limit) is not int:
        raise WorldInterfaceError("actor-action-arguments", "limit must be an integer")
    return query, scope, limit
