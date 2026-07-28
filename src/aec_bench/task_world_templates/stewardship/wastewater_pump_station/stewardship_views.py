# ABOUTME: Projects actor-visible pump-station state and structured handover records.
# ABOUTME: Binds each proposal to its exact view, observation history, and current context.

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_kernel import (
    assess_pump_station,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpStationEnvironment,
    PumpStationModel,
    PumpStationObservation,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    stewardship_content_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    ContinueOperation,
    ProposalContext,
    PumpStationEvidence,
    PumpStationObligation,
    PumpStationObligationStatus,
    PumpStationProcess,
    PumpStationProcessStatus,
    PumpStationProposal,
    PumpStationRestriction,
    PumpStationRestrictionStatus,
    PumpStationStewardshipState,
    PumpStationTransition,
    PumpStationWorkOrder,
    PumpStationWorkResources,
    RequestConditionalDeferral,
    RequestInspection,
    RequestObstructionClearance,
    RequestProvisionalClosure,
    RequestProvisionalReturn,
    RequestVerification,
    TransferDuty,
)


class PumpStationContinuityCarrier(StrEnum):
    """Actor-visible continuity material supplied to one proposal context."""

    CURRENT_ACTOR_VIEW = "current_actor_view"
    STRUCTURED_HANDOVER = "structured_handover"


class PumpStationAssignment(StrEnum):
    """Current public operating assignment of one pump."""

    DUTY = "duty"
    STANDBY = "standby"


@dataclass(frozen=True, slots=True)
class PumpStationProjectionContext:
    """Host-owned identities and time origins for one actor observation."""

    episode_id: str
    world_branch_id: str
    actor_id: str
    agent_tenure_id: str
    episode_started_at_seconds: int
    tenure_started_at_seconds: int
    projection_policy_id: str
    source_artifact_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "episode_id",
            "world_branch_id",
            "actor_id",
            "agent_tenure_id",
            "projection_policy_id",
        ):
            _require_text(getattr(self, field_name), field_name)
        _require_non_negative(
            self.episode_started_at_seconds,
            "episode_started_at_seconds",
        )
        _require_non_negative(
            self.tenure_started_at_seconds,
            "tenure_started_at_seconds",
        )
        _require_distinct_text(self.source_artifact_ids, "source_artifact_ids")


@dataclass(frozen=True, slots=True)
class PumpStationPumpClockView:
    """Actor-visible assignment and exposure clocks without latent condition."""

    pump_id: str
    assignment: PumpStationAssignment
    runtime_seconds: int
    completed_starts: int


@dataclass(frozen=True, slots=True)
class PumpStationCurrentStateView:
    """Complete authorised present state without latent or future information."""

    state_id: str
    state_sequence: int
    calendar_seconds: int
    duty_pump_id: str
    standby_pump_id: str
    duty_transfer_count: int
    pumps: tuple[PumpStationPumpClockView, ...]
    environment: PumpStationEnvironment
    observation: PumpStationObservation
    resources: PumpStationWorkResources
    restrictions: tuple[PumpStationRestriction, ...]
    obligations: tuple[PumpStationObligation, ...]
    work_orders: tuple[PumpStationWorkOrder, ...]
    processes: tuple[PumpStationProcess, ...]
    evidence: tuple[PumpStationEvidence, ...]


@dataclass(frozen=True, slots=True)
class PumpStationActorView:
    """Immutable actor-specific observation of one continuing episode."""

    view_id: str
    episode_id: str
    world_branch_id: str
    actor_id: str
    agent_tenure_id: str
    projection_policy_id: str
    creation_transition_id: str | None
    episode_elapsed_seconds: int
    tenure_elapsed_seconds: int
    source_artifact_ids: tuple[str, ...]
    current_state: PumpStationCurrentStateView


@dataclass(frozen=True, slots=True)
class PumpStationActorHistoryEntry:
    """Bounded actor-visible account of one realised transition."""

    transition_id: str
    sequence: int
    occurred_at_seconds: int
    agent_tenure_id: str
    proposal_id: str
    action_type: str
    reason: str
    execution: str
    restrictions_changed: tuple[str, ...]
    obligations_changed: tuple[str, ...]
    work_orders_changed: tuple[str, ...]
    evidence_created: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PumpStationStructuredHandover:
    """Fresh-tenure current view plus bounded prior stewardship context."""

    handover_id: str
    from_tenure_id: str
    to_tenure_id: str
    created_at_seconds: int
    current_actor_view: PumpStationActorView
    history: tuple[PumpStationActorHistoryEntry, ...]


@dataclass(frozen=True, slots=True)
class PumpStationObservationHistory:
    """Append-only manifest of views shown during one actor tenure."""

    agent_tenure_id: str
    view_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text(self.agent_tenure_id, "agent_tenure_id")
        if not self.view_ids:
            raise ValueError("view_ids must not be empty")
        for view_id in self.view_ids:
            _require_text(view_id, "view_ids")


