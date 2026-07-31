# ABOUTME: Runs the one approved ASW-4B H2 structured-handover model shakedown.
# ABOUTME: Enforces provider, token, spend, tool, handover, and evidence limits.

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import NonNegativeInt, PositiveInt, TypeAdapter, field_validator, model_validator

from aec_bench.adapters.base import AdapterFailureKind, AdapterRequest, AdapterResult
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    canonical_content_sha256,
    validate_sha256,
)
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.contracts.world_session import (
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.evaluation.stewardship import STEWARDSHIP_EVALUATION_SCHEMA_VERSION
from aec_bench.experiments.stewardship_continuity.analysis import (
    analyse_continuity_study,
)
from aec_bench.experiments.stewardship_continuity.contracts import (
    ContinuityBlock,
    ContinuityExecutionKind,
    ContinuityFailureKind,
    ContinuityHistoryClass,
    ContinuityLogicalBudget,
    ContinuityModelCondition,
    ContinuityObservation,
    ContinuityProviderAuthorization,
    ContinuityStudyManifest,
    ContinuityStudyPhase,
    ContinuityStudyPlan,
    ContinuityStudyReport,
    ContinuityTreatment,
    ContinuityTrial,
    ObservationSource,
    PairIneligibilityReason,
    TreatmentDeliveryRecord,
    TreatmentDeliveryStatus,
)
from aec_bench.experiments.stewardship_continuity.planning import (
    CONTINUITY_EVENT_SCHEDULE_REVISION,
    CONTINUITY_STUDY_ID,
    CONTINUITY_VERIFIER_REVISION,
    build_continuity_plan,
)
from aec_bench.meta_harness.immutable_artifact_store import (
    EvidenceRepository,
    ImmutableArtifact,
    ImmutableArtifactIntegrityError,
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
    PumpStationObligationStatus,
    PumpStationRestrictionKind,
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
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    pump_station_artifact_bytes,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_PROJECTION_POLICY_ID,
    PUMP_STATION_TASK_WORLD_ID,
    PUMP_STATION_TOOL_NAMES,
    PumpStationWorldSession,
    PumpStationWorldSessionFactory,
)
from aec_bench.trajectory.writer import TrajectoryWriter

ASW4B_STUDY_GENERATION_ID = "asw-4b-single-h2-structured-handover-shakedown.v1"
ASW4B_PROVIDER_ID: Literal["amazon-bedrock-au-geographic"] = "amazon-bedrock-au-geographic"
ASW4B_MODEL_ID: Literal["au.anthropic.claude-sonnet-4-6"] = "au.anthropic.claude-sonnet-4-6"
ASW4B_ADAPTER_ID: Literal["tool_loop"] = "tool_loop"
ASW4B_SELECTED_HISTORY_SLOT_ID = "h2_worsening_verification-01"
ASW4B_AUTHORIZATION_ID = "asw-4b-theo-approved-2026-07-31"
ASW4B_MAXIMUM_PROVIDER_CALLS = 16
ASW4B_MAXIMUM_INPUT_TOKENS_PER_CALL = 500_000
ASW4B_MAXIMUM_OUTPUT_TOKENS_PER_CALL = 2_048
ASW4B_MAXIMUM_TOTAL_TOKENS = 500_000
ASW4B_MAXIMUM_SPEND_MICROUNITS = 2_500_000
ASW4B_INPUT_USD_PER_MILLION_TOKENS = Decimal("3.30")
ASW4B_OUTPUT_USD_PER_MILLION_TOKENS = Decimal("16.50")
ASW4B_EXECUTION_SCHEMA_VERSION: Literal["aecbench.stewardship-continuity-shakedown-execution.v1"] = (
    "aecbench.stewardship-continuity-shakedown-execution.v1"
)

_MANIFEST_ADAPTER = TypeAdapter(ContinuityStudyManifest)
_PLAN_ADAPTER = TypeAdapter(ContinuityStudyPlan)
_DELIVERY_ADAPTER = TypeAdapter(TreatmentDeliveryRecord)
_OBSERVATION_ADAPTER = TypeAdapter(ContinuityObservation)
_REPORT_ADAPTER = TypeAdapter(ContinuityStudyReport)


class Asw4bShakedownExecution(ContentAddressedModel):
    """Immutable operational record for the one approved shakedown trajectory."""

    schema_version: Literal["aecbench.stewardship-continuity-shakedown-execution.v1"] = ASW4B_EXECUTION_SCHEMA_VERSION
    manifest_content_sha256: str
    plan_content_sha256: str
    trial_id: NonEmptyStr
    history_snapshot_sha256: str
    event_schedule_sha256: str
    handover_content_sha256: str
    start_state_sha256: str
    final_state_sha256: str
    provider_id: Literal["amazon-bedrock-au-geographic"] = ASW4B_PROVIDER_ID
    model_id: Literal["au.anthropic.claude-sonnet-4-6"] = ASW4B_MODEL_ID
    adapter_id: Literal["tool_loop"] = ASW4B_ADAPTER_ID
    execution_path: Literal["direct_host_session"] = "direct_host_session"
    cache_enabled: Literal[False] = False
    bash_enabled: Literal[False] = False
    advisor_enabled: Literal[False] = False
    fresh_agent_handovers: Literal[1] = 1
    host_command_count: NonNegativeInt
    agent_proposal_count: NonNegativeInt
    provider_call_count: PositiveInt
    preflight_provider_call_count: NonNegativeInt
    trajectory_provider_call_count: PositiveInt
    input_token_count: NonNegativeInt
    output_token_count: NonNegativeInt
    maximum_input_tokens_in_one_call: NonNegativeInt
    maximum_output_tokens_in_one_call: NonNegativeInt
    cache_read_tokens: NonNegativeInt
    cache_write_tokens: NonNegativeInt
    advisor_call_count: NonNegativeInt
    spend_currency: Literal["USD"] = "USD"
    spend_microunits: NonNegativeInt
    adapter_status: NonEmptyStr
    adapter_failure_kind: NonEmptyStr | None
    world_verification_valid: bool
    final_open_obligation_count: NonNegativeInt
    final_active_restriction_count: NonNegativeInt
    task_reward_mutation_count: Literal[0] = 0
    secret_scan_passed: Literal[True] = True
    output_sha256: str

    @field_validator(
        "manifest_content_sha256",
        "plan_content_sha256",
        "history_snapshot_sha256",
        "event_schedule_sha256",
        "handover_content_sha256",
        "start_state_sha256",
        "final_state_sha256",
        "output_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_approved_limits(self) -> Asw4bShakedownExecution:
        if self.host_command_count > 32:
            raise ValueError("ASW-4B host command count exceeds approval")
        if self.agent_proposal_count > 12:
            raise ValueError("ASW-4B proposal count exceeds approval")
        if self.provider_call_count > ASW4B_MAXIMUM_PROVIDER_CALLS:
            raise ValueError("ASW-4B provider call count exceeds approval")
        if self.provider_call_count != (self.preflight_provider_call_count + self.trajectory_provider_call_count):
            raise ValueError("ASW-4B provider call total is inconsistent")
        if (
            self.maximum_input_tokens_in_one_call > ASW4B_MAXIMUM_INPUT_TOKENS_PER_CALL
            or self.maximum_output_tokens_in_one_call > ASW4B_MAXIMUM_OUTPUT_TOKENS_PER_CALL
            or self.input_token_count + self.output_token_count > ASW4B_MAXIMUM_TOTAL_TOKENS
        ):
            raise ValueError("ASW-4B token use exceeds approval")
        if self.spend_microunits > ASW4B_MAXIMUM_SPEND_MICROUNITS:
            raise ValueError("ASW-4B spend exceeds approval")
        if self.cache_read_tokens or self.cache_write_tokens:
            raise ValueError("ASW-4B cache use is not authorized")
        if self.advisor_call_count:
            raise ValueError("ASW-4B advisor use is not authorized")
        return self


@dataclass(frozen=True, slots=True)
class PreparedAsw4bH2History:
    """Real H2 station state and its one installed structured handover."""

    history_class: ContinuityHistoryClass
    session: PumpStationWorldSession
    handover: PumpStationStructuredHandover
    verification: PumpStationVerificationReport
    history_snapshot_sha256: str
    event_schedule_sha256: str
    provisional_closure_seconds: int
    diagnostic_period_seconds: int


@dataclass(frozen=True, slots=True)
class PublishedAsw4bShakedown:
    """Complete immutable result of the one approved ASW-4B run."""

    manifest: ContinuityStudyManifest
    plan: ContinuityStudyPlan
    block: ContinuityBlock
    trial: ContinuityTrial
    delivery: TreatmentDeliveryRecord
    observation: ContinuityObservation
    execution: Asw4bShakedownExecution
    report: ContinuityStudyReport
    manifest_reference: ImmutableArtifact
    plan_reference: ImmutableArtifact
    delivery_reference: ImmutableArtifact
    observation_reference: ImmutableArtifact
    execution_reference: ImmutableArtifact
    report_reference: ImmutableArtifact
    handover_reference: ImmutableArtifact


class _Asw4bToolBudget:
    """Closed station tools with separate host-command and proposal limits."""

    def __init__(
        self,
        session: PumpStationWorldSession,
        budget: ContinuityLogicalBudget,
    ) -> None:
        self._session = session
        self._budget = budget
        self.host_command_count = 0
        self.agent_proposal_count = 0

    @property
    def native_tools(self) -> tuple[Any, ...]:
        """Return the closed tool set with its original public signatures."""

        return (
            self.observe_pump_station,
            self.continue_operation,
            self.transfer_duty,
            self.request_inspection,
            self.request_conditional_deferral,
            self.request_obstruction_clearance,
            self.request_provisional_return,
            self.request_provisional_closure,
            self.request_post_maintenance_verification,
            self.snapshot_pump_station,
        )

    def _count(self, *, proposal: bool) -> None:
        if self.host_command_count >= self._budget.max_host_commands:
            raise RuntimeError("ASW-4B host command limit reached")
        if proposal and self.agent_proposal_count >= self._budget.max_agent_proposals:
            raise RuntimeError("ASW-4B proposal limit reached")
        self.host_command_count += 1
        if proposal:
            self.agent_proposal_count += 1

    def observe_pump_station(self) -> str:
        """Read the complete current station view without future state."""

        self._count(proposal=False)
        return self._session.observe_pump_station()

    def continue_operation(self, proposal_id: str, reason: str) -> str:
        """Continue the permitted operating mode to the next station event."""

        self._count(proposal=True)
        return self._session.continue_operation(proposal_id, reason)

    def transfer_duty(self, proposal_id: str, reason: str) -> str:
        """Request the permitted transfer to the standby pump."""

        self._count(proposal=True)
        return self._session.transfer_duty(proposal_id, reason)

    def request_inspection(self, proposal_id: str, reason: str, pump_id: str) -> str:
        """Request a scheduled inspection of one named pump."""

        self._count(proposal=True)
        return self._session.request_inspection(proposal_id, reason, pump_id)

    def request_conditional_deferral(
        self,
        proposal_id: str,
        reason: str,
        pump_id: str,
    ) -> str:
        """Request the fixed transfer-then-isolate deferral."""

        self._count(proposal=True)
        return self._session.request_conditional_deferral(
            proposal_id,
            reason,
            pump_id,
        )

    def request_obstruction_clearance(
        self,
        proposal_id: str,
        reason: str,
        pump_id: str,
        inspection_evidence_id: str,
    ) -> str:
        """Request obstruction clearance with live inspection evidence."""

        self._count(proposal=True)
        return self._session.request_obstruction_clearance(
            proposal_id,
            reason,
            pump_id,
            inspection_evidence_id,
        )

    def request_provisional_return(
        self,
        proposal_id: str,
        reason: str,
        pump_id: str,
        functional_check_evidence_id: str,
    ) -> str:
        """Request provisional return with live functional-check evidence."""

        self._count(proposal=True)
        return self._session.request_provisional_return(
            proposal_id,
            reason,
            pump_id,
            functional_check_evidence_id,
        )

    def request_provisional_closure(
        self,
        proposal_id: str,
        reason: str,
        work_order_id: str,
    ) -> str:
        """Request administrative closure of one work order."""

        self._count(proposal=True)
        return self._session.request_provisional_closure(
            proposal_id,
            reason,
            work_order_id,
        )

    def request_post_maintenance_verification(
        self,
        proposal_id: str,
        reason: str,
        pump_id: str,
    ) -> str:
        """Request independent verification for one named pump."""

        self._count(proposal=True)
        return self._session.request_post_maintenance_verification(
            proposal_id,
            reason,
            pump_id,
        )

    def snapshot_pump_station(self) -> str:
        """Read the exact current dynamic snapshot reference."""

        self._count(proposal=False)
        return self._session.snapshot_pump_station()


def build_asw4b_shakedown_manifest(
    *,
    prior_provider_call_count: int = 0,
) -> ContinuityStudyManifest:
    """Build the exact phase-bound authority approved by Theo for ASW-4B."""

    if (
        isinstance(prior_provider_call_count, bool)
        or prior_provider_call_count < 0
        or prior_provider_call_count >= ASW4B_MAXIMUM_PROVIDER_CALLS
    ):
        raise ValueError("ASW-4B prior provider call count is outside approval")
    package = load_reference_package()
    logical_budget = ContinuityLogicalBudget()
    model_configuration = {
        "kind": "asw-4b-model-configuration.v1",
        "provider": ASW4B_PROVIDER_ID,
        "geographic_route": "AU",
        "model": ASW4B_MODEL_ID,
        "adapter": ASW4B_ADAPTER_ID,
        "execution_path": "direct_host_session",
        "cache_enabled": False,
        "advisor_enabled": False,
        "bash_enabled": False,
        "count_tokens_before_request": False,
        "maximum_provider_calls": ASW4B_MAXIMUM_PROVIDER_CALLS,
        "prior_provider_call_count": prior_provider_call_count,
        "maximum_trajectory_provider_calls": (ASW4B_MAXIMUM_PROVIDER_CALLS - prior_provider_call_count),
        "maximum_input_tokens_per_call": (ASW4B_MAXIMUM_INPUT_TOKENS_PER_CALL),
        "maximum_output_tokens_per_call": (ASW4B_MAXIMUM_OUTPUT_TOKENS_PER_CALL),
        "maximum_total_tokens": ASW4B_MAXIMUM_TOTAL_TOKENS,
        "maximum_spend_microunits": ASW4B_MAXIMUM_SPEND_MICROUNITS,
        "spend_currency": "USD",
        "input_usd_per_million_tokens": str(ASW4B_INPUT_USD_PER_MILLION_TOKENS),
        "output_usd_per_million_tokens": str(ASW4B_OUTPUT_USD_PER_MILLION_TOKENS),
        "logical_budget": logical_budget.model_dump(mode="json"),
        "system_prompt_revision": "asw-4b-station-steward.v1",
    }
    model_condition = ContinuityModelCondition(
        execution_kind=ContinuityExecutionKind.PROVIDER_MODEL,
        provider_id=ASW4B_PROVIDER_ID,
        model_id=ASW4B_MODEL_ID,
        adapter_id=ASW4B_ADAPTER_ID,
        model_configuration_sha256=canonical_content_sha256(
            model_configuration,
        ),
    )
    provider_authorization = ContinuityProviderAuthorization(
        authorization_id=ASW4B_AUTHORIZATION_ID,
        authorized_phase=ContinuityStudyPhase.SHAKEDOWN,
        approved_by="Theo",
        model_condition_sha256=model_condition.content_sha256,
        maximum_provider_calls=ASW4B_MAXIMUM_PROVIDER_CALLS,
        maximum_input_tokens_per_call=ASW4B_MAXIMUM_INPUT_TOKENS_PER_CALL,
        maximum_output_tokens_per_call=ASW4B_MAXIMUM_OUTPUT_TOKENS_PER_CALL,
        maximum_total_tokens=ASW4B_MAXIMUM_TOTAL_TOKENS,
        spend_currency="USD",
        maximum_spend_microunits=ASW4B_MAXIMUM_SPEND_MICROUNITS,
    )
    return ContinuityStudyManifest(
        study_id=CONTINUITY_STUDY_ID,
        study_generation_id=ASW4B_STUDY_GENERATION_ID,
        phase=ContinuityStudyPhase.SHAKEDOWN,
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
                "shakedown_selection": {
                    "history_slot_id": ASW4B_SELECTED_HISTORY_SLOT_ID,
                    "treatment": ContinuityTreatment.STRUCTURED_HANDOVER.value,
                    "trajectory_count": 1,
                },
            }
        ),
        model_condition=model_condition,
        provider_authorization=provider_authorization,
        history_classes=tuple(ContinuityHistoryClass),
        treatments=tuple(ContinuityTreatment),
        logical_budget=logical_budget,
        study_outcomes_allowed=False,
    )


