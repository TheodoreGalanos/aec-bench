# ABOUTME: Defines study-local contracts for retrieval-state continuity research.
# ABOUTME: Keeps generated analysis evidence separate from model study outcomes.

from __future__ import annotations

from collections import Counter
from enum import StrEnum
from typing import Literal, Self

from pydantic import NonNegativeInt, PositiveInt, field_validator, model_validator

from aec_bench.contracts.harness_kernel import ContentAddressedModel, canonical_content_sha256, validate_sha256
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr

STUDY_MANIFEST_SCHEMA_VERSION = "aecbench.retrieval-state-continuity-manifest.v1"
STUDY_PLAN_SCHEMA_VERSION = "aecbench.retrieval-state-continuity-plan.v1"
TREATMENT_DELIVERY_SCHEMA_VERSION = "aecbench.retrieval-state-continuity-delivery.v1"
STUDY_OBSERVATION_SCHEMA_VERSION = "aecbench.retrieval-state-continuity-observation.v1"
STUDY_REPORT_SCHEMA_VERSION = "aecbench.retrieval-state-continuity-report.v1"


class StudyPhase(StrEnum):
    """Authority class for one immutable study generation."""

    ANALYSIS_FIXTURE = "analysis_fixture"
    SHAKEDOWN = "shakedown"
    CONFIRMATORY = "confirmatory"


class Treatment(StrEnum):
    """The declared retrieval-state carrier difference."""

    RETRIEVAL_STATE_ABSENT = "retrieval_state_absent"
    RETRIEVAL_STATE_PRESERVED = "retrieval_state_preserved"


class ObservationSource(StrEnum):
    """Authority class for one retained observation."""

    GENERATED_ANALYSIS_FIXTURE = "generated_analysis_fixture"
    SHAKEDOWN = "shakedown"
    CONFIRMATORY = "confirmatory"


class TreatmentDeliveryStatus(StrEnum):
    """Host result for one carrier delivery."""

    DELIVERED = "delivered"
    NOT_DELIVERED = "not_delivered"
    CORRUPT = "corrupt"


class FailureKind(StrEnum):
    """Typed execution result used by endpoint and attrition rules."""

    NONE = "none"
    IDENTITY_DRIFT = "identity_drift"
    TREATMENT_DELIVERY_CORRUPTION = "treatment_delivery_corruption"
    HOST_FAILURE_BEFORE_DELIVERY = "host_failure_before_delivery"
    HOST_FAILURE_AFTER_DELIVERY = "host_failure_after_delivery"
    MODEL_EMPTY_OUTPUT = "model_empty_output"
    MODEL_TIMEOUT = "model_timeout"
    SEARCH_TOOL_FAILURE = "search_tool_failure"
    FETCH_TOOL_FAILURE = "fetch_tool_failure"
    CARRIER_SERIALIZATION_FAILURE = "carrier_serialization_failure"
    OUTPUT_CONTRACT_FAILURE = "output_contract_failure"
    INCOMPLETE = "incomplete"


class PairIneligibilityReason(StrEnum):
    """Reason one matched pair cannot enter the primary estimand."""

    MISSING_ARM = "missing_arm"
    MISSING_DELIVERY = "missing_delivery"
    HOST_FAILURE = "host_failure"
    IDENTITY_DRIFT = "identity_drift"
    TREATMENT_DELIVERY_CORRUPTION = "treatment_delivery_corruption"
    PAIR_IDENTITY_DRIFT = "pair_identity_drift"
    INCOMPLETE = "incomplete"


class StudyConclusion(StrEnum):
    """Bounded interpretation of one study report."""

    ANALYSIS_FIXTURE = "analysis_fixture"
    SHAKEDOWN = "shakedown"
    SUPPORTED = "supported"
    REFUTED = "refuted"
    INCONCLUSIVE = "inconclusive"
    COVERAGE_BLOCKED = "coverage_blocked"


class RetrievalStudyBudget(FrozenStrictModel):
    """Frozen logical retrieval and agent limits for each run."""

    maximum_search_calls: Literal[2] = 2
    maximum_fetch_calls: Literal[1] = 1
    maximum_references_per_result: Literal[5] = 5
    maximum_visible_bytes: Literal[8_000] = 8_000
    maximum_visible_tokens: Literal[2_000] = 2_000
    maximum_agent_turns: Literal[12] = 12
    simulated_retrieval_duration_seconds: Literal[0] = 0
    external_retrieval_provider_spend_microusd: Literal[0] = 0
    budget_conserved_at_handover: Literal[True] = True