@dataclass(frozen=True, slots=True)
class PumpStationCurrentContext:
    """Exact non-world material visible when an actor commits a proposal."""

    continuity_carrier: PumpStationContinuityCarrier
    conversation_prefix_id: str | None
    workspace_tool_ids: tuple[str, ...]
    visible_material_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.conversation_prefix_id is not None:
            _require_text(
                self.conversation_prefix_id,
                "conversation_prefix_id",
            )
        _require_distinct_text(
            self.workspace_tool_ids,
            "workspace_tool_ids",
        )
        _require_distinct_text(
            self.visible_material_ids,
            "visible_material_ids",
            allow_empty=True,
        )


@dataclass(frozen=True, slots=True)
class PumpStationInformationSet:
    """Content identity of a base view and exact actor-visible commitment context."""

    information_set_id: str
    base_view: PumpStationActorView
    observation_history: PumpStationObservationHistory
    current_context: PumpStationCurrentContext


_ACTION_TYPES: dict[type[object], str] = {
    ContinueOperation: "continue_operation",
    TransferDuty: "transfer_duty",
    RequestInspection: "request_inspection",
    RequestConditionalDeferral: "request_conditional_deferral",
    RequestObstructionClearance: "request_obstruction_clearance",
    RequestProvisionalReturn: "request_provisional_return",
    RequestProvisionalClosure: "request_provisional_closure",
    RequestVerification: "request_post_maintenance_verification",
}


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _require_non_negative(value: int, field_name: str) -> None:
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")


def _require_distinct_text(
    values: tuple[str, ...],
    field_name: str,
    *,
    allow_empty: bool = False,
) -> None:
    if not values and not allow_empty:
        raise ValueError(f"{field_name} must not be empty")
    for value in values:
        _require_text(value, field_name)
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must not contain duplicates")


def _current_state_view(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
) -> PumpStationCurrentStateView:
    assessment = assess_pump_station(
        model,
        state.physical,
        state.environment,
    )
    if assessment.state != state.physical:
        raise ValueError("physical assessment unexpectedly changed state")
    pumps = tuple(
        PumpStationPumpClockView(
            pump_id=pump.pump_id,
            assignment=(
                PumpStationAssignment.DUTY
                if pump.pump_id == state.physical.duty_pump_id
                else PumpStationAssignment.STANDBY
            ),
            runtime_seconds=pump.exposure.runtime_seconds,
            completed_starts=pump.exposure.completed_starts,
        )
        for pump in state.physical.pumps
    )
    restrictions = tuple(
        restriction for restriction in state.restrictions if restriction.status is PumpStationRestrictionStatus.ACTIVE
    )
    obligations = tuple(
        obligation for obligation in state.obligations if obligation.status is not PumpStationObligationStatus.FULFILLED
    )
    processes = tuple(process for process in state.processes if process.status is PumpStationProcessStatus.IN_PROGRESS)
    visible_state = {
        "state_sequence": state.sequence,
        "calendar_seconds": state.physical.calendar_seconds,
        "duty_pump_id": state.physical.duty_pump_id,
        "standby_pump_id": state.physical.standby_pump_id,
        "duty_transfer_count": state.physical.duty_transfer_count,
        "pumps": pumps,
        "environment": state.environment,
        "observation": assessment.observation,
        "resources": state.resources,
        "restrictions": restrictions,
        "obligations": obligations,
        "work_orders": state.work_orders,
        "processes": processes,
        "evidence": state.evidence,
    }
    return PumpStationCurrentStateView(
        state_id=stewardship_content_id(visible_state),
        state_sequence=state.sequence,
        calendar_seconds=state.physical.calendar_seconds,
        duty_pump_id=state.physical.duty_pump_id,
        standby_pump_id=state.physical.standby_pump_id,
        duty_transfer_count=state.physical.duty_transfer_count,
        pumps=pumps,
        environment=state.environment,
        observation=assessment.observation,
        resources=state.resources,
        restrictions=restrictions,
        obligations=obligations,
        work_orders=state.work_orders,
        processes=processes,
        evidence=state.evidence,
    )


def project_actor_view(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
    context: PumpStationProjectionContext,
) -> PumpStationActorView:
    """Project the complete permitted present state for one actor tenure."""
    now = state.physical.calendar_seconds
    if context.episode_started_at_seconds > now:
        raise ValueError("episode starts after the current station time")
    if context.tenure_started_at_seconds > now:
        raise ValueError("actor tenure starts after the current station time")
    current_state = _current_state_view(model, state)
    creation_transition_id = None if state.sequence == 0 else f"transition-{state.sequence:04d}"
    identity_payload = {
        "episode_id": context.episode_id,
        "world_branch_id": context.world_branch_id,
        "actor_id": context.actor_id,
        "agent_tenure_id": context.agent_tenure_id,
        "projection_policy_id": context.projection_policy_id,
        "creation_transition_id": creation_transition_id,
        "episode_elapsed_seconds": now - context.episode_started_at_seconds,
        "tenure_elapsed_seconds": now - context.tenure_started_at_seconds,
        "source_artifact_ids": context.source_artifact_ids,
        "current_state": current_state,
    }
    return PumpStationActorView(
        view_id=stewardship_content_id(identity_payload),
        episode_id=context.episode_id,
        world_branch_id=context.world_branch_id,
        actor_id=context.actor_id,
        agent_tenure_id=context.agent_tenure_id,
        projection_policy_id=context.projection_policy_id,
        creation_transition_id=creation_transition_id,
        episode_elapsed_seconds=now - context.episode_started_at_seconds,
        tenure_elapsed_seconds=now - context.tenure_started_at_seconds,
        source_artifact_ids=context.source_artifact_ids,
        current_state=current_state,
    )


