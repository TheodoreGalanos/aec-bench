# ABOUTME: Defines fail-closed evaluation outcomes, gap decomposition, and plane-specific costs.
# ABOUTME: Makes integrity, validity, utility, and independently grounded critic evidence explicit.

from __future__ import annotations

import math
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, FiniteFloat, NonNegativeInt, PositiveInt, field_validator, model_validator

from aec_bench.contracts.evaluation_plane import CriticRef, EvaluationPlanRef
from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    FrozenStrictModel,
    validate_sha256,
)
from aec_bench.contracts.validators import NonEmptyStr

UnitFloat = Annotated[FiniteFloat, Field(ge=0.0, le=1.0)]
OpenUnitFloat = Annotated[FiniteFloat, Field(gt=0.0, lt=1.0)]
NonNegativeFiniteFloat = Annotated[FiniteFloat, Field(ge=0.0)]


class EvaluationDisposition(StrEnum):
    """Terminal interpretation of one evaluation outcome."""

    ACCEPT = "accept"
    REJECT = "reject"
    ABSTAIN = "abstain"
    EXPERIMENT_ERROR = "experiment_error"


class CommonModeBasisKind(StrEnum):
    """Independent truth bases allowed to establish a shared critic failure."""

    EXECUTABLE_ANCHOR = "executable_anchor"
    HUMAN_AUDIT = "human_audit"


