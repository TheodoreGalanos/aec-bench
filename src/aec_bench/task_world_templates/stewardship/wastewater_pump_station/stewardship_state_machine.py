# ABOUTME: Applies current actor proposals and root controls to the coupled pump world.
# ABOUTME: Contains no historical state engine, treatment scheduler, or migration path.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any, TypeVar, cast

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpCondition,
    PumpStationCoupledModel,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PUMP_STATION_COUPLED_TREATMENT_VERSION,
    CancelProcess,
    ContinueOperation,
    PumpStationCommonBoundaryRequest,
    PumpStationCoupledStewardshipState,
    PumpStationCoupledTransition,
    PumpStationCoupledTransitionReceipt,
    PumpStationCoupledTreatmentRequest,
    PumpStationOperationsBoundaryReviewRequest,
    PumpStationProcessOutcomeRequest,
    PumpStationProposal,
    PumpStationProposalError,
    PumpStationRootControl,
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
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationCoupledActorView,
    PumpStationInformationSet,
    bind_information_set,
    coupled_actor_view_id,
)


def apply_coupled_stewardship_proposal(
    model: PumpStationCoupledModel,
    state: PumpStationCoupledStewardshipState,
    proposal: PumpStationProposal,
    *,
    information_set: PumpStationInformationSet,
) -> PumpStationCoupledTransition:
    """Apply one typed proposal through the current coupled world rules."""
    view = information_set.base_view
    context = proposal.context
    if not isinstance(view, PumpStationCoupledActorView):
        raise PumpStationProposalError(
            "proposal-type",
            "proposal requires a coupled actor view and typed context",
        )
    if view.view_id != coupled_actor_view_id(view):
        raise PumpStationProposalError(
            "proposal-binding",
            "actor view identity differs from its complete content",
        )
    if (
        bind_information_set(view, information_set.observation_history, information_set.current_context)
        != information_set
    ):
        raise PumpStationProposalError(
            "proposal-binding",
            "information set identity differs from its content",
        )
    expected = (
        context.agent_tenure_id,
        context.based_on_sequence,
        context.base_view_id,
        context.information_set_id,
    )
    observed = (
        view.agent_tenure_id,
        state.sequence,
        view.view_id,
        information_set.information_set_id,
    )
    if expected != observed or view.state_id != state.state_id or view.sequence != state.sequence:
        raise PumpStationProposalError(
            "proposal-binding",
            "proposal does not bind the selected state and information set",
        )
    action_name, arguments = _proposal_arguments(proposal)
    from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
        apply_coupled_actor_action,
    )

    return apply_coupled_actor_action(
        state,
        request_id=context.proposal_id,
        action_name=action_name,
        arguments={"reason": context.reason, **arguments},
        model=model,
    )


def _proposal_arguments(proposal: PumpStationProposal) -> tuple[str, dict[str, object]]:
    """Return the current actor operation and exact typed proposal fields."""
    if isinstance(proposal, ContinueOperation):
        return "continue_operation", {}
    if isinstance(proposal, RequestDutyAssignment):
        return (
            "request_duty_assignment",
            {
                "ordered_pump_ids": proposal.ordered_pump_ids,
                "source_outage_id": proposal.source_outage_id,
                "source_backlog_item_id": proposal.source_backlog_item_id,
            },
        )
    if isinstance(proposal, RequestInspection):
        if proposal.backlog_item_id is None:
            raise PumpStationProposalError("proposal-binding", "inspection lacks backlog binding")
        return (
            "request_inspection",
            {"pump_id": proposal.pump_id, "backlog_item_id": proposal.backlog_item_id},
        )
    if isinstance(proposal, RequestObstructionClearance):
        if proposal.backlog_item_id is None:
            raise PumpStationProposalError("proposal-binding", "clearance lacks backlog binding")
        return (
            "request_obstruction_clearance",
            {
                "pump_id": proposal.pump_id,
                "backlog_item_id": proposal.backlog_item_id,
                "inspection_evidence_id": proposal.inspection_evidence_id,
            },
        )
    if isinstance(proposal, RequestFunctionalCheck):
        return (
            "request_functional_check",
            {"pump_id": proposal.pump_id, "backlog_item_id": proposal.backlog_item_id},
        )
    if isinstance(proposal, RequestProvisionalReturn):
        return (
            "request_provisional_return",
            {
                "pump_id": proposal.pump_id,
                "functional_check_evidence_id": proposal.functional_check_evidence_id,
            },
        )
    if isinstance(proposal, RequestProvisionalClosure):
        return "request_provisional_closure", {"work_order_id": proposal.work_order_id}
    if isinstance(proposal, RequestVerification):
        if proposal.backlog_item_id is None:
            raise PumpStationProposalError("proposal-binding", "verification lacks backlog binding")
        return (
            "request_post_maintenance_verification",
            {"pump_id": proposal.pump_id, "backlog_item_id": proposal.backlog_item_id},
        )
    if isinstance(proposal, ResumeProcess):
        return "resume_process", {"process_id": proposal.process_id}
    if isinstance(proposal, CancelProcess):
        return "cancel_process", {"process_id": proposal.process_id}
    if isinstance(proposal, RequestConditionCheck):
        return "request_condition_check", {"pump_id": proposal.pump_id}
    if isinstance(proposal, RequestDependencyWaiver):
        return (
            "request_dependency_waiver",
            {
                "process_id": proposal.process_id,
                "dependency_id": proposal.dependency_id,
                "evidence_id": proposal.evidence_id,
            },
        )
    raise PumpStationProposalError(
        "proposal-type",
        f"unsupported proposal type {type(proposal).__name__}",
    )


