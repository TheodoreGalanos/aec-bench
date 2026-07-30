# ABOUTME: Defines versioned study-local contracts for the first stewardship continuity study.
# ABOUTME: Separates provider-free analysis fixtures from shakedown and confirmatory outcomes.

from __future__ import annotations

from collections import Counter
from enum import StrEnum
from typing import Literal, Self

from pydantic import NonNegativeInt, PositiveInt, field_validator, model_validator

from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    canonical_content_sha256,
    validate_sha256,
)
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr

CONTINUITY_STUDY_MANIFEST_SCHEMA_VERSION: Literal["aecbench.stewardship-continuity-study-manifest.v1"] = (
    "aecbench.stewardship-continuity-study-manifest.v1"
)
CONTINUITY_STUDY_PLAN_SCHEMA_VERSION: Literal["aecbench.stewardship-continuity-study-plan.v1"] = (
    "aecbench.stewardship-continuity-study-plan.v1"
)
TREATMENT_DELIVERY_SCHEMA_VERSION: Literal["aecbench.stewardship-continuity-treatment-delivery.v1"] = (
    "aecbench.stewardship-continuity-treatment-delivery.v1"
)
CONTINUITY_OBSERVATION_SCHEMA_VERSION: Literal["aecbench.stewardship-continuity-observation.v1"] = (
    "aecbench.stewardship-continuity-observation.v1"
)
CONTINUITY_STUDY_REPORT_SCHEMA_VERSION: Literal["aecbench.stewardship-continuity-study-report.v1"] = (
    "aecbench.stewardship-continuity-study-report.v1"
)
CONTINUITY_MODEL_CONDITION_SCHEMA_VERSION: Literal["aecbench.stewardship-continuity-model-condition.v1"] = (
    "aecbench.stewardship-continuity-model-condition.v1"
)
CONTINUITY_PROVIDER_AUTHORIZATION_SCHEMA_VERSION: Literal[
    "aecbench.stewardship-continuity-provider-authorization.v1"
] = "aecbench.stewardship-continuity-provider-authorization.v1"

DIAGNOSTIC_PERIOD_SECONDS: Literal[28_800] = 28_800


class ContinuityStudyPhase(StrEnum):
    """Execution class for one immutable study generation."""

    ANALYSIS_FIXTURE = "analysis_fixture"
    SHAKEDOWN = "shakedown"
    CONFIRMATORY = "confirmatory"


class ContinuityExecutionKind(StrEnum):
    """Execution identity class bound into one study manifest."""

    ANALYSIS_FIXTURE = "analysis_fixture"
    PROVIDER_MODEL = "provider_model"


class ContinuityTreatment(StrEnum):
    """The two actor-visible continuity carriers in the first study."""

    CURRENT_ACTOR_VIEW = "current_actor_view"
    STRUCTURED_HANDOVER = "structured_handover"


class ContinuityHistoryClass(StrEnum):
    """The two matched history classes frozen by the research charter."""

    H1_STABLE_INSPECTED = "h1_stable_inspected"
    H2_WORSENING_VERIFICATION = "h2_worsening_verification"


class EvaluationWindow(StrEnum):
    """Hidden post-handover window expressed in diagnostic periods."""

    THREE_DIAGNOSTIC_PERIODS = "3D"
    FOUR_DIAGNOSTIC_PERIODS = "4D"

    @property
    def multiplier(self) -> int:
        """Return the exact number of diagnostic periods."""

        if self is EvaluationWindow.THREE_DIAGNOSTIC_PERIODS:
            return 3
        return 4

    @property
    def seconds(self) -> int:
        """Return the exact simulated duration."""

        return self.multiplier * DIAGNOSTIC_PERIOD_SECONDS


class TreatmentDeliveryStatus(StrEnum):
    """Host result for continuity-carrier delivery."""

    DELIVERED = "delivered"
    NOT_DELIVERED = "not_delivered"
    CORRUPT = "corrupt"


class ObservationSource(StrEnum):
    """Authority class for one analysis input."""

    GENERATED_ANALYSIS_FIXTURE = "generated_analysis_fixture"
    SHAKEDOWN = "shakedown"
    CONFIRMATORY = "confirmatory"