def calculate_asw4b_spend_microunits(
    *,
    input_tokens: int,
    output_tokens: int,
) -> int:
    """Calculate the approved AU-route Bedrock price, rounded up."""

    for value, label in (
        (input_tokens, "input_tokens"),
        (output_tokens, "output_tokens"),
    ):
        if isinstance(value, bool) or value < 0:
            raise ValueError(f"{label} must be a non-negative integer")
    amount = (
        Decimal(input_tokens) * ASW4B_INPUT_USD_PER_MILLION_TOKENS
        + Decimal(output_tokens) * ASW4B_OUTPUT_USD_PER_MILLION_TOKENS
    )
    return int(amount.to_integral_value(rounding=ROUND_CEILING))


def maximum_asw4b_spend_microunits() -> int:
    """Return the most expensive token mix allowed by all approved limits."""

    maximum_output = min(
        ASW4B_MAXIMUM_TOTAL_TOKENS,
        ASW4B_MAXIMUM_PROVIDER_CALLS * ASW4B_MAXIMUM_OUTPUT_TOKENS_PER_CALL,
    )
    return calculate_asw4b_spend_microunits(
        input_tokens=ASW4B_MAXIMUM_TOTAL_TOKENS - maximum_output,
        output_tokens=maximum_output,
    )