_RecordT = TypeVar("_RecordT")


def _changed_owner_ids(
    before: tuple[_RecordT, ...],
    after: tuple[_RecordT, ...],
    identity: Callable[[_RecordT], str],
) -> tuple[str, ...]:
    before_by_id = {identity(item): item for item in before}
    after_by_id = {identity(item): item for item in after}
    return tuple(
        sorted(
            record_id
            for record_id in before_by_id.keys() | after_by_id.keys()
            if before_by_id.get(record_id) != after_by_id.get(record_id)
        )
    )


def _liability_owner_records(state: PumpStationCoupledStewardshipState) -> dict[str, object]:
    owners: dict[str, object] = {item.obligation_id: item for item in state.obligations}
    owners.update({item.episode_id: item for item in state.outage_episodes})
    owners.update({item.item_id: item for item in state.backlog if item.generation_rule_id in {"WG-06", "WG-07"}})
    return owners


def _changed_liability_owner_ids(
    before: PumpStationCoupledStewardshipState,
    after: PumpStationCoupledStewardshipState,
) -> tuple[str, ...]:
    before_owners = _liability_owner_records(before)
    after_owners = _liability_owner_records(after)
    return tuple(
        sorted(
            owner_id
            for owner_id in before_owners.keys() | after_owners.keys()
            if before_owners.get(owner_id) != after_owners.get(owner_id)
        )
    )


def _required_authorities(action_kind: str) -> tuple[str, ...]:
    if action_kind == "request_functional_check":
        return ("maintenance", "operations")
    if action_kind in {
        "continue_operation",
        "request_duty_assignment",
        "request_provisional_return",
        "operations_boundary_review",
        "common_boundary_control",
    }:
        return ("operations",)
    if action_kind in {
        "request_inspection",
        "request_obstruction_clearance",
        "resume_process",
        "cancel_process",
    }:
        return ("maintenance",)
    if action_kind in {"request_post_maintenance_verification", "process_outcome"}:
        return ("verification",)
    if action_kind in {"request_provisional_closure", "request_dependency_waiver"}:
        return ("work_management",)
    if action_kind == "request_condition_check":
        return ("engineering",)
    return ("host",)


def finish_coupled_transition(
    before: PumpStationCoupledStewardshipState,
    after: PumpStationCoupledStewardshipState,
    *,
    request_id: str,
    action_kind: str,
    actor_action: bool,
    target_id: str | None,
    backlog_item_id: str | None,
    reason: str,
    changed_record_ids: tuple[str, ...],
    operating_interval_id: str | None = None,
    authority_requirements: tuple[str, ...] | None = None,
) -> PumpStationCoupledTransition:
    """Finish one transition with the current task-owned receipt rules."""
    sequenced = replace(after, sequence=before.sequence + 1)
    receipt = PumpStationCoupledTransitionReceipt(
        sequence=sequenced.sequence,
        transition_id=f"transition-{sequenced.sequence}-{request_id}",
        request_id=request_id,
        action_or_control_kind=action_kind,
        actor_action=actor_action,
        authority_outcome="permitted",
        required_authorities=authority_requirements or _required_authorities(action_kind),
        authority_decision_detail="All required task authorities accepted the bound request.",
        permit_ids=(f"controlled-test-permit-{request_id}",) if action_kind == "request_functional_check" else (),
        execution_status="applied",
        before_state_id=before.state_id,
        after_state_id=sequenced.state_id,
        start_calendar_seconds=before.calendar_seconds,
        end_calendar_seconds=sequenced.calendar_seconds,
        target_id=target_id,
        backlog_item_id=backlog_item_id,
        reason=reason,
        changed_record_ids=changed_record_ids,
        changed_pool_ids=_changed_owner_ids(
            before.resources.pools, sequenced.resources.pools, lambda item: item.pool_id
        ),
        changed_reservation_ids=_changed_owner_ids(
            before.resource_reservations,
            sequenced.resource_reservations,
            lambda item: item.reservation_id,
        ),
        changed_backlog_item_ids=_changed_owner_ids(before.backlog, sequenced.backlog, lambda item: item.item_id),
        generation_record_ids=_changed_owner_ids(
            before.generation_records,
            sequenced.generation_records,
            lambda item: item.backlog_item_id,
        ),
        changed_liability_owner_ids=_changed_liability_owner_ids(before, sequenced),
        operating_interval_id=operating_interval_id,
    )
    return PumpStationCoupledTransition(state=sequenced, receipt=receipt)