class ContinuityFailureKind(StrEnum):
    """Typed execution result used by attrition and endpoint rules."""

    NONE = "none"
    IDENTITY_DRIFT = "identity_drift"
    TREATMENT_DELIVERY_CORRUPTION = "treatment_delivery_corruption"
    HOST_FAILURE_BEFORE_DELIVERY = "host_failure_before_delivery"
    HOST_FAILURE_AFTER_DELIVERY = "host_failure_after_delivery"
    MODEL_EMPTY_OUTPUT = "model_empty_output"
    MODEL_TIMEOUT = "model_timeout"
    TOOL_FAILURE = "tool_failure"
    CARRIER_SERIALIZATION_FAILURE = "carrier_serialization_failure"
    OUTPUT_CONTRACT_FAILURE = "output_contract_failure"
    INCOMPLETE = "incomplete"


class PairIneligibilityReason(StrEnum):
    """Reason one planned pair cannot enter the paired estimand."""

    MISSING_ARM = "missing_arm"
    MISSING_DELIVERY = "missing_delivery"
    HOST_FAILURE = "host_failure"
    IDENTITY_DRIFT = "identity_drift"
    TREATMENT_DELIVERY_CORRUPTION = "treatment_delivery_corruption"
    PAIR_IDENTITY_DRIFT = "pair_identity_drift"
    INCOMPLETE = "incomplete"


class ContinuityConclusion(StrEnum):
    """Bounded interpretation of one study report."""

    ANALYSIS_FIXTURE = "analysis_fixture"
    SHAKEDOWN = "shakedown"
    SUPPORTED = "supported"
    REFUTED = "refuted"
    INCONCLUSIVE = "inconclusive"
    COVERAGE_BLOCKED = "coverage_blocked"


class ContinuityLogicalBudget(FrozenStrictModel):
    """Fixed logical limits applied to each planned trajectory."""

    max_model_turns: Literal[16] = 16
    max_agent_proposals: Literal[12] = 12
    max_host_commands: Literal[32] = 32
    fresh_agent_handovers: Literal[1] = 1
    temporal_retrieval_allowed: Literal[False] = False
    external_historical_search_allowed: Literal[False] = False
    evaluation_window_visible: Literal[False] = False
    future_events_visible: Literal[False] = False


class ContinuityAnalysisSpecification(FrozenStrictModel):
    """Frozen primary endpoint, estimand, uncertainty, and conclusion rules."""

    endpoint: Literal["binary_obligation_continuity_failure"] = "binary_obligation_continuity_failure"
    estimand: Literal["mean_paired_risk_difference"] = "mean_paired_risk_difference"
    difference_order: Literal["structured_handover_minus_current_actor_view"] = (
        "structured_handover_minus_current_actor_view"
    )
    minimum_meaningful_effect: float = 0.25
    confidence_level: float = 0.95
    uncertainty_method: Literal["paired_block_bootstrap_percentile_linear_v1"] = (
        "paired_block_bootstrap_percentile_linear_v1"
    )
    bootstrap_replicates: Literal[20_000] = 20_000
    bootstrap_seed: Literal[20_260_729] = 20_260_729
    minimum_eligible_blocks: Literal[28] = 28
    maximum_host_fault_arm_imbalance: Literal[2] = 2
    missing_pairs_replaced: Literal[False] = False

    @model_validator(mode="after")
    def validate_frozen_floats(self) -> Self:
        if self.minimum_meaningful_effect != 0.25:
            raise ValueError("minimum meaningful effect must remain 0.25")
        if self.confidence_level != 0.95:
            raise ValueError("confidence level must remain 0.95")
        return self


class ContinuityModelCondition(ContentAddressedModel):
    """Exact provider/model/adapter condition declared before execution."""

    schema_version: Literal["aecbench.stewardship-continuity-model-condition.v1"] = (
        CONTINUITY_MODEL_CONDITION_SCHEMA_VERSION
    )
    execution_kind: ContinuityExecutionKind
    provider_id: NonEmptyStr | None
    model_id: NonEmptyStr | None
    adapter_id: NonEmptyStr | None
    model_configuration_sha256: str

    @field_validator("model_configuration_sha256")
    @classmethod
    def validate_model_configuration_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_execution_identity(self) -> Self:
        provider_values = (
            self.provider_id,
            self.model_id,
            self.adapter_id,
        )
        if self.execution_kind is ContinuityExecutionKind.ANALYSIS_FIXTURE:
            if any(value is not None for value in provider_values):
                raise ValueError("analysis fixture cannot declare provider model identity")
        elif any(value is None for value in provider_values):
            raise ValueError("provider model condition requires provider, model, and adapter identities")
        return self


