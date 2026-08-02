# ABOUTME: Defines pump-station actor action schemas and converts exact requests to proposals.
# ABOUTME: Keeps task action names, fields, and proposal semantics outside the shared host contract.

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
    RequestConditionalDeferral,
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
    TransferDuty,
)

PUMP_STATION_ACTOR_INTERFACE_VERSION = "pump-station.actor.v1"
PUMP_STATION_ACTOR_INTERFACE_VERSION_V2 = "pump-station.actor.v2"
PUMP_STATION_ACTOR_ACTION_NAMES = (
    "continue_operation",
    "transfer_duty",
    "request_inspection",
    "request_conditional_deferral",
    "request_obstruction_clearance",
    "request_provisional_return",
    "request_provisional_closure",
    "request_post_maintenance_verification",
    "resume_process",
    "cancel_process",
    "request_dependency_waiver",
    "request_condition_check",
)
PUMP_STATION_TEMPORAL_EVIDENCE_ACTION_NAMES = (
    "search_evidence",
    "fetch_evidence",
)
PUMP_STATION_ACTOR_ACTION_NAMES_V2 = (
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
    "search_evidence",
    "fetch_evidence",
)


class _ReasonArguments(FrozenStrictModel):
    reason: NonEmptyStr


class _PumpArguments(_ReasonArguments):
    pump_id: NonEmptyStr


class _ObstructionClearanceArguments(_PumpArguments):
    inspection_evidence_id: NonEmptyStr


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


class _EvidenceRelianceArguments(FrozenStrictModel):
    relied_on_evidence_refs: tuple[NonEmptyStr, ...]


