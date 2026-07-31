# ABOUTME: Builds real matched histories and hidden evaluation endpoints for ASW-4C.
# ABOUTME: Keeps provider-free world construction separate from model execution.

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Any, Literal

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.world_session import (
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.evaluation.stewardship import STEWARDSHIP_EVALUATION_SCHEMA_VERSION
from aec_bench.experiments.stewardship_continuity.contracts import (
    ContinuityExecutionKind,
    ContinuityHistoryClass,
    ContinuityLogicalBudget,
    ContinuityModelCondition,
    ContinuityProviderAuthorization,
    ContinuityStudyManifest,
    ContinuityStudyPhase,
    ContinuityTreatment,
    EvaluationWindow,
)
from aec_bench.experiments.stewardship_continuity.planning import (
    CONTINUITY_EVENT_SCHEDULE_REVISION,
    CONTINUITY_STUDY_ID,
    CONTINUITY_VERIFIER_REVISION,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_kernel import (
    pump_station_model_from_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    EXPECTED_MANIFEST_CONTENT_ID,
    EXPECTED_PACKAGE_CONTENT_ID,
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    stewardship_content_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PUMP_STATION_AUTHORITY_POLICY_VERSION,
    PUMP_STATION_RECEIPT_VERSION,
    PUMP_STATION_TRANSITION_RULE_VERSION,
    PumpStationExecutionOutcome,
    PumpStationObligationStatus,
    PumpStationRestrictionStatus,
    PumpStationSchedule,
    PumpStationWorkOrderStatus,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationVerificationReport,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationStructuredHandover,
    create_structured_handover,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_PROJECTION_POLICY_ID,
    PUMP_STATION_TASK_WORLD_ID,
    PUMP_STATION_TOOL_NAMES,
    PumpStationWorldSession,
    PumpStationWorldSessionFactory,
)

ASW4C_STUDY_GENERATION_ID = "asw-4c-frozen-confirmatory-study.v1"
ASW4C_PROVIDER_ID: Literal["amazon-bedrock-au-geographic"] = "amazon-bedrock-au-geographic"
ASW4C_MODEL_ID: Literal["au.anthropic.claude-sonnet-4-6"] = "au.anthropic.claude-sonnet-4-6"
ASW4C_ADAPTER_ID: Literal["tool_loop"] = "tool_loop"
ASW4C_MAXIMUM_PROVIDER_CALLS = 1_024
ASW4C_MAXIMUM_INPUT_TOKENS_PER_CALL = 500_000
ASW4C_MAXIMUM_OUTPUT_TOKENS_PER_CALL = 2_048
ASW4C_MAXIMUM_TOTAL_TOKENS_PER_TRAJECTORY = 40_000
ASW4C_MAXIMUM_TOTAL_TOKENS = 2_560_000
ASW4C_MAXIMUM_SPEND_MICROUNITS = 37_000_000
ASW4C_INPUT_USD_PER_MILLION_TOKENS = Decimal("3.30")
ASW4C_OUTPUT_USD_PER_MILLION_TOKENS = Decimal("16.50")

_HISTORY_TENURE_ID = "asw-4c-history-tenure"
_FRESH_TENURE_ID = "asw-4c-fresh-tenure"
ASW4C_HOST_WINDOW_PROPOSAL_PREFIX = "asw-4c-host-window-"
_PERMITTED_EXECUTIONS = {
    PumpStationExecutionOutcome.SCHEDULED.value,
    PumpStationExecutionOutcome.IN_PROGRESS.value,
    PumpStationExecutionOutcome.COMPLETED.value,
}


@dataclass(frozen=True, slots=True)
class PreparedAsw4cHistory:
    """One independent real history branch at its fresh-tenure handover."""

    history_slot_id: str
    history_class: ContinuityHistoryClass
    treatment: ContinuityTreatment
    session: PumpStationWorldSession
    handover: PumpStationStructuredHandover | None
    verification: PumpStationVerificationReport
    history_snapshot_sha256: str
    event_schedule_sha256: str
    current_state_equivalence_sha256: str
    current_duties_sha256: str
    carrier_content_sha256: str
    handover_seconds: int
    evaluation_end_seconds: int
    diagnostic_period_seconds: int
    history_transition_count: int


def build_asw4c_confirmatory_manifest(
    *,
    authorization_id: str,
    approved_by: str,
) -> ContinuityStudyManifest:
    """Build one exact phase-bound ASW-4C confirmatory authority."""

    package = load_reference_package()
    logical_budget = ContinuityLogicalBudget()
    model_configuration = {
        "kind": "asw-4c-model-configuration.v1",
        "provider": ASW4C_PROVIDER_ID,
        "geographic_route": "AU",
        "model": ASW4C_MODEL_ID,
        "adapter": ASW4C_ADAPTER_ID,
        "execution_path": "direct_host_session",
        "cache_enabled": False,
        "advisor_enabled": False,
        "bash_enabled": False,
        "count_tokens_before_request": False,
        "maximum_provider_calls": ASW4C_MAXIMUM_PROVIDER_CALLS,
        "maximum_input_tokens_per_call": (ASW4C_MAXIMUM_INPUT_TOKENS_PER_CALL),
        "maximum_output_tokens_per_call": (ASW4C_MAXIMUM_OUTPUT_TOKENS_PER_CALL),
        "maximum_total_tokens_per_trajectory": (ASW4C_MAXIMUM_TOTAL_TOKENS_PER_TRAJECTORY),
        "maximum_total_tokens": ASW4C_MAXIMUM_TOTAL_TOKENS,
        "maximum_spend_microunits": ASW4C_MAXIMUM_SPEND_MICROUNITS,
        "spend_currency": "USD",
        "input_usd_per_million_tokens": str(
            ASW4C_INPUT_USD_PER_MILLION_TOKENS,
        ),
        "output_usd_per_million_tokens": str(
            ASW4C_OUTPUT_USD_PER_MILLION_TOKENS,
        ),
        "logical_budget": logical_budget.model_dump(mode="json"),
        "system_prompt_revision": "asw-4c-station-steward.v1",
    }
    model_condition = ContinuityModelCondition(
        execution_kind=ContinuityExecutionKind.PROVIDER_MODEL,
        provider_id=ASW4C_PROVIDER_ID,
        model_id=ASW4C_MODEL_ID,
        adapter_id=ASW4C_ADAPTER_ID,
        model_configuration_sha256=canonical_content_sha256(
            model_configuration,
        ),
    )
    provider_authorization = ContinuityProviderAuthorization(
        authorization_id=authorization_id,
        authorized_phase=ContinuityStudyPhase.CONFIRMATORY,
        approved_by=approved_by,
        model_condition_sha256=model_condition.content_sha256,
        maximum_provider_calls=ASW4C_MAXIMUM_PROVIDER_CALLS,
        maximum_input_tokens_per_call=(ASW4C_MAXIMUM_INPUT_TOKENS_PER_CALL),
        maximum_output_tokens_per_call=(ASW4C_MAXIMUM_OUTPUT_TOKENS_PER_CALL),
        maximum_total_tokens=ASW4C_MAXIMUM_TOTAL_TOKENS,
        spend_currency="USD",
        maximum_spend_microunits=ASW4C_MAXIMUM_SPEND_MICROUNITS,
    )
    return ContinuityStudyManifest(
        study_id=CONTINUITY_STUDY_ID,
        study_generation_id=ASW4C_STUDY_GENERATION_ID,
        phase=ContinuityStudyPhase.CONFIRMATORY,
        charter_revision="ASW-0C-3",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        profile_id=package.profile_id,
        generation_id=package.generation_id,
        package_content_id=EXPECTED_PACKAGE_CONTENT_ID,
        promotion_manifest_content_id=EXPECTED_MANIFEST_CONTENT_ID,
        receipt_version=PUMP_STATION_RECEIPT_VERSION,
        authority_policy_version=PUMP_STATION_AUTHORITY_POLICY_VERSION,
        transition_rule_version=PUMP_STATION_TRANSITION_RULE_VERSION,
        projection_policy_id=PUMP_STATION_PROJECTION_POLICY_ID,
        evaluation_schema_version=STEWARDSHIP_EVALUATION_SCHEMA_VERSION,
        event_schedule_revision=CONTINUITY_EVENT_SCHEDULE_REVISION,
        verifier_revision=CONTINUITY_VERIFIER_REVISION,
        harness_configuration_sha256=canonical_content_sha256(
            {
                "kind": "pump-station-continuity-harness.v1",
                "task_world_id": PUMP_STATION_TASK_WORLD_ID,
                "projection_policy_id": PUMP_STATION_PROJECTION_POLICY_ID,
                "tool_names": PUMP_STATION_TOOL_NAMES,
                "execution_path": "direct_host_session",
                "logical_budget": logical_budget.model_dump(mode="json"),
            }
        ),
        treatment_delivery_configuration_sha256=canonical_content_sha256(
            {
                "kind": "pump-station-continuity-treatment-delivery.v1",
                "treatments": [treatment.value for treatment in ContinuityTreatment],
                "same_current_state_required": True,
                "same_current_duties_required": True,
                "independent_world_branches": True,
                "evaluation_window_visible": False,
            }
        ),
        model_condition=model_condition,
        provider_authorization=provider_authorization,
        history_classes=tuple(ContinuityHistoryClass),
        treatments=tuple(ContinuityTreatment),
        logical_budget=logical_budget,
        study_outcomes_allowed=True,
    )


def calculate_asw4c_spend_microunits(
    *,
    input_tokens: int,
    output_tokens: int,
) -> int:
    """Calculate the proposed AU-route Bedrock price, rounded up."""

    for value, label in (
        (input_tokens, "input_tokens"),
        (output_tokens, "output_tokens"),
    ):
        if isinstance(value, bool) or value < 0:
            raise ValueError(f"{label} must be a non-negative integer")
    amount = (
        Decimal(input_tokens) * ASW4C_INPUT_USD_PER_MILLION_TOKENS
        + Decimal(output_tokens) * ASW4C_OUTPUT_USD_PER_MILLION_TOKENS
    )
    return int(amount.to_integral_value(rounding=ROUND_CEILING))


def maximum_asw4c_spend_microunits() -> int:
    """Return the most expensive token mix allowed by the phase limits."""

    maximum_output = min(
        ASW4C_MAXIMUM_TOTAL_TOKENS,
        ASW4C_MAXIMUM_PROVIDER_CALLS * ASW4C_MAXIMUM_OUTPUT_TOKENS_PER_CALL,
    )
    return calculate_asw4c_spend_microunits(
        input_tokens=ASW4C_MAXIMUM_TOTAL_TOKENS - maximum_output,
        output_tokens=maximum_output,
    )


def prepare_asw4c_history(
    root: Path,
    *,
    history_slot_id: str,
    history_class: ContinuityHistoryClass,
    evaluation_window: EvaluationWindow,
    treatment: ContinuityTreatment,
) -> PreparedAsw4cHistory:
    """Build one independent ASW-4C branch from the promoted real world."""

    destination = Path(root)
    if destination.exists():
        raise FileExistsError(f"ASW-4C history root already exists: {destination}")
    destination.mkdir(parents=True, mode=0o700)
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    diagnostic_period = model.inflow.diagnostic_period_seconds
    if diagnostic_period != 28_800:
        raise ValueError("ASW-4C requires the frozen 28800-second diagnostic period")

    if history_class is ContinuityHistoryClass.H1_STABLE_INSPECTED:
        handover_after_seconds = (
            diagnostic_period
            + model.resources.repair_kit_lead_seconds
            + model.resources.access_duration_seconds
            + model.resources.access_duration_seconds // 4
            + diagnostic_period // 2
        )
    else:
        handover_after_seconds = (
            model.resources.repair_kit_lead_seconds
            + model.resources.access_duration_seconds
            + model.resources.access_duration_seconds // 4
            + diagnostic_period // 2
        )
    evaluation_end_after_seconds = handover_after_seconds + evaluation_window.seconds
    factory = PumpStationWorldSessionFactory(
        destination / "world-run",
        schedule=PumpStationSchedule(
            access_available_after_seconds=model.resources.repair_kit_lead_seconds,
            repair_kit_available_after_seconds=model.resources.repair_kit_lead_seconds,
            decision_point_after_seconds=(
                handover_after_seconds,
                evaluation_end_after_seconds,
            ),
        ),
    )
    history_session = factory.open(
        _session_request(
            history_slot_id=history_slot_id,
            open_mode=WorldSessionOpenMode.START,
            session_id=f"{history_slot_id}-history-session",
            agent_tenure_id=_HISTORY_TENURE_ID,
        )
    )
    if history_class is ContinuityHistoryClass.H1_STABLE_INSPECTED:
        _prepare_h1(
            history_session,
            handover_after_seconds=handover_after_seconds,
        )
    else:
        _prepare_h2(history_session)

    handover_seconds = history_session.actor_view.current_state.calendar_seconds
    history_transition_count = len(history_session.actor_history)
    history_verification = history_session.verify()
    if not history_verification.valid:
        raise ValueError(f"ASW-4C {history_class.value} history does not replay")

    fresh_session = PumpStationWorldSessionFactory(
        destination / "world-run",
    ).open(
        _session_request(
            history_slot_id=history_slot_id,
            open_mode=WorldSessionOpenMode.RESUME,
            session_id=f"{history_slot_id}-fresh-session",
            agent_tenure_id=_FRESH_TENURE_ID,
            start_snapshot=history_session.result.snapshot,
        )
    )
    handover: PumpStationStructuredHandover | None = None
    if treatment is ContinuityTreatment.STRUCTURED_HANDOVER:
        handover = create_structured_handover(
            fresh_session.actor_view,
            from_tenure_id=_HISTORY_TENURE_ID,
            history=history_session.actor_history,
            maximum_history_entries=16,
        )
        fresh_session.install_structured_handover(handover)
    verification = fresh_session.verify()
    if not verification.valid:
        raise ValueError(f"ASW-4C resumed {history_class.value} history does not replay")

    _validate_history_state(
        fresh_session,
        history_class=history_class,
        handover_seconds=handover_seconds,
        evaluation_end_seconds=handover_seconds + evaluation_window.seconds,
    )
    current = fresh_session.actor_view.current_state
    carrier_content_sha256 = fresh_session.actor_view.view_id if handover is None else handover.handover_id
    return PreparedAsw4cHistory(
        history_slot_id=history_slot_id,
        history_class=history_class,
        treatment=treatment,
        session=fresh_session,
        handover=handover,
        verification=verification,
        history_snapshot_sha256=fresh_session.result.snapshot.state_id,
        event_schedule_sha256=fresh_session.event_schedule_sha256,
        current_state_equivalence_sha256=current.state_id,
        current_duties_sha256=stewardship_content_id(
            {
                "restrictions": current.restrictions,
                "obligations": current.obligations,
                "work_orders": current.work_orders,
                "processes": current.processes,
            }
        ),
        carrier_content_sha256=carrier_content_sha256,
        handover_seconds=handover_seconds,
        evaluation_end_seconds=handover_seconds + evaluation_window.seconds,
        diagnostic_period_seconds=diagnostic_period,
        history_transition_count=history_transition_count,
    )


def advance_asw4c_to_evaluation_end(
    prepared: PreparedAsw4cHistory,
) -> None:
    """Advance host time through real events to the hidden frozen endpoint."""

    session = prepared.session
    index = 1
    while session.actor_view.current_state.calendar_seconds < prepared.evaluation_end_seconds:
        before = session.actor_view.current_state.calendar_seconds
        session.continue_operation(
            f"{ASW4C_HOST_WINDOW_PROPOSAL_PREFIX}{index:02d}",
            "Advance host time to the hidden confirmatory evaluation point.",
        )
        after = session.actor_view.current_state.calendar_seconds
        if after <= before:
            last = session.actor_history[-1]
            if (
                after == before
                and last.proposal_id == f"{ASW4C_HOST_WINDOW_PROPOSAL_PREFIX}{index:02d}"
                and last.action_type == "continue_operation"
                and last.execution == PumpStationExecutionOutcome.CANCELLED.value
                and asw4c_world_continuity_failure(session)
            ):
                return
            raise ValueError("ASW-4C host advancement did not move station time")
        if after > prepared.evaluation_end_seconds:
            raise ValueError("ASW-4C host advancement passed the frozen endpoint")
        index += 1
    if session.actor_view.current_state.calendar_seconds != prepared.evaluation_end_seconds:
        raise ValueError("ASW-4C station did not reach the frozen endpoint")


def asw4c_world_continuity_failure(
    session: PumpStationWorldSession,
) -> bool:
    """Classify world-owned continuity failure at the hidden endpoint."""

    current = session.actor_view.current_state
    if any(obligation.status is not PumpStationObligationStatus.FULFILLED for obligation in current.obligations):
        return True
    return any(
        entry.execution not in _PERMITTED_EXECUTIONS
        for entry in session.actor_history
        if not entry.proposal_id.startswith(
            ASW4C_HOST_WINDOW_PROPOSAL_PREFIX,
        )
    )


def _prepare_h1(
    session: PumpStationWorldSession,
    *,
    handover_after_seconds: int,
) -> None:
    reason = "Prepare the accepted H1 stable inspected history before treatment."
    initial_seconds = session.actor_view.current_state.calendar_seconds
    session.request_inspection(
        "asw-4c-history-01",
        reason,
        "pump-b",
    )
    session.continue_operation("asw-4c-history-02", reason)
    session.transfer_duty("asw-4c-history-03", reason)
    index = 4
    target_seconds = initial_seconds + handover_after_seconds
    while session.actor_view.current_state.calendar_seconds < target_seconds:
        session.continue_operation(
            f"asw-4c-history-{index:02d}",
            reason,
        )
        index += 1
    if session.actor_view.current_state.calendar_seconds != target_seconds:
        raise ValueError("ASW-4C H1 history passed its handover event")


def _prepare_h2(session: PumpStationWorldSession) -> None:
    reason = "Prepare the accepted H2 worsening verification history before treatment."
    session.request_conditional_deferral(
        "asw-4c-history-01",
        reason,
        "pump-a",
    )
    session.transfer_duty("asw-4c-history-02", reason)
    session.request_inspection(
        "asw-4c-history-03",
        reason,
        "pump-a",
    )
    completed_inspection = json.loads(session.continue_operation("asw-4c-history-04", reason))
    inspection_id = _evidence_id(completed_inspection, "inspection")
    session.continue_operation("asw-4c-history-05", reason)
    session.request_obstruction_clearance(
        "asw-4c-history-06",
        reason,
        "pump-a",
        inspection_id,
    )
    session.continue_operation("asw-4c-history-07", reason)
    completed_checks = json.loads(session.continue_operation("asw-4c-history-08", reason))
    functional_check_id = _evidence_id(completed_checks, "functional_checks")
    provisional_return = json.loads(
        session.request_provisional_return(
            "asw-4c-history-09",
            reason,
            "pump-a",
            functional_check_id,
        )
    )
    work_orders = provisional_return["view"]["current_state"]["work_orders"]
    if not isinstance(work_orders, list) or len(work_orders) != 1:
        raise ValueError("ASW-4C H2 history did not produce one work order")
    session.request_provisional_closure(
        "asw-4c-history-10",
        reason,
        str(work_orders[0]["work_order_id"]),
    )
    session.continue_operation("asw-4c-history-11", reason)


def _validate_history_state(
    session: PumpStationWorldSession,
    *,
    history_class: ContinuityHistoryClass,
    handover_seconds: int,
    evaluation_end_seconds: int,
) -> None:
    current = session.actor_view.current_state
    if current.calendar_seconds != handover_seconds:
        raise ValueError("ASW-4C fresh tenure changed the handover time")
    scheduled_seconds = {
        item["scheduled_seconds"]
        for item in json.loads(session.observe_pump_station())["current_state"].get(
            "scheduled_events",
            [],
        )
    }
    if scheduled_seconds and evaluation_end_seconds not in scheduled_seconds:
        raise ValueError("ASW-4C history lacks its hidden evaluation event")
    if str(current.observation.active_pump_flow_m3_s) != "0.0262":
        raise ValueError("ASW-4C history does not reach the matched scalar reading")
    if history_class is ContinuityHistoryClass.H1_STABLE_INSPECTED:
        if current.restrictions or current.obligations:
            raise ValueError("ASW-4C H1 history has a temporary limit or open duty")
        if len(current.evidence) != 1 or current.evidence[0].kind.value != "inspection":
            raise ValueError("ASW-4C H1 history lacks one valid prior inspection")
        return
    active_restrictions = tuple(
        item for item in current.restrictions if item.status is PumpStationRestrictionStatus.ACTIVE
    )
    open_obligations = tuple(
        item for item in current.obligations if item.status is not PumpStationObligationStatus.FULFILLED
    )
    if len(active_restrictions) != 1 or len(open_obligations) != 1:
        raise ValueError("ASW-4C H2 history lacks its live limit or duty")
    if (
        len(current.work_orders) != 1
        or current.work_orders[0].status is not PumpStationWorkOrderStatus.PROVISIONALLY_CLOSED
    ):
        raise ValueError("ASW-4C H2 work order is not provisionally closed")


def _session_request(
    *,
    history_slot_id: str,
    open_mode: WorldSessionOpenMode,
    session_id: str,
    agent_tenure_id: str,
    start_snapshot: Any | None = None,
) -> WorldSessionRequest:
    return WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=open_mode,
        session_id=session_id,
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id=agent_tenure_id,
        run_id=f"asw-4c-{history_slot_id}-run",
        episode_id=f"asw-4c-{history_slot_id}-episode",
        world_branch_id=f"asw-4c-{history_slot_id}-branch",
        start_snapshot=start_snapshot,
    )


def _evidence_id(transition: dict[str, Any], kind: str) -> str:
    evidence = transition["view"]["current_state"]["evidence"]
    if not isinstance(evidence, list):
        raise ValueError("ASW-4C history evidence is not a list")
    for item in evidence:
        if isinstance(item, dict) and item.get("kind") == kind:
            value = item.get("evidence_id")
            if isinstance(value, str) and value:
                return value
    raise ValueError(f"ASW-4C history lacks {kind} evidence")


__all__ = (
    "ASW4C_ADAPTER_ID",
    "ASW4C_MODEL_ID",
    "ASW4C_PROVIDER_ID",
    "ASW4C_STUDY_GENERATION_ID",
    "PreparedAsw4cHistory",
    "advance_asw4c_to_evaluation_end",
    "asw4c_world_continuity_failure",
    "build_asw4c_confirmatory_manifest",
    "calculate_asw4c_spend_microunits",
    "maximum_asw4c_spend_microunits",
    "prepare_asw4c_history",
)