class ContinuityProviderAuthorization(ContentAddressedModel):
    """Approved provider, token, call, and spend limits for one phase."""

    schema_version: Literal["aecbench.stewardship-continuity-provider-authorization.v1"] = (
        CONTINUITY_PROVIDER_AUTHORIZATION_SCHEMA_VERSION
    )
    authorization_id: NonEmptyStr
    authorized_phase: ContinuityStudyPhase
    approved_by: NonEmptyStr
    model_condition_sha256: str
    maximum_provider_calls: PositiveInt
    maximum_input_tokens_per_call: PositiveInt
    maximum_output_tokens_per_call: PositiveInt
    maximum_total_tokens: PositiveInt
    spend_currency: NonEmptyStr
    maximum_spend_microunits: PositiveInt

    @field_validator("model_condition_sha256")
    @classmethod
    def validate_model_condition_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_provider_authority(self) -> Self:
        if self.authorized_phase is ContinuityStudyPhase.ANALYSIS_FIXTURE:
            raise ValueError("provider authority cannot authorize analysis fixtures")
        if self.spend_currency != self.spend_currency.upper() or len(self.spend_currency) != 3:
            raise ValueError("provider spend currency must be a three-letter uppercase code")
        theoretical_maximum = self.maximum_provider_calls * (
            self.maximum_input_tokens_per_call + self.maximum_output_tokens_per_call
        )
        if self.maximum_total_tokens > theoretical_maximum:
            raise ValueError("total token authority exceeds the per-call limits")
        return self