def prepare_asw4b_h2_history(root: Path) -> PreparedAsw4bH2History:
    """Drive the real station to the frozen H2 handover point."""

    destination = Path(root)
    if destination.exists():
        raise FileExistsError(f"ASW-4B history root already exists: {destination}")
    destination.mkdir(parents=True, mode=0o700)
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    diagnostic_period = model.inflow.diagnostic_period_seconds
    handover_after_seconds = (
        model.resources.repair_kit_lead_seconds
        + model.resources.access_duration_seconds
        + model.resources.access_duration_seconds // 4
        + diagnostic_period // 2
    )
    evaluation_end_after_seconds = handover_after_seconds + (3 * diagnostic_period)
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
        _world_session_request(
            open_mode=WorldSessionOpenMode.START,
            session_id="asw-4b-history-session",
            agent_tenure_id="asw-4b-history-tenure",
        )
    )
    reason = "Prepare the accepted H2 station history before treatment."
    history_session.request_conditional_deferral(
        "asw-4b-history-01",
        reason,
        "pump-a",
    )
    history_session.transfer_duty("asw-4b-history-02", reason)
    history_session.request_inspection(
        "asw-4b-history-03",
        reason,
        "pump-a",
    )
    completed_inspection = json.loads(history_session.continue_operation("asw-4b-history-04", reason))
    inspection_id = _evidence_id(completed_inspection, "inspection")
    history_session.continue_operation("asw-4b-history-05", reason)
    history_session.request_obstruction_clearance(
        "asw-4b-history-06",
        reason,
        "pump-a",
        inspection_id,
    )
    history_session.continue_operation("asw-4b-history-07", reason)
    completed_checks = json.loads(history_session.continue_operation("asw-4b-history-08", reason))
    functional_check_id = _evidence_id(
        completed_checks,
        "functional_checks",
    )
    provisional_return = json.loads(
        history_session.request_provisional_return(
            "asw-4b-history-09",
            reason,
            "pump-a",
            functional_check_id,
        )
    )
    work_orders = provisional_return["view"]["current_state"]["work_orders"]
    if not isinstance(work_orders, list) or len(work_orders) != 1:
        raise ValueError("ASW-4B history did not produce one work order")
    work_order_id = str(work_orders[0]["work_order_id"])
    history_session.request_provisional_closure(
        "asw-4b-history-10",
        reason,
        work_order_id,
    )
    provisional_closure_seconds = history_session.actor_view.current_state.calendar_seconds
    history_session.continue_operation("asw-4b-history-11", reason)
    history_verification = history_session.verify()
    if not history_verification.valid:
        raise ValueError("ASW-4B H2 history does not replay")

    fresh_session = PumpStationWorldSessionFactory(
        destination / "world-run",
    ).open(
        _world_session_request(
            open_mode=WorldSessionOpenMode.RESUME,
            session_id="asw-4b-fresh-session",
            agent_tenure_id="asw-4b-fresh-tenure",
            start_snapshot=history_session.result.snapshot,
        )
    )
    handover = create_structured_handover(
        fresh_session.actor_view,
        from_tenure_id="asw-4b-history-tenure",
        history=history_session.actor_history,
        maximum_history_entries=16,
    )
    fresh_session.install_structured_handover(handover)
    verification = fresh_session.verify()
    if not verification.valid:
        raise ValueError("ASW-4B resumed H2 history does not replay")
    _validate_h2_handover_state(
        fresh_session,
        provisional_closure_seconds=provisional_closure_seconds,
        diagnostic_period_seconds=diagnostic_period,
    )
    return PreparedAsw4bH2History(
        history_class=ContinuityHistoryClass.H2_WORSENING_VERIFICATION,
        session=fresh_session,
        handover=handover,
        verification=verification,
        history_snapshot_sha256=fresh_session.result.snapshot.state_id,
        event_schedule_sha256=fresh_session.event_schedule_sha256,
        provisional_closure_seconds=provisional_closure_seconds,
        diagnostic_period_seconds=diagnostic_period,
    )


