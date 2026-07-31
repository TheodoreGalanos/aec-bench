# ABOUTME: Prepares, publishes, resumes, and executes the frozen ASW-4C study.
# ABOUTME: Keeps trial evidence immutable and provider authority phase-bound.

from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Any, Literal, Self

from pydantic import (
    NonNegativeInt,
    PositiveInt,
    TypeAdapter,
    field_validator,
    model_validator,
)

from aec_bench.adapters.base import (
    AdapterFailureKind,
    AdapterRequest,
    AdapterResult,
)
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.evaluation_result import StewardshipEvaluation
from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    validate_sha256,
)
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.evaluation.stewardship import (
    evaluate_pump_station_stewardship_run,
)
from aec_bench.experiments.stewardship_continuity.analysis import (
    analyse_continuity_study,
)
from aec_bench.experiments.stewardship_continuity.artifacts import (
    reload_and_verify_study_report,
)
from aec_bench.experiments.stewardship_continuity.confirmatory import (
    ASW4C_ADAPTER_ID,
    ASW4C_HOST_WINDOW_PROPOSAL_PREFIX,
    ASW4C_INPUT_USD_PER_MILLION_TOKENS,
    ASW4C_MAXIMUM_INPUT_TOKENS_PER_CALL,
    ASW4C_MAXIMUM_OUTPUT_TOKENS_PER_CALL,
    ASW4C_MAXIMUM_TOTAL_TOKENS_PER_TRAJECTORY,
    ASW4C_MODEL_ID,
    ASW4C_OUTPUT_USD_PER_MILLION_TOKENS,
    PreparedAsw4cHistory,
    advance_asw4c_to_evaluation_end,
    asw4c_world_continuity_failure,
    build_asw4c_confirmatory_manifest,
    calculate_asw4c_spend_microunits,
    prepare_asw4c_history,
)
from aec_bench.experiments.stewardship_continuity.contracts import (
    ContinuityFailureKind,
    ContinuityHistoryClass,
    ContinuityObservation,
    ContinuityStudyManifest,
    ContinuityStudyPhase,
    ContinuityStudyPlan,
    ContinuityStudyReport,
    ContinuityTreatment,
    ContinuityTrial,
    EvaluationWindow,
    ObservationSource,
    PairIneligibilityReason,
    TreatmentDeliveryRecord,
    TreatmentDeliveryStatus,
)
from aec_bench.experiments.stewardship_continuity.planning import (
    build_continuity_plan,
)
from aec_bench.ledger.durability import fsync_directory
from aec_bench.meta_harness.immutable_artifact_store import (
    EvidenceRepository,
    ImmutableArtifactIntegrityError,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationExecutionOutcome,
    PumpStationObligationStatus,
    PumpStationStewardshipState,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationActorView,
    PumpStationStructuredHandover,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PUMP_STATION_SERIALIZATION_VERSION,
    PumpStationCurrentRunPointer,
    PumpStationStateSnapshotRef,
    PumpStationWorldRunCommit,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    load_pump_station_artifact,
    pump_station_artifact_bytes,
    pump_station_artifact_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
    PUMP_STATION_TOOL_NAMES,
    PumpStationWorldSession,
    PumpStationWorldSessionFactory,
)
from aec_bench.trajectory.writer import TrajectoryWriter

ASW4C_PREPARED_TRIAL_SCHEMA_VERSION: Literal["aecbench.stewardship-continuity-prepared-trial.v1"] = (
    "aecbench.stewardship-continuity-prepared-trial.v1"
)
ASW4C_STUDY_INDEX_SCHEMA_VERSION: Literal["aecbench.stewardship-continuity-study-index.v1"] = (
    "aecbench.stewardship-continuity-study-index.v1"
)
ASW4C_TRIAL_START_SCHEMA_VERSION: Literal["aecbench.stewardship-continuity-trial-start.v1"] = (
    "aecbench.stewardship-continuity-trial-start.v1"
)
ASW4C_TRIAL_EXECUTION_SCHEMA_VERSION: Literal["aecbench.stewardship-continuity-trial-execution.v1"] = (
    "aecbench.stewardship-continuity-trial-execution.v1"
)
ASW4C_TRIAL_COMPLETION_SCHEMA_VERSION: Literal["aecbench.stewardship-continuity-trial-completion.v1"] = (
    "aecbench.stewardship-continuity-trial-completion.v1"
)
ASW4C_FINAL_INDEX_SCHEMA_VERSION: Literal["aecbench.stewardship-continuity-final-index.v1"] = (
    "aecbench.stewardship-continuity-final-index.v1"
)
ASW4C_TOKEN_MEASUREMENT_AMENDMENT_SCHEMA_VERSION: Literal[
    "aecbench.stewardship-continuity-token-measurement-amendment.v1"
] = "aecbench.stewardship-continuity-token-measurement-amendment.v1"

_MANIFEST_ADAPTER = TypeAdapter(ContinuityStudyManifest)
_PLAN_ADAPTER = TypeAdapter(ContinuityStudyPlan)
_DELIVERY_ADAPTER = TypeAdapter(TreatmentDeliveryRecord)
_OBSERVATION_ADAPTER = TypeAdapter(ContinuityObservation)
_EVALUATION_ADAPTER = TypeAdapter(StewardshipEvaluation)


class Asw4cPreparedTrial(ContentAddressedModel):
    """Immutable provider-free world and carrier record for one trial."""

    schema_version: Literal["aecbench.stewardship-continuity-prepared-trial.v1"] = ASW4C_PREPARED_TRIAL_SCHEMA_VERSION
    manifest_content_sha256: str
    plan_content_sha256: str
    block_id: NonEmptyStr
    trial_id: NonEmptyStr
    history_slot_id: NonEmptyStr
    history_class: ContinuityHistoryClass
    treatment: ContinuityTreatment
    evaluation_window: EvaluationWindow
    world_relative_path: NonEmptyStr
    carrier_relative_path: NonEmptyStr
    start_snapshot: StewardshipStateSnapshotRef
    history_snapshot_sha256: str
    event_schedule_sha256: str
    current_state_equivalence_sha256: str
    current_duties_sha256: str
    carrier_content_sha256: str
    handover_content_sha256: str | None
    handover_seconds: NonNegativeInt
    evaluation_end_seconds: PositiveInt
    diagnostic_period_seconds: PositiveInt
    history_transition_count: PositiveInt
    quantized_scalar_reading: NonEmptyStr
    open_obligation_count: NonNegativeInt
    active_restriction_count: NonNegativeInt

    @field_validator(
        "manifest_content_sha256",
        "plan_content_sha256",
        "history_snapshot_sha256",
        "event_schedule_sha256",
        "current_state_equivalence_sha256",
        "current_duties_sha256",
        "carrier_content_sha256",
    )
    @classmethod
    def validate_required_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("handover_content_sha256")
    @classmethod
    def validate_optional_hash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_sha256(value)

    @field_validator("world_relative_path", "carrier_relative_path")
    @classmethod
    def validate_relative_paths(cls, value: str) -> str:
        logical = PurePosixPath(value)
        if logical.is_absolute() or not logical.parts or any(part in {"", ".", ".."} for part in logical.parts):
            raise ValueError("ASW-4C prepared paths must be confined and relative")
        return value

    @model_validator(mode="after")
    def validate_prepared_trial(self) -> Self:
        has_handover = self.handover_content_sha256 is not None
        if has_handover != (self.treatment is ContinuityTreatment.STRUCTURED_HANDOVER):
            raise ValueError("ASW-4C prepared carrier differs from its treatment")
        if self.evaluation_end_seconds - self.handover_seconds != self.evaluation_window.seconds:
            raise ValueError("ASW-4C prepared endpoint differs from its window")
        if self.quantized_scalar_reading != "0.0262":
            raise ValueError("ASW-4C prepared trial lacks the matched scalar")
        return self


class Asw4cStudyIndex(ContentAddressedModel):
    """Root identity for one complete provider-free ASW-4C preparation."""

    schema_version: Literal["aecbench.stewardship-continuity-study-index.v1"] = ASW4C_STUDY_INDEX_SCHEMA_VERSION
    manifest_content_sha256: str
    plan_content_sha256: str
    prepared_trial_content_sha256: tuple[str, ...]
    delivery_content_sha256: tuple[str, ...]

    @field_validator(
        "manifest_content_sha256",
        "plan_content_sha256",
    )
    @classmethod
    def validate_root_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator(
        "prepared_trial_content_sha256",
        "delivery_content_sha256",
    )
    @classmethod
    def validate_ordered_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != 64 or len(set(value)) != 64:
            raise ValueError("ASW-4C study index requires 64 unique records")
        for digest in value:
            validate_sha256(digest)
        return value