class ContinuityStudyManifest(ContentAddressedModel):
    """Immutable study design and execution authority for one generation."""

    schema_version: Literal["aecbench.stewardship-continuity-study-manifest.v1"] = (
        CONTINUITY_STUDY_MANIFEST_SCHEMA_VERSION
    )
    study_id: NonEmptyStr
    study_generation_id: NonEmptyStr
    phase: ContinuityStudyPhase
    charter_revision: NonEmptyStr
    task_world_id: NonEmptyStr
    profile_id: NonEmptyStr
    generation_id: NonEmptyStr
    package_content_id: str
    promotion_manifest_content_id: str
    receipt_version: NonEmptyStr
    authority_policy_version: NonEmptyStr
    transition_rule_version: NonEmptyStr
    projection_policy_id: NonEmptyStr
    evaluation_schema_version: NonEmptyStr
    event_schedule_revision: NonEmptyStr
    verifier_revision: NonEmptyStr
    harness_configuration_sha256: str
    treatment_delivery_configuration_sha256: str
    model_condition: ContinuityModelCondition
    provider_authorization: ContinuityProviderAuthorization | None
    adaptation_mode: Literal["none"] = "none"
    diagnostic_period_seconds: Literal[28_800] = DIAGNOSTIC_PERIOD_SECONDS
    history_classes: tuple[ContinuityHistoryClass, ...]
    treatments: tuple[ContinuityTreatment, ...]
    blocks_per_history: Literal[16] = 16
    ordering_method: Literal["counterbalanced_pair_order_v1"] = "counterbalanced_pair_order_v1"
    logical_budget: ContinuityLogicalBudget = ContinuityLogicalBudget()
    analysis: ContinuityAnalysisSpecification = ContinuityAnalysisSpecification()
    study_outcomes_allowed: bool
    task_reward_mutation_allowed: Literal[False] = False

    @field_validator(
        "package_content_id",
        "promotion_manifest_content_id",
        "harness_configuration_sha256",
        "treatment_delivery_configuration_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_study_authority(self) -> Self:
        if self.history_classes != tuple(ContinuityHistoryClass):
            raise ValueError("study manifest must contain the two canonical history classes")
        if self.treatments != tuple(ContinuityTreatment):
            raise ValueError("study manifest must contain the two canonical continuity treatments")
        if self.phase is ContinuityStudyPhase.ANALYSIS_FIXTURE:
            if (
                self.model_condition.execution_kind is not ContinuityExecutionKind.ANALYSIS_FIXTURE
                or self.provider_authorization is not None
            ):
                raise ValueError("analysis-fixture generation cannot authorize provider calls")
            if self.study_outcomes_allowed:
                raise ValueError("analysis-fixture generation cannot contain study outcomes")
        else:
            if (
                self.model_condition.execution_kind is not ContinuityExecutionKind.PROVIDER_MODEL
                or self.provider_authorization is None
            ):
                raise ValueError(f"{self.phase.value} generation requires explicit provider authority")
            if self.provider_authorization.authorized_phase is not self.phase:
                raise ValueError("provider authority does not authorize the selected study phase")
            if self.provider_authorization.model_condition_sha256 != self.model_condition.content_sha256:
                raise ValueError("provider authority does not bind the selected model condition")
            if self.phase is ContinuityStudyPhase.SHAKEDOWN and self.study_outcomes_allowed:
                raise ValueError("shakedown generation cannot enter the confirmatory estimand")
            if self.phase is ContinuityStudyPhase.CONFIRMATORY and not self.study_outcomes_allowed:
                raise ValueError("confirmatory generation must authorize outcome evidence")
        return self

    @property
    def provider_calls_allowed(self) -> int:
        """Return zero without authority or the exact approved call limit."""

        if self.provider_authorization is None:
            return 0
        return self.provider_authorization.maximum_provider_calls


class ContinuityTrial(ContentAddressedModel):
    """One ordered continuity treatment inside a matched history block."""

    schema_version: Literal["aecbench.stewardship-continuity-trial.v1"] = "aecbench.stewardship-continuity-trial.v1"
    trial_id: NonEmptyStr
    study_id: NonEmptyStr
    study_generation_id: NonEmptyStr
    block_id: NonEmptyStr
    sequence_index: PositiveInt
    repetition: PositiveInt
    history_class: ContinuityHistoryClass
    history_slot_id: NonEmptyStr
    treatment: ContinuityTreatment
    order_index: PositiveInt
    evaluation_window: EvaluationWindow
    evaluation_window_seconds: PositiveInt
    logical_budget_sha256: str

    @field_validator("logical_budget_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_trial(self) -> Self:
        if self.order_index not in {1, 2}:
            raise ValueError("continuity trial order_index must be one or two")
        if self.evaluation_window_seconds != self.evaluation_window.seconds:
            raise ValueError("continuity trial window seconds differ from the frozen window")
        expected = continuity_trial_id(
            study_id=self.study_id,
            study_generation_id=self.study_generation_id,
            block_id=self.block_id,
            sequence_index=self.sequence_index,
            repetition=self.repetition,
            history_class=self.history_class,
            history_slot_id=self.history_slot_id,
            treatment=self.treatment,
            order_index=self.order_index,
            evaluation_window=self.evaluation_window,
            logical_budget_sha256=self.logical_budget_sha256,
        )
        if self.trial_id != expected:
            raise ValueError("trial_id must bind the canonical continuity trial")
        return self


class ContinuityBlock(ContentAddressedModel):
    """One matched history with both continuity treatments."""

    schema_version: Literal["aecbench.stewardship-continuity-block.v1"] = "aecbench.stewardship-continuity-block.v1"
    block_id: NonEmptyStr
    study_id: NonEmptyStr
    study_generation_id: NonEmptyStr
    sequence_index: PositiveInt
    repetition: PositiveInt
    history_class: ContinuityHistoryClass
    history_slot_id: NonEmptyStr
    evaluation_window: EvaluationWindow
    history_snapshot_sha256: str
    event_schedule_sha256: str
    trials: tuple[ContinuityTrial, ...]

    @field_validator("history_snapshot_sha256", "event_schedule_sha256")
    @classmethod
    def validate_condition_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_block(self) -> Self:
        expected = continuity_block_id(
            study_id=self.study_id,
            study_generation_id=self.study_generation_id,
            sequence_index=self.sequence_index,
            repetition=self.repetition,
            history_class=self.history_class,
            history_slot_id=self.history_slot_id,
            evaluation_window=self.evaluation_window,
            history_snapshot_sha256=self.history_snapshot_sha256,
            event_schedule_sha256=self.event_schedule_sha256,
        )
        if self.block_id != expected:
            raise ValueError("block_id must bind the canonical continuity block")
        if len(self.trials) != 2:
            raise ValueError("continuity block must contain exactly two trials")
        if tuple(trial.order_index for trial in self.trials) != (1, 2):
            raise ValueError("continuity block trials must use canonical order indexes")
        if {trial.treatment for trial in self.trials} != set(ContinuityTreatment):
            raise ValueError("continuity block must contain both continuity treatments")
        if any(
            trial.block_id != self.block_id
            or trial.study_id != self.study_id
            or trial.study_generation_id != self.study_generation_id
            or trial.sequence_index != self.sequence_index
            or trial.repetition != self.repetition
            or trial.history_class is not self.history_class
            or trial.history_slot_id != self.history_slot_id
            or trial.evaluation_window is not self.evaluation_window
            for trial in self.trials
        ):
            raise ValueError("continuity block trials differ from their parent block")
        return self


class ContinuityStudyPlan(ContentAddressedModel):
    """Complete provider-independent expansion of the first study design."""

    schema_version: Literal["aecbench.stewardship-continuity-study-plan.v1"] = CONTINUITY_STUDY_PLAN_SCHEMA_VERSION
    manifest_content_sha256: str
    study_id: NonEmptyStr
    study_generation_id: NonEmptyStr
    blocks_per_history: Literal[16] = 16
    blocks: tuple[ContinuityBlock, ...]
    trials: tuple[ContinuityTrial, ...]

    @field_validator("manifest_content_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        if len(self.blocks) != 32:
            raise ValueError("continuity plan must contain 32 matched blocks")
        if tuple(block.sequence_index for block in self.blocks) != tuple(range(1, 33)):
            raise ValueError("continuity blocks must use contiguous sequence indexes")
        flattened = tuple(trial for block in self.blocks for trial in block.trials)
        if self.trials != flattened:
            raise ValueError("continuity plan trials must equal the ordered block trials")
        if len(self.trials) != 64:
            raise ValueError("continuity plan must contain 64 planned trials")
        trial_ids = tuple(trial.trial_id for trial in self.trials)
        if len(trial_ids) != len(set(trial_ids)):
            raise ValueError("continuity trial ids must be unique")
        if Counter(block.history_class for block in self.blocks) != {
            ContinuityHistoryClass.H1_STABLE_INSPECTED: 16,
            ContinuityHistoryClass.H2_WORSENING_VERIFICATION: 16,
        }:
            raise ValueError("continuity plan must contain 16 blocks per history class")
        self._validate_counterbalance()
        return self

    def _validate_counterbalance(self) -> None:
        for history_class in ContinuityHistoryClass:
            selected = tuple(block for block in self.blocks if block.history_class is history_class)
            if Counter(block.evaluation_window for block in selected) != {
                EvaluationWindow.THREE_DIAGNOSTIC_PERIODS: 8,
                EvaluationWindow.FOUR_DIAGNOSTIC_PERIODS: 8,
            }:
                raise ValueError("continuity windows must be balanced within each history")
            if Counter(block.trials[0].treatment for block in selected) != {
                ContinuityTreatment.CURRENT_ACTOR_VIEW: 8,
                ContinuityTreatment.STRUCTURED_HANDOVER: 8,
            }:
                raise ValueError("continuity treatment order must be balanced within each history")
            for evaluation_window in EvaluationWindow:
                window_blocks = tuple(block for block in selected if block.evaluation_window is evaluation_window)
                if Counter(block.trials[0].treatment for block in window_blocks) != {
                    ContinuityTreatment.CURRENT_ACTOR_VIEW: 4,
                    ContinuityTreatment.STRUCTURED_HANDOVER: 4,
                }:
                    raise ValueError(
                        "continuity order must be balanced within each history and window",
                    )


class TreatmentDeliveryRecord(ContentAddressedModel):
    """Exact host record for one continuity-carrier delivery."""

    schema_version: Literal["aecbench.stewardship-continuity-treatment-delivery.v1"] = TREATMENT_DELIVERY_SCHEMA_VERSION
    manifest_content_sha256: str
    plan_content_sha256: str
    block_id: NonEmptyStr
    trial_id: NonEmptyStr
    treatment: ContinuityTreatment
    source: ObservationSource
    status: TreatmentDeliveryStatus
    delivered_before_outcome: bool
    current_state_equivalence_sha256: str
    current_duties_sha256: str
    carrier_content_sha256: str | None
    provider_call_count: NonNegativeInt

    @field_validator(
        "manifest_content_sha256",
        "plan_content_sha256",
        "current_state_equivalence_sha256",
        "current_duties_sha256",
    )
    @classmethod
    def validate_required_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("carrier_content_sha256")
    @classmethod
    def validate_optional_hash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_delivery(self) -> Self:
        if self.status is TreatmentDeliveryStatus.DELIVERED:
            if not self.delivered_before_outcome or self.carrier_content_sha256 is None:
                raise ValueError("delivered treatment requires a pre-outcome carrier identity")
        elif self.delivered_before_outcome or self.carrier_content_sha256 is not None:
            raise ValueError("undelivered treatment cannot claim a delivered carrier")
        if self.source is ObservationSource.GENERATED_ANALYSIS_FIXTURE and self.provider_call_count != 0:
            raise ValueError("analysis-fixture delivery cannot contain provider calls")
        return self


_POST_DELIVERY_FAILURES = {
    ContinuityFailureKind.MODEL_EMPTY_OUTPUT,
    ContinuityFailureKind.MODEL_TIMEOUT,
    ContinuityFailureKind.TOOL_FAILURE,
    ContinuityFailureKind.CARRIER_SERIALIZATION_FAILURE,
    ContinuityFailureKind.OUTPUT_CONTRACT_FAILURE,
}
_INELIGIBLE_FAILURES = {
    ContinuityFailureKind.IDENTITY_DRIFT,
    ContinuityFailureKind.TREATMENT_DELIVERY_CORRUPTION,
    ContinuityFailureKind.HOST_FAILURE_BEFORE_DELIVERY,
    ContinuityFailureKind.HOST_FAILURE_AFTER_DELIVERY,
    ContinuityFailureKind.INCOMPLETE,
}


class ContinuityObservation(ContentAddressedModel):
    """One retained trajectory result or generated analysis fixture."""

    schema_version: Literal["aecbench.stewardship-continuity-observation.v1"] = CONTINUITY_OBSERVATION_SCHEMA_VERSION
    manifest_content_sha256: str
    plan_content_sha256: str
    block_id: NonEmptyStr
    trial_id: NonEmptyStr
    treatment: ContinuityTreatment
    source: ObservationSource
    delivery_content_sha256: str
    history_snapshot_sha256: str
    event_schedule_sha256: str
    logical_budget_sha256: str
    model_condition_sha256: str
    failure_kind: ContinuityFailureKind
    continuity_failure: bool | None
    ineligibility_reason: PairIneligibilityReason | None
    study_outcome_eligible: bool
    provider_call_count: NonNegativeInt
    input_token_count: NonNegativeInt
    output_token_count: NonNegativeInt
    maximum_input_tokens_in_one_call: NonNegativeInt
    maximum_output_tokens_in_one_call: NonNegativeInt
    spend_currency: NonEmptyStr | None
    spend_microunits: NonNegativeInt
    task_reward_mutation_count: NonNegativeInt

    @field_validator(
        "manifest_content_sha256",
        "plan_content_sha256",
        "delivery_content_sha256",
        "history_snapshot_sha256",
        "event_schedule_sha256",
        "logical_budget_sha256",
        "model_condition_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_observation(self) -> Self:
        if self.maximum_input_tokens_in_one_call > self.input_token_count:
            raise ValueError("maximum input tokens cannot exceed total input tokens")
        if self.maximum_output_tokens_in_one_call > self.output_token_count:
            raise ValueError("maximum output tokens cannot exceed total output tokens")
        if self.spend_currency is not None and (
            self.spend_currency != self.spend_currency.upper() or len(self.spend_currency) != 3
        ):
            raise ValueError("observation spend currency must be a three-letter uppercase code")
        usage_values = (
            self.input_token_count,
            self.output_token_count,
            self.maximum_input_tokens_in_one_call,
            self.maximum_output_tokens_in_one_call,
            self.spend_microunits,
        )
        if self.provider_call_count == 0:
            if any(usage_values) or self.spend_currency is not None:
                raise ValueError("observation without provider calls cannot contain provider usage")
        elif self.spend_currency is None:
            raise ValueError("observation with provider calls requires a spend currency")
        if self.source is ObservationSource.GENERATED_ANALYSIS_FIXTURE:
            if self.study_outcome_eligible:
                raise ValueError("analysis fixture cannot be a study outcome")
            if self.provider_call_count != 0:
                raise ValueError("analysis fixture cannot contain provider calls")
            if any(usage_values) or self.spend_currency is not None:
                raise ValueError("analysis fixture cannot contain token or spend usage")
            if self.task_reward_mutation_count != 0:
                raise ValueError("analysis fixture cannot mutate task reward")
        if self.failure_kind is ContinuityFailureKind.NONE:
            if self.continuity_failure is None or self.ineligibility_reason is not None:
                raise ValueError("completed observation requires one binary endpoint")
        elif self.failure_kind in _POST_DELIVERY_FAILURES:
            if self.continuity_failure is not True or self.ineligibility_reason is not None:
                raise ValueError("post-delivery model or tool failure must count as continuity failure")
        elif self.failure_kind in _INELIGIBLE_FAILURES:
            if self.continuity_failure is not None or self.ineligibility_reason is None:
                raise ValueError("host, identity, delivery, or incomplete failure must be ineligible")
            if self.study_outcome_eligible:
                raise ValueError("ineligible observation cannot enter the study outcome")
        return self

    @property
    def is_host_fault(self) -> bool:
        """Return whether the observation records a host-owned failure."""

        return self.failure_kind in {
            ContinuityFailureKind.HOST_FAILURE_BEFORE_DELIVERY,
            ContinuityFailureKind.HOST_FAILURE_AFTER_DELIVERY,
        }


class ProviderFreeFixtureEvidence(FrozenStrictModel):
    """Generated treatment and endpoint values used only to test analysis code."""

    deliveries: tuple[TreatmentDeliveryRecord, ...]
    observations: tuple[ContinuityObservation, ...]


class ConfidenceInterval(FrozenStrictModel):
    """Two-sided percentile interval over paired block differences."""

    level: float = 0.95
    lower: float
    upper: float

    @model_validator(mode="after")
    def validate_interval(self) -> Self:
        if self.level != 0.95:
            raise ValueError("confidence interval level must remain 0.95")
        if self.lower > self.upper:
            raise ValueError("confidence interval lower bound exceeds upper bound")
        return self


class BlockCoverage(FrozenStrictModel):
    """Coverage and paired endpoint result for one planned block."""

    block_id: NonEmptyStr
    observed_trial_ids: tuple[NonEmptyStr, ...]
    analyzable: bool
    ineligibility_reason: PairIneligibilityReason | None
    paired_difference: Literal[-1, 0, 1] | None

    @model_validator(mode="after")
    def validate_block_coverage(self) -> Self:
        if self.analyzable:
            if self.ineligibility_reason is not None or self.paired_difference is None:
                raise ValueError("analyzable block requires one paired difference")
        elif self.ineligibility_reason is None or self.paired_difference is not None:
            raise ValueError("ineligible block requires one typed reason and no difference")
        return self


class ContinuityCoverageReport(FrozenStrictModel):
    """Exact planned, observed, paired, and ineligible coverage."""

    exact: bool
    planned_trial_count: PositiveInt
    observed_trial_count: NonNegativeInt
    missing_trial_ids: tuple[NonEmptyStr, ...]
    complete_block_count: NonNegativeInt
    analyzable_block_count: NonNegativeInt
    host_fault_count_by_treatment: dict[ContinuityTreatment, NonNegativeInt]
    host_fault_arm_imbalance: NonNegativeInt
    blocks: tuple[BlockCoverage, ...]


class ContinuityStudyReport(ContentAddressedModel):
    """Immutable report recomputed from a manifest, plan, and retained evidence."""

    schema_version: Literal["aecbench.stewardship-continuity-study-report.v1"] = CONTINUITY_STUDY_REPORT_SCHEMA_VERSION
    manifest_content_sha256: str
    plan_content_sha256: str
    phase: ContinuityStudyPhase
    conclusion: ContinuityConclusion
    fixture_rule_result: ContinuityConclusion | None
    coverage: ContinuityCoverageReport
    point_estimate: float | None
    confidence_interval: ConfidenceInterval | None
    bootstrap_replicates: PositiveInt
    bootstrap_seed: int
    provider_call_count: NonNegativeInt
    input_token_count: NonNegativeInt
    output_token_count: NonNegativeInt
    maximum_input_tokens_in_one_call: NonNegativeInt
    maximum_output_tokens_in_one_call: NonNegativeInt
    spend_currency: NonEmptyStr | None
    spend_microunits: NonNegativeInt
    study_outcome_count: NonNegativeInt
    fixture_observation_count: NonNegativeInt
    task_reward_mutation_count: NonNegativeInt
    delivery_content_sha256: tuple[str, ...]
    observation_content_sha256: tuple[str, ...]

    @field_validator(
        "manifest_content_sha256",
        "plan_content_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator(
        "delivery_content_sha256",
        "observation_content_sha256",
    )
    @classmethod
    def validate_hash_sequences(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("study report evidence identities must be unique")
        for digest in value:
            validate_sha256(digest)
        return value

    @model_validator(mode="after")
    def validate_report_authority(self) -> Self:
        if self.maximum_input_tokens_in_one_call > self.input_token_count:
            raise ValueError("report maximum input tokens exceed total input tokens")
        if self.maximum_output_tokens_in_one_call > self.output_token_count:
            raise ValueError("report maximum output tokens exceed total output tokens")
        if self.spend_currency is not None and (
            self.spend_currency != self.spend_currency.upper() or len(self.spend_currency) != 3
        ):
            raise ValueError("report spend currency must be a three-letter uppercase code")
        usage_values = (
            self.input_token_count,
            self.output_token_count,
            self.maximum_input_tokens_in_one_call,
            self.maximum_output_tokens_in_one_call,
            self.spend_microunits,
        )
        if self.provider_call_count == 0:
            if any(usage_values):
                raise ValueError("report without provider calls cannot contain provider usage")
        elif self.spend_currency is None:
            raise ValueError("report with provider calls requires a spend currency")
        statistical_conclusions = {
            ContinuityConclusion.SUPPORTED,
            ContinuityConclusion.REFUTED,
            ContinuityConclusion.INCONCLUSIVE,
            ContinuityConclusion.COVERAGE_BLOCKED,
        }
        if self.phase is ContinuityStudyPhase.ANALYSIS_FIXTURE:
            if self.conclusion is not ContinuityConclusion.ANALYSIS_FIXTURE:
                raise ValueError("analysis fixture cannot make a study conclusion")
            if self.fixture_rule_result not in statistical_conclusions:
                raise ValueError("analysis fixture must expose its diagnostic rule result")
            if self.provider_call_count != 0 or self.study_outcome_count != 0 or self.task_reward_mutation_count != 0:
                raise ValueError("analysis fixture must contain zero calls, outcomes, and reward changes")
            if any(usage_values) or self.spend_currency is not None:
                raise ValueError("analysis fixture must contain zero token and spend usage")
        elif self.phase is ContinuityStudyPhase.SHAKEDOWN:
            if self.conclusion is not ContinuityConclusion.SHAKEDOWN:
                raise ValueError("shakedown report cannot make a confirmatory conclusion")
            if self.fixture_rule_result is not None:
                raise ValueError("shakedown report cannot contain a fixture rule result")
            if self.study_outcome_count != 0 or self.fixture_observation_count != 0:
                raise ValueError("shakedown report cannot contain study outcomes or fixtures")
        else:
            if self.conclusion not in statistical_conclusions:
                raise ValueError("confirmatory report requires a confirmatory conclusion")
            if self.fixture_rule_result is not None or self.fixture_observation_count != 0:
                raise ValueError("confirmatory report cannot contain fixture results")
        if self.task_reward_mutation_count != 0:
            raise ValueError("continuity study reports cannot contain task reward changes")
        return self


def continuity_block_id(
    *,
    study_id: str,
    study_generation_id: str,
    sequence_index: int,
    repetition: int,
    history_class: ContinuityHistoryClass,
    history_slot_id: str,
    evaluation_window: EvaluationWindow,
    history_snapshot_sha256: str,
    event_schedule_sha256: str,
) -> str:
    """Return one canonical matched-block identity."""

    return "block-" + canonical_content_sha256(
        {
            "study_id": study_id,
            "study_generation_id": study_generation_id,
            "sequence_index": sequence_index,
            "repetition": repetition,
            "history_class": history_class.value,
            "history_slot_id": history_slot_id,
            "evaluation_window": evaluation_window.value,
            "history_snapshot_sha256": history_snapshot_sha256,
            "event_schedule_sha256": event_schedule_sha256,
        }
    )


def continuity_trial_id(
    *,
    study_id: str,
    study_generation_id: str,
    block_id: str,
    sequence_index: int,
    repetition: int,
    history_class: ContinuityHistoryClass,
    history_slot_id: str,
    treatment: ContinuityTreatment,
    order_index: int,
    evaluation_window: EvaluationWindow,
    logical_budget_sha256: str,
) -> str:
    """Return one canonical treatment-trial identity."""

    return "trial-" + canonical_content_sha256(
        {
            "study_id": study_id,
            "study_generation_id": study_generation_id,
            "block_id": block_id,
            "sequence_index": sequence_index,
            "repetition": repetition,
            "history_class": history_class.value,
            "history_slot_id": history_slot_id,
            "treatment": treatment.value,
            "order_index": order_index,
            "evaluation_window": evaluation_window.value,
            "logical_budget_sha256": logical_budget_sha256,
        }
    )


def logical_budget_sha256(budget: ContinuityLogicalBudget) -> str:
    """Return the canonical identity of the frozen logical budget."""

    return canonical_content_sha256(budget.model_dump(mode="json"))