def select_asw4b_shakedown_trial(
    plan: ContinuityStudyPlan,
) -> tuple[ContinuityBlock, ContinuityTrial]:
    """Select the one approved H2 structured-handover trajectory."""

    block = next(item for item in plan.blocks if item.history_slot_id == ASW4B_SELECTED_HISTORY_SLOT_ID)
    trial = next(item for item in block.trials if item.treatment is ContinuityTreatment.STRUCTURED_HANDOVER)
    return block, trial


def run_asw4b_shakedown(
    root: Path,
    *,
    registry: Any | None = None,
    prior_provider_call_count: int = 0,
) -> PublishedAsw4bShakedown:
    """Run, publish, and independently verify the approved ASW-4B sample."""

    destination = Path(root)
    if destination.exists():
        raise FileExistsError(f"ASW-4B output already exists: {destination}")
    destination.mkdir(parents=True, mode=0o700)
    repository = EvidenceRepository(destination, host_private=True)
    prepared = prepare_asw4b_h2_history(destination / "history")
    manifest = build_asw4b_shakedown_manifest(
        prior_provider_call_count=prior_provider_call_count,
    )
    plan = build_continuity_plan(
        manifest,
        history_snapshot_sha256_by_slot={
            ASW4B_SELECTED_HISTORY_SLOT_ID: (prepared.history_snapshot_sha256),
        },
        event_schedule_sha256_by_slot={
            ASW4B_SELECTED_HISTORY_SLOT_ID: prepared.event_schedule_sha256,
        },
    )
    block, trial = select_asw4b_shakedown_trial(plan)
    delivery = _treatment_delivery(
        manifest=manifest,
        plan=plan,
        block=block,
        trial=trial,
        prepared=prepared,
    )

    manifest_reference = repository.publish_content_addressed_model(
        collection="manifests",
        filename="study-manifest.json",
        model=manifest,
        adapter=_MANIFEST_ADAPTER,
    ).artifact
    plan_reference = repository.publish_content_addressed_model(
        collection="plans",
        filename="study-plan.json",
        model=plan,
        adapter=_PLAN_ADAPTER,
    ).artifact
    delivery_reference = repository.publish_content_addressed_model(
        collection="treatment-deliveries",
        filename="treatment-delivery.json",
        model=delivery,
        adapter=_DELIVERY_ADAPTER,
    ).artifact
    handover_reference = repository.publish_bytes(
        (f"handovers/{prepared.handover.handover_id}/structured-handover.json"),
        pump_station_artifact_bytes(prepared.handover),
    )

    agent_root = destination / "agent-evidence"
    agent_root.mkdir(mode=0o700)
    budgeted_tools = _Asw4bToolBudget(
        prepared.session,
        manifest.logical_budget,
    )
    trajectory = TrajectoryWriter(path=str(agent_root / "trajectory.jsonl"))
    try:
        selected_registry = registry or _local_adapter_registry()
        adapter = selected_registry.build(
            adapter_kind=ASW4B_ADAPTER_ID,
            model_name=ASW4B_MODEL_ID,
            workspace=str(agent_root),
            trajectory_writer=trajectory,
            native_tools=list(budgeted_tools.native_tools),
            enable_bash=False,
            cache=False,
        )
        adapter_result = adapter.execute(
            AdapterRequest(
                instruction=_model_instruction(prepared.handover),
                system_prompt=_model_system_prompt(),
                tools=list(prepared.session.tool_specs),
                configuration=_adapter_configuration(
                    prior_provider_call_count=prior_provider_call_count,
                ),
                output_path=str(agent_root / "output.md"),
                output_format="markdown",
            )
        )
    finally:
        trajectory.close()

    _write_adapter_evidence(agent_root, adapter_result)
    usage = _validated_usage(
        adapter_result,
        manifest,
        prior_provider_call_count=prior_provider_call_count,
    )
    verification = prepared.session.verify()
    observation = _observation(
        manifest=manifest,
        plan=plan,
        block=block,
        trial=trial,
        delivery=delivery,
        adapter_result=adapter_result,
        verification=verification,
        usage=usage,
    )
    report = analyse_continuity_study(
        manifest=manifest,
        plan=plan,
        deliveries=(delivery,),
        observations=(observation,),
    )
    output = adapter_result.raw_output_text or ""
    execution = Asw4bShakedownExecution(
        manifest_content_sha256=manifest.content_sha256,
        plan_content_sha256=plan.content_sha256,
        trial_id=trial.trial_id,
        history_snapshot_sha256=block.history_snapshot_sha256,
        event_schedule_sha256=block.event_schedule_sha256,
        handover_content_sha256=prepared.handover.handover_id,
        start_state_sha256=prepared.history_snapshot_sha256,
        final_state_sha256=prepared.session.result.snapshot.state_id,
        host_command_count=budgeted_tools.host_command_count,
        agent_proposal_count=budgeted_tools.agent_proposal_count,
        provider_call_count=usage.provider_calls,
        preflight_provider_call_count=usage.preflight_provider_calls,
        trajectory_provider_call_count=usage.trajectory_provider_calls,
        input_token_count=usage.input_tokens,
        output_token_count=usage.output_tokens,
        maximum_input_tokens_in_one_call=usage.maximum_input_tokens,
        maximum_output_tokens_in_one_call=usage.maximum_output_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        cache_write_tokens=usage.cache_write_tokens,
        advisor_call_count=usage.advisor_calls,
        spend_microunits=usage.spend_microunits,
        adapter_status=adapter_result.agent_output.status.value,
        adapter_failure_kind=(None if adapter_result.failure_kind is None else adapter_result.failure_kind.value),
        world_verification_valid=verification.valid,
        final_open_obligation_count=len(verification.open_obligation_ids),
        final_active_restriction_count=len(verification.active_restriction_ids),
        output_sha256=hashlib.sha256(output.encode("utf-8")).hexdigest(),
        secret_scan_passed=True,
    )

    observation_reference = repository.publish_content_addressed_model(
        collection="observations",
        filename="observation.json",
        model=observation,
        adapter=_OBSERVATION_ADAPTER,
    ).artifact
    execution_adapter = TypeAdapter(Asw4bShakedownExecution)
    execution_reference = repository.publish_content_addressed_model(
        collection="executions",
        filename="shakedown-execution.json",
        model=execution,
        adapter=execution_adapter,
    ).artifact
    report_reference = repository.publish_content_addressed_model(
        collection="reports",
        filename="study-report.json",
        model=report,
        adapter=_REPORT_ADAPTER,
    ).artifact
    _assert_no_secret_material(destination)

    from aec_bench.experiments.stewardship_continuity.artifacts import (
        reload_and_verify_study_report,
    )

    if (
        reload_and_verify_study_report(
            root=destination,
            report_content_sha256=report.content_sha256,
        )
        != report
    ):
        raise ImmutableArtifactIntegrityError(
            "reloaded ASW-4B report differs",
        )
    reloaded_execution = repository.load_content_addressed_model(
        collection="executions",
        content_sha256=execution.content_sha256,
        filename="shakedown-execution.json",
        adapter=execution_adapter,
    ).model
    if reloaded_execution != execution:
        raise ImmutableArtifactIntegrityError(
            "reloaded ASW-4B execution differs",
        )
    return PublishedAsw4bShakedown(
        manifest=manifest,
        plan=plan,
        block=block,
        trial=trial,
        delivery=delivery,
        observation=observation,
        execution=execution,
        report=report,
        manifest_reference=manifest_reference,
        plan_reference=plan_reference,
        delivery_reference=delivery_reference,
        observation_reference=observation_reference,
        execution_reference=execution_reference,
        report_reference=report_reference,
        handover_reference=handover_reference,
    )