def actor_history_entry(
    transition: PumpStationTransition,
    proposal: PumpStationProposal,
) -> PumpStationActorHistoryEntry:
    """Create the bounded actor-visible history record for one proposal."""
    action_type = _ACTION_TYPES.get(type(proposal))
    if action_type is None:
        raise ValueError(f"unsupported proposal type {type(proposal).__name__}")
    receipt = transition.receipt
    return PumpStationActorHistoryEntry(
        transition_id=receipt.transition_id,
        sequence=receipt.sequence,
        occurred_at_seconds=transition.state.physical.calendar_seconds,
        agent_tenure_id=proposal.context.agent_tenure_id,
        proposal_id=proposal.context.proposal_id,
        action_type=action_type,
        reason=proposal.context.reason,
        execution=receipt.execution.value,
        restrictions_changed=receipt.restrictions_changed,
        obligations_changed=receipt.obligations_changed,
        work_orders_changed=receipt.work_orders_changed,
        evidence_created=receipt.evidence_created,
    )


def create_structured_handover(
    current_actor_view: PumpStationActorView,
    *,
    from_tenure_id: str,
    history: tuple[PumpStationActorHistoryEntry, ...],
    maximum_history_entries: int,
) -> PumpStationStructuredHandover:
    """Create a bounded handover without changing authoritative world state."""
    _require_text(from_tenure_id, "from_tenure_id")
    if from_tenure_id == current_actor_view.agent_tenure_id:
        raise ValueError("handover requires a fresh recipient tenure")
    if maximum_history_entries <= 0:
        raise ValueError("maximum_history_entries must be positive")
    bounded_history = history[-maximum_history_entries:]
    identity_payload = {
        "from_tenure_id": from_tenure_id,
        "to_tenure_id": current_actor_view.agent_tenure_id,
        "created_at_seconds": current_actor_view.current_state.calendar_seconds,
        "current_view_id": current_actor_view.view_id,
        "history": bounded_history,
    }
    return PumpStationStructuredHandover(
        handover_id=stewardship_content_id(identity_payload),
        from_tenure_id=from_tenure_id,
        to_tenure_id=current_actor_view.agent_tenure_id,
        created_at_seconds=current_actor_view.current_state.calendar_seconds,
        current_actor_view=current_actor_view,
        history=bounded_history,
    )


def _information_set_id(
    base_view: PumpStationActorView,
    observation_history: PumpStationObservationHistory,
    current_context: PumpStationCurrentContext,
) -> str:
    return stewardship_content_id(
        {
            "base_view_id": base_view.view_id,
            "observation_history": observation_history,
            "current_context": current_context,
        }
    )


def bind_information_set(
    base_view: PumpStationActorView,
    observation_history: PumpStationObservationHistory,
    current_context: PumpStationCurrentContext,
) -> PumpStationInformationSet:
    """Bind the exact view, tenure history, and visible commitment context."""
    if observation_history.agent_tenure_id != base_view.agent_tenure_id:
        raise ValueError("observation history belongs to a different actor tenure")
    if observation_history.view_ids[-1] != base_view.view_id:
        raise ValueError("latest observation must be the base view")
    return PumpStationInformationSet(
        information_set_id=_information_set_id(
            base_view,
            observation_history,
            current_context,
        ),
        base_view=base_view,
        observation_history=observation_history,
        current_context=current_context,
    )


def proposal_binding_error(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
    context: ProposalContext,
    information_set: PumpStationInformationSet,
) -> str | None:
    """Return the first fail-closed proposal binding error, if present."""
    view = information_set.base_view
    if context.agent_tenure_id != view.agent_tenure_id:
        return "proposal and base view use different actor tenures"
    if context.base_view_id != view.view_id:
        return "proposal base view does not match the supplied information set"
    if context.information_set_id != information_set.information_set_id:
        return "proposal information set does not match the supplied information set"
    if information_set.observation_history.agent_tenure_id != context.agent_tenure_id:
        return "observation history belongs to a different actor tenure"
    if information_set.observation_history.view_ids[-1] != view.view_id:
        return "latest observation is not the proposal base view"
    if information_set.information_set_id != _information_set_id(
        view,
        information_set.observation_history,
        information_set.current_context,
    ):
        return "information set identity does not match its content"
    if (
        context.based_on_sequence != state.sequence
        or view.current_state.state_sequence != state.sequence
        or view.current_state != _current_state_view(model, state)
    ):
        return "proposal is bound to a stale world view"
    return None