class Asw4cTrialStart(ContentAddressedModel):
    """Immutable fence written before one outcome-bearing model execution."""

    schema_version: Literal["aecbench.stewardship-continuity-trial-start.v1"] = ASW4C_TRIAL_START_SCHEMA_VERSION
    manifest_content_sha256: str
    plan_content_sha256: str
    trial_id: NonEmptyStr
    prepared_trial_content_sha256: str
    delivery_content_sha256: str
    sequence_index: PositiveInt
    cumulative_provider_calls_before: NonNegativeInt
    cumulative_input_tokens_before: NonNegativeInt
    cumulative_output_tokens_before: NonNegativeInt
    cumulative_spend_microunits_before: NonNegativeInt
    provider_execution_started: Literal[True] = True

    @field_validator(
        "manifest_content_sha256",
        "plan_content_sha256",
        "prepared_trial_content_sha256",
        "delivery_content_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class Asw4cTokenMeasurementAmendment(ContentAddressedModel):
    """Immutable approval that makes token use measured instead of limiting."""

    schema_version: Literal["aecbench.stewardship-continuity-token-measurement-amendment.v1"] = (
        ASW4C_TOKEN_MEASUREMENT_AMENDMENT_SCHEMA_VERSION
    )
    manifest_content_sha256: str
    authorization_id: NonEmptyStr
    approved_by: NonEmptyStr
    tokens_are_measurements: Literal[True] = True
    hard_provider_call_limit: Literal[1_024] = 1_024
    hard_spend_microunits: Literal[37_000_000] = 37_000_000
    hard_model_turn_limit: Literal[16] = 16
    hard_output_tokens_per_call: Literal[2_048] = 2_048
    cumulative_provider_calls_before: NonNegativeInt
    cumulative_input_tokens_before: NonNegativeInt
    cumulative_output_tokens_before: NonNegativeInt
    outcome_direction_inspected: Literal[False] = False

    @field_validator("manifest_content_sha256")
    @classmethod
    def validate_manifest_hash(cls, value: str) -> str:
        return validate_sha256(value)


class Asw4cTrialExecution(ContentAddressedModel):
    """Immutable model, host, world, endpoint, and evidence record."""

    schema_version: Literal["aecbench.stewardship-continuity-trial-execution.v1"] = ASW4C_TRIAL_EXECUTION_SCHEMA_VERSION
    manifest_content_sha256: str
    plan_content_sha256: str
    trial_id: NonEmptyStr
    start_content_sha256: str
    delivery_content_sha256: str
    history_snapshot_sha256: str
    event_schedule_sha256: str
    carrier_content_sha256: str
    start_state_sha256: str
    endpoint_state_sha256: str
    final_state_sha256: str
    evaluation_artifact_sha256: str
    output_sha256: str
    agent_result_sha256: str
    conversation_sha256: str
    trajectory_sha256: str
    provider_id: Literal["amazon-bedrock-au-geographic"] = "amazon-bedrock-au-geographic"
    model_id: Literal["au.anthropic.claude-sonnet-4-6"] = "au.anthropic.claude-sonnet-4-6"
    adapter_id: Literal["tool_loop"] = "tool_loop"
    execution_path: Literal["direct_host_session"] = "direct_host_session"
    cache_enabled: Literal[False] = False
    bash_enabled: Literal[False] = False
    advisor_enabled: Literal[False] = False
    fresh_agent_handovers: Literal[1] = 1
    model_turn_count: NonNegativeInt
    host_command_count: NonNegativeInt
    agent_proposal_count: NonNegativeInt
    invalid_command_count: NonNegativeInt
    endpoint_host_advancement_count: NonNegativeInt
    provider_call_count: NonNegativeInt
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
    failure_kind: ContinuityFailureKind
    continuity_failure: bool | None
    ineligibility_reason: PairIneligibilityReason | None
    world_verification_valid: bool
    stewardship_evaluation_valid: bool
    final_open_obligation_count: NonNegativeInt
    final_active_restriction_count: NonNegativeInt
    task_reward_mutation_count: Literal[0] = 0
    secret_scan_passed: Literal[True] = True

    @field_validator(
        "manifest_content_sha256",
        "plan_content_sha256",
        "start_content_sha256",
        "delivery_content_sha256",
        "history_snapshot_sha256",
        "event_schedule_sha256",
        "carrier_content_sha256",
        "start_state_sha256",
        "endpoint_state_sha256",
        "final_state_sha256",
        "evaluation_artifact_sha256",
        "output_sha256",
        "agent_result_sha256",
        "conversation_sha256",
        "trajectory_sha256",
    )
    @classmethod
    def validate_execution_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_trial_limits(self) -> Self:
        if self.model_turn_count > 16:
            raise ValueError("ASW-4C model turn count exceeds approval")
        if self.host_command_count > 32:
            raise ValueError("ASW-4C host command count exceeds approval")
        if self.agent_proposal_count > 12:
            raise ValueError("ASW-4C proposal count exceeds approval")
        if self.provider_call_count > 16:
            raise ValueError("ASW-4C provider call count exceeds approval")
        if (
            self.maximum_input_tokens_in_one_call > ASW4C_MAXIMUM_INPUT_TOKENS_PER_CALL
            or self.maximum_output_tokens_in_one_call > ASW4C_MAXIMUM_OUTPUT_TOKENS_PER_CALL
        ):
            raise ValueError("ASW-4C trial token use exceeds approval")
        if self.cache_read_tokens or self.cache_write_tokens:
            raise ValueError("ASW-4C cache use is not authorized")
        if self.advisor_call_count:
            raise ValueError("ASW-4C advisor use is not authorized")
        return self


class Asw4cTrialCompletion(ContentAddressedModel):
    """Immutable completion marker published after one trial is reloadable."""

    schema_version: Literal["aecbench.stewardship-continuity-trial-completion.v1"] = (
        ASW4C_TRIAL_COMPLETION_SCHEMA_VERSION
    )
    manifest_content_sha256: str
    plan_content_sha256: str
    trial_id: NonEmptyStr
    start_content_sha256: str
    prepared_trial_content_sha256: str
    delivery_content_sha256: str
    observation_content_sha256: str
    execution_content_sha256: str
    evaluation_artifact_sha256: str

    @field_validator(
        "manifest_content_sha256",
        "plan_content_sha256",
        "start_content_sha256",
        "prepared_trial_content_sha256",
        "delivery_content_sha256",
        "observation_content_sha256",
        "execution_content_sha256",
        "evaluation_artifact_sha256",
    )
    @classmethod
    def validate_completion_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class Asw4cFinalIndex(ContentAddressedModel):
    """Immutable pointer to the complete recomputable confirmatory report."""

    schema_version: Literal["aecbench.stewardship-continuity-final-index.v1"] = ASW4C_FINAL_INDEX_SCHEMA_VERSION
    manifest_content_sha256: str
    plan_content_sha256: str
    report_content_sha256: str
    completion_content_sha256: tuple[str, ...]

    @field_validator(
        "manifest_content_sha256",
        "plan_content_sha256",
        "report_content_sha256",
    )
    @classmethod
    def validate_final_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("completion_content_sha256")
    @classmethod
    def validate_completion_hashes(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if len(value) != 64 or len(set(value)) != 64:
            raise ValueError("ASW-4C final index requires 64 completions")
        for digest in value:
            validate_sha256(digest)
        return value


_PREPARED_TRIAL_ADAPTER = TypeAdapter(Asw4cPreparedTrial)
_STUDY_INDEX_ADAPTER = TypeAdapter(Asw4cStudyIndex)
_TRIAL_START_ADAPTER = TypeAdapter(Asw4cTrialStart)
_TOKEN_MEASUREMENT_AMENDMENT_ADAPTER = TypeAdapter(
    Asw4cTokenMeasurementAmendment,
)
_TRIAL_EXECUTION_ADAPTER = TypeAdapter(Asw4cTrialExecution)
_TRIAL_COMPLETION_ADAPTER = TypeAdapter(Asw4cTrialCompletion)
_FINAL_INDEX_ADAPTER = TypeAdapter(Asw4cFinalIndex)
_TOKEN_MEASUREMENT_AMENDMENT_PATH = "authority-amendments/token-measurement.json"


@dataclass(frozen=True, slots=True)
class PreparedAsw4cStudy:
    """Reloaded complete provider-free preparation for ASW-4C."""

    root: Path
    index: Asw4cStudyIndex
    manifest: ContinuityStudyManifest
    plan: ContinuityStudyPlan
    prepared_trials: tuple[Asw4cPreparedTrial, ...]
    deliveries: tuple[TreatmentDeliveryRecord, ...]


@dataclass(frozen=True, slots=True)
class Asw4cConfirmatoryProgress:
    """Current complete or safely paused ASW-4C execution state."""

    study: PreparedAsw4cStudy
    completions: tuple[Asw4cTrialCompletion, ...]
    observations: tuple[ContinuityObservation, ...]
    executions: tuple[Asw4cTrialExecution, ...]
    report: ContinuityStudyReport | None
    completed_trial_count: int
    complete: bool


class Asw4cInterruptedTrialError(RuntimeError):
    """Refuse to repeat a trial with a start fence but no completion."""


class Asw4cAuthorityExhaustedError(RuntimeError):
    """Stop before a new trial when its full reserve is unavailable."""


@dataclass(frozen=True, slots=True)
class _ValidatedUsage:
    provider_calls: int
    input_tokens: int
    output_tokens: int
    maximum_input_tokens: int
    maximum_output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    advisor_calls: int
    spend_microunits: int


@dataclass(frozen=True, slots=True)
class _CompletedAgentEvidence:
    evidence_sha256: dict[str, str]
    result_payload: dict[str, Any]
    usage: _ValidatedUsage
    model_turn_count: int
    host_command_count: int
    agent_proposal_count: int
    invalid_command_count: int


@dataclass(frozen=True, slots=True)
class _WorldChainForensics:
    selected_snapshot: PumpStationStateSnapshotRef
    last_valid_snapshot: PumpStationStateSnapshotRef
    invalid_commit_id: str
    invalid_commit: PumpStationWorldRunCommit
    selected_post_start_proposal_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _EndpointWorldPrefix:
    endpoint_snapshot: PumpStationStateSnapshotRef
    final_snapshot: PumpStationStateSnapshotRef
    endpoint_state: PumpStationStewardshipState
    final_state: PumpStationStewardshipState
    continuity_failure: bool
    invalid_command_count: int
    host_advancement_count: int


@dataclass(frozen=True, slots=True)
class _RetainedTrials:
    completions: tuple[Asw4cTrialCompletion, ...]
    observations: tuple[ContinuityObservation, ...]
    executions: tuple[Asw4cTrialExecution, ...]


class _Asw4cToolBudget:
    """Closed station tools with frozen command and proposal limits."""

    def __init__(self, session: PumpStationWorldSession) -> None:
        self._session = session
        self._lock = Lock()
        self.host_command_count = 0
        self.agent_proposal_count = 0
        self.invalid_command_count = 0

    @property
    def native_tools(self) -> tuple[Any, ...]:
        """Return the closed station tool set with public signatures."""

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
        if self.host_command_count >= 32:
            raise RuntimeError("ASW-4C host command limit reached")
        if proposal and self.agent_proposal_count >= 12:
            raise RuntimeError("ASW-4C proposal limit reached")
        self.host_command_count += 1
        if proposal:
            self.agent_proposal_count += 1

    def _invoke(self, action: Any, *, proposal: bool) -> str:
        with self._lock:
            self._count(proposal=proposal)
            try:
                result = action()
            except Exception:
                self.invalid_command_count += 1
                raise
            if not isinstance(result, str):
                self.invalid_command_count += 1
                raise TypeError("ASW-4C station tool did not return text")
            return result

    def observe_pump_station(self) -> str:
        """Read the complete current station view without future state."""

        return self._invoke(
            self._session.observe_pump_station,
            proposal=False,
        )

    def continue_operation(self, proposal_id: str, reason: str) -> str:
        """Continue the permitted operating mode to the next station event."""

        return self._invoke(
            lambda: self._session.continue_operation(proposal_id, reason),
            proposal=True,
        )

    def transfer_duty(self, proposal_id: str, reason: str) -> str:
        """Request the permitted transfer to the standby pump."""

        return self._invoke(
            lambda: self._session.transfer_duty(proposal_id, reason),
            proposal=True,
        )

    def request_inspection(
        self,
        proposal_id: str,
        reason: str,
        pump_id: str,
    ) -> str:
        """Request a scheduled inspection of one named pump."""

        return self._invoke(
            lambda: self._session.request_inspection(
                proposal_id,
                reason,
                pump_id,
            ),
            proposal=True,
        )

    def request_conditional_deferral(
        self,
        proposal_id: str,
        reason: str,
        pump_id: str,
    ) -> str:
        """Request the fixed transfer-then-isolate deferral."""

        return self._invoke(
            lambda: self._session.request_conditional_deferral(
                proposal_id,
                reason,
                pump_id,
            ),
            proposal=True,
        )

    def request_obstruction_clearance(
        self,
        proposal_id: str,
        reason: str,
        pump_id: str,
        inspection_evidence_id: str,
    ) -> str:
        """Request obstruction clearance with live inspection evidence."""

        return self._invoke(
            lambda: self._session.request_obstruction_clearance(
                proposal_id,
                reason,
                pump_id,
                inspection_evidence_id,
            ),
            proposal=True,
        )

    def request_provisional_return(
        self,
        proposal_id: str,
        reason: str,
        pump_id: str,
        functional_check_evidence_id: str,
    ) -> str:
        """Request provisional return with accepted check evidence."""

        return self._invoke(
            lambda: self._session.request_provisional_return(
                proposal_id,
                reason,
                pump_id,
                functional_check_evidence_id,
            ),
            proposal=True,
        )

    def request_provisional_closure(
        self,
        proposal_id: str,
        reason: str,
        work_order_id: str,
    ) -> str:
        """Request administrative closure of one work order."""

        return self._invoke(
            lambda: self._session.request_provisional_closure(
                proposal_id,
                reason,
                work_order_id,
            ),
            proposal=True,
        )

    def request_post_maintenance_verification(
        self,
        proposal_id: str,
        reason: str,
        pump_id: str,
    ) -> str:
        """Request independent verification for one named pump."""

        return self._invoke(
            lambda: self._session.request_post_maintenance_verification(
                proposal_id,
                reason,
                pump_id,
            ),
            proposal=True,
        )

    def snapshot_pump_station(self) -> str:
        """Read the exact current dynamic snapshot reference."""

        return self._invoke(
            self._session.snapshot_pump_station,
            proposal=False,
        )


def prepare_asw4c_confirmatory_study(
    root: Path,
    *,
    authorization_id: str,
    approved_by: str,
) -> PreparedAsw4cStudy:
    """Atomically prepare all frozen worlds and evidence without a provider."""

    destination = Path(root)
    manifest = build_asw4c_confirmatory_manifest(
        authorization_id=authorization_id,
        approved_by=approved_by,
    )
    if destination.exists():
        reloaded = reload_asw4c_confirmatory_study(destination)
        if reloaded.manifest != manifest:
            raise ImmutableArtifactIntegrityError(
                "existing ASW-4C preparation has another authority",
            )
        return reloaded

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / (f".{destination.name}.prepare-{uuid.uuid4().hex}")
    staging.mkdir(mode=0o700)
    try:
        _prepare_staging_study(
            staging,
            manifest=manifest,
        )
        if destination.exists():
            raise FileExistsError(
                f"ASW-4C destination appeared during preparation: {destination}",
            )
        os.replace(staging, destination)
        fsync_directory(destination.parent)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return reload_asw4c_confirmatory_study(destination)


def reload_asw4c_confirmatory_study(
    root: Path,
) -> PreparedAsw4cStudy:
    """Reload and validate one exact provider-free ASW-4C preparation."""

    destination = Path(root)
    repository = EvidenceRepository(destination, host_private=True)
    index = repository.load_model(
        "study-index.json",
        _STUDY_INDEX_ADAPTER,
    )
    manifest = repository.load_content_addressed_model(
        collection="manifests",
        content_sha256=index.manifest_content_sha256,
        filename="study-manifest.json",
        adapter=_MANIFEST_ADAPTER,
    ).model
    plan = repository.load_content_addressed_model(
        collection="plans",
        content_sha256=index.plan_content_sha256,
        filename="study-plan.json",
        adapter=_PLAN_ADAPTER,
    ).model
    prepared_trials = tuple(
        repository.load_content_addressed_model(
            collection="prepared-trials",
            content_sha256=content_sha256,
            filename="prepared-trial.json",
            adapter=_PREPARED_TRIAL_ADAPTER,
        ).model
        for content_sha256 in index.prepared_trial_content_sha256
    )
    deliveries = tuple(
        repository.load_content_addressed_model(
            collection="treatment-deliveries",
            content_sha256=content_sha256,
            filename="treatment-delivery.json",
            adapter=_DELIVERY_ADAPTER,
        ).model
        for content_sha256 in index.delivery_content_sha256
    )
    _validate_reloaded_preparation(
        repository=repository,
        index=index,
        manifest=manifest,
        plan=plan,
        prepared_trials=prepared_trials,
        deliveries=deliveries,
    )
    return PreparedAsw4cStudy(
        root=destination,
        index=index,
        manifest=manifest,
        plan=plan,
        prepared_trials=prepared_trials,
        deliveries=deliveries,
    )


def publish_asw4c_token_measurement_amendment(
    root: Path,
    *,
    authorization_id: str,
    approved_by: str,
) -> Asw4cTokenMeasurementAmendment:
    """Publish Theo's token-measurement authority before execution resumes."""

    study = reload_asw4c_confirmatory_study(root)
    repository = EvidenceRepository(study.root, host_private=True)
    retained = _load_retained_trials(
        study,
        reject_interrupted=False,
    )
    retained_by_trial = {observation.trial_id: observation for observation in retained.observations}
    calls = 0
    input_tokens = 0
    output_tokens = 0
    for relative_path in repository.list_child_files(
        "agent-evidence",
        filename="agent-result.json",
    ):
        payload = json.loads(repository.load_bytes(relative_path))
        if not isinstance(payload, dict):
            raise ImmutableArtifactIntegrityError(
                "ASW-4C agent result is not an object",
            )
        trial_id = PurePosixPath(relative_path).parent.name
        retained_observation = retained_by_trial.get(trial_id)
        calls += _usage_value_or_retained(
            payload.get("provider_calls"),
            retained_observation,
            "provider_call_count",
        )
        input_tokens += _usage_value_or_retained(
            payload.get("input_tokens"),
            retained_observation,
            "input_token_count",
        )
        output_tokens += _usage_value_or_retained(
            payload.get("output_tokens"),
            retained_observation,
            "output_token_count",
        )
    amendment = Asw4cTokenMeasurementAmendment(
        manifest_content_sha256=study.manifest.content_sha256,
        authorization_id=authorization_id,
        approved_by=approved_by,
        cumulative_provider_calls_before=calls,
        cumulative_input_tokens_before=input_tokens,
        cumulative_output_tokens_before=output_tokens,
    )
    repository.publish_model(
        _TOKEN_MEASUREMENT_AMENDMENT_PATH,
        amendment,
        _TOKEN_MEASUREMENT_AMENDMENT_ADAPTER,
    )
    return repository.load_model(
        _TOKEN_MEASUREMENT_AMENDMENT_PATH,
        _TOKEN_MEASUREMENT_AMENDMENT_ADAPTER,
    )


def run_asw4c_confirmatory(
    root: Path,
    *,
    authorization_id: str,
    approved_by: str,
    registry: Any | None = None,
    maximum_new_trials: int | None = None,
) -> Asw4cConfirmatoryProgress:
    """Execute or resume the frozen ASW-4C trials in plan order."""

    if maximum_new_trials is not None and (isinstance(maximum_new_trials, bool) or maximum_new_trials < 1):
        raise ValueError("maximum_new_trials must be a positive integer")
    study = prepare_asw4c_confirmatory_study(
        root,
        authorization_id=authorization_id,
        approved_by=approved_by,
    )
    repository = EvidenceRepository(study.root, host_private=True)
    token_measurement = (
        _load_token_measurement_amendment(
            repository=repository,
            manifest=study.manifest,
        )
        is not None
    )
    retained = _load_retained_trials(
        study,
        reject_interrupted=True,
    )
    completed_ids = {completion.trial_id for completion in retained.completions}
    prepared_by_trial = {item.trial_id: item for item in study.prepared_trials}
    delivery_by_trial = {item.trial_id: item for item in study.deliveries}
    selected_registry = registry or _local_adapter_registry()
    new_trial_count = 0

    for order, trial in enumerate(study.plan.trials, start=1):
        if trial.trial_id in completed_ids:
            continue
        if maximum_new_trials is not None and new_trial_count >= maximum_new_trials:
            break
        _ensure_trajectory_reserve(
            study.manifest,
            retained.observations,
            token_measurement=token_measurement,
        )
        prepared = prepared_by_trial[trial.trial_id]
        delivery = delivery_by_trial[trial.trial_id]
        start = Asw4cTrialStart(
            manifest_content_sha256=study.manifest.content_sha256,
            plan_content_sha256=study.plan.content_sha256,
            trial_id=trial.trial_id,
            prepared_trial_content_sha256=prepared.content_sha256,
            delivery_content_sha256=delivery.content_sha256,
            sequence_index=order,
            cumulative_provider_calls_before=sum(item.provider_call_count for item in retained.observations),
            cumulative_input_tokens_before=sum(item.input_token_count for item in retained.observations),
            cumulative_output_tokens_before=sum(item.output_token_count for item in retained.observations),
            cumulative_spend_microunits_before=sum(item.spend_microunits for item in retained.observations),
        )
        repository.publish_model(
            _trial_start_path(trial.trial_id),
            start,
            _TRIAL_START_ADAPTER,
        )
        observation, execution, evaluation_sha256 = _execute_asw4c_trial(
            repository=repository,
            study=study,
            trial=trial,
            prepared_record=prepared,
            delivery=delivery,
            start=start,
            registry=selected_registry,
            token_measurement=token_measurement,
        )
        _validate_stage_usage(
            study.manifest,
            (*retained.observations, observation),
            token_measurement=token_measurement,
        )
        repository.publish_content_addressed_model(
            collection="observations",
            filename="observation.json",
            model=observation,
            adapter=_OBSERVATION_ADAPTER,
        )
        repository.publish_content_addressed_model(
            collection="executions",
            filename="trial-execution.json",
            model=execution,
            adapter=_TRIAL_EXECUTION_ADAPTER,
        )
        completion = Asw4cTrialCompletion(
            manifest_content_sha256=study.manifest.content_sha256,
            plan_content_sha256=study.plan.content_sha256,
            trial_id=trial.trial_id,
            start_content_sha256=start.content_sha256,
            prepared_trial_content_sha256=prepared.content_sha256,
            delivery_content_sha256=delivery.content_sha256,
            observation_content_sha256=observation.content_sha256,
            execution_content_sha256=execution.content_sha256,
            evaluation_artifact_sha256=evaluation_sha256,
        )
        _verify_trial_before_completion(
            repository=repository,
            trial=trial,
            completion=completion,
        )
        repository.publish_model(
            _trial_completion_path(trial.trial_id),
            completion,
            _TRIAL_COMPLETION_ADAPTER,
        )
        new_trial_count += 1
        retained = _load_retained_trials(
            study,
            reject_interrupted=True,
        )
        completed_ids.add(trial.trial_id)

    if len(retained.completions) == len(study.plan.trials):
        _publish_final_report(
            repository=repository,
            study=study,
            retained=retained,
        )
        return reload_asw4c_confirmatory_result(study.root)
    return Asw4cConfirmatoryProgress(
        study=study,
        completions=retained.completions,
        observations=retained.observations,
        executions=retained.executions,
        report=None,
        completed_trial_count=len(retained.completions),
        complete=False,
    )


def recover_asw4c_interrupted_provider_fault(
    root: Path,
) -> Asw4cConfirmatoryProgress:
    """Record one proven expired host credential fault without repeating its trial."""

    return _recover_asw4c_interrupted_trial(
        root,
        evidence_kind="expired_credential",
    )


def recover_asw4c_interrupted_count_tokens_permission(
    root: Path,
) -> Asw4cConfirmatoryProgress:
    """Record one denied token-count request as a host fault without retry."""

    return _recover_asw4c_interrupted_trial(
        root,
        evidence_kind="count_tokens_permission",
    )


def recover_asw4c_interrupted_token_guard(
    root: Path,
) -> Asw4cConfirmatoryProgress:
    """Record the initial token guard as one measured host fault without retry."""

    return _recover_asw4c_interrupted_trial(
        root,
        evidence_kind="token_guard",
    )


def recover_asw4c_interrupted_world_terminal(
    root: Path,
) -> Asw4cConfirmatoryProgress:
    """Record one proven world-owned early failure without repeating its trial."""

    return _recover_asw4c_interrupted_trial(
        root,
        evidence_kind="world_terminal",
    )


def recover_asw4c_interrupted_endpoint_overshoot(
    root: Path,
) -> Asw4cConfirmatoryProgress:
    """Evaluate the exact frozen prefix after an agent passes the endpoint."""

    return _recover_asw4c_interrupted_trial(
        root,
        evidence_kind="endpoint_overshoot",
    )


def recover_asw4c_interrupted_concurrent_tool_fault(
    root: Path,
) -> Asw4cConfirmatoryProgress:
    """Record one proven concurrent station-tool host fault without retry."""

    return _recover_asw4c_interrupted_trial(
        root,
        evidence_kind="concurrent_tool_fault",
    )


def _recover_asw4c_interrupted_trial(
    root: Path,
    *,
    evidence_kind: Literal[
        "expired_credential",
        "count_tokens_permission",
        "token_guard",
        "world_terminal",
        "endpoint_overshoot",
        "concurrent_tool_fault",
    ],
) -> Asw4cConfirmatoryProgress:
    study = reload_asw4c_confirmatory_study(root)
    repository = EvidenceRepository(study.root, host_private=True)
    token_measurement = (
        _load_token_measurement_amendment(
            repository=repository,
            manifest=study.manifest,
        )
        is not None
    )
    if evidence_kind == "token_guard" and not token_measurement:
        raise Asw4cInterruptedTrialError(
            "ASW-4C token guard recovery requires the approved amendment",
        )
    retained = _load_retained_trials(
        study,
        reject_interrupted=False,
    )
    completed_ids = {completion.trial_id for completion in retained.completions}
    interrupted = tuple(
        trial
        for trial in study.plan.trials
        if repository.exists(_trial_start_path(trial.trial_id))
        and not repository.exists(_trial_completion_path(trial.trial_id))
    )
    if len(interrupted) != 1:
        raise Asw4cInterruptedTrialError(
            "ASW-4C recovery requires exactly one interrupted trial",
        )
    trial = interrupted[0]
    sequence_index = next(
        index for index, planned in enumerate(study.plan.trials, start=1) if planned.trial_id == trial.trial_id
    )
    expected_completed_ids = {planned.trial_id for planned in study.plan.trials[: sequence_index - 1]}
    if completed_ids != expected_completed_ids:
        raise Asw4cInterruptedTrialError(
            "ASW-4C interrupted trial does not follow retained plan order",
        )

    prepared = next(item for item in study.prepared_trials if item.trial_id == trial.trial_id)
    delivery = next(item for item in study.deliveries if item.trial_id == trial.trial_id)
    start = repository.load_model(
        _trial_start_path(trial.trial_id),
        _TRIAL_START_ADAPTER,
    )
    _validate_interrupted_start(
        study=study,
        trial=trial,
        prepared=prepared,
        delivery=delivery,
        start=start,
        retained=retained,
        sequence_index=sequence_index,
    )
    completed_evidence: _CompletedAgentEvidence | None = None
    if evidence_kind == "expired_credential":
        evidence_sha256, result_payload = _load_expired_credential_evidence(
            repository=repository,
            trial_id=trial.trial_id,
        )
        usage = _ValidatedUsage(
            provider_calls=1,
            input_tokens=0,
            output_tokens=0,
            maximum_input_tokens=0,
            maximum_output_tokens=0,
            cache_read_tokens=0,
            cache_write_tokens=0,
            advisor_calls=0,
            spend_microunits=0,
        )
        model_turn_count = 0
    elif evidence_kind == "count_tokens_permission":
        evidence_sha256, result_payload = _load_count_tokens_permission_evidence(
            repository=repository,
            trial_id=trial.trial_id,
        )
        usage = _ValidatedUsage(
            provider_calls=1,
            input_tokens=0,
            output_tokens=0,
            maximum_input_tokens=0,
            maximum_output_tokens=0,
            cache_read_tokens=0,
            cache_write_tokens=0,
            advisor_calls=0,
            spend_microunits=0,
        )
        model_turn_count = 0
    elif evidence_kind == "token_guard":
        (
            evidence_sha256,
            result_payload,
            usage,
            model_turn_count,
        ) = _load_token_guard_evidence(
            repository=repository,
            trial_id=trial.trial_id,
        )
    elif evidence_kind in {
        "world_terminal",
        "endpoint_overshoot",
    }:
        completed_evidence = _load_completed_agent_evidence(
            repository=repository,
            trial_id=trial.trial_id,
            token_measurement=token_measurement,
        )
        evidence_sha256 = completed_evidence.evidence_sha256
        result_payload = completed_evidence.result_payload
        usage = completed_evidence.usage
        model_turn_count = completed_evidence.model_turn_count
    else:
        (
            evidence_sha256,
            result_payload,
            usage,
            model_turn_count,
        ) = _load_concurrent_tool_fault_evidence(
            repository=repository,
            trial_id=trial.trial_id,
        )
    if evidence_kind == "endpoint_overshoot":
        if completed_evidence is None:
            raise Asw4cInterruptedTrialError(
                "ASW-4C endpoint recovery lacks completed agent evidence",
            )
        observation, execution, evaluation_sha256 = _build_interrupted_endpoint_overshoot(
            repository=repository,
            study=study,
            trial=trial,
            prepared_record=prepared,
            delivery=delivery,
            start=start,
            evidence=completed_evidence,
        )
    elif evidence_kind == "concurrent_tool_fault":
        observation, execution, evaluation_sha256 = _build_interrupted_concurrent_tool_fault(
            repository=repository,
            study=study,
            trial=trial,
            prepared_record=prepared,
            delivery=delivery,
            start=start,
            evidence_sha256=evidence_sha256,
            result_payload=result_payload,
            usage=usage,
            model_turn_count=model_turn_count,
        )
    elif completed_evidence is None:
        observation, execution, evaluation_sha256 = _build_interrupted_host_fault(
            repository=repository,
            study=study,
            trial=trial,
            prepared_record=prepared,
            delivery=delivery,
            start=start,
            evidence_sha256=evidence_sha256,
            result_payload=result_payload,
            usage=usage,
            model_turn_count=model_turn_count,
            resume_current=(evidence_kind == "token_guard"),
        )
    else:
        observation, execution, evaluation_sha256 = _build_interrupted_world_terminal(
            repository=repository,
            study=study,
            trial=trial,
            prepared_record=prepared,
            delivery=delivery,
            start=start,
            evidence=completed_evidence,
        )
    _validate_stage_usage(
        study.manifest,
        (*retained.observations, observation),
        token_measurement=token_measurement,
    )
    repository.publish_content_addressed_model(
        collection="observations",
        filename="observation.json",
        model=observation,
        adapter=_OBSERVATION_ADAPTER,
    )
    repository.publish_content_addressed_model(
        collection="executions",
        filename="trial-execution.json",
        model=execution,
        adapter=_TRIAL_EXECUTION_ADAPTER,
    )
    completion = Asw4cTrialCompletion(
        manifest_content_sha256=study.manifest.content_sha256,
        plan_content_sha256=study.plan.content_sha256,
        trial_id=trial.trial_id,
        start_content_sha256=start.content_sha256,
        prepared_trial_content_sha256=prepared.content_sha256,
        delivery_content_sha256=delivery.content_sha256,
        observation_content_sha256=observation.content_sha256,
        execution_content_sha256=execution.content_sha256,
        evaluation_artifact_sha256=evaluation_sha256,
    )
    _verify_trial_before_completion(
        repository=repository,
        trial=trial,
        completion=completion,
    )
    repository.publish_model(
        _trial_completion_path(trial.trial_id),
        completion,
        _TRIAL_COMPLETION_ADAPTER,
    )
    recovered = _load_retained_trials(
        study,
        reject_interrupted=True,
    )
    if len(recovered.completions) == len(study.plan.trials):
        _publish_final_report(
            repository=repository,
            study=study,
            retained=recovered,
        )
        return reload_asw4c_confirmatory_result(study.root)
    return Asw4cConfirmatoryProgress(
        study=study,
        completions=recovered.completions,
        observations=recovered.observations,
        executions=recovered.executions,
        report=None,
        completed_trial_count=len(recovered.completions),
        complete=False,
    )


def reload_asw4c_confirmatory_result(
    root: Path,
) -> Asw4cConfirmatoryProgress:
    """Reload every completion and independently recompute the final report."""

    study = reload_asw4c_confirmatory_study(root)
    repository = EvidenceRepository(study.root, host_private=True)
    retained = _load_retained_trials(
        study,
        reject_interrupted=True,
    )
    if len(retained.completions) != len(study.plan.trials):
        raise ImmutableArtifactIntegrityError(
            "ASW-4C final result does not contain 64 completions",
        )
    final_index = repository.load_model(
        "final-index.json",
        _FINAL_INDEX_ADAPTER,
    )
    if (
        final_index.manifest_content_sha256 != study.manifest.content_sha256
        or final_index.plan_content_sha256 != study.plan.content_sha256
        or final_index.completion_content_sha256 != tuple(item.content_sha256 for item in retained.completions)
    ):
        raise ImmutableArtifactIntegrityError(
            "ASW-4C final index differs from retained completions",
        )
    tokens_are_measurements = (
        _load_token_measurement_amendment(
            repository=repository,
            manifest=study.manifest,
        )
        is not None
    )
    report = reload_and_verify_study_report(
        root=study.root,
        report_content_sha256=final_index.report_content_sha256,
        tokens_are_measurements=tokens_are_measurements,
    )
    _validate_stage_usage(
        study.manifest,
        retained.observations,
        token_measurement=tokens_are_measurements,
    )
    _assert_no_secret_material(study.root)
    return Asw4cConfirmatoryProgress(
        study=study,
        completions=retained.completions,
        observations=retained.observations,
        executions=retained.executions,
        report=report,
        completed_trial_count=len(retained.completions),
        complete=True,
    )


def _execute_asw4c_trial(
    *,
    repository: EvidenceRepository,
    study: PreparedAsw4cStudy,
    trial: ContinuityTrial,
    prepared_record: Asw4cPreparedTrial,
    delivery: TreatmentDeliveryRecord,
    start: Asw4cTrialStart,
    registry: Any,
    token_measurement: bool,
) -> tuple[ContinuityObservation, Asw4cTrialExecution, str]:
    authority = study.manifest.provider_authorization
    if authority is None:
        raise ValueError("ASW-4C manifest has no provider authority")
    prepared = _open_prepared_history(
        repository=repository,
        record=prepared_record,
    )
    agent_relative_root = f"agent-evidence/{trial.trial_id}"
    agent_root = repository.root / agent_relative_root
    agent_root.mkdir(parents=True, mode=0o700)
    budgeted_tools = _Asw4cToolBudget(prepared.session)
    trajectory_path = agent_root / "trajectory.jsonl"
    trajectory = TrajectoryWriter(path=str(trajectory_path))
    try:
        adapter = registry.build(
            adapter_kind=ASW4C_ADAPTER_ID,
            model_name=ASW4C_MODEL_ID,
            workspace=str(agent_root),
            trajectory_writer=trajectory,
            native_tools=list(budgeted_tools.native_tools),
            enable_bash=False,
            cache=False,
        )
        carrier_payload = repository.load_bytes(
            prepared_record.carrier_relative_path,
        ).decode("utf-8")
        adapter_result = adapter.execute(
            AdapterRequest(
                instruction=_model_instruction(
                    treatment=trial.treatment,
                    carrier_payload=carrier_payload,
                ),
                system_prompt=_model_system_prompt(),
                tools=list(prepared.session.tool_specs),
                configuration=_adapter_configuration(
                    token_measurement=token_measurement,
                    remaining_spend_microunits=(
                        authority.maximum_spend_microunits - start.cumulative_spend_microunits_before
                    ),
                ),
                output_path=str(agent_root / "adapter-output.md"),
                output_format="markdown",
            )
        )
    finally:
        trajectory.close()
    trajectory_path.chmod(0o600)

    evidence_sha256 = _publish_agent_evidence(
        repository=repository,
        relative_root=agent_relative_root,
        result=adapter_result,
    )
    usage = _validated_usage(
        adapter_result,
        token_measurement=token_measurement,
    )
    history_count_before_endpoint = len(prepared.session.actor_history)
    advance_asw4c_to_evaluation_end(prepared)
    endpoint_host_advancement_count = len(prepared.session.actor_history) - history_count_before_endpoint
    verification = prepared.session.verify()
    evaluation = evaluate_pump_station_stewardship_run(
        run_dir=(repository.root / prepared_record.world_relative_path / "world-run"),
    )
    evaluation_relative_path = f"evaluations/{trial.trial_id}.json"
    repository.publish_model(
        evaluation_relative_path,
        evaluation,
        _EVALUATION_ADAPTER,
    )
    evaluation_reference = repository.reference(evaluation_relative_path)
    failure_kind, continuity_failure, ineligibility_reason = _classify_asw4c_execution(
        result=adapter_result,
        budgeted_tools=budgeted_tools,
        verification_valid=verification.valid,
        world_continuity_failure=asw4c_world_continuity_failure(
            prepared.session,
        ),
    )
    observation = ContinuityObservation(
        manifest_content_sha256=study.manifest.content_sha256,
        plan_content_sha256=study.plan.content_sha256,
        block_id=trial.block_id,
        trial_id=trial.trial_id,
        treatment=trial.treatment,
        source=ObservationSource.CONFIRMATORY,
        delivery_content_sha256=delivery.content_sha256,
        history_snapshot_sha256=prepared_record.history_snapshot_sha256,
        event_schedule_sha256=prepared_record.event_schedule_sha256,
        logical_budget_sha256=trial.logical_budget_sha256,
        model_condition_sha256=study.manifest.model_condition.content_sha256,
        failure_kind=failure_kind,
        continuity_failure=continuity_failure,
        ineligibility_reason=ineligibility_reason,
        study_outcome_eligible=ineligibility_reason is None,
        provider_call_count=usage.provider_calls,
        input_token_count=usage.input_tokens,
        output_token_count=usage.output_tokens,
        maximum_input_tokens_in_one_call=usage.maximum_input_tokens,
        maximum_output_tokens_in_one_call=usage.maximum_output_tokens,
        spend_currency=("USD" if usage.provider_calls else None),
        spend_microunits=usage.spend_microunits,
        task_reward_mutation_count=0,
    )
    _assert_no_secret_material(agent_root)
    current = prepared.session.actor_view.current_state
    execution = Asw4cTrialExecution(
        manifest_content_sha256=study.manifest.content_sha256,
        plan_content_sha256=study.plan.content_sha256,
        trial_id=trial.trial_id,
        start_content_sha256=start.content_sha256,
        delivery_content_sha256=delivery.content_sha256,
        history_snapshot_sha256=prepared_record.history_snapshot_sha256,
        event_schedule_sha256=prepared_record.event_schedule_sha256,
        carrier_content_sha256=prepared_record.carrier_content_sha256,
        start_state_sha256=prepared_record.start_snapshot.state_id,
        endpoint_state_sha256=prepared.session.result.snapshot.state_id,
        final_state_sha256=prepared.session.result.snapshot.state_id,
        evaluation_artifact_sha256=evaluation_reference.sha256,
        output_sha256=evidence_sha256["output.md"],
        agent_result_sha256=evidence_sha256["agent-result.json"],
        conversation_sha256=evidence_sha256["conversation.jsonl"],
        trajectory_sha256=evidence_sha256["trajectory.jsonl"],
        model_turn_count=adapter_result.turns_used or 0,
        host_command_count=budgeted_tools.host_command_count,
        agent_proposal_count=budgeted_tools.agent_proposal_count,
        invalid_command_count=budgeted_tools.invalid_command_count,
        endpoint_host_advancement_count=(endpoint_host_advancement_count),
        provider_call_count=usage.provider_calls,
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
        failure_kind=failure_kind,
        continuity_failure=continuity_failure,
        ineligibility_reason=ineligibility_reason,
        world_verification_valid=verification.valid,
        stewardship_evaluation_valid=evaluation.valid,
        final_open_obligation_count=len(current.obligations),
        final_active_restriction_count=len(current.restrictions),
        secret_scan_passed=True,
    )
    return observation, execution, evaluation_reference.sha256


def _validate_interrupted_start(
    *,
    study: PreparedAsw4cStudy,
    trial: ContinuityTrial,
    prepared: Asw4cPreparedTrial,
    delivery: TreatmentDeliveryRecord,
    start: Asw4cTrialStart,
    retained: _RetainedTrials,
    sequence_index: int,
) -> None:
    if (
        start.manifest_content_sha256 != study.manifest.content_sha256
        or start.plan_content_sha256 != study.plan.content_sha256
        or start.trial_id != trial.trial_id
        or start.prepared_trial_content_sha256 != prepared.content_sha256
        or start.delivery_content_sha256 != delivery.content_sha256
        or start.sequence_index != sequence_index
        or start.cumulative_provider_calls_before != sum(item.provider_call_count for item in retained.observations)
        or start.cumulative_input_tokens_before != sum(item.input_token_count for item in retained.observations)
        or start.cumulative_output_tokens_before != sum(item.output_token_count for item in retained.observations)
        or start.cumulative_spend_microunits_before != sum(item.spend_microunits for item in retained.observations)
        or delivery.status is not TreatmentDeliveryStatus.DELIVERED
        or not delivery.delivered_before_outcome
    ):
        raise Asw4cInterruptedTrialError(
            "ASW-4C interrupted start differs from the retained study",
        )


def _load_expired_credential_evidence(
    *,
    repository: EvidenceRepository,
    trial_id: str,
) -> tuple[dict[str, str], dict[str, Any]]:
    relative_root = f"agent-evidence/{trial_id}"
    filenames = (
        "output.md",
        "agent-result.json",
        "conversation.jsonl",
        "trajectory.jsonl",
    )
    evidence = {
        filename: repository.reference(
            f"{relative_root}/{filename}",
        ).sha256
        for filename in filenames
    }
    output = repository.load_bytes(f"{relative_root}/output.md")
    result_payload = json.loads(
        repository.load_bytes(
            f"{relative_root}/agent-result.json",
        )
    )
    if not isinstance(result_payload, dict):
        raise Asw4cInterruptedTrialError(
            "ASW-4C interrupted agent result is not an object",
        )
    provider_error = result_payload.get("provider_error")
    usage_fields = (
        "provider_calls",
        "input_tokens",
        "output_tokens",
        "maximum_input_tokens_in_one_call",
        "maximum_output_tokens_in_one_call",
        "cache_read_tokens",
        "cache_write_tokens",
        "advisor_calls",
    )
    if (
        output
        or result_payload.get("status") != AgentOutputStatus.FAILED.value
        or result_payload.get("adapter_name") != ASW4C_ADAPTER_ID
        or result_payload.get("resolved_model") != ASW4C_MODEL_ID
        or result_payload.get("failure_kind") != AdapterFailureKind.PROVIDER_ERROR.value
        or result_payload.get("turns_used") is not None
        or result_payload.get("max_turns") != 16
        or not isinstance(provider_error, str)
        or "ExpiredTokenException" not in provider_error
        or "security token included in the request is expired" not in provider_error.lower()
        or any(result_payload.get(field) is not None for field in usage_fields)
    ):
        raise Asw4cInterruptedTrialError(
            "ASW-4C interruption is not a proven expired host credential fault",
        )
    conversation = repository.load_bytes(
        f"{relative_root}/conversation.jsonl",
    )
    try:
        entries = tuple(json.loads(line) for line in conversation.splitlines() if line)
    except (TypeError, ValueError) as exc:
        raise Asw4cInterruptedTrialError(
            "ASW-4C interrupted conversation evidence is invalid",
        ) from exc
    if any(
        not isinstance(entry, dict) or entry.get("tool_name") is not None or entry.get("role") == "tool"
        for entry in entries
    ):
        raise Asw4cInterruptedTrialError(
            "ASW-4C expired credential recovery found a tool execution",
        )
    _assert_no_secret_material(repository.root / relative_root)
    return evidence, result_payload


def _load_count_tokens_permission_evidence(
    *,
    repository: EvidenceRepository,
    trial_id: str,
) -> tuple[dict[str, str], dict[str, Any]]:
    relative_root = f"agent-evidence/{trial_id}"
    filenames = (
        "output.md",
        "agent-result.json",
        "conversation.jsonl",
        "trajectory.jsonl",
    )
    evidence = {
        filename: repository.reference(
            f"{relative_root}/{filename}",
        ).sha256
        for filename in filenames
    }
    output = repository.load_bytes(f"{relative_root}/output.md")
    result_payload = json.loads(
        repository.load_bytes(
            f"{relative_root}/agent-result.json",
        )
    )
    if not isinstance(result_payload, dict):
        raise Asw4cInterruptedTrialError(
            "ASW-4C interrupted agent result is not an object",
        )
    provider_error = result_payload.get("provider_error")
    configuration = result_payload.get("configuration_record")
    if (
        output
        or result_payload.get("status") != AgentOutputStatus.FAILED.value
        or result_payload.get("adapter_name") != ASW4C_ADAPTER_ID
        or result_payload.get("resolved_model") != ASW4C_MODEL_ID
        or result_payload.get("failure_kind") != AdapterFailureKind.PROVIDER_ERROR.value
        or result_payload.get("turns_used") is not None
        or result_payload.get("max_turns") != 16
        or not isinstance(provider_error, str)
        or "AccessDeniedException" not in provider_error
        or "bedrock:CountTokens" not in provider_error
        or result_payload.get("provider_calls") is not None
        or result_payload.get("input_tokens") != 0
        or result_payload.get("output_tokens") != 0
        or result_payload.get("maximum_input_tokens_in_one_call") is not None
        or result_payload.get("maximum_output_tokens_in_one_call") is not None
        or result_payload.get("cache_read_tokens") != 0
        or result_payload.get("cache_write_tokens") != 0
        or result_payload.get("advisor_calls") is not None
        or not isinstance(configuration, dict)
        or configuration.get("count_tokens_before_request") is not True
    ):
        raise Asw4cInterruptedTrialError(
            "ASW-4C interruption is not a denied token-count host fault",
        )
    conversation = repository.load_bytes(
        f"{relative_root}/conversation.jsonl",
    )
    try:
        entries = tuple(json.loads(line) for line in conversation.splitlines() if line)
    except (TypeError, ValueError) as exc:
        raise Asw4cInterruptedTrialError(
            "ASW-4C interrupted conversation evidence is invalid",
        ) from exc
    if any(
        not isinstance(entry, dict) or entry.get("tool_name") is not None or entry.get("role") == "tool"
        for entry in entries
    ):
        raise Asw4cInterruptedTrialError(
            "ASW-4C denied token-count recovery found a tool execution",
        )
    trajectory = repository.load_bytes(
        f"{relative_root}/trajectory.jsonl",
    )
    try:
        trajectory_entries = tuple(json.loads(line) for line in trajectory.splitlines() if line)
    except (TypeError, ValueError) as exc:
        raise Asw4cInterruptedTrialError(
            "ASW-4C denied token-count trajectory is invalid",
        ) from exc
    if (
        len(trajectory_entries) != 1
        or not isinstance(trajectory_entries[0], dict)
        or trajectory_entries[0].get("format") != "aec-bench-trajectory"
    ):
        raise Asw4cInterruptedTrialError(
            "ASW-4C denied token-count recovery found a model trace",
        )
    _assert_no_secret_material(repository.root / relative_root)
    return evidence, result_payload


def _load_token_guard_evidence(
    *,
    repository: EvidenceRepository,
    trial_id: str,
) -> tuple[dict[str, str], dict[str, Any], _ValidatedUsage, int]:
    relative_root = f"agent-evidence/{trial_id}"
    filenames = (
        "output.md",
        "agent-result.json",
        "conversation.jsonl",
        "trajectory.jsonl",
    )
    evidence = {
        filename: repository.reference(
            f"{relative_root}/{filename}",
        ).sha256
        for filename in filenames
    }
    output = repository.load_bytes(f"{relative_root}/output.md")
    result_payload = json.loads(
        repository.load_bytes(
            f"{relative_root}/agent-result.json",
        )
    )
    if not isinstance(result_payload, dict):
        raise Asw4cInterruptedTrialError(
            "ASW-4C interrupted agent result is not an object",
        )
    integer_fields = (
        "turns_used",
        "provider_calls",
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
    )
    if (
        output
        or result_payload.get("status") != AgentOutputStatus.FAILED.value
        or result_payload.get("adapter_name") != ASW4C_ADAPTER_ID
        or result_payload.get("resolved_model") != ASW4C_MODEL_ID
        or result_payload.get("failure_kind") != AdapterFailureKind.TOKEN_BUDGET_REACHED.value
        or result_payload.get("provider_error") is not None
        or result_payload.get("max_turns") != 16
        or result_payload.get("maximum_input_tokens_in_one_call") is not None
        or result_payload.get("maximum_output_tokens_in_one_call") is not None
        or any(
            not isinstance(result_payload.get(field), int)
            or isinstance(result_payload.get(field), bool)
            or int(result_payload[field]) < 0
            for field in integer_fields
        )
        or result_payload.get("advisor_calls") not in {None, 0}
    ):
        raise Asw4cInterruptedTrialError(
            "ASW-4C interruption is not the measured token guard fault",
        )
    conversation = repository.load_bytes(
        f"{relative_root}/conversation.jsonl",
    )
    try:
        entries = tuple(json.loads(line) for line in conversation.splitlines() if line)
    except (TypeError, ValueError) as exc:
        raise Asw4cInterruptedTrialError(
            "ASW-4C interrupted conversation evidence is invalid",
        ) from exc
    if any(
        not isinstance(entry, dict) or entry.get("tool_name") is not None or entry.get("role") == "tool"
        for entry in entries
    ):
        raise Asw4cInterruptedTrialError(
            "ASW-4C token guard recovery found a tool execution",
        )
    provider_calls = int(result_payload["provider_calls"])
    input_tokens = int(result_payload["input_tokens"])
    output_tokens = int(result_payload["output_tokens"])
    usage = _ValidatedUsage(
        provider_calls=provider_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        maximum_input_tokens=input_tokens,
        maximum_output_tokens=min(
            output_tokens,
            ASW4C_MAXIMUM_OUTPUT_TOKENS_PER_CALL,
        ),
        cache_read_tokens=int(result_payload["cache_read_tokens"]),
        cache_write_tokens=int(result_payload["cache_write_tokens"]),
        advisor_calls=0,
        spend_microunits=calculate_asw4c_spend_microunits(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
    )
    if (
        usage.provider_calls > 16
        or usage.maximum_input_tokens > ASW4C_MAXIMUM_INPUT_TOKENS_PER_CALL
        or usage.cache_read_tokens
        or usage.cache_write_tokens
    ):
        raise Asw4cInterruptedTrialError(
            "ASW-4C token guard evidence exceeds retained hard controls",
        )
    _assert_no_secret_material(repository.root / relative_root)
    return evidence, result_payload, usage, int(result_payload["turns_used"])


def _load_completed_agent_evidence(
    *,
    repository: EvidenceRepository,
    trial_id: str,
    token_measurement: bool,
) -> _CompletedAgentEvidence:
    relative_root = f"agent-evidence/{trial_id}"
    filenames = (
        "output.md",
        "agent-result.json",
        "conversation.jsonl",
        "trajectory.jsonl",
    )
    evidence = {
        filename: repository.reference(
            f"{relative_root}/{filename}",
        ).sha256
        for filename in filenames
    }
    output = repository.load_bytes(f"{relative_root}/output.md")
    result_payload = json.loads(
        repository.load_bytes(
            f"{relative_root}/agent-result.json",
        )
    )
    if not isinstance(result_payload, dict):
        raise Asw4cInterruptedTrialError(
            "ASW-4C interrupted agent result is not an object",
        )
    integer_fields = (
        "turns_used",
        "provider_calls",
        "input_tokens",
        "output_tokens",
        "maximum_input_tokens_in_one_call",
        "maximum_output_tokens_in_one_call",
        "cache_read_tokens",
        "cache_write_tokens",
    )
    if (
        not output
        or result_payload.get("status") != AgentOutputStatus.COMPLETED.value
        or result_payload.get("adapter_name") != ASW4C_ADAPTER_ID
        or result_payload.get("resolved_model") != ASW4C_MODEL_ID
        or result_payload.get("failure_kind") is not None
        or result_payload.get("provider_error") is not None
        or result_payload.get("max_turns") != 16
        or any(
            not isinstance(result_payload.get(field), int)
            or isinstance(result_payload.get(field), bool)
            or int(result_payload[field]) < 0
            for field in integer_fields
        )
        or result_payload.get("advisor_calls") not in {None, 0}
    ):
        raise Asw4cInterruptedTrialError(
            "ASW-4C interruption is not a completed model execution",
        )
    usage = _ValidatedUsage(
        provider_calls=int(result_payload["provider_calls"]),
        input_tokens=int(result_payload["input_tokens"]),
        output_tokens=int(result_payload["output_tokens"]),
        maximum_input_tokens=int(
            result_payload["maximum_input_tokens_in_one_call"],
        ),
        maximum_output_tokens=int(
            result_payload["maximum_output_tokens_in_one_call"],
        ),
        cache_read_tokens=int(result_payload["cache_read_tokens"]),
        cache_write_tokens=int(result_payload["cache_write_tokens"]),
        advisor_calls=0,
        spend_microunits=calculate_asw4c_spend_microunits(
            input_tokens=int(result_payload["input_tokens"]),
            output_tokens=int(result_payload["output_tokens"]),
        ),
    )
    if (
        usage.provider_calls < 1
        or usage.provider_calls > 16
        or usage.maximum_input_tokens > ASW4C_MAXIMUM_INPUT_TOKENS_PER_CALL
        or usage.maximum_output_tokens > ASW4C_MAXIMUM_OUTPUT_TOKENS_PER_CALL
        or (
            not token_measurement
            and usage.input_tokens + usage.output_tokens > ASW4C_MAXIMUM_TOTAL_TOKENS_PER_TRAJECTORY
        )
        or usage.cache_read_tokens
        or usage.cache_write_tokens
    ):
        raise Asw4cInterruptedTrialError(
            "ASW-4C completed model evidence exceeds retained hard controls",
        )

    trajectory = repository.load_bytes(
        f"{relative_root}/trajectory.jsonl",
    )
    try:
        entries = tuple(json.loads(line) for line in trajectory.splitlines() if line)
    except (TypeError, ValueError) as exc:
        raise Asw4cInterruptedTrialError(
            "ASW-4C interrupted trajectory evidence is invalid",
        ) from exc
    if any(not isinstance(entry, dict) for entry in entries):
        raise Asw4cInterruptedTrialError(
            "ASW-4C interrupted trajectory contains a non-object",
        )
    tool_calls = tuple(entry for entry in entries if entry.get("role") == "tool_call")
    tool_results = tuple(entry for entry in entries if entry.get("role") == "tool_result")
    tool_names = tuple(entry.get("tool_name") for entry in tool_calls)
    result_names = tuple(entry.get("tool_name") for entry in tool_results)
    if (
        any(name not in PUMP_STATION_TOOL_NAMES for name in tool_names)
        or sorted(str(name) for name in tool_names) != sorted(str(name) for name in result_names)
        or any(
            not isinstance(entry.get("exit_code"), int) or isinstance(entry.get("exit_code"), bool)
            for entry in tool_results
        )
    ):
        raise Asw4cInterruptedTrialError(
            "ASW-4C interrupted trajectory does not contain a closed tool trace",
        )
    read_only_tools = {
        "observe_pump_station",
        "snapshot_pump_station",
    }
    host_command_count = len(tool_calls)
    agent_proposal_count = sum(name not in read_only_tools for name in tool_names)
    invalid_command_count = sum(int(entry["exit_code"]) != 0 for entry in tool_results)
    if host_command_count > 32 or agent_proposal_count > 12:
        raise Asw4cInterruptedTrialError(
            "ASW-4C completed model trace exceeds command controls",
        )
    _assert_no_secret_material(repository.root / relative_root)
    return _CompletedAgentEvidence(
        evidence_sha256=evidence,
        result_payload=result_payload,
        usage=usage,
        model_turn_count=int(result_payload["turns_used"]),
        host_command_count=host_command_count,
        agent_proposal_count=agent_proposal_count,
        invalid_command_count=invalid_command_count,
    )


def _load_concurrent_tool_fault_evidence(
    *,
    repository: EvidenceRepository,
    trial_id: str,
) -> tuple[dict[str, str], dict[str, Any], _ValidatedUsage, int]:
    relative_root = f"agent-evidence/{trial_id}"
    filenames = (
        "output.md",
        "agent-result.json",
        "conversation.jsonl",
        "trajectory.jsonl",
    )
    evidence = {
        filename: repository.reference(
            f"{relative_root}/{filename}",
        ).sha256
        for filename in filenames
    }
    output = repository.load_bytes(f"{relative_root}/output.md")
    result_payload = json.loads(
        repository.load_bytes(
            f"{relative_root}/agent-result.json",
        )
    )
    if not isinstance(result_payload, dict):
        raise Asw4cInterruptedTrialError(
            "ASW-4C interrupted agent result is not an object",
        )
    unavailable_usage_fields = (
        "turns_used",
        "provider_calls",
        "input_tokens",
        "output_tokens",
        "maximum_input_tokens_in_one_call",
        "maximum_output_tokens_in_one_call",
        "cache_read_tokens",
        "cache_write_tokens",
        "advisor_calls",
    )
    if (
        output
        or result_payload.get("status") != AgentOutputStatus.FAILED.value
        or result_payload.get("adapter_name") != ASW4C_ADAPTER_ID
        or result_payload.get("resolved_model") != ASW4C_MODEL_ID
        or result_payload.get("failure_kind") != AdapterFailureKind.PROVIDER_ERROR.value
        or result_payload.get("provider_error") != "artifact-integrity: commit does not extend its parent"
        or result_payload.get("max_turns") != 16
        or any(result_payload.get(field) is not None for field in unavailable_usage_fields)
    ):
        raise Asw4cInterruptedTrialError(
            "ASW-4C interruption is not the concurrent station-tool fault",
        )
    trajectory = repository.load_bytes(
        f"{relative_root}/trajectory.jsonl",
    )
    try:
        trajectory_entries = tuple(json.loads(line) for line in trajectory.splitlines() if line)
    except (TypeError, ValueError) as exc:
        raise Asw4cInterruptedTrialError(
            "ASW-4C concurrent fault trajectory is invalid",
        ) from exc
    if (
        len(trajectory_entries) != 1
        or not isinstance(trajectory_entries[0], dict)
        or trajectory_entries[0].get("format") != "aec-bench-trajectory"
    ):
        raise Asw4cInterruptedTrialError(
            "ASW-4C concurrent fault unexpectedly retained a tool trace",
        )
    _assert_no_secret_material(repository.root / relative_root)
    return (
        evidence,
        result_payload,
        _ValidatedUsage(
            provider_calls=2,
            input_tokens=0,
            output_tokens=0,
            maximum_input_tokens=0,
            maximum_output_tokens=0,
            cache_read_tokens=0,
            cache_write_tokens=0,
            advisor_calls=0,
            spend_microunits=0,
        ),
        2,
    )


def _build_interrupted_host_fault(
    *,
    repository: EvidenceRepository,
    study: PreparedAsw4cStudy,
    trial: ContinuityTrial,
    prepared_record: Asw4cPreparedTrial,
    delivery: TreatmentDeliveryRecord,
    start: Asw4cTrialStart,
    evidence_sha256: dict[str, str],
    result_payload: dict[str, Any],
    usage: _ValidatedUsage,
    model_turn_count: int,
    resume_current: bool,
) -> tuple[ContinuityObservation, Asw4cTrialExecution, str]:
    prepared = (
        _open_interrupted_current_history(
            repository=repository,
            record=prepared_record,
        )
        if resume_current
        else _open_prepared_history(
            repository=repository,
            record=prepared_record,
        )
    )
    verification = prepared.session.verify()
    if not verification.valid:
        raise Asw4cInterruptedTrialError(
            "ASW-4C interrupted world does not remain at its valid start",
        )
    evaluation = evaluate_pump_station_stewardship_run(
        run_dir=(repository.root / prepared_record.world_relative_path / "world-run"),
    )
    evaluation_relative_path = f"evaluations/{trial.trial_id}.json"
    repository.publish_model(
        evaluation_relative_path,
        evaluation,
        _EVALUATION_ADAPTER,
    )
    evaluation_reference = repository.reference(evaluation_relative_path)
    failure_kind = ContinuityFailureKind.HOST_FAILURE_AFTER_DELIVERY
    ineligibility_reason = PairIneligibilityReason.HOST_FAILURE
    durable_action_count = max(
        0,
        len(prepared.session.actor_history) - prepared_record.history_transition_count,
    )
    observation = ContinuityObservation(
        manifest_content_sha256=study.manifest.content_sha256,
        plan_content_sha256=study.plan.content_sha256,
        block_id=trial.block_id,
        trial_id=trial.trial_id,
        treatment=trial.treatment,
        source=ObservationSource.CONFIRMATORY,
        delivery_content_sha256=delivery.content_sha256,
        history_snapshot_sha256=prepared_record.history_snapshot_sha256,
        event_schedule_sha256=prepared_record.event_schedule_sha256,
        logical_budget_sha256=trial.logical_budget_sha256,
        model_condition_sha256=(study.manifest.model_condition.content_sha256),
        failure_kind=failure_kind,
        continuity_failure=None,
        ineligibility_reason=ineligibility_reason,
        study_outcome_eligible=False,
        provider_call_count=usage.provider_calls,
        input_token_count=usage.input_tokens,
        output_token_count=usage.output_tokens,
        maximum_input_tokens_in_one_call=usage.maximum_input_tokens,
        maximum_output_tokens_in_one_call=usage.maximum_output_tokens,
        spend_currency=("USD" if usage.provider_calls else None),
        spend_microunits=usage.spend_microunits,
        task_reward_mutation_count=0,
    )
    current = prepared.session.actor_view.current_state
    execution = Asw4cTrialExecution(
        manifest_content_sha256=study.manifest.content_sha256,
        plan_content_sha256=study.plan.content_sha256,
        trial_id=trial.trial_id,
        start_content_sha256=start.content_sha256,
        delivery_content_sha256=delivery.content_sha256,
        history_snapshot_sha256=prepared_record.history_snapshot_sha256,
        event_schedule_sha256=prepared_record.event_schedule_sha256,
        carrier_content_sha256=prepared_record.carrier_content_sha256,
        start_state_sha256=prepared_record.start_snapshot.state_id,
        endpoint_state_sha256=prepared.session.result.snapshot.state_id,
        final_state_sha256=prepared.session.result.snapshot.state_id,
        evaluation_artifact_sha256=evaluation_reference.sha256,
        output_sha256=evidence_sha256["output.md"],
        agent_result_sha256=evidence_sha256["agent-result.json"],
        conversation_sha256=evidence_sha256["conversation.jsonl"],
        trajectory_sha256=evidence_sha256["trajectory.jsonl"],
        model_turn_count=model_turn_count,
        host_command_count=durable_action_count,
        agent_proposal_count=durable_action_count,
        invalid_command_count=0,
        endpoint_host_advancement_count=0,
        provider_call_count=usage.provider_calls,
        input_token_count=usage.input_tokens,
        output_token_count=usage.output_tokens,
        maximum_input_tokens_in_one_call=usage.maximum_input_tokens,
        maximum_output_tokens_in_one_call=usage.maximum_output_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        cache_write_tokens=usage.cache_write_tokens,
        advisor_call_count=usage.advisor_calls,
        spend_microunits=usage.spend_microunits,
        adapter_status=str(result_payload["status"]),
        adapter_failure_kind=str(result_payload["failure_kind"]),
        failure_kind=failure_kind,
        continuity_failure=None,
        ineligibility_reason=ineligibility_reason,
        world_verification_valid=True,
        stewardship_evaluation_valid=evaluation.valid,
        final_open_obligation_count=len(current.obligations),
        final_active_restriction_count=len(current.restrictions),
        secret_scan_passed=True,
    )
    return observation, execution, evaluation_reference.sha256


def _build_interrupted_concurrent_tool_fault(
    *,
    repository: EvidenceRepository,
    study: PreparedAsw4cStudy,
    trial: ContinuityTrial,
    prepared_record: Asw4cPreparedTrial,
    delivery: TreatmentDeliveryRecord,
    start: Asw4cTrialStart,
    evidence_sha256: dict[str, str],
    result_payload: dict[str, Any],
    usage: _ValidatedUsage,
    model_turn_count: int,
) -> tuple[ContinuityObservation, Asw4cTrialExecution, str]:
    world_root = repository.root / prepared_record.world_relative_path / "world-run"
    world_repository = PumpStationWorldRunRepository(world_root)
    forensics = _forensic_world_prefix(
        repository=world_repository,
        start_snapshot=prepared_record.start_snapshot,
    )
    evaluation = _evaluate_forensic_world_prefix(
        world_root=world_root,
        snapshot=forensics.last_valid_snapshot,
    )
    evaluation_relative_path = f"evaluations/{trial.trial_id}.json"
    repository.publish_model(
        evaluation_relative_path,
        evaluation,
        _EVALUATION_ADAPTER,
    )
    evaluation_reference = repository.reference(evaluation_relative_path)
    recovery_payload = {
        "schema_version": "aecbench.stewardship-continuity-concurrent-tool-fault.v1",
        "trial_id": trial.trial_id,
        "agent_result_sha256": evidence_sha256["agent-result.json"],
        "error": str(result_payload["provider_error"]),
        "selected_invalid_commit_id": forensics.invalid_commit_id,
        "last_valid_commit_id": forensics.last_valid_snapshot.commit_id,
        "last_valid_state_id": forensics.last_valid_snapshot.state_id,
        "selected_post_start_proposal_ids": list(
            forensics.selected_post_start_proposal_ids,
        ),
        "provider_call_count": usage.provider_calls,
        "token_measurement_complete": False,
        "token_measurement_reason": (
            "The pre-amendment adapter discarded RunUsage when the host tool "
            "exception escaped. CloudWatch and Bedrock invocation-log reads "
            "were denied to the approved role."
        ),
    }
    repository.publish_bytes(
        f"host-faults/{trial.trial_id}.json",
        (
            json.dumps(
                recovery_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8"),
    )
    failure_kind = ContinuityFailureKind.HOST_FAILURE_AFTER_DELIVERY
    ineligibility_reason = PairIneligibilityReason.HOST_FAILURE
    observation = ContinuityObservation(
        manifest_content_sha256=study.manifest.content_sha256,
        plan_content_sha256=study.plan.content_sha256,
        block_id=trial.block_id,
        trial_id=trial.trial_id,
        treatment=trial.treatment,
        source=ObservationSource.CONFIRMATORY,
        delivery_content_sha256=delivery.content_sha256,
        history_snapshot_sha256=prepared_record.history_snapshot_sha256,
        event_schedule_sha256=prepared_record.event_schedule_sha256,
        logical_budget_sha256=trial.logical_budget_sha256,
        model_condition_sha256=study.manifest.model_condition.content_sha256,
        failure_kind=failure_kind,
        continuity_failure=None,
        ineligibility_reason=ineligibility_reason,
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
    final_state = world_repository.load_state(
        forensics.last_valid_snapshot.state_id,
    )
    inferred_command_count = (
        len(
            forensics.selected_post_start_proposal_ids,
        )
        + 1
    )
    execution = Asw4cTrialExecution(
        manifest_content_sha256=study.manifest.content_sha256,
        plan_content_sha256=study.plan.content_sha256,
        trial_id=trial.trial_id,
        start_content_sha256=start.content_sha256,
        delivery_content_sha256=delivery.content_sha256,
        history_snapshot_sha256=prepared_record.history_snapshot_sha256,
        event_schedule_sha256=prepared_record.event_schedule_sha256,
        carrier_content_sha256=prepared_record.carrier_content_sha256,
        start_state_sha256=prepared_record.start_snapshot.state_id,
        endpoint_state_sha256=forensics.last_valid_snapshot.state_id,
        final_state_sha256=forensics.last_valid_snapshot.state_id,
        evaluation_artifact_sha256=evaluation_reference.sha256,
        output_sha256=evidence_sha256["output.md"],
        agent_result_sha256=evidence_sha256["agent-result.json"],
        conversation_sha256=evidence_sha256["conversation.jsonl"],
        trajectory_sha256=evidence_sha256["trajectory.jsonl"],
        model_turn_count=model_turn_count,
        host_command_count=inferred_command_count,
        agent_proposal_count=inferred_command_count,
        invalid_command_count=1,
        endpoint_host_advancement_count=0,
        provider_call_count=usage.provider_calls,
        input_token_count=usage.input_tokens,
        output_token_count=usage.output_tokens,
        maximum_input_tokens_in_one_call=usage.maximum_input_tokens,
        maximum_output_tokens_in_one_call=usage.maximum_output_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        cache_write_tokens=usage.cache_write_tokens,
        advisor_call_count=usage.advisor_calls,
        spend_microunits=usage.spend_microunits,
        adapter_status=str(result_payload["status"]),
        adapter_failure_kind=str(result_payload["failure_kind"]),
        failure_kind=failure_kind,
        continuity_failure=None,
        ineligibility_reason=ineligibility_reason,
        world_verification_valid=False,
        stewardship_evaluation_valid=evaluation.valid,
        final_open_obligation_count=len(final_state.obligations),
        final_active_restriction_count=len(final_state.restrictions),
        secret_scan_passed=True,
    )
    return observation, execution, evaluation_reference.sha256


def _forensic_world_prefix(
    *,
    repository: PumpStationWorldRunRepository,
    start_snapshot: StewardshipStateSnapshotRef,
) -> _WorldChainForensics:
    selected = repository.current_snapshot()
    reverse_chain: list[tuple[str, PumpStationWorldRunCommit]] = []
    commit_id: str | None = selected.commit_id
    seen: set[str] = set()
    while commit_id is not None:
        if commit_id in seen:
            raise Asw4cInterruptedTrialError(
                "ASW-4C concurrent fault chain contains a cycle",
            )
        seen.add(commit_id)
        commit = repository.load_commit(commit_id)
        reverse_chain.append((commit_id, commit))
        commit_id = commit.parent_commit_id
    chain = tuple(reversed(reverse_chain))
    start_index = next(
        (index for index, (candidate_id, _) in enumerate(chain) if candidate_id == start_snapshot.commit_id),
        None,
    )
    if start_index is None:
        raise Asw4cInterruptedTrialError(
            "ASW-4C concurrent fault chain does not contain its prepared start",
        )
    previous_id, previous = chain[start_index]
    selected_post_start_proposal_ids: list[str] = []
    invalid_id: str | None = None
    invalid: PumpStationWorldRunCommit | None = None
    for candidate_id, candidate in chain[start_index + 1 :]:
        proposal, information_set, transition = repository._load_step(  # noqa: SLF001
            candidate,
        )
        if candidate.proposal_id is None:
            raise Asw4cInterruptedTrialError(
                "ASW-4C concurrent fault commit has no proposal",
            )
        selected_post_start_proposal_ids.append(candidate.proposal_id)
        if (
            candidate.sequence != previous.sequence + 1
            or candidate.parent_commit_id != previous_id
            or transition.receipt.pre_state_id != previous.state_id
            or proposal.context.based_on_sequence != previous.sequence
            or information_set.base_view.current_state.state_sequence != previous.sequence
        ):
            invalid_id = candidate_id
            invalid = candidate
            break
        previous_id, previous = candidate_id, candidate
    if invalid is None or invalid_id != selected.commit_id or len(selected_post_start_proposal_ids) != 2:
        raise Asw4cInterruptedTrialError(
            "ASW-4C interruption is not the selected two-action stale-view fault",
        )
    last_valid = PumpStationStateSnapshotRef(
        snapshot_version=selected.snapshot_version,
        run_id=selected.run_id,
        episode_id=selected.episode_id,
        world_branch_id=selected.world_branch_id,
        sequence=previous.sequence,
        state_id=previous.state_id,
        commit_id=previous_id,
    )
    return _WorldChainForensics(
        selected_snapshot=selected,
        last_valid_snapshot=last_valid,
        invalid_commit_id=invalid_id,
        invalid_commit=invalid,
        selected_post_start_proposal_ids=tuple(
            selected_post_start_proposal_ids,
        ),
    )


def _evaluate_forensic_world_prefix(
    *,
    world_root: Path,
    snapshot: PumpStationStateSnapshotRef,
) -> StewardshipEvaluation:
    with TemporaryDirectory(prefix="asw4c-forensic-world-") as temporary:
        forensic_root = Path(temporary) / "world-run"
        shutil.copytree(world_root, forensic_root)
        forensic_repository = PumpStationWorldRunRepository(forensic_root)
        forensic_repository._replace_current(  # noqa: SLF001
            PumpStationCurrentRunPointer(
                serialization_version=PUMP_STATION_SERIALIZATION_VERSION,
                run_id=snapshot.run_id,
                sequence=snapshot.sequence,
                state_id=snapshot.state_id,
                commit_id=snapshot.commit_id,
            )
        )
        return evaluate_pump_station_stewardship_run(
            run_dir=forensic_root,
        )


def _endpoint_world_prefix(
    *,
    repository: PumpStationWorldRunRepository,
    start_snapshot: StewardshipStateSnapshotRef,
    evaluation_end_seconds: int,
) -> _EndpointWorldPrefix:
    selected = repository.current_snapshot()
    chain = repository.commits()
    start_index = next(
        (index for index, commit in enumerate(chain) if pump_station_artifact_id(commit) == start_snapshot.commit_id),
        None,
    )
    if start_index is None:
        raise Asw4cInterruptedTrialError(
            "ASW-4C endpoint chain does not contain its prepared start",
        )
    states = tuple(repository.load_state(commit.state_id) for commit in chain)
    final_state = states[-1]
    if final_state.physical.calendar_seconds <= evaluation_end_seconds:
        raise Asw4cInterruptedTrialError(
            "ASW-4C interrupted world did not pass the frozen endpoint",
        )
    if any(
        current.physical.calendar_seconds < prior.physical.calendar_seconds
        for prior, current in zip(states, states[1:], strict=False)
    ):
        raise Asw4cInterruptedTrialError(
            "ASW-4C endpoint chain moves calendar time backwards",
        )
    endpoint_indices = tuple(
        index
        for index, state in enumerate(states)
        if (index >= start_index and state.physical.calendar_seconds == evaluation_end_seconds)
    )
    if not endpoint_indices:
        raise Asw4cInterruptedTrialError(
            "ASW-4C endpoint chain has no exact frozen state",
        )
    endpoint_index = endpoint_indices[-1]
    endpoint_commit = chain[endpoint_index]
    endpoint_state = states[endpoint_index]
    permitted = {
        PumpStationExecutionOutcome.SCHEDULED,
        PumpStationExecutionOutcome.IN_PROGRESS,
        PumpStationExecutionOutcome.COMPLETED,
    }
    invalid_command_count = 0
    host_advancement_count = 0
    for commit in chain[start_index + 1 : endpoint_index + 1]:
        transition = repository.load_transition(commit)
        proposal_id = transition.receipt.proposal_id or ""
        if proposal_id.startswith(ASW4C_HOST_WINDOW_PROPOSAL_PREFIX):
            host_advancement_count += 1
        elif transition.receipt.execution not in permitted:
            invalid_command_count += 1
    continuity_failure = (
        any(obligation.status is not PumpStationObligationStatus.FULFILLED for obligation in endpoint_state.obligations)
        or invalid_command_count > 0
    )
    endpoint_snapshot = PumpStationStateSnapshotRef(
        snapshot_version=selected.snapshot_version,
        run_id=selected.run_id,
        episode_id=selected.episode_id,
        world_branch_id=selected.world_branch_id,
        sequence=endpoint_commit.sequence,
        state_id=endpoint_commit.state_id,
        commit_id=pump_station_artifact_id(endpoint_commit),
    )
    return _EndpointWorldPrefix(
        endpoint_snapshot=endpoint_snapshot,
        final_snapshot=selected,
        endpoint_state=endpoint_state,
        final_state=final_state,
        continuity_failure=continuity_failure,
        invalid_command_count=invalid_command_count,
        host_advancement_count=host_advancement_count,
    )


def _build_interrupted_endpoint_overshoot(
    *,
    repository: EvidenceRepository,
    study: PreparedAsw4cStudy,
    trial: ContinuityTrial,
    prepared_record: Asw4cPreparedTrial,
    delivery: TreatmentDeliveryRecord,
    start: Asw4cTrialStart,
    evidence: _CompletedAgentEvidence,
) -> tuple[ContinuityObservation, Asw4cTrialExecution, str]:
    prepared = _open_interrupted_current_history(
        repository=repository,
        record=prepared_record,
    )
    world_root = repository.root / prepared_record.world_relative_path / "world-run"
    prefix = _endpoint_world_prefix(
        repository=PumpStationWorldRunRepository(world_root),
        start_snapshot=prepared_record.start_snapshot,
        evaluation_end_seconds=prepared.evaluation_end_seconds,
    )
    evaluation = _evaluate_forensic_world_prefix(
        world_root=world_root,
        snapshot=prefix.endpoint_snapshot,
    )
    evaluation_relative_path = f"evaluations/{trial.trial_id}.json"
    repository.publish_model(
        evaluation_relative_path,
        evaluation,
        _EVALUATION_ADAPTER,
    )
    evaluation_reference = repository.reference(evaluation_relative_path)
    repository.publish_bytes(
        f"endpoint-prefixes/{trial.trial_id}.json",
        (
            json.dumps(
                {
                    "schema_version": ("aecbench.stewardship-continuity-endpoint-prefix.v1"),
                    "trial_id": trial.trial_id,
                    "evaluation_end_seconds": (prepared.evaluation_end_seconds),
                    "endpoint_sequence": (prefix.endpoint_snapshot.sequence),
                    "endpoint_state_id": (prefix.endpoint_snapshot.state_id),
                    "final_sequence": prefix.final_snapshot.sequence,
                    "final_state_id": prefix.final_snapshot.state_id,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8"),
    )
    failure_kind = ContinuityFailureKind.TOOL_FAILURE if prefix.invalid_command_count else ContinuityFailureKind.NONE
    usage = evidence.usage
    observation = ContinuityObservation(
        manifest_content_sha256=study.manifest.content_sha256,
        plan_content_sha256=study.plan.content_sha256,
        block_id=trial.block_id,
        trial_id=trial.trial_id,
        treatment=trial.treatment,
        source=ObservationSource.CONFIRMATORY,
        delivery_content_sha256=delivery.content_sha256,
        history_snapshot_sha256=prepared_record.history_snapshot_sha256,
        event_schedule_sha256=prepared_record.event_schedule_sha256,
        logical_budget_sha256=trial.logical_budget_sha256,
        model_condition_sha256=(study.manifest.model_condition.content_sha256),
        failure_kind=failure_kind,
        continuity_failure=prefix.continuity_failure,
        ineligibility_reason=None,
        study_outcome_eligible=True,
        provider_call_count=usage.provider_calls,
        input_token_count=usage.input_tokens,
        output_token_count=usage.output_tokens,
        maximum_input_tokens_in_one_call=usage.maximum_input_tokens,
        maximum_output_tokens_in_one_call=usage.maximum_output_tokens,
        spend_currency="USD",
        spend_microunits=usage.spend_microunits,
        task_reward_mutation_count=0,
    )
    execution = Asw4cTrialExecution(
        manifest_content_sha256=study.manifest.content_sha256,
        plan_content_sha256=study.plan.content_sha256,
        trial_id=trial.trial_id,
        start_content_sha256=start.content_sha256,
        delivery_content_sha256=delivery.content_sha256,
        history_snapshot_sha256=prepared_record.history_snapshot_sha256,
        event_schedule_sha256=prepared_record.event_schedule_sha256,
        carrier_content_sha256=prepared_record.carrier_content_sha256,
        start_state_sha256=prepared_record.start_snapshot.state_id,
        endpoint_state_sha256=prefix.endpoint_snapshot.state_id,
        final_state_sha256=prefix.final_snapshot.state_id,
        evaluation_artifact_sha256=evaluation_reference.sha256,
        output_sha256=evidence.evidence_sha256["output.md"],
        agent_result_sha256=evidence.evidence_sha256["agent-result.json"],
        conversation_sha256=evidence.evidence_sha256["conversation.jsonl"],
        trajectory_sha256=evidence.evidence_sha256["trajectory.jsonl"],
        model_turn_count=evidence.model_turn_count,
        host_command_count=evidence.host_command_count,
        agent_proposal_count=evidence.agent_proposal_count,
        invalid_command_count=evidence.invalid_command_count,
        endpoint_host_advancement_count=prefix.host_advancement_count,
        provider_call_count=usage.provider_calls,
        input_token_count=usage.input_tokens,
        output_token_count=usage.output_tokens,
        maximum_input_tokens_in_one_call=usage.maximum_input_tokens,
        maximum_output_tokens_in_one_call=usage.maximum_output_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        cache_write_tokens=usage.cache_write_tokens,
        advisor_call_count=usage.advisor_calls,
        spend_microunits=usage.spend_microunits,
        adapter_status=str(evidence.result_payload["status"]),
        adapter_failure_kind=None,
        failure_kind=failure_kind,
        continuity_failure=prefix.continuity_failure,
        ineligibility_reason=None,
        world_verification_valid=prepared.verification.valid,
        stewardship_evaluation_valid=evaluation.valid,
        final_open_obligation_count=len(
            prefix.final_state.obligations,
        ),
        final_active_restriction_count=len(
            prefix.final_state.restrictions,
        ),
        secret_scan_passed=True,
    )
    _assert_no_secret_material(repository.root)
    return observation, execution, evaluation_reference.sha256


def _build_interrupted_world_terminal(
    *,
    repository: EvidenceRepository,
    study: PreparedAsw4cStudy,
    trial: ContinuityTrial,
    prepared_record: Asw4cPreparedTrial,
    delivery: TreatmentDeliveryRecord,
    start: Asw4cTrialStart,
    evidence: _CompletedAgentEvidence,
) -> tuple[ContinuityObservation, Asw4cTrialExecution, str]:
    prepared = _open_interrupted_current_history(
        repository=repository,
        record=prepared_record,
    )
    verification = prepared.session.verify()
    current = prepared.session.actor_view.current_state
    post_history = prepared.session.actor_history[prepared_record.history_transition_count :]
    host_advancements = tuple(
        entry
        for entry in post_history
        if entry.proposal_id.startswith(
            ASW4C_HOST_WINDOW_PROPOSAL_PREFIX,
        )
    )
    if (
        not verification.valid
        or current.calendar_seconds >= prepared.evaluation_end_seconds
        or not host_advancements
        or post_history[-1] != host_advancements[-1]
        or host_advancements[-1].action_type != "continue_operation"
        or host_advancements[-1].execution != "cancelled"
        or not asw4c_world_continuity_failure(prepared.session)
    ):
        raise Asw4cInterruptedTrialError(
            "ASW-4C interruption is not a world-owned early terminal",
        )
    evaluation = evaluate_pump_station_stewardship_run(
        run_dir=(repository.root / prepared_record.world_relative_path / "world-run"),
    )
    evaluation_relative_path = f"evaluations/{trial.trial_id}.json"
    repository.publish_model(
        evaluation_relative_path,
        evaluation,
        _EVALUATION_ADAPTER,
    )
    evaluation_reference = repository.reference(evaluation_relative_path)
    failure_kind = ContinuityFailureKind.TOOL_FAILURE if evidence.invalid_command_count else ContinuityFailureKind.NONE
    usage = evidence.usage
    observation = ContinuityObservation(
        manifest_content_sha256=study.manifest.content_sha256,
        plan_content_sha256=study.plan.content_sha256,
        block_id=trial.block_id,
        trial_id=trial.trial_id,
        treatment=trial.treatment,
        source=ObservationSource.CONFIRMATORY,
        delivery_content_sha256=delivery.content_sha256,
        history_snapshot_sha256=prepared_record.history_snapshot_sha256,
        event_schedule_sha256=prepared_record.event_schedule_sha256,
        logical_budget_sha256=trial.logical_budget_sha256,
        model_condition_sha256=study.manifest.model_condition.content_sha256,
        failure_kind=failure_kind,
        continuity_failure=True,
        ineligibility_reason=None,
        study_outcome_eligible=True,
        provider_call_count=usage.provider_calls,
        input_token_count=usage.input_tokens,
        output_token_count=usage.output_tokens,
        maximum_input_tokens_in_one_call=usage.maximum_input_tokens,
        maximum_output_tokens_in_one_call=usage.maximum_output_tokens,
        spend_currency="USD",
        spend_microunits=usage.spend_microunits,
        task_reward_mutation_count=0,
    )
    execution = Asw4cTrialExecution(
        manifest_content_sha256=study.manifest.content_sha256,
        plan_content_sha256=study.plan.content_sha256,
        trial_id=trial.trial_id,
        start_content_sha256=start.content_sha256,
        delivery_content_sha256=delivery.content_sha256,
        history_snapshot_sha256=prepared_record.history_snapshot_sha256,
        event_schedule_sha256=prepared_record.event_schedule_sha256,
        carrier_content_sha256=prepared_record.carrier_content_sha256,
        start_state_sha256=prepared_record.start_snapshot.state_id,
        endpoint_state_sha256=prepared.session.result.snapshot.state_id,
        final_state_sha256=prepared.session.result.snapshot.state_id,
        evaluation_artifact_sha256=evaluation_reference.sha256,
        output_sha256=evidence.evidence_sha256["output.md"],
        agent_result_sha256=evidence.evidence_sha256["agent-result.json"],
        conversation_sha256=evidence.evidence_sha256["conversation.jsonl"],
        trajectory_sha256=evidence.evidence_sha256["trajectory.jsonl"],
        model_turn_count=evidence.model_turn_count,
        host_command_count=evidence.host_command_count,
        agent_proposal_count=evidence.agent_proposal_count,
        invalid_command_count=evidence.invalid_command_count,
        endpoint_host_advancement_count=len(host_advancements),
        provider_call_count=usage.provider_calls,
        input_token_count=usage.input_tokens,
        output_token_count=usage.output_tokens,
        maximum_input_tokens_in_one_call=usage.maximum_input_tokens,
        maximum_output_tokens_in_one_call=usage.maximum_output_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        cache_write_tokens=usage.cache_write_tokens,
        advisor_call_count=usage.advisor_calls,
        spend_microunits=usage.spend_microunits,
        adapter_status=str(evidence.result_payload["status"]),
        adapter_failure_kind=None,
        failure_kind=failure_kind,
        continuity_failure=True,
        ineligibility_reason=None,
        world_verification_valid=True,
        stewardship_evaluation_valid=evaluation.valid,
        final_open_obligation_count=len(current.obligations),
        final_active_restriction_count=len(current.restrictions),
        secret_scan_passed=True,
    )
    return observation, execution, evaluation_reference.sha256


def _open_interrupted_current_history(
    *,
    repository: EvidenceRepository,
    record: Asw4cPreparedTrial,
) -> PreparedAsw4cHistory:
    carrier_payload = repository.load_bytes(record.carrier_relative_path)
    if record.treatment is ContinuityTreatment.CURRENT_ACTOR_VIEW:
        actor_view = load_pump_station_artifact(
            carrier_payload,
            PumpStationActorView,
        )
        handover = None
    else:
        handover = load_pump_station_artifact(
            carrier_payload,
            PumpStationStructuredHandover,
        )
        actor_view = handover.current_actor_view
    world_root = repository.root / record.world_relative_path / "world-run"
    selected = PumpStationWorldRunRepository(
        world_root,
    ).current_snapshot()
    if (
        selected.run_id != record.start_snapshot.run_id
        or selected.episode_id != record.start_snapshot.episode_id
        or selected.world_branch_id != record.start_snapshot.world_branch_id
        or selected.sequence < record.start_snapshot.sequence
    ):
        raise Asw4cInterruptedTrialError(
            "ASW-4C interrupted world identity differs from its start",
        )
    snapshot = StewardshipStateSnapshotRef(
        run_id=selected.run_id,
        episode_id=selected.episode_id,
        world_branch_id=selected.world_branch_id,
        sequence=selected.sequence,
        state_id=selected.state_id,
        commit_id=selected.commit_id,
    )
    session = PumpStationWorldSessionFactory(
        world_root,
    ).open(
        WorldSessionRequest(
            execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
            open_mode=WorldSessionOpenMode.RESUME,
            session_id=f"{record.trial_id}-recovery-session",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            agent_tenure_id=actor_view.agent_tenure_id,
            run_id=snapshot.run_id,
            episode_id=snapshot.episode_id,
            world_branch_id=snapshot.world_branch_id,
            start_snapshot=snapshot,
        )
    )
    if handover is not None and selected.sequence == record.start_snapshot.sequence:
        session.install_structured_handover(handover)
    verification = session.verify()
    if not verification.valid:
        raise Asw4cInterruptedTrialError(
            "ASW-4C interrupted current world does not replay",
        )
    current = session.actor_view.current_state
    return PreparedAsw4cHistory(
        history_slot_id=record.history_slot_id,
        history_class=record.history_class,
        treatment=record.treatment,
        session=session,
        handover=handover,
        verification=verification,
        history_snapshot_sha256=record.history_snapshot_sha256,
        event_schedule_sha256=record.event_schedule_sha256,
        current_state_equivalence_sha256=current.state_id,
        current_duties_sha256=record.current_duties_sha256,
        carrier_content_sha256=record.carrier_content_sha256,
        handover_seconds=record.handover_seconds,
        evaluation_end_seconds=record.evaluation_end_seconds,
        diagnostic_period_seconds=record.diagnostic_period_seconds,
        history_transition_count=record.history_transition_count,
    )


def _open_prepared_history(
    *,
    repository: EvidenceRepository,
    record: Asw4cPreparedTrial,
) -> PreparedAsw4cHistory:
    carrier_payload = repository.load_bytes(record.carrier_relative_path)
    if record.treatment is ContinuityTreatment.CURRENT_ACTOR_VIEW:
        actor_view = load_pump_station_artifact(
            carrier_payload,
            PumpStationActorView,
        )
        handover = None
    else:
        handover = load_pump_station_artifact(
            carrier_payload,
            PumpStationStructuredHandover,
        )
        actor_view = handover.current_actor_view
    snapshot = record.start_snapshot
    session = PumpStationWorldSessionFactory(
        repository.root / record.world_relative_path / "world-run",
    ).open(
        WorldSessionRequest(
            execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
            open_mode=WorldSessionOpenMode.RESUME,
            session_id=f"{record.trial_id}-outcome-session",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            agent_tenure_id=actor_view.agent_tenure_id,
            run_id=snapshot.run_id,
            episode_id=snapshot.episode_id,
            world_branch_id=snapshot.world_branch_id,
            start_snapshot=snapshot,
        )
    )
    if session.actor_view != actor_view:
        raise ImmutableArtifactIntegrityError(
            f"ASW-4C live carrier differs for {record.trial_id}",
        )
    if handover is not None:
        session.install_structured_handover(handover)
    if (
        session.result.snapshot != snapshot
        or session.event_schedule_sha256 != record.event_schedule_sha256
        or session.actor_view.current_state.state_id != record.current_state_equivalence_sha256
    ):
        raise ImmutableArtifactIntegrityError(
            f"ASW-4C live start identity differs for {record.trial_id}",
        )
    verification = session.verify()
    if not verification.valid:
        raise ImmutableArtifactIntegrityError(
            f"ASW-4C live start does not replay for {record.trial_id}",
        )
    return PreparedAsw4cHistory(
        history_slot_id=record.history_slot_id,
        history_class=record.history_class,
        treatment=record.treatment,
        session=session,
        handover=handover,
        verification=verification,
        history_snapshot_sha256=record.history_snapshot_sha256,
        event_schedule_sha256=record.event_schedule_sha256,
        current_state_equivalence_sha256=(record.current_state_equivalence_sha256),
        current_duties_sha256=record.current_duties_sha256,
        carrier_content_sha256=record.carrier_content_sha256,
        handover_seconds=record.handover_seconds,
        evaluation_end_seconds=record.evaluation_end_seconds,
        diagnostic_period_seconds=record.diagnostic_period_seconds,
        history_transition_count=record.history_transition_count,
    )


def _validated_usage(
    result: AdapterResult,
    *,
    token_measurement: bool = False,
) -> _ValidatedUsage:
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
        raise ValueError(
            "ASW-4C provider usage is incomplete: " + ", ".join(missing),
        )
    selected = {name: int(value) for name, value in values.items() if value is not None}
    if any(value < 0 for value in selected.values()):
        raise ValueError("ASW-4C provider usage contains a negative value")
    advisor_calls = result.usage_advisor_calls or 0
    spend = calculate_asw4c_spend_microunits(
        input_tokens=selected["input_tokens"],
        output_tokens=selected["output_tokens"],
    )
    usage = _ValidatedUsage(
        provider_calls=selected["provider_calls"],
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
        usage.provider_calls > 16
        or usage.maximum_input_tokens > ASW4C_MAXIMUM_INPUT_TOKENS_PER_CALL
        or usage.maximum_output_tokens > ASW4C_MAXIMUM_OUTPUT_TOKENS_PER_CALL
        or (
            not token_measurement
            and (
                usage.input_tokens + usage.output_tokens > ASW4C_MAXIMUM_TOTAL_TOKENS_PER_TRAJECTORY
                or usage.spend_microunits
                > _maximum_trajectory_spend_microunits(
                    token_measurement=False,
                )
            )
        )
    ):
        raise ValueError("ASW-4C provider usage exceeds trial authority")
    if usage.cache_read_tokens or usage.cache_write_tokens:
        raise ValueError("ASW-4C unexpectedly used provider cache")
    if usage.advisor_calls:
        raise ValueError("ASW-4C unexpectedly used an advisor")
    return usage


def _classify_asw4c_execution(
    *,
    result: AdapterResult,
    budgeted_tools: _Asw4cToolBudget,
    verification_valid: bool,
    world_continuity_failure: bool,
) -> tuple[
    ContinuityFailureKind,
    bool | None,
    PairIneligibilityReason | None,
]:
    if not verification_valid:
        return (
            ContinuityFailureKind.HOST_FAILURE_AFTER_DELIVERY,
            None,
            PairIneligibilityReason.HOST_FAILURE,
        )
    if budgeted_tools.invalid_command_count:
        return ContinuityFailureKind.TOOL_FAILURE, True, None
    if result.failure_kind is not None:
        mapped = {
            AdapterFailureKind.TIMEOUT: ContinuityFailureKind.MODEL_TIMEOUT,
            AdapterFailureKind.MISSING_OUTPUT: (ContinuityFailureKind.MODEL_EMPTY_OUTPUT),
        }.get(result.failure_kind, ContinuityFailureKind.TOOL_FAILURE)
        return mapped, True, None
    if result.agent_output.status is AgentOutputStatus.EMPTY:
        return ContinuityFailureKind.MODEL_EMPTY_OUTPUT, True, None
    return ContinuityFailureKind.NONE, world_continuity_failure, None


def _publish_agent_evidence(
    *,
    repository: EvidenceRepository,
    relative_root: str,
    result: AdapterResult,
) -> dict[str, str]:
    output = (result.raw_output_text or "").encode("utf-8")
    result_payload = _json_bytes(
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
        }
    )
    conversation = b"".join(
        _json_line_bytes(
            {
                "role": entry.role.value,
                "event": entry.event.value,
                "content": entry.content,
                "tool_name": entry.tool_name,
                "tool_call_id": entry.tool_call_id,
            }
        )
        for entry in result.transcript
    )
    payloads = {
        "output.md": output,
        "agent-result.json": result_payload,
        "conversation.jsonl": conversation,
        "trajectory.jsonl": repository.load_bytes(
            f"{relative_root}/trajectory.jsonl",
        ),
    }
    references = {
        filename: repository.publish_bytes(
            f"{relative_root}/{filename}",
            payload,
        )
        for filename, payload in payloads.items()
    }
    return {filename: reference.sha256 for filename, reference in references.items()}


def _load_retained_trials(
    study: PreparedAsw4cStudy,
    *,
    reject_interrupted: bool,
) -> _RetainedTrials:
    repository = EvidenceRepository(study.root, host_private=True)
    completions: list[Asw4cTrialCompletion] = []
    observations: list[ContinuityObservation] = []
    executions: list[Asw4cTrialExecution] = []
    for trial in study.plan.trials:
        start_path = _trial_start_path(trial.trial_id)
        completion_path = _trial_completion_path(trial.trial_id)
        if not repository.exists(completion_path):
            if reject_interrupted and repository.exists(start_path):
                raise Asw4cInterruptedTrialError(
                    f"ASW-4C trial has a start fence without completion: {trial.trial_id}",
                )
            continue
        completion = repository.load_model(
            completion_path,
            _TRIAL_COMPLETION_ADAPTER,
        )
        start = repository.load_model(
            start_path,
            _TRIAL_START_ADAPTER,
        )
        observation = repository.load_content_addressed_model(
            collection="observations",
            content_sha256=completion.observation_content_sha256,
            filename="observation.json",
            adapter=_OBSERVATION_ADAPTER,
        ).model
        execution = repository.load_content_addressed_model(
            collection="executions",
            content_sha256=completion.execution_content_sha256,
            filename="trial-execution.json",
            adapter=_TRIAL_EXECUTION_ADAPTER,
        ).model
        if (
            completion.trial_id != trial.trial_id
            or start.trial_id != trial.trial_id
            or observation.trial_id != trial.trial_id
            or execution.trial_id != trial.trial_id
            or completion.start_content_sha256 != start.content_sha256
            or execution.start_content_sha256 != start.content_sha256
            or completion.delivery_content_sha256 != observation.delivery_content_sha256
            or completion.delivery_content_sha256 != execution.delivery_content_sha256
            or completion.evaluation_artifact_sha256 != execution.evaluation_artifact_sha256
        ):
            raise ImmutableArtifactIntegrityError(
                f"ASW-4C retained trial identity drift for {trial.trial_id}",
            )
        _verify_execution_artifacts(
            repository=repository,
            execution=execution,
        )
        completions.append(completion)
        observations.append(observation)
        executions.append(execution)
    return _RetainedTrials(
        completions=tuple(completions),
        observations=tuple(observations),
        executions=tuple(executions),
    )


def _verify_trial_before_completion(
    *,
    repository: EvidenceRepository,
    trial: ContinuityTrial,
    completion: Asw4cTrialCompletion,
) -> None:
    observation = repository.load_content_addressed_model(
        collection="observations",
        content_sha256=completion.observation_content_sha256,
        filename="observation.json",
        adapter=_OBSERVATION_ADAPTER,
    ).model
    execution = repository.load_content_addressed_model(
        collection="executions",
        content_sha256=completion.execution_content_sha256,
        filename="trial-execution.json",
        adapter=_TRIAL_EXECUTION_ADAPTER,
    ).model
    if observation.trial_id != trial.trial_id or execution.trial_id != trial.trial_id:
        raise ImmutableArtifactIntegrityError(
            f"ASW-4C trial completion differs for {trial.trial_id}",
        )
    _verify_execution_artifacts(
        repository=repository,
        execution=execution,
    )


def _verify_execution_artifacts(
    *,
    repository: EvidenceRepository,
    execution: Asw4cTrialExecution,
) -> None:
    relative_root = f"agent-evidence/{execution.trial_id}"
    expected = {
        "output.md": execution.output_sha256,
        "agent-result.json": execution.agent_result_sha256,
        "conversation.jsonl": execution.conversation_sha256,
        "trajectory.jsonl": execution.trajectory_sha256,
    }
    for filename, sha256 in expected.items():
        repository.load_bytes(
            f"{relative_root}/{filename}",
            expected_sha256=sha256,
        )
    repository.load_bytes(
        f"evaluations/{execution.trial_id}.json",
        expected_sha256=execution.evaluation_artifact_sha256,
    )


def _publish_final_report(
    *,
    repository: EvidenceRepository,
    study: PreparedAsw4cStudy,
    retained: _RetainedTrials,
) -> None:
    tokens_are_measurements = (
        _load_token_measurement_amendment(
            repository=repository,
            manifest=study.manifest,
        )
        is not None
    )
    report = analyse_continuity_study(
        manifest=study.manifest,
        plan=study.plan,
        deliveries=study.deliveries,
        observations=retained.observations,
        tokens_are_measurements=tokens_are_measurements,
    )
    repository.publish_content_addressed_model(
        collection="reports",
        filename="study-report.json",
        model=report,
        adapter=TypeAdapter(ContinuityStudyReport),
    )
    final_index = Asw4cFinalIndex(
        manifest_content_sha256=study.manifest.content_sha256,
        plan_content_sha256=study.plan.content_sha256,
        report_content_sha256=report.content_sha256,
        completion_content_sha256=tuple(item.content_sha256 for item in retained.completions),
    )
    repository.publish_model(
        "final-index.json",
        final_index,
        _FINAL_INDEX_ADAPTER,
    )
    if (
        reload_and_verify_study_report(
            root=study.root,
            report_content_sha256=report.content_sha256,
            tokens_are_measurements=tokens_are_measurements,
        )
        != report
    ):
        raise ImmutableArtifactIntegrityError(
            "reloaded ASW-4C report differs",
        )


def _ensure_trajectory_reserve(
    manifest: ContinuityStudyManifest,
    observations: tuple[ContinuityObservation, ...],
    *,
    token_measurement: bool,
) -> None:
    authority = manifest.provider_authorization
    if authority is None:
        raise ValueError("ASW-4C manifest has no provider authority")
    calls = sum(item.provider_call_count for item in observations)
    spend = sum(item.spend_microunits for item in observations)
    remaining_spend = authority.maximum_spend_microunits - spend
    token_measurement_spend_available = not token_measurement or (
        remaining_spend > 0 and _spend_guard_input_token_limit(remaining_spend) > 0
    )
    if (
        calls + 16 > authority.maximum_provider_calls
        or (
            not token_measurement
            and sum(item.input_token_count + item.output_token_count for item in observations)
            + ASW4C_MAXIMUM_TOTAL_TOKENS_PER_TRAJECTORY
            > authority.maximum_total_tokens
        )
        or not token_measurement_spend_available
        or (
            not token_measurement
            and spend
            + _maximum_trajectory_spend_microunits(
                token_measurement=False,
            )
            > authority.maximum_spend_microunits
        )
    ):
        raise Asw4cAuthorityExhaustedError(
            "ASW-4C authority cannot reserve one complete next trajectory",
        )


def _validate_stage_usage(
    manifest: ContinuityStudyManifest,
    observations: tuple[ContinuityObservation, ...],
    *,
    token_measurement: bool = False,
) -> None:
    authority = manifest.provider_authorization
    if authority is None:
        raise ValueError("ASW-4C manifest has no provider authority")
    if (
        sum(item.provider_call_count for item in observations) > authority.maximum_provider_calls
        or (
            not token_measurement
            and sum(item.input_token_count + item.output_token_count for item in observations)
            > authority.maximum_total_tokens
        )
        or sum(item.spend_microunits for item in observations) > authority.maximum_spend_microunits
        or max(
            (item.maximum_input_tokens_in_one_call for item in observations),
            default=0,
        )
        > authority.maximum_input_tokens_per_call
        or max(
            (item.maximum_output_tokens_in_one_call for item in observations),
            default=0,
        )
        > authority.maximum_output_tokens_per_call
    ):
        raise ValueError("ASW-4C retained usage exceeds phase authority")


def _maximum_trajectory_spend_microunits(
    *,
    token_measurement: bool,
) -> int:
    if token_measurement:
        return calculate_asw4c_spend_microunits(
            input_tokens=16 * ASW4C_MAXIMUM_INPUT_TOKENS_PER_CALL,
            output_tokens=16 * ASW4C_MAXIMUM_OUTPUT_TOKENS_PER_CALL,
        )
    maximum_output = min(
        ASW4C_MAXIMUM_TOTAL_TOKENS_PER_TRAJECTORY,
        16 * ASW4C_MAXIMUM_OUTPUT_TOKENS_PER_CALL,
    )
    return calculate_asw4c_spend_microunits(
        input_tokens=(ASW4C_MAXIMUM_TOTAL_TOKENS_PER_TRAJECTORY - maximum_output),
        output_tokens=maximum_output,
    )


def _adapter_configuration(
    *,
    token_measurement: bool,
    remaining_spend_microunits: int,
) -> dict[str, Any]:
    configuration = {
        "max_turns": 16,
        "max_tool_calls": 32,
        "max_output_tokens_per_call": (ASW4C_MAXIMUM_OUTPUT_TOKENS_PER_CALL),
        "count_tokens_before_request": False,
        "cache_enabled": False,
        "advisor_enabled": False,
        "bash_enabled": False,
    }
    if token_measurement:
        configuration["max_input_tokens"] = _spend_guard_input_token_limit(
            remaining_spend_microunits,
        )
    else:
        configuration["max_input_tokens"] = ASW4C_MAXIMUM_TOTAL_TOKENS_PER_TRAJECTORY
        configuration["max_total_tokens"] = ASW4C_MAXIMUM_TOTAL_TOKENS_PER_TRAJECTORY
    return configuration


def _spend_guard_input_token_limit(
    remaining_spend_microunits: int,
) -> int:
    """Convert remaining phase spend into a safe trajectory input limit."""

    if isinstance(remaining_spend_microunits, bool) or remaining_spend_microunits < 0:
        raise ValueError("remaining_spend_microunits must be non-negative")
    reserved_output_tokens = 16 * ASW4C_MAXIMUM_OUTPUT_TOKENS_PER_CALL
    remaining_input_spend = (
        Decimal(remaining_spend_microunits) - Decimal(reserved_output_tokens) * ASW4C_OUTPUT_USD_PER_MILLION_TOKENS
    )
    if remaining_input_spend <= 0:
        return 0
    affordable_input_tokens = int(
        (remaining_input_spend / ASW4C_INPUT_USD_PER_MILLION_TOKENS).to_integral_value(rounding=ROUND_FLOOR)
    )
    return max(
        0,
        affordable_input_tokens - ASW4C_MAXIMUM_INPUT_TOKENS_PER_CALL,
    )


def _model_system_prompt() -> str:
    return (
        "You are the accountable wastewater pump-station steward for a fresh "
        "work tenure. Use only the declared station tools and supplied "
        "continuity material. Work from live identifiers. Do not invent "
        "evidence. A work-order closure does not remove an operating limit or "
        "complete an independent verification duty. Keep each proposal_id "
        "unique. Stop after the present required follow-up is safely dealt "
        "with."
    )


def _model_instruction(
    *,
    treatment: ContinuityTreatment,
    carrier_payload: str,
) -> str:
    label = "CURRENT STATION VIEW" if treatment is ContinuityTreatment.CURRENT_ACTOR_VIEW else "STRUCTURED HANDOVER"
    return (
        "Continue stewardship of the live station. Read the supplied material, "
        "observe the station when needed, and deal with every present operating "
        "limit and required follow-up through the declared tools. Do not use "
        "external search. Use only information available now. Return a short "
        "factual summary when the present required follow-up is safely dealt "
        f"with.\n\n{label}\n{carrier_payload}"
    )


def _local_adapter_registry() -> Any:
    from aec_bench.adapters.local_registry import LocalAdapterRegistry

    return LocalAdapterRegistry()


def _trial_start_path(trial_id: str) -> str:
    return f"trial-starts/{trial_id}.json"


def _trial_completion_path(trial_id: str) -> str:
    return f"trial-completions/{trial_id}.json"


def _usage_value_or_retained(
    value: object,
    observation: ContinuityObservation | None,
    field_name: Literal[
        "provider_call_count",
        "input_token_count",
        "output_token_count",
    ],
) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    if observation is not None:
        return int(getattr(observation, field_name))
    raise ImmutableArtifactIntegrityError(
        f"ASW-4C agent result lacks {field_name}",
    )


def _load_token_measurement_amendment(
    *,
    repository: EvidenceRepository,
    manifest: ContinuityStudyManifest,
) -> Asw4cTokenMeasurementAmendment | None:
    if not repository.exists(_TOKEN_MEASUREMENT_AMENDMENT_PATH):
        return None
    amendment = repository.load_model(
        _TOKEN_MEASUREMENT_AMENDMENT_PATH,
        _TOKEN_MEASUREMENT_AMENDMENT_ADAPTER,
    )
    if amendment.manifest_content_sha256 != manifest.content_sha256:
        raise ImmutableArtifactIntegrityError(
            "ASW-4C token amendment differs from the study manifest",
        )
    return amendment


def _json_bytes(payload: object) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _json_line_bytes(payload: object) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _prepare_staging_study(
    root: Path,
    *,
    manifest: ContinuityStudyManifest,
) -> None:
    repository = EvidenceRepository(root, host_private=True)
    preliminary_plan = build_continuity_plan(manifest)
    histories: dict[
        tuple[str, ContinuityTreatment],
        PreparedAsw4cHistory,
    ] = {}
    history_sha256_by_slot: dict[str, str] = {}
    event_sha256_by_slot: dict[str, str] = {}

    for block in preliminary_plan.blocks:
        pair = tuple(
            prepare_asw4c_history(
                root
                / _world_relative_path(
                    history_slot_id=block.history_slot_id,
                    treatment=trial.treatment,
                ),
                history_slot_id=block.history_slot_id,
                history_class=block.history_class,
                evaluation_window=block.evaluation_window,
                treatment=trial.treatment,
            )
            for trial in block.trials
        )
        _validate_prepared_pair(pair)
        for prepared in pair:
            histories[(block.history_slot_id, prepared.treatment)] = prepared
        history_sha256_by_slot[block.history_slot_id] = pair[0].history_snapshot_sha256
        event_sha256_by_slot[block.history_slot_id] = pair[0].event_schedule_sha256

    plan = build_continuity_plan(
        manifest,
        history_snapshot_sha256_by_slot=history_sha256_by_slot,
        event_schedule_sha256_by_slot=event_sha256_by_slot,
    )
    repository.publish_content_addressed_model(
        collection="manifests",
        filename="study-manifest.json",
        model=manifest,
        adapter=_MANIFEST_ADAPTER,
    )
    repository.publish_content_addressed_model(
        collection="plans",
        filename="study-plan.json",
        model=plan,
        adapter=_PLAN_ADAPTER,
    )

    prepared_records: list[Asw4cPreparedTrial] = []
    deliveries: list[TreatmentDeliveryRecord] = []
    for block in plan.blocks:
        for trial in block.trials:
            prepared = histories[(block.history_slot_id, trial.treatment)]
            carrier_relative_path = _carrier_relative_path(trial)
            carrier = prepared.session.actor_view if prepared.handover is None else prepared.handover
            repository.publish_bytes(
                carrier_relative_path,
                pump_station_artifact_bytes(carrier),
            )
            current = prepared.session.actor_view.current_state
            record = Asw4cPreparedTrial(
                manifest_content_sha256=manifest.content_sha256,
                plan_content_sha256=plan.content_sha256,
                block_id=block.block_id,
                trial_id=trial.trial_id,
                history_slot_id=block.history_slot_id,
                history_class=block.history_class,
                treatment=trial.treatment,
                evaluation_window=block.evaluation_window,
                world_relative_path=_world_relative_path(
                    history_slot_id=block.history_slot_id,
                    treatment=trial.treatment,
                ),
                carrier_relative_path=carrier_relative_path,
                start_snapshot=prepared.session.result.snapshot,
                history_snapshot_sha256=prepared.history_snapshot_sha256,
                event_schedule_sha256=prepared.event_schedule_sha256,
                current_state_equivalence_sha256=(prepared.current_state_equivalence_sha256),
                current_duties_sha256=prepared.current_duties_sha256,
                carrier_content_sha256=prepared.carrier_content_sha256,
                handover_content_sha256=(None if prepared.handover is None else prepared.handover.handover_id),
                handover_seconds=prepared.handover_seconds,
                evaluation_end_seconds=prepared.evaluation_end_seconds,
                diagnostic_period_seconds=prepared.diagnostic_period_seconds,
                history_transition_count=prepared.history_transition_count,
                quantized_scalar_reading=str(
                    current.observation.active_pump_flow_m3_s,
                ),
                open_obligation_count=len(current.obligations),
                active_restriction_count=len(current.restrictions),
            )
            delivery = TreatmentDeliveryRecord(
                manifest_content_sha256=manifest.content_sha256,
                plan_content_sha256=plan.content_sha256,
                block_id=block.block_id,
                trial_id=trial.trial_id,
                treatment=trial.treatment,
                source=ObservationSource.CONFIRMATORY,
                status=TreatmentDeliveryStatus.DELIVERED,
                delivered_before_outcome=True,
                current_state_equivalence_sha256=(record.current_state_equivalence_sha256),
                current_duties_sha256=record.current_duties_sha256,
                carrier_content_sha256=record.carrier_content_sha256,
                provider_call_count=0,
            )
            repository.publish_content_addressed_model(
                collection="prepared-trials",
                filename="prepared-trial.json",
                model=record,
                adapter=_PREPARED_TRIAL_ADAPTER,
            )
            repository.publish_content_addressed_model(
                collection="treatment-deliveries",
                filename="treatment-delivery.json",
                model=delivery,
                adapter=_DELIVERY_ADAPTER,
            )
            prepared_records.append(record)
            deliveries.append(delivery)

    index = Asw4cStudyIndex(
        manifest_content_sha256=manifest.content_sha256,
        plan_content_sha256=plan.content_sha256,
        prepared_trial_content_sha256=tuple(item.content_sha256 for item in prepared_records),
        delivery_content_sha256=tuple(item.content_sha256 for item in deliveries),
    )
    repository.publish_model(
        "study-index.json",
        index,
        _STUDY_INDEX_ADAPTER,
    )
    _assert_no_secret_material(root)


def _validate_prepared_pair(
    pair: tuple[PreparedAsw4cHistory, ...],
) -> None:
    if len(pair) != 2 or {item.treatment for item in pair} != set(ContinuityTreatment):
        raise ValueError("ASW-4C prepared pair lacks both treatments")
    fields = (
        "history_snapshot_sha256",
        "event_schedule_sha256",
        "current_state_equivalence_sha256",
        "current_duties_sha256",
        "handover_seconds",
        "evaluation_end_seconds",
    )
    if any(getattr(pair[0], field_name) != getattr(pair[1], field_name) for field_name in fields):
        raise ValueError("ASW-4C prepared treatment branches are not matched")
    readings = {
        str(
            item.session.actor_view.current_state.observation.active_pump_flow_m3_s,
        )
        for item in pair
    }
    if readings != {"0.0262"}:
        raise ValueError("ASW-4C prepared pair lacks the matched scalar")


def _validate_reloaded_preparation(
    *,
    repository: EvidenceRepository,
    index: Asw4cStudyIndex,
    manifest: ContinuityStudyManifest,
    plan: ContinuityStudyPlan,
    prepared_trials: tuple[Asw4cPreparedTrial, ...],
    deliveries: tuple[TreatmentDeliveryRecord, ...],
) -> None:
    if manifest.phase is not ContinuityStudyPhase.CONFIRMATORY:
        raise ImmutableArtifactIntegrityError(
            "ASW-4C preparation is not confirmatory",
        )
    if plan.manifest_content_sha256 != manifest.content_sha256 or index.plan_content_sha256 != plan.content_sha256:
        raise ImmutableArtifactIntegrityError(
            "ASW-4C prepared manifest and plan differ",
        )
    trial_ids = tuple(trial.trial_id for trial in plan.trials)
    if tuple(item.trial_id for item in prepared_trials) != trial_ids:
        raise ImmutableArtifactIntegrityError(
            "ASW-4C prepared trials differ from plan order",
        )
    if tuple(item.trial_id for item in deliveries) != trial_ids:
        raise ImmutableArtifactIntegrityError(
            "ASW-4C deliveries differ from plan order",
        )
    for trial, prepared, delivery in zip(
        plan.trials,
        prepared_trials,
        deliveries,
        strict=True,
    ):
        if (
            prepared.manifest_content_sha256 != manifest.content_sha256
            or prepared.plan_content_sha256 != plan.content_sha256
            or delivery.manifest_content_sha256 != manifest.content_sha256
            or delivery.plan_content_sha256 != plan.content_sha256
            or prepared.block_id != trial.block_id
            or delivery.block_id != trial.block_id
            or prepared.treatment is not trial.treatment
            or delivery.treatment is not trial.treatment
            or delivery.current_state_equivalence_sha256 != prepared.current_state_equivalence_sha256
            or delivery.current_duties_sha256 != prepared.current_duties_sha256
            or delivery.carrier_content_sha256 != prepared.carrier_content_sha256
        ):
            raise ImmutableArtifactIntegrityError(
                f"ASW-4C prepared identity drift for {trial.trial_id}",
            )
        world_path = repository.root / prepared.world_relative_path
        if not (world_path / "world-run" / "manifest.json").is_file():
            raise ImmutableArtifactIntegrityError(
                f"ASW-4C prepared world is missing for {trial.trial_id}",
            )
        carrier_payload = repository.load_bytes(
            prepared.carrier_relative_path,
        )
        carrier_type: type[PumpStationActorView | PumpStationStructuredHandover] = (
            PumpStationActorView
            if trial.treatment is ContinuityTreatment.CURRENT_ACTOR_VIEW
            else PumpStationStructuredHandover
        )
        carrier = load_pump_station_artifact(
            carrier_payload,
            carrier_type,
        )
        carrier_id = carrier.view_id if isinstance(carrier, PumpStationActorView) else carrier.handover_id
        if carrier_id != prepared.carrier_content_sha256:
            raise ImmutableArtifactIntegrityError(
                f"ASW-4C carrier identity drift for {trial.trial_id}",
            )
    for block in plan.blocks:
        pair = tuple(prepared_trials[plan.trials.index(trial)] for trial in block.trials)
        if (
            pair[0].history_snapshot_sha256 != pair[1].history_snapshot_sha256
            or pair[0].event_schedule_sha256 != pair[1].event_schedule_sha256
            or pair[0].current_state_equivalence_sha256 != pair[1].current_state_equivalence_sha256
            or pair[0].current_duties_sha256 != pair[1].current_duties_sha256
        ):
            raise ImmutableArtifactIntegrityError(
                f"ASW-4C reloaded pair drift for {block.block_id}",
            )
    _assert_no_secret_material(repository.root)


def _world_relative_path(
    *,
    history_slot_id: str,
    treatment: ContinuityTreatment,
) -> str:
    return f"worlds/{history_slot_id}/{treatment.value}"


def _carrier_relative_path(trial: ContinuityTrial) -> str:
    filename = (
        "current-view.json" if trial.treatment is ContinuityTreatment.CURRENT_ACTOR_VIEW else "structured-handover.json"
    )
    return f"carriers/{trial.trial_id}/{filename}"


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
            raise ValueError(
                f"ASW-4C evidence contains credential material: {path.name}",
            )


__all__ = (
    "ASW4C_FINAL_INDEX_SCHEMA_VERSION",
    "ASW4C_PREPARED_TRIAL_SCHEMA_VERSION",
    "ASW4C_STUDY_INDEX_SCHEMA_VERSION",
    "ASW4C_TOKEN_MEASUREMENT_AMENDMENT_SCHEMA_VERSION",
    "ASW4C_TRIAL_COMPLETION_SCHEMA_VERSION",
    "ASW4C_TRIAL_EXECUTION_SCHEMA_VERSION",
    "ASW4C_TRIAL_START_SCHEMA_VERSION",
    "Asw4cAuthorityExhaustedError",
    "Asw4cConfirmatoryProgress",
    "Asw4cFinalIndex",
    "Asw4cInterruptedTrialError",
    "Asw4cPreparedTrial",
    "Asw4cStudyIndex",
    "Asw4cTokenMeasurementAmendment",
    "Asw4cTrialCompletion",
    "Asw4cTrialExecution",
    "Asw4cTrialStart",
    "PreparedAsw4cStudy",
    "prepare_asw4c_confirmatory_study",
    "publish_asw4c_token_measurement_amendment",
    "recover_asw4c_interrupted_count_tokens_permission",
    "recover_asw4c_interrupted_concurrent_tool_fault",
    "recover_asw4c_interrupted_endpoint_overshoot",
    "recover_asw4c_interrupted_provider_fault",
    "recover_asw4c_interrupted_token_guard",
    "recover_asw4c_interrupted_world_terminal",
    "reload_asw4c_confirmatory_result",
    "reload_asw4c_confirmatory_study",
    "run_asw4c_confirmatory",
)