class IntegrityCheck(FrozenStrictModel):
    """One runtime integrity invariant and the evidence supporting its result."""

    check_id: NonEmptyStr
    passed: bool
    evidence_sha256s: tuple[str, ...] = ()
    reasons: tuple[NonEmptyStr, ...] = ()

    @field_validator("evidence_sha256s")
    @classmethod
    def canonicalize_evidence_sha256s(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError("integrity check evidence references must be unique")
        return tuple(sorted(value))

    @field_validator("reasons")
    @classmethod
    def canonicalize_reasons(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("integrity check reasons must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def validate_failure_evidence(self) -> Self:
        if not self.passed and not self.reasons:
            raise ValueError("failed integrity check requires at least one reason")
        return self


class IntegrityEvaluation(ContentAddressedModel):
    """Content-addressed result of evaluating all mandatory integrity checks."""

    schema_version: Literal["aecbench.integrity-evaluation.v1"] = "aecbench.integrity-evaluation.v1"
    checks: tuple[IntegrityCheck, ...]
    passed: bool

    @field_validator("checks")
    @classmethod
    def canonicalize_checks(cls, value: tuple[IntegrityCheck, ...]) -> tuple[IntegrityCheck, ...]:
        if not value:
            raise ValueError("integrity evaluation requires at least one check")
        check_ids = tuple(check.check_id for check in value)
        if len(check_ids) != len(set(check_ids)):
            raise ValueError("integrity check identifiers must be unique")
        return tuple(sorted(value, key=lambda check: check.check_id))

    @model_validator(mode="after")
    def validate_passed(self) -> Self:
        if self.passed is not all(check.passed for check in self.checks):
            raise ValueError("integrity evaluation result must equal the conjunction of its checks")
        return self

    @classmethod
    def create(cls, *, checks: tuple[IntegrityCheck, ...]) -> IntegrityEvaluation:
        """Derive the aggregate result instead of trusting a caller-supplied flag."""
        return cls(checks=checks, passed=all(check.passed for check in checks))


class ValidityEvaluation(FrozenStrictModel):
    """Verifier completion and output-contract validity, evaluated before utility."""

    verifier_completed: bool
    output_parseable: bool
    schema_valid: bool
    output_contract_valid: bool
    valid: bool
    reasons: tuple[NonEmptyStr, ...] = ()

    @field_validator("reasons")
    @classmethod
    def canonicalize_reasons(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("validity reasons must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        expected = (
            self.verifier_completed and self.output_parseable and self.schema_valid and self.output_contract_valid
        )
        if self.valid is not expected:
            raise ValueError("validity result must equal all verifier and output-contract checks")
        if not self.valid and not self.reasons:
            raise ValueError("invalid evaluation requires at least one reason")
        return self


class UtilityEvaluation(FrozenStrictModel):
    """Task utility that may only be interpreted after integrity and validity pass."""

    normalized_utility: UnitFloat
    reward: UnitFloat
    solved: bool
    acceptance_threshold_met: bool

    @property
    def is_zero(self) -> bool:
        """Return whether this is the canonical zero-utility result."""
        return (
            self.normalized_utility == 0.0
            and self.reward == 0.0
            and not self.solved
            and not self.acceptance_threshold_met
        )

    @classmethod
    def zero(cls) -> UtilityEvaluation:
        """Return the only utility permitted for verifier-complete invalid output."""
        return cls(
            normalized_utility=0.0,
            reward=0.0,
            solved=False,
            acceptance_threshold_met=False,
        )


class CommonModeBasis(FrozenStrictModel):
    """Executable or human-audited truth used to identify a shared critic miss."""

    kind: CommonModeBasisKind
    basis_id: NonEmptyStr
    basis_sha256: str
    truth_gain: FiniteFloat

    @field_validator("basis_sha256")
    @classmethod
    def validate_basis_sha256(cls, value: str) -> str:
        return validate_sha256(value)


class SelectionNullEstimate(ContentAddressedModel):
    """Resampled differential null with a matched-aggregation envelope and estimator precision.

    ``interval_low`` and ``interval_high`` describe the empirical null
    distribution at the same aggregation unit as the treatment measurement.
    They are not a confidence interval around ``differential_estimate``.
    ``monte_carlo_standard_error`` separately records precision of that mean.
    """

    schema_version: Literal["aecbench.selection-null-estimate.v1"] = "aecbench.selection-null-estimate.v1"
    differential_estimate: FiniteFloat
    interval_low: FiniteFloat
    interval_high: FiniteFloat
    null_envelope_coverage: OpenUnitFloat = 0.95
    monte_carlo_standard_error: NonNegativeFiniteFloat
    resample_count: PositiveInt
    independent_selection_blocks: PositiveInt
    candidate_pool_width: PositiveInt
    evidence_sha256: str

    @field_validator("evidence_sha256")
    @classmethod
    def validate_evidence_sha256(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_uncertainty_interval(self) -> Self:
        if self.interval_low > self.interval_high:
            raise ValueError("selection-null interval_low must not exceed interval_high")
        if not self.interval_low <= self.differential_estimate <= self.interval_high:
            raise ValueError("selection-null estimate must fall within its uncertainty interval")
        if self.independent_selection_blocks > self.resample_count:
            raise ValueError("selection-null independent blocks cannot exceed resamples")
        return self


class CriticGapDecomposition(ContentAddressedModel):
    """Separate winner's-curse optimism, null-adjusted disagreement, and grounded breach.

    The null-adjusted residual is a detector, not evidence of a critic seam by
    itself. Common-mode breach remains unmeasured unless executable truth or
    human audit establishes a basis outside both critics.
    """

    schema_version: Literal["aecbench.critic-gap-decomposition.v1"] = "aecbench.critic-gap-decomposition.v1"
    selection_sample_development_gain: FiniteFloat
    fresh_sample_development_gain: FiniteFloat
    acceptance_gain: FiniteFloat
    null_estimate: SelectionNullEstimate
    raw_critic_gap: FiniteFloat
    selection_optimism: FiniteFloat
    fresh_differential_gap: FiniteFloat
    null_adjusted_residual: FiniteFloat
    common_mode_breach: NonNegativeFiniteFloat | None = None
    common_mode_basis: CommonModeBasis | None = None

    @model_validator(mode="after")
    def validate_decomposition(self) -> Self:
        expected_values = {
            "raw_critic_gap": self.selection_sample_development_gain - self.acceptance_gain,
            "selection_optimism": (self.selection_sample_development_gain - self.fresh_sample_development_gain),
            "fresh_differential_gap": self.fresh_sample_development_gain - self.acceptance_gain,
            "null_adjusted_residual": (
                self.fresh_sample_development_gain - self.acceptance_gain - self.null_estimate.differential_estimate
            ),
        }
        for field_name, expected in expected_values.items():
            actual = getattr(self, field_name)
            if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12):
                raise ValueError(f"{field_name} does not match the critic-gap decomposition")

        if self.common_mode_breach is not None and self.common_mode_basis is None:
            raise ValueError("common-mode breach requires an executable-anchor or human-audit basis")
        if self.common_mode_basis is not None and self.common_mode_breach is None:
            raise ValueError("common-mode basis requires a measured common-mode breach")
        if self.common_mode_basis is not None and self.common_mode_breach is not None:
            expected_breach = max(
                0.0,
                min(
                    self.fresh_sample_development_gain - self.common_mode_basis.truth_gain,
                    self.acceptance_gain - self.common_mode_basis.truth_gain,
                ),
            )
            if not math.isclose(
                self.common_mode_breach,
                expected_breach,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise ValueError("common_mode_breach does not match its independent truth basis")
        return self

    @classmethod
    def create(
        cls,
        *,
        selection_sample_development_gain: float,
        fresh_sample_development_gain: float,
        acceptance_gain: float,
        null_estimate: SelectionNullEstimate,
        common_mode_basis: CommonModeBasis | None = None,
    ) -> CriticGapDecomposition:
        """Derive every gap component from measured gains and an optional truth basis."""
        raw_critic_gap = selection_sample_development_gain - acceptance_gain
        selection_optimism = selection_sample_development_gain - fresh_sample_development_gain
        fresh_differential_gap = fresh_sample_development_gain - acceptance_gain
        null_adjusted_residual = fresh_differential_gap - null_estimate.differential_estimate
        common_mode_breach = (
            None
            if common_mode_basis is None
            else max(
                0.0,
                min(
                    fresh_sample_development_gain - common_mode_basis.truth_gain,
                    acceptance_gain - common_mode_basis.truth_gain,
                ),
            )
        )
        return cls(
            selection_sample_development_gain=selection_sample_development_gain,
            fresh_sample_development_gain=fresh_sample_development_gain,
            acceptance_gain=acceptance_gain,
            null_estimate=null_estimate,
            raw_critic_gap=raw_critic_gap,
            selection_optimism=selection_optimism,
            fresh_differential_gap=fresh_differential_gap,
            null_adjusted_residual=null_adjusted_residual,
            common_mode_breach=common_mode_breach,
            common_mode_basis=common_mode_basis,
        )


class ResourceCost(FrozenStrictModel):
    """Observed resource use for one named candidate or critic-plane activity."""

    provider_calls: NonNegativeInt
    tokens: NonNegativeInt
    provider_cost_usd: NonNegativeFiniteFloat
    wall_time_seconds: NonNegativeFiniteFloat


class CandidatePlaneCost(FrozenStrictModel):
    """Costs incurred to propose and execute candidates."""

    proposal: ResourceCost
    execution: ResourceCost

    @property
    def provider_cost_usd(self) -> float:
        """Return candidate-plane provider spend."""
        return self.proposal.provider_cost_usd + self.execution.provider_cost_usd


class CriticPlaneCost(FrozenStrictModel):
    """Costs incurred to judge, attack, monitor, and audit candidates."""

    development: ResourceCost
    acceptance: ResourceCost
    red_team: ResourceCost
    monitor: ResourceCost
    human_audit: ResourceCost

    @property
    def provider_cost_usd(self) -> float:
        """Return critic-plane provider spend without candidate execution spend."""
        return sum(
            cost.provider_cost_usd
            for cost in (
                self.development,
                self.acceptance,
                self.red_team,
                self.monitor,
                self.human_audit,
            )
        )


class EvaluationCostBreakdown(ContentAddressedModel):
    """Content-addressed accounting that never folds judging into candidate execution."""

    schema_version: Literal["aecbench.evaluation-cost-breakdown.v1"] = "aecbench.evaluation-cost-breakdown.v1"
    candidate: CandidatePlaneCost
    critic_plane: CriticPlaneCost

    @property
    def candidate_provider_cost_usd(self) -> float:
        """Return proposal and candidate-execution provider spend."""
        return self.candidate.provider_cost_usd

    @property
    def critic_plane_provider_cost_usd(self) -> float:
        """Return development, acceptance, red-team, monitor, and audit spend."""
        return self.critic_plane.provider_cost_usd

    @property
    def all_in_provider_cost_usd(self) -> float:
        """Return total provider spend while preserving its two source planes."""
        return self.candidate_provider_cost_usd + self.critic_plane_provider_cost_usd


class EvaluationOutcome(ContentAddressedModel):
    """One fail-closed, causally bound result from the ordered evaluation gate."""

    schema_version: Literal["aecbench.evaluation-outcome.v1"] = "aecbench.evaluation-outcome.v1"
    evaluation_plan_sha256: str
    candidate_sha256: str
    evidence_set_sha256: str
    integrity: IntegrityEvaluation
    validity: ValidityEvaluation | None = None
    utility: UtilityEvaluation | None = None
    critic_gap: CriticGapDecomposition | None = None
    costs: EvaluationCostBreakdown
    disposition: EvaluationDisposition
    promotion_eligible: bool
    reasons: tuple[NonEmptyStr, ...] = ()

    @field_validator(
        "evaluation_plan_sha256",
        "candidate_sha256",
        "evidence_set_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("reasons")
    @classmethod
    def canonicalize_reasons(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("evaluation outcome reasons must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def validate_lexicographic_gate(self) -> Self:
        if not self.integrity.passed:
            _validate_integrity_failure(self)
            return self

        if self.validity is None:
            raise ValueError("passed integrity requires validity evaluation")

        if not self.validity.verifier_completed:
            _validate_incomplete_verifier(self)
            return self

        if not self.validity.valid:
            _validate_invalid_output(self)
            return self

        _validate_valid_output(self)
        return self


_NONSCORING_DISPOSITIONS = frozenset(
    {
        EvaluationDisposition.ABSTAIN,
        EvaluationDisposition.EXPERIMENT_ERROR,
    }
)


def _validate_integrity_failure(outcome: EvaluationOutcome) -> None:
    if outcome.validity is not None or outcome.utility is not None or outcome.critic_gap is not None:
        raise ValueError("integrity failure blocks validity, utility, and critic scoring")
    if outcome.promotion_eligible:
        raise ValueError("integrity failure blocks promotion")
    if outcome.disposition not in _NONSCORING_DISPOSITIONS:
        raise ValueError("integrity failure requires abstain or experiment_error")


def _validate_incomplete_verifier(outcome: EvaluationOutcome) -> None:
    if outcome.utility is not None or outcome.critic_gap is not None:
        raise ValueError("incomplete verifier blocks utility and critic scoring")
    if outcome.promotion_eligible:
        raise ValueError("incomplete verifier blocks promotion")
    if outcome.disposition not in _NONSCORING_DISPOSITIONS:
        raise ValueError("incomplete verifier requires abstain or experiment_error")


def _validate_invalid_output(outcome: EvaluationOutcome) -> None:
    if outcome.utility is None or not outcome.utility.is_zero:
        raise ValueError("verifier-complete invalid output requires zero utility")
    if outcome.critic_gap is not None:
        raise ValueError("invalid output blocks critic-gap scoring")
    if outcome.promotion_eligible:
        raise ValueError("invalid output blocks promotion")
    if outcome.disposition is not EvaluationDisposition.REJECT:
        raise ValueError("verifier-complete invalid output must be rejected")


def _validate_valid_output(outcome: EvaluationOutcome) -> None:
    if outcome.utility is None:
        raise ValueError("valid output requires utility evaluation")
    if outcome.disposition is EvaluationDisposition.ACCEPT:
        if not outcome.utility.acceptance_threshold_met:
            raise ValueError("accepted outcome must meet its utility threshold")
        if not outcome.promotion_eligible:
            raise ValueError("accepted outcome must be promotion eligible")
    elif outcome.promotion_eligible:
        raise ValueError("only an accepted outcome may be promotion eligible")


class CriticEvaluationOutcome(ContentAddressedModel):
    """Critic-bound envelope around one legacy evaluation outcome.

    The legacy ``EvaluationOutcome`` remains loadable for historical evidence. New
    consequential decisions use this envelope so the producing critic, released
    generation, execution principal, kernel, and evaluation plan are explicit.
    """

    schema_version: Literal["aecbench.critic-evaluation-outcome.v1"] = "aecbench.critic-evaluation-outcome.v1"
    evaluation_plan_ref: EvaluationPlanRef
    critic: CriticRef
    execution_principal_id: NonEmptyStr
    critic_release_authority_event_id: NonEmptyStr
    critic_release_authority_event_sha256: str
    kernel_sha256: str
    outcome: EvaluationOutcome

    @field_validator(
        "critic_release_authority_event_sha256",
        "kernel_sha256",
    )
    @classmethod
    def validate_binding_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_critic_binding(self) -> Self:
        if self.outcome.evaluation_plan_sha256 != self.evaluation_plan_ref.content_sha256:
            raise ValueError("critic outcome does not bind the exact evaluation plan")
        if self.critic.compatibility_generation != self.evaluation_plan_ref.evaluation_generation:
            raise ValueError("critic outcome generation differs from the evaluation plan")
        return self