@dataclass(frozen=True, slots=True)
class _ValidatedUsage:
    provider_calls: int
    preflight_provider_calls: int
    trajectory_provider_calls: int
    input_tokens: int
    output_tokens: int
    maximum_input_tokens: int
    maximum_output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    advisor_calls: int
    spend_microunits: int


def _validated_usage(
    result: AdapterResult,
    manifest: ContinuityStudyManifest,
    *,
    prior_provider_call_count: int,
) -> _ValidatedUsage:
    authority = manifest.provider_authorization
    if authority is None:
        raise ValueError("ASW-4B manifest has no provider authority")
    values = {
        "provider_calls": result.usage_model_calls,
        "input_tokens": result.usage_input_tokens,
        "output_tokens": result.usage_output_tokens,
        "maximum_input_tokens": result.maximum_input_tokens_in_one_call,
        "maximum_output_tokens": result.maximum_output_tokens_in_one_call,
        "cache_read_tokens": result.usage_cache_read_tokens,
        "cache_write_tokens": result.usage_cache_write_tokens,
    }
    missing = tuple(name for name, value in values.items() if value is None)
    if missing:
        raise ValueError(f"ASW-4B provider usage is incomplete: {', '.join(missing)}")
    selected = {name: value for name, value in values.items() if value is not None}
    if selected["provider_calls"] < 1:
        raise ValueError("ASW-4B shakedown made no provider call")
    total_provider_calls = prior_provider_call_count + selected["provider_calls"]
    advisor_calls = result.usage_advisor_calls or 0
    spend = calculate_asw4b_spend_microunits(
        input_tokens=selected["input_tokens"],
        output_tokens=selected["output_tokens"],
    )
    usage = _ValidatedUsage(
        provider_calls=total_provider_calls,
        preflight_provider_calls=prior_provider_call_count,
        trajectory_provider_calls=selected["provider_calls"],
        input_tokens=selected["input_tokens"],
        output_tokens=selected["output_tokens"],
        maximum_input_tokens=selected["maximum_input_tokens"],
        maximum_output_tokens=selected["maximum_output_tokens"],
        cache_read_tokens=selected["cache_read_tokens"],
        cache_write_tokens=selected["cache_write_tokens"],
        advisor_calls=advisor_calls,
        spend_microunits=spend,
    )
    if (
        usage.provider_calls > authority.maximum_provider_calls
        or usage.maximum_input_tokens > authority.maximum_input_tokens_per_call
        or usage.maximum_output_tokens > authority.maximum_output_tokens_per_call
        or usage.input_tokens + usage.output_tokens > authority.maximum_total_tokens
        or usage.spend_microunits > authority.maximum_spend_microunits
    ):
        raise ValueError("ASW-4B provider usage exceeds its authority")
    if usage.cache_read_tokens or usage.cache_write_tokens:
        raise ValueError("ASW-4B unexpectedly used provider cache")
    if usage.advisor_calls:
        raise ValueError("ASW-4B unexpectedly used an advisor")
    return usage


