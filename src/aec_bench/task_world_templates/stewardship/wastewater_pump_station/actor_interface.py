# ABOUTME: Defines the current pump-station actor action catalogue and exact task argument schemas.
# ABOUTME: Converts validated actions to task proposals while host-owned decision context stays private.

from __future__ import annotations

from typing import cast

from pydantic import JsonValue, ValidationError

from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.contracts.world_interface import (
    WorldActorActionCapability,
    WorldActorActionRequest,
    WorldActorCapabilityCatalogue,
    WorldInterfaceError,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    CancelProcess,
    ContinueOperation,
    ProposalContext,
    PumpStationProposal,
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


class _ReasonArguments(FrozenStrictModel):
    reason: NonEmptyStr


class _PumpArguments(_ReasonArguments):
    pump_id: NonEmptyStr


class _ProvisionalReturnArguments(_PumpArguments):
    functional_check_evidence_id: NonEmptyStr


class _WorkOrderArguments(_ReasonArguments):
    work_order_id: NonEmptyStr


class _DutyAssignmentArguments(_ReasonArguments):
    ordered_pump_ids: tuple[NonEmptyStr, ...]
    source_outage_id: NonEmptyStr | None = None
    source_backlog_item_id: NonEmptyStr | None = None


class _BacklogPumpArguments(_PumpArguments):
    backlog_item_id: NonEmptyStr


class _BacklogClearanceArguments(_BacklogPumpArguments):
    inspection_evidence_id: NonEmptyStr


class _ProcessArguments(_ReasonArguments):
    process_id: NonEmptyStr


class _DependencyWaiverArguments(_ProcessArguments):
    dependency_id: NonEmptyStr
    evidence_id: NonEmptyStr


class TemporalEvidenceSearchArguments(FrozenStrictModel):
    """Actor-visible arguments for one bounded documentary search."""

    query: NonEmptyStr
    scope: NonEmptyStr = "all"
    limit: int = 5


class TemporalEvidenceFetchArguments(FrozenStrictModel):
    """Actor-visible arguments for one opaque-reference fetch."""

    reference: NonEmptyStr


_ARGUMENT_MODELS: dict[str, type[FrozenStrictModel]] = {
    "continue_operation": _ReasonArguments,
    "request_duty_assignment": _DutyAssignmentArguments,
    "request_inspection": _BacklogPumpArguments,
    "request_obstruction_clearance": _BacklogClearanceArguments,
    "request_functional_check": _BacklogPumpArguments,
    "request_provisional_return": _ProvisionalReturnArguments,
    "request_provisional_closure": _WorkOrderArguments,
    "request_post_maintenance_verification": _BacklogPumpArguments,
    "resume_process": _ProcessArguments,
    "cancel_process": _ProcessArguments,
    "request_dependency_waiver": _DependencyWaiverArguments,
    "request_condition_check": _PumpArguments,
    "search_evidence": TemporalEvidenceSearchArguments,
    "fetch_evidence": TemporalEvidenceFetchArguments,
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
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_system import (
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
                input_schema=cast(
                    dict[str, JsonValue],
                    _ARGUMENT_MODELS[name].model_json_schema(),
                ),
            )
            for name in PUMP_STATION_ACTOR_ACTION_NAMES
        ),
    )