_PROPOSAL_ARGUMENT_MODELS: dict[str, type[_ReasonArguments]] = {
    "continue_operation": _ReasonArguments,
    "transfer_duty": _ReasonArguments,
    "request_inspection": _PumpArguments,
    "request_conditional_deferral": _PumpArguments,
    "request_obstruction_clearance": _ObstructionClearanceArguments,
    "request_provisional_return": _ProvisionalReturnArguments,
    "request_provisional_closure": _WorkOrderArguments,
    "request_post_maintenance_verification": _PumpArguments,
    "resume_process": _ProcessArguments,
    "cancel_process": _ProcessArguments,
    "request_dependency_waiver": _DependencyWaiverArguments,
    "request_condition_check": _PumpArguments,
}
_ARGUMENT_MODELS: dict[str, type[FrozenStrictModel]] = {
    **_PROPOSAL_ARGUMENT_MODELS,
    "search_evidence": TemporalEvidenceSearchArguments,
    "fetch_evidence": TemporalEvidenceFetchArguments,
}
_ARGUMENT_MODELS_V2: dict[str, type[FrozenStrictModel]] = {
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
    "transfer_duty": "Request the permitted transfer from duty to standby pump.",
    "request_inspection": "Request a scheduled inspection of one named pump.",
    "request_conditional_deferral": "Request the fixed transfer-then-isolate deferral.",
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


def pump_station_actor_capabilities_v2(
    *,
    task_world_id: str,
    temporal_repository_verified: bool,
) -> WorldActorCapabilityCatalogue:
    """Return the exact ASW-8 catalogue only when its evidence tools are usable."""
    if not temporal_repository_verified:
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_system import (
            PumpStationReferenceSystemError,
        )

        raise PumpStationReferenceSystemError(
            "temporal-capability",
            "actor interface v2 requires a verified temporal-evidence repository",
        )
    return WorldActorCapabilityCatalogue(
        task_world_id=task_world_id,
        interface_version=PUMP_STATION_ACTOR_INTERFACE_VERSION_V2,
        observation_schema_ref="pump-station.actor-view.v4",
        actions=tuple(
            WorldActorActionCapability(
                name=name,
                description=_ACTION_DESCRIPTIONS[name],
                input_schema=cast(
                    dict[str, JsonValue],
                    _ARGUMENT_MODELS_V2[name].model_json_schema(),
                ),
            )
            for name in PUMP_STATION_ACTOR_ACTION_NAMES_V2
        ),
    )


def validate_pump_station_actor_arguments_v2(
    action_name: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    """Validate one ASW-8 action against the exact advertised input schema."""
    model = _ARGUMENT_MODELS_V2.get(action_name)
    if model is None:
        raise WorldInterfaceError("unknown-actor-action", action_name)
    try:
        validated = model.model_validate(arguments)
    except ValidationError as error:
        raise WorldInterfaceError(
            "actor-action-arguments",
            f"invalid arguments for {action_name}: {error}",
        ) from error
    return cast(
        dict[str, object],
        validated.model_dump(mode="python", exclude_none=True),
    )


def pump_station_proposal_from_validated_arguments_v2(
    *,
    action_name: str,
    arguments: dict[str, object],
    context: ProposalContext,
) -> PumpStationProposal:
    """Create one typed ASW-8 proposal from validated actor arguments."""
    model_type = _ARGUMENT_MODELS_V2.get(action_name)
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
        return RequestInspection(
            context=context,
            pump_id=cast(_BacklogPumpArguments, validated).pump_id,
        )
    if action_name == "request_obstruction_clearance":
        clearance = cast(_BacklogClearanceArguments, validated)
        return RequestObstructionClearance(
            context=context,
            pump_id=clearance.pump_id,
            inspection_evidence_id=clearance.inspection_evidence_id,
        )
    if action_name == "request_functional_check":
        functional = cast(_BacklogPumpArguments, validated)
        return RequestFunctionalCheck(
            context=context,
            pump_id=functional.pump_id,
            backlog_item_id=functional.backlog_item_id,
        )
    if action_name == "request_provisional_return":
        provisional_return = cast(_ProvisionalReturnArguments, validated)
        return RequestProvisionalReturn(
            context=context,
            pump_id=provisional_return.pump_id,
            functional_check_evidence_id=provisional_return.functional_check_evidence_id,
        )
    if action_name == "request_provisional_closure":
        return RequestProvisionalClosure(
            context=context,
            work_order_id=cast(_WorkOrderArguments, validated).work_order_id,
        )
    if action_name == "request_post_maintenance_verification":
        return RequestVerification(
            context=context,
            pump_id=cast(_BacklogPumpArguments, validated).pump_id,
        )
    if action_name == "resume_process":
        return ResumeProcess(
            context=context,
            process_id=cast(_ProcessArguments, validated).process_id,
        )
    if action_name == "cancel_process":
        return CancelProcess(
            context=context,
            process_id=cast(_ProcessArguments, validated).process_id,
        )
    if action_name == "request_condition_check":
        return RequestConditionCheck(
            context=context,
            pump_id=cast(_PumpArguments, validated).pump_id,
        )
    waiver = cast(_DependencyWaiverArguments, validated)
    return RequestDependencyWaiver(
        context=context,
        process_id=waiver.process_id,
        dependency_id=waiver.dependency_id,
        evidence_id=waiver.evidence_id,
    )


def pump_station_actor_capabilities(
    *,
    task_world_id: str,
    rich_work_processes: bool,
    evidence_health: bool = False,
    temporal_evidence: bool = False,
) -> WorldActorCapabilityCatalogue:
    """Return the closed task-owned action catalogue for the selected world version."""

    names: tuple[str, ...]
    if temporal_evidence:
        names = (
            *PUMP_STATION_ACTOR_ACTION_NAMES,
            *PUMP_STATION_TEMPORAL_EVIDENCE_ACTION_NAMES,
        )
    elif evidence_health:
        names = PUMP_STATION_ACTOR_ACTION_NAMES
    elif rich_work_processes:
        names = PUMP_STATION_ACTOR_ACTION_NAMES[:11]
    else:
        names = PUMP_STATION_ACTOR_ACTION_NAMES[:8]
    actions = tuple(
        WorldActorActionCapability(
            name=name,
            description=_ACTION_DESCRIPTIONS[name],
            input_schema=_actor_input_schema(
                name,
                temporal_evidence=temporal_evidence,
            ),
        )
        for name in names
    )
    return WorldActorCapabilityCatalogue(
        task_world_id=task_world_id,
        interface_version=(
            "pump-station.actor.temporal-evidence.v1" if temporal_evidence else PUMP_STATION_ACTOR_INTERFACE_VERSION
        ),
        observation_schema_ref=(
            "pump-station.actor-view.v3"
            if evidence_health
            else "pump-station.actor-view.v2"
            if rich_work_processes
            else "pump-station.actor-view.v1"
        ),
        actions=actions,
    )


def pump_station_evidence_reliance_refs(
    request: WorldActorActionRequest,
) -> tuple[str, ...]:
    """Return validated explicit evidence reliance from one temporal world action."""

    raw = request.arguments.get("relied_on_evidence_refs")
    if raw is None:
        return ()
    try:
        reliance = _EvidenceRelianceArguments.model_validate({"relied_on_evidence_refs": raw})
    except ValidationError as exc:
        raise WorldInterfaceError(
            "actor-action-arguments-invalid",
            str(exc),
        ) from exc
    if len(reliance.relied_on_evidence_refs) != len(set(reliance.relied_on_evidence_refs)):
        raise WorldInterfaceError(
            "actor-action-arguments-invalid",
            "relied-on evidence references must be distinct",
        )
    return tuple(reliance.relied_on_evidence_refs)


def pump_station_request_without_evidence_reliance(
    request: WorldActorActionRequest,
) -> WorldActorActionRequest:
    """Return the unchanged world-proposal fields without temporal reliance metadata."""

    return WorldActorActionRequest(
        request_id=request.request_id,
        action_name=request.action_name,
        binding=request.binding,
        arguments={key: value for key, value in request.arguments.items() if key != "relied_on_evidence_refs"},
    )


def _actor_input_schema(
    name: str,
    *,
    temporal_evidence: bool,
) -> dict[str, JsonValue]:
    schema = cast(dict[str, JsonValue], _ARGUMENT_MODELS[name].model_json_schema())
    if not temporal_evidence or name in PUMP_STATION_TEMPORAL_EVIDENCE_ACTION_NAMES:
        return schema
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        raise TypeError("actor argument schema lacks properties")
    properties["relied_on_evidence_refs"] = {
        "default": [],
        "items": {"type": "string"},
        "title": "Relied On Evidence Refs",
        "type": "array",
        "uniqueItems": True,
    }
    return schema


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
    except ValidationError as exc:
        raise WorldInterfaceError(
            "actor-action-arguments-invalid",
            str(exc),
        ) from exc


def pump_station_proposal_from_actor_request(
    request: WorldActorActionRequest,
) -> PumpStationProposal:
    """Validate task-owned fields and create the one requested typed proposal."""

    model_type = _PROPOSAL_ARGUMENT_MODELS.get(request.action_name)
    if model_type is None:
        raise WorldInterfaceError("actor-action-unavailable", request.action_name)
    try:
        arguments = model_type.model_validate(request.arguments)
    except ValidationError as exc:
        raise WorldInterfaceError(
            "actor-action-arguments-invalid",
            str(exc),
        ) from exc
    context = ProposalContext(
        proposal_id=request.request_id,
        agent_tenure_id=request.binding.agent_tenure_id,
        based_on_sequence=request.binding.sequence,
        base_view_id=request.binding.actor_view_id,
        information_set_id=request.binding.information_set_id,
        reason=arguments.reason,
    )
    if request.action_name == "continue_operation":
        return ContinueOperation(context=context)
    if request.action_name == "transfer_duty":
        return TransferDuty(context=context)
    if request.action_name == "request_inspection":
        return RequestInspection(context=context, pump_id=cast(_PumpArguments, arguments).pump_id)
    if request.action_name == "request_condition_check":
        return RequestConditionCheck(
            context=context,
            pump_id=cast(_PumpArguments, arguments).pump_id,
        )
    if request.action_name == "request_conditional_deferral":
        return RequestConditionalDeferral(
            context=context,
            pump_id=cast(_PumpArguments, arguments).pump_id,
        )
    if request.action_name == "request_obstruction_clearance":
        obstruction = cast(_ObstructionClearanceArguments, arguments)
        return RequestObstructionClearance(
            context=context,
            pump_id=obstruction.pump_id,
            inspection_evidence_id=obstruction.inspection_evidence_id,
        )
    if request.action_name == "request_provisional_return":
        provisional_return = cast(_ProvisionalReturnArguments, arguments)
        return RequestProvisionalReturn(
            context=context,
            pump_id=provisional_return.pump_id,
            functional_check_evidence_id=provisional_return.functional_check_evidence_id,
        )
    if request.action_name == "request_provisional_closure":
        return RequestProvisionalClosure(
            context=context,
            work_order_id=cast(_WorkOrderArguments, arguments).work_order_id,
        )
    if request.action_name == "request_post_maintenance_verification":
        return RequestVerification(
            context=context,
            pump_id=cast(_PumpArguments, arguments).pump_id,
        )
    if request.action_name == "resume_process":
        return ResumeProcess(
            context=context,
            process_id=cast(_ProcessArguments, arguments).process_id,
        )
    if request.action_name == "cancel_process":
        return CancelProcess(
            context=context,
            process_id=cast(_ProcessArguments, arguments).process_id,
        )
    dependency_waiver = cast(_DependencyWaiverArguments, arguments)
    return RequestDependencyWaiver(
        context=context,
        process_id=dependency_waiver.process_id,
        dependency_id=dependency_waiver.dependency_id,
        evidence_id=dependency_waiver.evidence_id,
    )