def _treatment_delivery(
    *,
    manifest: ContinuityStudyManifest,
    plan: ContinuityStudyPlan,
    block: ContinuityBlock,
    trial: ContinuityTrial,
    prepared: PreparedAsw4bH2History,
) -> TreatmentDeliveryRecord:
    current = prepared.handover.current_actor_view.current_state
    return TreatmentDeliveryRecord(
        manifest_content_sha256=manifest.content_sha256,
        plan_content_sha256=plan.content_sha256,
        block_id=block.block_id,
        trial_id=trial.trial_id,
        treatment=trial.treatment,
        source=ObservationSource.SHAKEDOWN,
        status=TreatmentDeliveryStatus.DELIVERED,
        delivered_before_outcome=True,
        current_state_equivalence_sha256=current.state_id,
        current_duties_sha256=stewardship_content_id(
            {
                "restrictions": current.restrictions,
                "obligations": current.obligations,
                "work_orders": current.work_orders,
                "processes": current.processes,
            }
        ),
        carrier_content_sha256=prepared.handover.handover_id,
        provider_call_count=0,
    )


def _observation(
    *,
    manifest: ContinuityStudyManifest,
    plan: ContinuityStudyPlan,
    block: ContinuityBlock,
    trial: ContinuityTrial,
    delivery: TreatmentDeliveryRecord,
    adapter_result: AdapterResult,
    verification: PumpStationVerificationReport,
    usage: _ValidatedUsage,
) -> ContinuityObservation:
    failure_kind, continuity_failure, ineligibility = _classify_execution(
        adapter_result,
        verification,
    )
    return ContinuityObservation(
        manifest_content_sha256=manifest.content_sha256,
        plan_content_sha256=plan.content_sha256,
        block_id=block.block_id,
        trial_id=trial.trial_id,
        treatment=trial.treatment,
        source=ObservationSource.SHAKEDOWN,
        delivery_content_sha256=delivery.content_sha256,
        history_snapshot_sha256=block.history_snapshot_sha256,
        event_schedule_sha256=block.event_schedule_sha256,
        logical_budget_sha256=trial.logical_budget_sha256,
        model_condition_sha256=manifest.model_condition.content_sha256,
        failure_kind=failure_kind,
        continuity_failure=continuity_failure,
        ineligibility_reason=ineligibility,
        study_outcome_eligible=False,
        provider_call_count=usage.provider_calls,
        input_token_count=usage.input_tokens,
        output_token_count=usage.output_tokens,
        maximum_input_tokens_in_one_call=usage.maximum_input_tokens,
        maximum_output_tokens_in_one_call=usage.maximum_output_tokens,
        spend_currency="USD",
        spend_microunits=usage.spend_microunits,
        task_reward_mutation_count=0,
    )


