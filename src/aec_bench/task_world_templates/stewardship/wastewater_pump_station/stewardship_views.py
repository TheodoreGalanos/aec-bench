# ABOUTME: Projects actor-visible pump-station state and structured handover records.
# ABOUTME: Binds each proposal to its exact view, observation history, and current context.

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.evidence_health import (
    PumpStationEvidenceQuality,
    evidence_quality_at,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_kernel import (
    assess_pump_station,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpInspectionObservation,
    PumpStationEnvironment,
    PumpStationModel,
    PumpStationObservation,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    stewardship_content_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    CancelProcess,
    ContinueOperation,
    ProposalContext,
    PumpStationAuthority,
    PumpStationDependencyWaiver,
    PumpStationEvidence,
    PumpStationEvidenceKind,
    PumpStationObligation,
    PumpStationObligationStatus,
    PumpStationProcess,
    PumpStationProcessDependency,
    PumpStationProcessStatus,
    PumpStationProposal,
    PumpStationResourceReservation,
    PumpStationRestriction,
    PumpStationRestrictionStatus,
    PumpStationStewardshipState,
    PumpStationTransition,
    PumpStationWorkOrder,
    PumpStationWorkResources,
    RequestConditionalDeferral,
    RequestConditionCheck,
    RequestDependencyWaiver,
    RequestInspection,
    RequestObstructionClearance,
    RequestProvisionalClosure,
    RequestProvisionalReturn,
    RequestVerification,
    ResumeProcess,
    TransferDuty,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.time_presentation import (
    PUMP_STATION_TIME_PROJECTION_POLICY_ID,
    PumpStationTimeContext,
    pump_station_time_context,
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
class PumpStationObservationSourceView:
    """Actor-visible source, timing, and quality of the current station reading."""

    source_id: str
    component_scope: tuple[str, ...]
    baseline_id: str
    operating_regime_id: str
    observed_at_seconds: int
    produced_at_seconds: int
    available_at_seconds: int
    age_seconds: int
    quality: PumpStationEvidenceQuality
    observation: PumpStationObservation | None


@dataclass(frozen=True, slots=True)
class PumpStationEvidenceView:
    """Actor-visible evidence with computed age and explicit provenance."""

    evidence_id: str
    kind: PumpStationEvidenceKind
    pump_id: str
    produced_by: PumpStationAuthority
    accepted_by: PumpStationAuthority | None
    accepted: bool
    source_id: str
    component_scope: tuple[str, ...]
    baseline_id: str
    operating_regime_id: str
    observed_at_seconds: int
    produced_at_seconds: int
    available_at_seconds: int
    age_seconds: int
    quality: PumpStationEvidenceQuality
    applicable: bool
    contradicts_evidence_id: str | None
    supersedes_evidence_id: str | None
    inspection: PumpInspectionObservation | None = None
    condition_observation: PumpStationObservation | None = None
    passed: bool | None = None


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
    observation: PumpStationObservation | None
    resources: PumpStationWorkResources
    restrictions: tuple[PumpStationRestriction, ...]
    obligations: tuple[PumpStationObligation, ...]
    work_orders: tuple[PumpStationWorkOrder, ...]
    processes: tuple[PumpStationProcess, ...]
    evidence: tuple[PumpStationEvidence | PumpStationEvidenceView, ...]
    state_version: str = "pump-station-stewardship-state.v1"
    dependencies: tuple[PumpStationProcessDependency, ...] = ()
    dependency_waivers: tuple[PumpStationDependencyWaiver, ...] = ()
    resource_reservations: tuple[PumpStationResourceReservation, ...] = ()
    observation_source: PumpStationObservationSourceView | None = None


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
    time_context: PumpStationTimeContext | None = None


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
    RequestConditionCheck: "request_condition_check",
    RequestConditionalDeferral: "request_conditional_deferral",
    RequestObstructionClearance: "request_obstruction_clearance",
    RequestProvisionalReturn: "request_provisional_return",
    RequestProvisionalClosure: "request_provisional_closure",
    RequestVerification: "request_post_maintenance_verification",
    ResumeProcess: "resume_process",
    CancelProcess: "cancel_process",
    RequestDependencyWaiver: "request_dependency_waiver",
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
    processes = tuple(
        process
        for process in state.processes
        if process.status
        in {
            PumpStationProcessStatus.IN_PROGRESS,
            PumpStationProcessStatus.BLOCKED,
            PumpStationProcessStatus.ACTIVE,
            PumpStationProcessStatus.SUSPENDED,
        }
    )
    profile = "v3" if state.state_version.endswith(".v3") else "v2" if state.state_version.endswith(".v2") else "v1"
    observation: PumpStationObservation | None = assessment.observation
    observation_source: PumpStationObservationSourceView | None = None
    visible_evidence: tuple[PumpStationEvidence | PumpStationEvidenceView, ...] = state.evidence
    if profile == "v3":
        if len(state.evidence_sources) != 1:
            raise ValueError("version 3 requires exactly one observation source")
        source = state.evidence_sources[0]
        source_quality = evidence_quality_at(
            source.quality,
            observed_at_seconds=source.observed_at_seconds,
            now_seconds=state.physical.calendar_seconds,
        )
        observation = source.observation if source.reading_available else None
        observation_source = PumpStationObservationSourceView(
            source_id=source.source_id,
            component_scope=source.component_scope,
            baseline_id=source.baseline_id,
            operating_regime_id=source.operating_regime_id,
            observed_at_seconds=source.observed_at_seconds,
            produced_at_seconds=source.produced_at_seconds,
            available_at_seconds=source.available_at_seconds,
            age_seconds=state.physical.calendar_seconds - source.observed_at_seconds,
            quality=source_quality,
            observation=observation,
        )
        projected_evidence: list[PumpStationEvidenceView] = []
        for item in state.evidence:
            if item.health is None:
                raise ValueError("version 3 evidence lacks health metadata")
            health = item.health
            applicable = health.source_id != source.source_id or (
                health.baseline_id == source.baseline_id and health.operating_regime_id == source.operating_regime_id
            )
            quality = evidence_quality_at(
                health.quality,
                observed_at_seconds=health.observed_at_seconds,
                now_seconds=state.physical.calendar_seconds,
            )
            if not applicable and quality is PumpStationEvidenceQuality.CURRENT:
                quality = PumpStationEvidenceQuality.SUSPECT
            projected_evidence.append(
                PumpStationEvidenceView(
                    evidence_id=item.evidence_id,
                    kind=item.kind,
                    pump_id=item.pump_id,
                    produced_by=item.produced_by,
                    accepted_by=item.accepted_by,
                    accepted=health.accepted,
                    source_id=health.source_id,
                    component_scope=health.component_scope,
                    baseline_id=health.baseline_id,
                    operating_regime_id=health.operating_regime_id,
                    observed_at_seconds=health.observed_at_seconds,
                    produced_at_seconds=health.produced_at_seconds,
                    available_at_seconds=health.available_at_seconds,
                    age_seconds=(state.physical.calendar_seconds - health.observed_at_seconds),
                    quality=quality,
                    applicable=applicable,
                    contradicts_evidence_id=health.contradicts_evidence_id,
                    supersedes_evidence_id=health.supersedes_evidence_id,
                    inspection=item.inspection,
                    condition_observation=item.condition_observation,
                    passed=item.passed,
                )
            )
        visible_evidence = tuple(projected_evidence)
    visible_state = {
        "state_sequence": state.sequence,
        "calendar_seconds": state.physical.calendar_seconds,
        "duty_pump_id": state.physical.duty_pump_id,
        "standby_pump_id": state.physical.standby_pump_id,
        "duty_transfer_count": state.physical.duty_transfer_count,
        "pumps": pumps,
        "environment": state.environment,
        "observation": observation,
        "resources": state.resources,
        "restrictions": restrictions,
        "obligations": obligations,
        "work_orders": state.work_orders,
        "processes": processes,
        "evidence": visible_evidence,
    }
    if profile in {"v2", "v3"}:
        visible_state.update(
            {
                "state_version": state.state_version,
                "dependencies": state.dependencies,
                "dependency_waivers": state.dependency_waivers,
                "resource_reservations": state.resource_reservations,
            }
        )
    if profile == "v3":
        visible_state["observation_source"] = observation_source
    return PumpStationCurrentStateView(
        state_id=stewardship_content_id(
            visible_state,
            record_profile=profile,
        ),
        state_sequence=state.sequence,
        calendar_seconds=state.physical.calendar_seconds,
        duty_pump_id=state.physical.duty_pump_id,
        standby_pump_id=state.physical.standby_pump_id,
        duty_transfer_count=state.physical.duty_transfer_count,
        pumps=pumps,
        environment=state.environment,
        observation=observation,
        resources=state.resources,
        restrictions=restrictions,
        obligations=obligations,
        work_orders=state.work_orders,
        processes=processes,
        evidence=visible_evidence,
        state_version=state.state_version,
        dependencies=state.dependencies,
        dependency_waivers=state.dependency_waivers,
        resource_reservations=state.resource_reservations,
        observation_source=observation_source,
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
    time_context = (
        pump_station_time_context(
            state,
            episode_elapsed_seconds=now - context.episode_started_at_seconds,
            tenure_elapsed_seconds=now - context.tenure_started_at_seconds,
        )
        if context.projection_policy_id == PUMP_STATION_TIME_PROJECTION_POLICY_ID
        else None
    )
    identity_payload: dict[str, object] = {
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
    if time_context is not None:
        identity_payload["time_context"] = time_context
    record_profile = (
        "v4"
        if time_context is not None
        else "v3"
        if state.state_version.endswith(".v3")
        else "v2"
        if state.state_version.endswith(".v2")
        else "v1"
    )
    return PumpStationActorView(
        view_id=stewardship_content_id(
            identity_payload,
            record_profile=record_profile,
        ),
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
        time_context=time_context,
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
        },
        record_profile=(
            "v3"
            if base_view.current_state.state_version.endswith(".v3")
            else "v2"
            if base_view.current_state.state_version.endswith(".v2")
            else "v1"
        ),
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