class StudyAnalysisSpecification(FrozenStrictModel):
    """Frozen endpoint, estimand, interval, coverage, and decision rules."""

    endpoint: Literal["binary_epistemic_decision_failure"] = "binary_epistemic_decision_failure"
    estimand: Literal["mean_paired_risk_difference"] = "mean_paired_risk_difference"
    difference_order: Literal["retrieval_state_absent_minus_preserved"] = "retrieval_state_absent_minus_preserved"
    independent_world_history_count: Literal[8] = 8
    model_sampling_replicates_per_history: Literal[4] = 4
    minimum_meaningful_effect: float = 0.25
    confidence_level: float = 0.95
    uncertainty_method: Literal["world_history_clustered_paired_bootstrap_percentile_linear_v1"] = (
        "world_history_clustered_paired_bootstrap_percentile_linear_v1"
    )
    bootstrap_replicates: Literal[20_000] = 20_000
    bootstrap_seed: Literal[20_260_802] = 20_260_802
    minimum_eligible_world_histories: Literal[7] = 7
    minimum_eligible_pairs: Literal[28] = 28
    missing_pairs_replaced: Literal[False] = False
    post_delivery_failures_are_outcomes: Literal[True] = True
    only_pre_delivery_or_treatment_invariant_host_faults_excluded: Literal[True] = True

    @model_validator(mode="after")
    def validate_frozen_floats(self) -> Self:
        if self.minimum_meaningful_effect != 0.25:
            raise ValueError("minimum meaningful effect must remain 0.25")
        if self.confidence_level != 0.95:
            raise ValueError("confidence level must remain 0.95")
        return self


class TreatmentSpecification(ContentAddressedModel):
    """Origin and assignment basis for the only actor-visible treatment difference."""

    schema_version: str = STUDY_MANIFEST_SCHEMA_VERSION
    origin: Literal["host_constructed_sanitized_projection"] = "host_constructed_sanitized_projection"
    assignment_basis: Literal["seeded_hidden_within_pair"] = "seeded_hidden_within_pair"
    base_carrier_id: Literal["pump-station-structured-handover-retrieval-clean.v1"] = (
        "pump-station-structured-handover-retrieval-clean.v1"
    )
    projection_id: Literal["pump-station-unresolved-retrieval-state.v1"] = "pump-station-unresolved-retrieval-state.v1"
    includes_visible_results: Literal[True] = True
    includes_unresolved_searches: Literal[True] = True
    includes_remaining_budget: Literal[True] = True
    includes_private_reasons: Literal[False] = False
    includes_hidden_frontier: Literal[False] = False
    only_visible_input_difference: Literal[True] = True