def _classify_execution(
    result: AdapterResult,
    verification: PumpStationVerificationReport,
) -> tuple[
    ContinuityFailureKind,
    bool | None,
    PairIneligibilityReason | None,
]:
    if not verification.valid:
        return (
            ContinuityFailureKind.HOST_FAILURE_AFTER_DELIVERY,
            None,
            PairIneligibilityReason.HOST_FAILURE,
        )
    if result.failure_kind is not None:
        mapped = {
            AdapterFailureKind.TIMEOUT: ContinuityFailureKind.MODEL_TIMEOUT,
            AdapterFailureKind.MISSING_OUTPUT: (ContinuityFailureKind.MODEL_EMPTY_OUTPUT),
        }.get(result.failure_kind, ContinuityFailureKind.TOOL_FAILURE)
        return mapped, True, None
    if result.agent_output.status is AgentOutputStatus.EMPTY:
        return ContinuityFailureKind.MODEL_EMPTY_OUTPUT, True, None
    return (
        ContinuityFailureKind.NONE,
        bool(verification.open_obligation_ids),
        None,
    )


def _validate_h2_handover_state(
    session: PumpStationWorldSession,
    *,
    provisional_closure_seconds: int,
    diagnostic_period_seconds: int,
) -> None:
    current = session.actor_view.current_state
    if current.calendar_seconds != provisional_closure_seconds + diagnostic_period_seconds // 2:
        raise ValueError("ASW-4B handover is not at D/2 after closure")
    restrictions = tuple(
        item
        for item in current.restrictions
        if item.kind is PumpStationRestrictionKind.POST_MAINTENANCE_RUN_IN
        and item.status is PumpStationRestrictionStatus.ACTIVE
    )
    obligations = tuple(
        item for item in current.obligations if item.status is not PumpStationObligationStatus.FULFILLED
    )
    if len(restrictions) != 1 or len(obligations) != 1:
        raise ValueError("ASW-4B H2 state lacks its live restriction or duty")
    if obligations[0].due_calendar_seconds - current.calendar_seconds != 3 * diagnostic_period_seconds // 2:
        raise ValueError("ASW-4B verification duty is not close to its trigger")
    if (
        len(current.work_orders) != 1
        or current.work_orders[0].status is not PumpStationWorkOrderStatus.PROVISIONALLY_CLOSED
    ):
        raise ValueError("ASW-4B H2 work order is not provisionally closed")