def validate_pump_station_actor_arguments(
    action_name: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    """Validate one action against the exact advertised input schema."""

    model = _ARGUMENT_MODELS.get(action_name)
    if model is None:
        raise WorldInterfaceError("unknown-actor-action", action_name)
    try:
        validated = model.model_validate(arguments)
    except ValidationError as error:
        raise WorldInterfaceError(
            "actor-action-arguments",
            f"invalid arguments for {action_name}: {error}",
        ) from error
    return cast(dict[str, object], validated.model_dump(mode="python", exclude_none=True))


def pump_station_temporal_access_arguments(
    request: WorldActorActionRequest,
) -> TemporalEvidenceSearchArguments | TemporalEvidenceFetchArguments:
    """Validate one temporal access request without creating a world proposal."""

    try:
        if request.action_name == "search_evidence":
            return TemporalEvidenceSearchArguments.model_validate(request.arguments)
        if request.action_name == "fetch_evidence":
            return TemporalEvidenceFetchArguments.model_validate(request.arguments)
        raise WorldInterfaceError("actor-action-unavailable", request.action_name)
    except ValidationError as error:
        raise WorldInterfaceError("actor-action-arguments", str(error)) from error


def pump_station_proposal_from_validated_arguments(
    *,
    action_name: str,
    arguments: dict[str, object],
    context: ProposalContext,
) -> PumpStationProposal:
    """Create one typed proposal from validated arguments and private host context."""

    model_type = _ARGUMENT_MODELS.get(action_name)
    if model_type is None or action_name in PUMP_STATION_TEMPORAL_EVIDENCE_ACTION_NAMES:
        raise WorldInterfaceError("actor-action-unavailable", action_name)
    try:
        validated = model_type.model_validate(arguments)
    except ValidationError as error:
        raise WorldInterfaceError(
            "actor-action-arguments",
            f"invalid arguments for {action_name}: {error}",
        ) from error
    reason = getattr(validated, "reason", None)
    if reason != context.reason:
        raise WorldInterfaceError(
            "actor-action-arguments",
            "proposal context reason differs from the actor arguments",
        )
    if action_name == "continue_operation":
        return ContinueOperation(context=context)
    if action_name == "request_duty_assignment":
        duty = cast(_DutyAssignmentArguments, validated)
        return RequestDutyAssignment(
            context=context,
            ordered_pump_ids=duty.ordered_pump_ids,
            source_outage_id=duty.source_outage_id,
            source_backlog_item_id=duty.source_backlog_item_id,
        )
    if action_name == "request_inspection":
        inspection = cast(_BacklogPumpArguments, validated)
        return RequestInspection(
            context=context, pump_id=inspection.pump_id, backlog_item_id=inspection.backlog_item_id
        )
    if action_name == "request_obstruction_clearance":
        clearance = cast(_BacklogClearanceArguments, validated)
        return RequestObstructionClearance(
            context=context,
            pump_id=clearance.pump_id,
            inspection_evidence_id=clearance.inspection_evidence_id,
            backlog_item_id=clearance.backlog_item_id,
        )
    if action_name == "request_functional_check":
        functional = cast(_BacklogPumpArguments, validated)
        return RequestFunctionalCheck(
            context=context,
            pump_id=functional.pump_id,
            backlog_item_id=functional.backlog_item_id,
        )
    if action_name == "request_provisional_return":
        returned = cast(_ProvisionalReturnArguments, validated)
        return RequestProvisionalReturn(
            context=context,
            pump_id=returned.pump_id,
            functional_check_evidence_id=returned.functional_check_evidence_id,
        )
    if action_name == "request_provisional_closure":
        return RequestProvisionalClosure(
            context=context, work_order_id=cast(_WorkOrderArguments, validated).work_order_id
        )
    if action_name == "request_post_maintenance_verification":
        verification = cast(_BacklogPumpArguments, validated)
        return RequestVerification(
            context=context,
            pump_id=verification.pump_id,
            backlog_item_id=verification.backlog_item_id,
        )
    if action_name == "resume_process":
        return ResumeProcess(context=context, process_id=cast(_ProcessArguments, validated).process_id)
    if action_name == "cancel_process":
        return CancelProcess(context=context, process_id=cast(_ProcessArguments, validated).process_id)
    if action_name == "request_condition_check":
        return RequestConditionCheck(context=context, pump_id=cast(_PumpArguments, validated).pump_id)
    waiver = cast(_DependencyWaiverArguments, validated)
    return RequestDependencyWaiver(
        context=context,
        process_id=waiver.process_id,
        dependency_id=waiver.dependency_id,
        evidence_id=waiver.evidence_id,
    )