class StudyManifest(ContentAddressedModel):
    """Content-addressed provider-free specification for the paired study."""

    schema_version: str = STUDY_MANIFEST_SCHEMA_VERSION
    study_id: NonEmptyStr
    study_generation_id: NonEmptyStr
    phase: StudyPhase
    profile_id: NonEmptyStr
    generation_id: NonEmptyStr
    package_content_id: str
    certification_content_id: str
    corpus_snapshot_id: str
    corpus_lineage_id: str
    retrieval_policy_id: str
    access_policy_id: str
    availability_schedule_id: str
    branch_policy_id: str
    cost_policy_id: str
    material_evidence_version_id: NonEmptyStr
    acceptable_evidence_version_ids: tuple[NonEmptyStr, ...]
    development_query_routes: tuple[NonEmptyStr, ...]
    decision_rule_id: NonEmptyStr
    retrievability_certificate_sha256: str
    base_carrier_audit_sha256: str
    current_actor_view_policy_id: NonEmptyStr
    verifier_id: NonEmptyStr
    pre_handover_world_time_seconds: int
    evidence_available_at_seconds: int
    decision_deadline_seconds: int
    decision_interval_seconds: Literal[3_600] = 3_600
    world_history_seeds: tuple[PositiveInt, ...]
    schedule_algorithm: Literal["seeded_balanced_adjacent_pairs_v1"] = "seeded_balanced_adjacent_pairs_v1"
    schedule_seed: Literal[20_260_802] = 20_260_802
    treatments: tuple[Treatment, ...]
    treatment: TreatmentSpecification
    budget: RetrievalStudyBudget
    analysis: StudyAnalysisSpecification
    provider_calls_allowed: Literal[0] = 0
    study_outcomes_allowed: Literal[False] = False
    task_reward_mutation_allowed: Literal[False] = False
    promotion_permitted: Literal[False] = False

    @field_validator(
        "package_content_id",
        "certification_content_id",
        "corpus_snapshot_id",
        "corpus_lineage_id",
        "retrieval_policy_id",
        "access_policy_id",
        "availability_schedule_id",
        "branch_policy_id",
        "cost_policy_id",
        "retrievability_certificate_sha256",
        "base_carrier_audit_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_design(self) -> Self:
        if self.phase is not StudyPhase.ANALYSIS_FIXTURE:
            raise ValueError("provider-free specification must use analysis_fixture authority")
        if self.treatments != tuple(Treatment):
            raise ValueError("study manifest must contain the two canonical treatments")
        if len(self.world_history_seeds) != self.analysis.independent_world_history_count:
            raise ValueError("world history count differs from the analysis specification")
        if len(self.world_history_seeds) != len(set(self.world_history_seeds)):
            raise ValueError("world history seeds must be distinct")
        if self.pre_handover_world_time_seconds >= self.evidence_available_at_seconds:
            raise ValueError("material evidence must be unavailable before handover")
        if self.decision_deadline_seconds - self.evidence_available_at_seconds != self.decision_interval_seconds:
            raise ValueError("decision deadline differs from the frozen post-availability interval")
        if self.material_evidence_version_id not in self.acceptable_evidence_version_ids:
            raise ValueError("material evidence must be in an acceptable evidence class")
        if len(self.development_query_routes) < 3:
            raise ValueError("retrievability calibration requires several query routes")
        return self


def study_block_id(
    *,
    manifest_content_sha256: str,
    sequence_index: int,
    world_history_seed: int,
    sampling_replicate: int,
    history_snapshot_sha256: str,
    event_schedule_sha256: str,
) -> str:
    """Return the opaque identity of one matched block."""

    return "block-" + canonical_content_sha256(
        {
            "manifest_content_sha256": manifest_content_sha256,
            "sequence_index": sequence_index,
            "world_history_seed": world_history_seed,
            "sampling_replicate": sampling_replicate,
            "history_snapshot_sha256": history_snapshot_sha256,
            "event_schedule_sha256": event_schedule_sha256,
        }
    )


def study_trial_id(
    *,
    block_id: str,
    treatment: Treatment,
    order_index: int,
    execution_position: int,
    budget_sha256: str,
) -> str:
    """Return an opaque trial identity without a treatment label."""

    return "trial-" + canonical_content_sha256(
        {
            "block_id": block_id,
            "treatment": treatment.value,
            "order_index": order_index,
            "execution_position": execution_position,
            "budget_sha256": budget_sha256,
        }
    )


class PlannedTrial(ContentAddressedModel):
    """One hidden treatment assignment within a matched block."""

    schema_version: str = STUDY_PLAN_SCHEMA_VERSION
    trial_id: NonEmptyStr
    block_id: NonEmptyStr
    treatment: Treatment
    order_index: PositiveInt
    execution_position: PositiveInt
    budget_sha256: str

    @field_validator("budget_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_trial(self) -> Self:
        if self.order_index not in {1, 2}:
            raise ValueError("trial order index must be one or two")
        expected = study_trial_id(
            block_id=self.block_id,
            treatment=self.treatment,
            order_index=self.order_index,
            execution_position=self.execution_position,
            budget_sha256=self.budget_sha256,
        )
        if self.trial_id != expected:
            raise ValueError("trial_id must bind the canonical trial")
        return self


class StudyBlock(ContentAddressedModel):
    """One realised history shared by both treatment arms."""

    schema_version: str = STUDY_PLAN_SCHEMA_VERSION
    block_id: NonEmptyStr
    manifest_content_sha256: str
    sequence_index: PositiveInt
    world_history_seed: PositiveInt
    sampling_replicate: PositiveInt
    history_snapshot_sha256: str
    event_schedule_sha256: str
    non_treatment_input_sha256: str
    current_actor_view_sha256: str
    base_carrier_sha256: str
    trials: tuple[PlannedTrial, ...]

    @field_validator(
        "manifest_content_sha256",
        "history_snapshot_sha256",
        "event_schedule_sha256",
        "non_treatment_input_sha256",
        "current_actor_view_sha256",
        "base_carrier_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_block(self) -> Self:
        expected = study_block_id(
            manifest_content_sha256=self.manifest_content_sha256,
            sequence_index=self.sequence_index,
            world_history_seed=self.world_history_seed,
            sampling_replicate=self.sampling_replicate,
            history_snapshot_sha256=self.history_snapshot_sha256,
            event_schedule_sha256=self.event_schedule_sha256,
        )
        if self.block_id != expected:
            raise ValueError("block_id must bind the canonical block")
        if len(self.trials) != 2 or {trial.treatment for trial in self.trials} != set(Treatment):
            raise ValueError("study block must contain both treatments")
        if tuple(trial.order_index for trial in self.trials) != (1, 2):
            raise ValueError("study block trials must use canonical order indexes")
        if self.trials[0].execution_position + 1 != self.trials[1].execution_position:
            raise ValueError("paired trials must be adjacent in the execution schedule")
        if any(trial.block_id != self.block_id for trial in self.trials):
            raise ValueError("study block trials differ from their parent block")
        return self


class StudyPlan(ContentAddressedModel):
    """Complete provider-independent expansion of the frozen paired design."""

    schema_version: str = STUDY_PLAN_SCHEMA_VERSION
    manifest_content_sha256: str
    schedule_algorithm: Literal["seeded_balanced_adjacent_pairs_v1"]
    schedule_seed: Literal[20_260_802]
    blocks: tuple[StudyBlock, ...]
    trials: tuple[PlannedTrial, ...]

    @field_validator("manifest_content_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        if len(self.blocks) != 32:
            raise ValueError("study plan must contain 32 matched blocks")
        if tuple(block.sequence_index for block in self.blocks) != tuple(range(1, 33)):
            raise ValueError("study blocks must use contiguous sequence indexes")
        flattened = tuple(trial for block in self.blocks for trial in block.trials)
        if self.trials != flattened:
            raise ValueError("study plan trials must equal the ordered block trials")
        if len(self.trials) != 64:
            raise ValueError("study plan must contain 64 planned trials")
        if tuple(trial.execution_position for trial in self.trials) != tuple(range(1, 65)):
            raise ValueError("study trials must use contiguous execution positions")
        if len({trial.trial_id for trial in self.trials}) != len(self.trials):
            raise ValueError("study trial ids must be unique")
        counts = Counter(block.world_history_seed for block in self.blocks)
        if set(counts.values()) != {4} or len(counts) != 8:
            raise ValueError("study plan must contain four pairs for each of eight histories")
        for seed in counts:
            selected = tuple(block for block in self.blocks if block.world_history_seed == seed)
            if {block.sampling_replicate for block in selected} != {1, 2, 3, 4}:
                raise ValueError("history sampling replicates must be one through four")
            if Counter(block.trials[0].treatment for block in selected) != {
                Treatment.RETRIEVAL_STATE_ABSENT: 2,
                Treatment.RETRIEVAL_STATE_PRESERVED: 2,
            }:
                raise ValueError("treatment order must be balanced within each world history")
        return self


class TreatmentDelivery(ContentAddressedModel):
    """Exact host record for treatment delivery and visible-input isolation."""

    schema_version: str = TREATMENT_DELIVERY_SCHEMA_VERSION
    manifest_content_sha256: str
    plan_content_sha256: str
    block_id: NonEmptyStr
    trial_id: NonEmptyStr
    treatment: Treatment
    source: ObservationSource
    status: TreatmentDeliveryStatus
    delivered_before_outcome: bool
    non_treatment_input_sha256: str
    current_actor_view_sha256: str
    history_snapshot_sha256: str
    event_schedule_sha256: str
    base_carrier_sha256: str
    treatment_projection_sha256: str | None
    delivered_carrier_sha256: str | None
    visible_input_audit_sha256: str
    provider_call_count: NonNegativeInt

    @field_validator(
        "manifest_content_sha256",
        "plan_content_sha256",
        "non_treatment_input_sha256",
        "current_actor_view_sha256",
        "history_snapshot_sha256",
        "event_schedule_sha256",
        "base_carrier_sha256",
        "visible_input_audit_sha256",
    )
    @classmethod
    def validate_required_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("treatment_projection_sha256", "delivered_carrier_sha256")
    @classmethod
    def validate_optional_hashes(cls, value: str | None) -> str | None:
        return None if value is None else validate_sha256(value)

    @model_validator(mode="after")
    def validate_delivery(self) -> Self:
        if self.status is TreatmentDeliveryStatus.DELIVERED:
            if not self.delivered_before_outcome or self.delivered_carrier_sha256 is None:
                raise ValueError("delivered treatment requires a pre-outcome carrier identity")
        elif self.delivered_before_outcome or self.delivered_carrier_sha256 is not None:
            raise ValueError("undelivered treatment cannot claim a delivered carrier")
        if self.treatment is Treatment.RETRIEVAL_STATE_ABSENT and self.treatment_projection_sha256 is not None:
            raise ValueError("absent treatment cannot contain a retrieval-state projection")
        if (
            self.treatment is Treatment.RETRIEVAL_STATE_PRESERVED
            and self.status is TreatmentDeliveryStatus.DELIVERED
            and self.treatment_projection_sha256 is None
        ):
            raise ValueError("preserved treatment requires a retrieval-state projection")
        if self.source is ObservationSource.GENERATED_ANALYSIS_FIXTURE and self.provider_call_count != 0:
            raise ValueError("analysis-fixture delivery cannot contain provider calls")
        return self


_POST_DELIVERY_FAILURES = {
    FailureKind.MODEL_EMPTY_OUTPUT,
    FailureKind.MODEL_TIMEOUT,
    FailureKind.SEARCH_TOOL_FAILURE,
    FailureKind.FETCH_TOOL_FAILURE,
    FailureKind.CARRIER_SERIALIZATION_FAILURE,
    FailureKind.OUTPUT_CONTRACT_FAILURE,
}
_INELIGIBLE_FAILURES = {
    FailureKind.IDENTITY_DRIFT,
    FailureKind.TREATMENT_DELIVERY_CORRUPTION,
    FailureKind.HOST_FAILURE_BEFORE_DELIVERY,
    FailureKind.HOST_FAILURE_AFTER_DELIVERY,
    FailureKind.INCOMPLETE,
}


class StudyObservation(ContentAddressedModel):
    """One retained run result with endpoint, secondary, cost, and failure data."""

    schema_version: str = STUDY_OBSERVATION_SCHEMA_VERSION
    manifest_content_sha256: str
    plan_content_sha256: str
    block_id: NonEmptyStr
    trial_id: NonEmptyStr
    world_history_seed: PositiveInt
    sampling_replicate: PositiveInt
    treatment: Treatment
    source: ObservationSource
    delivery_content_sha256: str
    history_snapshot_sha256: str
    event_schedule_sha256: str
    budget_sha256: str
    failure_kind: FailureKind
    epistemic_decision_failure: bool | None
    ineligibility_reason: PairIneligibilityReason | None
    material_evidence_acquired: bool
    material_evidence_used: bool
    stale_source_relied_on: bool
    conservative_action: bool
    search_call_count: NonNegativeInt
    fetch_call_count: NonNegativeInt
    visible_retrieval_bytes: NonNegativeInt
    visible_retrieval_tokens: NonNegativeInt
    agent_turn_count: NonNegativeInt
    provider_call_count: NonNegativeInt
    input_token_count: NonNegativeInt
    output_token_count: NonNegativeInt
    reported_analysis_token_count: NonNegativeInt | None
    analysis_tokens_included_in_output: bool
    total_token_count: NonNegativeInt
    spend_currency: NonEmptyStr | None
    spend_microunits: NonNegativeInt
    study_outcome_eligible: bool
    task_reward_mutation_count: NonNegativeInt

    @field_validator(
        "manifest_content_sha256",
        "plan_content_sha256",
        "delivery_content_sha256",
        "history_snapshot_sha256",
        "event_schedule_sha256",
        "budget_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_observation(self) -> Self:
        if self.failure_kind is FailureKind.NONE:
            if self.epistemic_decision_failure is None or self.ineligibility_reason is not None:
                raise ValueError("completed observation requires one binary endpoint")
        elif self.failure_kind in _POST_DELIVERY_FAILURES:
            if self.epistemic_decision_failure is not True or self.ineligibility_reason is not None:
                raise ValueError("post-delivery agent or tool failure must count as decision failure")
        elif self.failure_kind in _INELIGIBLE_FAILURES:
            if self.epistemic_decision_failure is not None or self.ineligibility_reason is None:
                raise ValueError("host or protocol failure requires a typed ineligibility reason")
        if self.material_evidence_used and not self.material_evidence_acquired:
            raise ValueError("material evidence cannot be used before acquisition")
        if self.total_token_count != self.input_token_count + self.output_token_count:
            raise ValueError("total tokens must equal input plus output tokens")
        if self.reported_analysis_token_count is not None and self.analysis_tokens_included_in_output is False:
            if self.reported_analysis_token_count > self.output_token_count:
                raise ValueError("separate analysis tokens cannot exceed output tokens")
        if self.source is ObservationSource.GENERATED_ANALYSIS_FIXTURE:
            if any(
                (
                    self.provider_call_count,
                    self.input_token_count,
                    self.output_token_count,
                    self.total_token_count,
                    self.spend_microunits,
                    self.task_reward_mutation_count,
                )
            ):
                raise ValueError("analysis fixture cannot contain provider, token, spend, or reward effects")
            if self.reported_analysis_token_count is not None or self.spend_currency is not None:
                raise ValueError("analysis fixture cannot contain provider usage metadata")
            if self.study_outcome_eligible:
                raise ValueError("analysis fixture cannot become a study outcome")
        return self


class ConfidenceInterval(FrozenStrictModel):
    """Two-sided interval for the paired risk difference."""

    lower: float
    upper: float
    confidence_level: float

    @model_validator(mode="after")
    def validate_interval(self) -> Self:
        if self.lower > self.upper:
            raise ValueError("confidence interval bounds are reversed")
        if self.confidence_level != 0.95:
            raise ValueError("confidence level must remain 0.95")
        return self


class PairCoverage(FrozenStrictModel):
    """Eligibility and paired endpoint for one planned block."""

    block_id: NonEmptyStr
    world_history_seed: PositiveInt
    observed_trial_ids: tuple[NonEmptyStr, ...]
    analyzable: bool
    ineligibility_reason: PairIneligibilityReason | None
    paired_difference: Literal[-1, 0, 1] | None


class CoverageReport(FrozenStrictModel):
    """Exact trial, pair, and world-history coverage."""

    exact: bool
    planned_trial_count: PositiveInt
    observed_trial_count: NonNegativeInt
    missing_trial_ids: tuple[NonEmptyStr, ...]
    complete_pair_count: NonNegativeInt
    analyzable_pair_count: NonNegativeInt
    eligible_world_history_count: NonNegativeInt
    pairs: tuple[PairCoverage, ...]


class StudyReport(ContentAddressedModel):
    """Immutable result that separates fixture checks from study conclusions."""

    schema_version: str = STUDY_REPORT_SCHEMA_VERSION
    manifest_content_sha256: str
    plan_content_sha256: str
    phase: StudyPhase
    gate_order: tuple[NonEmptyStr, ...]
    integrity_passed: bool
    validity_passed: bool
    conclusion: StudyConclusion
    fixture_rule_result: StudyConclusion | None
    coverage: CoverageReport
    point_estimate: float | None
    confidence_interval: ConfidenceInterval | None
    provider_call_count: NonNegativeInt
    input_token_count: NonNegativeInt
    output_token_count: NonNegativeInt
    reported_analysis_token_count: NonNegativeInt | None
    analysis_tokens_included_in_output: bool
    total_token_count: NonNegativeInt
    spend_currency: NonEmptyStr | None
    spend_microunits: NonNegativeInt
    study_outcome_count: NonNegativeInt
    fixture_observation_count: NonNegativeInt
    task_reward_mutation_count: NonNegativeInt
    promotion_permitted: Literal[False] = False
    delivery_content_sha256: tuple[str, ...]
    observation_content_sha256: tuple[str, ...]

    @field_validator("manifest_content_sha256", "plan_content_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        if self.gate_order != ("integrity", "validity", "endpoint"):
            raise ValueError("study gates must remain integrity, validity, then endpoint")
        if self.total_token_count != self.input_token_count + self.output_token_count:
            raise ValueError("report total tokens must equal input plus output tokens")
        if self.phase is StudyPhase.ANALYSIS_FIXTURE:
            if self.conclusion is not StudyConclusion.ANALYSIS_FIXTURE or self.fixture_rule_result is None:
                raise ValueError("analysis fixture cannot make a study conclusion")
            if self.study_outcome_count != 0 or self.provider_call_count != 0:
                raise ValueError("analysis fixture cannot contain model calls or study outcomes")
        elif self.phase is StudyPhase.SHAKEDOWN:
            if self.conclusion is not StudyConclusion.SHAKEDOWN or self.fixture_rule_result is not None:
                raise ValueError("shakedown report cannot make a confirmatory conclusion")
        elif self.conclusion in {StudyConclusion.ANALYSIS_FIXTURE, StudyConclusion.SHAKEDOWN}:
            raise ValueError("confirmatory report requires a bounded study conclusion")
        return self


class FixtureEvidence(FrozenStrictModel):
    """Generated evidence that can test analysis but cannot enter the estimand."""

    deliveries: tuple[TreatmentDelivery, ...]
    observations: tuple[StudyObservation, ...]