def _world_session_request(
    *,
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
        run_id="asw-4b-h2-run",
        episode_id="asw-4b-h2-episode",
        world_branch_id="asw-4b-h2-branch",
        start_snapshot=start_snapshot,
    )


def _evidence_id(transition: dict[str, Any], kind: str) -> str:
    evidence = transition["view"]["current_state"]["evidence"]
    if not isinstance(evidence, list):
        raise ValueError("ASW-4B history evidence is not a list")
    for item in evidence:
        if isinstance(item, dict) and item.get("kind") == kind:
            value = item.get("evidence_id")
            if isinstance(value, str) and value:
                return value
    raise ValueError(f"ASW-4B history lacks {kind} evidence")


def _adapter_configuration(
    *,
    prior_provider_call_count: int,
) -> dict[str, Any]:
    return {
        "max_turns": (ASW4B_MAXIMUM_PROVIDER_CALLS - prior_provider_call_count),
        "max_tool_calls": 32,
        "max_input_tokens": ASW4B_MAXIMUM_INPUT_TOKENS_PER_CALL,
        "max_total_tokens": ASW4B_MAXIMUM_TOTAL_TOKENS,
        "max_output_tokens_per_call": ASW4B_MAXIMUM_OUTPUT_TOKENS_PER_CALL,
        "count_tokens_before_request": False,
        "cache_enabled": False,
        "advisor_enabled": False,
        "bash_enabled": False,
    }


def _model_system_prompt() -> str:
    return (
        "You are the accountable wastewater pump-station steward for a fresh "
        "work tenure. Use only the declared station tools and the supplied "
        "structured handover. Work from live identifiers. Do not invent "
        "evidence. A work-order closure does not remove an operating limit or "
        "complete an independent verification duty. Keep each proposal_id "
        "unique. Stop after the present duties are safely dealt with."
    )


def _model_instruction(handover: PumpStationStructuredHandover) -> str:
    return (
        "Continue stewardship of the live station. Read the structured "
        "handover, observe the station when needed, and deal with every present "
        "restriction and required follow-up through the declared tools. Do not "
        "use external search. Do not assume future events or a study end time. "
        "Return a short factual summary when the present required follow-up is "
        "complete.\n\nSTRUCTURED HANDOVER\n" + pump_station_artifact_bytes(handover).decode("utf-8")
    )


def _local_adapter_registry() -> Any:
    from aec_bench.adapters.local_registry import LocalAdapterRegistry

    return LocalAdapterRegistry()


def _write_adapter_evidence(
    destination: Path,
    result: AdapterResult,
) -> None:
    output = result.raw_output_text or ""
    (destination / "output.md").write_text(output, encoding="utf-8")
    _write_json(
        destination / "agent-result.json",
        {
            "status": result.agent_output.status.value,
            "adapter_name": result.adapter_name,
            "resolved_model": result.resolved_model,
            "configuration_record": result.configuration_record,
            "turns_used": result.turns_used,
            "max_turns": result.max_turns,
            "provider_calls": result.usage_model_calls,
            "input_tokens": result.usage_input_tokens,
            "output_tokens": result.usage_output_tokens,
            "maximum_input_tokens_in_one_call": (result.maximum_input_tokens_in_one_call),
            "maximum_output_tokens_in_one_call": (result.maximum_output_tokens_in_one_call),
            "cache_read_tokens": result.usage_cache_read_tokens,
            "cache_write_tokens": result.usage_cache_write_tokens,
            "advisor_calls": result.usage_advisor_calls,
            "failure_kind": (None if result.failure_kind is None else result.failure_kind.value),
            "provider_error": result.provider_error,
        },
    )
    with (destination / "conversation.jsonl").open(
        "w",
        encoding="utf-8",
    ) as handle:
        for entry in result.transcript:
            handle.write(
                json.dumps(
                    {
                        "role": entry.role.value,
                        "event": entry.event.value,
                        "content": entry.content,
                        "tool_name": entry.tool_name,
                        "tool_call_id": entry.tool_call_id,
                    },
                    sort_keys=True,
                )
                + "\n"
            )


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _assert_no_secret_material(root: Path) -> None:
    credential_names = (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_BEARER_TOKEN_BEDROCK",
    )
    forbidden = {name.encode("utf-8") for name in credential_names}
    forbidden.update(value.encode("utf-8") for name in credential_names if len(value := os.environ.get(name, "")) >= 8)
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        payload = path.read_bytes()
        if any(item in payload for item in forbidden):
            raise ValueError(f"ASW-4B evidence contains credential material: {path.name}")


__all__ = (
    "ASW4B_ADAPTER_ID",
    "ASW4B_MODEL_ID",
    "ASW4B_PROVIDER_ID",
    "ASW4B_STUDY_GENERATION_ID",
    "Asw4bShakedownExecution",
    "PreparedAsw4bH2History",
    "PublishedAsw4bShakedown",
    "build_asw4b_shakedown_manifest",
    "calculate_asw4b_spend_microunits",
    "maximum_asw4b_spend_microunits",
    "prepare_asw4b_h2_history",
    "run_asw4b_shakedown",
    "select_asw4b_shakedown_trial",
)