def apply_stewardship_control(
    state: PumpStationCoupledStewardshipState,
    control: PumpStationRootControl,
) -> PumpStationCoupledTransition:
    """Apply one closed root host control through the current coupled rules."""
    from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
        apply_common_boundary_control,
        apply_operations_boundary_review,
        apply_process_outcome,
    )

    if isinstance(control, PumpStationOperationsBoundaryReviewRequest):
        return apply_operations_boundary_review(state, control)
    if isinstance(control, PumpStationProcessOutcomeRequest):
        return apply_process_outcome(state, control)
    if isinstance(control, PumpStationCommonBoundaryRequest):
        return apply_common_boundary_control(state, control)
    if isinstance(control, PumpStationCoupledTreatmentRequest):
        return apply_coupled_treatment(state, control)
    raise PumpStationProposalError("control-type", f"unsupported control type {type(control).__name__}")


def apply_coupled_treatment(
    state: PumpStationCoupledStewardshipState,
    request: PumpStationCoupledTreatmentRequest,
) -> PumpStationCoupledTransition:
    """Apply one current child-only common-cause treatment."""
    if request.version != PUMP_STATION_COUPLED_TREATMENT_VERSION:
        raise PumpStationProposalError("coupled-treatment-version", request.version)
    if request.authority_id != "rollout-host":
        raise PumpStationProposalError("coupled-treatment-authority", request.authority_id)
    if request.base_state_id != state.state_id:
        raise PumpStationProposalError("stale-coupled-treatment", request.request_id)
    if not request.treatment_label.strip():
        raise PumpStationProposalError("coupled-treatment-label", request.request_id)
    pump_ids = tuple(pump.pump_id for pump in state.physical.pumps)
    if (
        not request.affected_pump_ids
        or len(set(request.affected_pump_ids)) != len(request.affected_pump_ids)
        or not set(request.affected_pump_ids) <= set(pump_ids)
    ):
        raise PumpStationProposalError("coupled-treatment-targets", request.request_id)
    if request.obstruction_delta < 0 or request.clearance_loss_delta < 0:
        raise PumpStationProposalError("coupled-treatment-delta", request.request_id)
    updated_pumps: list[Any] = []
    for pump in state.physical.pumps:
        if pump.pump_id not in request.affected_pump_ids:
            updated_pumps.append(pump)
            continue
        obstruction = pump.condition.obstruction + request.obstruction_delta
        clearance_loss = pump.condition.clearance_loss + request.clearance_loss_delta
        if obstruction > 1 or clearance_loss > 1:
            raise PumpStationProposalError("coupled-treatment-range", pump.pump_id)
        updated_pumps.append(
            replace(
                pump,
                condition=PumpCondition(obstruction=obstruction, clearance_loss=clearance_loss),
            )
        )
    updated = replace(
        state,
        physical=replace(state.physical, pumps=cast(tuple[Any, Any, Any], tuple(updated_pumps))),
        event_effect_ids=(*state.event_effect_ids, request.content_id),
    )
    return finish_coupled_transition(
        state,
        updated,
        request_id=request.request_id,
        action_kind="coupled_physical_treatment",
        actor_action=False,
        target_id=None,
        backlog_item_id=None,
        reason="Apply the authorised child-only common-cause treatment.",
        changed_record_ids=(request.content_id, *request.affected_pump_ids),
    )


__all__ = [
    "apply_coupled_stewardship_proposal",
    "apply_coupled_treatment",
    "apply_stewardship_control",
    "finish_coupled_transition",
]
