# ABOUTME: Owns motif lifecycle policy, deterministic promotion decisions, and replay.
# ABOUTME: Keeps evidence gates independent from motif persistence and structural selection.

from __future__ import annotations

from typing import Any

from pydantic import FiniteFloat, PositiveInt, field_validator, model_validator

from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.meta_harness.motifs.contracts import (
    HarnessProgramMotif,
    MotifStatus,
    NonNegativeFiniteFloat,
    UnitFloat,
    _canonical_sha256,
    _validate_bound_hash,
    _validate_sha256,
)


class MotifPromotionPolicy(FrozenStrictModel):
    """Evidence thresholds for advancing motifs through the reusable lifecycle."""

    minimum_supporting_world_lineages: PositiveInt = 2
    minimum_calibration_world_lineages: PositiveInt = 2
    minimum_objective_reward: UnitFloat = 0.0
    minimum_validity_rate: UnitFloat = 1.0
    minimum_joint_uplift: FiniteFloat = 0.0
    minimum_joint_incremental_uplift: FiniteFloat = 0.0
    minimum_joint_incremental_uplift_lower_bound: FiniteFloat = 0.0
    maximum_estimated_cost_usd: NonNegativeFiniteFloat | None = None
    minimum_transfer_world_lineages: PositiveInt = 2
    minimum_transfer_objective_reward: UnitFloat = 0.0
    minimum_transfer_validity_rate: UnitFloat = 1.0
    minimum_transfer_joint_uplift: FiniteFloat = 0.0
    minimum_transfer_joint_incremental_uplift: FiniteFloat = 0.0
    minimum_transfer_joint_incremental_uplift_lower_bound: FiniteFloat = 0.0
    maximum_transfer_estimated_cost_usd: NonNegativeFiniteFloat | None = None


class MotifPromotionDecision(FrozenStrictModel):
    """Content-addressed pure decision over one motif record and requested lifecycle edge."""

    decision_sha256: NonEmptyStr
    motif_sha256: NonEmptyStr
    current_status: MotifStatus
    target_status: MotifStatus
    accepted: bool
    reasons: tuple[NonEmptyStr, ...]

    @field_validator("decision_sha256", "motif_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return _validate_sha256(value)

    @model_validator(mode="after")
    def validate_identity(self) -> MotifPromotionDecision:
        _validate_bound_hash(self, "decision_sha256")
        if self.accepted == bool(self.reasons):
            raise ValueError(
                "accepted promotion decisions must have no reasons and rejected decisions must have reasons"
            )
        return self

    @classmethod
    def create(
        cls,
        *,
        motif_sha256: str,
        current_status: MotifStatus,
        target_status: MotifStatus,
        reasons: tuple[str, ...],
    ) -> MotifPromotionDecision:
        payload: dict[str, Any] = {
            "motif_sha256": motif_sha256,
            "current_status": current_status.value,
            "target_status": target_status.value,
            "accepted": not reasons,
            "reasons": reasons,
        }
        return cls(decision_sha256=_canonical_sha256(payload), **payload)


def decide_motif_promotion(
    motif: HarnessProgramMotif,
    target_status: MotifStatus | str,
    policy: MotifPromotionPolicy,
) -> MotifPromotionDecision:
    """Return a deterministic, side-effect-free promotion decision for one lifecycle edge."""

    target = MotifStatus(target_status)
    allowed_target = {
        MotifStatus.CANDIDATE: MotifStatus.PROVISIONAL,
        MotifStatus.PROVISIONAL: MotifStatus.REUSABLE,
        MotifStatus.REUSABLE: MotifStatus.TRANSFER_VALIDATED,
        MotifStatus.TRANSFER_VALIDATED: None,
        MotifStatus.RETIRED: None,
    }[motif.status]

    if target is MotifStatus.RETIRED and motif.status is not MotifStatus.RETIRED:
        reasons: list[str] = []
    elif target is not allowed_target:
        reasons = ["invalid_status_transition"]
    elif target is MotifStatus.PROVISIONAL:
        reasons = _provisional_reasons(motif)
    elif target is MotifStatus.REUSABLE:
        reasons = _reusable_reasons(motif, policy)
    elif target is MotifStatus.TRANSFER_VALIDATED:
        reasons = _transfer_reasons(motif, policy)
    else:
        reasons = ["invalid_status_transition"]

    return MotifPromotionDecision.create(
        motif_sha256=motif.motif_sha256,
        current_status=motif.status,
        target_status=target,
        reasons=tuple(reasons),
    )


def apply_motif_promotion(
    motif: HarnessProgramMotif,
    decision: MotifPromotionDecision,
    policy: MotifPromotionPolicy,
) -> HarnessProgramMotif:
    """Apply only non-authoritative lifecycle edges after rechecking the pure decision."""

    _validate_motif_promotion_application(motif, decision, policy)
    if decision.target_status in {
        MotifStatus.REUSABLE,
        MotifStatus.TRANSFER_VALIDATED,
    }:
        raise ValueError(f"governed motif promotion is required for {decision.target_status.value} status")
    return _create_promoted_motif(motif, decision)


def apply_authorized_motif_promotion(
    motif: HarnessProgramMotif,
    decision: MotifPromotionDecision,
    policy: MotifPromotionPolicy,
) -> HarnessProgramMotif:
    """Create a protected status edge after the caller has verified durable authority."""

    _validate_motif_promotion_application(motif, decision, policy)
    return _create_promoted_motif(motif, decision)


def _validate_motif_promotion_application(
    motif: HarnessProgramMotif,
    decision: MotifPromotionDecision,
    policy: MotifPromotionPolicy,
) -> None:
    """Recompute and validate one immutable promotion decision before any record is created."""

    if not decision.accepted:
        raise ValueError("cannot apply a rejected motif promotion decision")
    if decision.motif_sha256 != motif.motif_sha256 or decision.current_status is not motif.status:
        raise ValueError("motif promotion decision does not bind the supplied motif record")
    expected = decide_motif_promotion(motif, decision.target_status, policy)
    if decision != expected:
        raise ValueError("motif promotion decision does not match the current evidence gate")


def _create_promoted_motif(
    motif: HarnessProgramMotif,
    decision: MotifPromotionDecision,
) -> HarnessProgramMotif:
    """Create the immutable child record after the caller has enforced its authority boundary."""

    return HarnessProgramMotif.create(
        status=decision.target_status,
        kernel_abi_sha256=motif.kernel_abi_sha256,
        hx_template=motif.hx_template,
        px_template=motif.px_template,
        applicability=motif.applicability,
        descriptor=motif.descriptor,
        accepted_repair_refs=motif.accepted_repair_refs,
        factorial_evidence_refs=motif.factorial_evidence_refs,
        quality_evidence_refs=motif.quality_evidence_refs,
        transfer_evidence_refs=motif.transfer_evidence_refs,
        parent_motif_sha256=motif.motif_sha256,
    )


def _provisional_reasons(motif: HarnessProgramMotif) -> list[str]:
    reasons: list[str] = []
    if not motif.accepted_repair_refs:
        reasons.append("accepted_repair_evidence_required")
    if not motif.quality_evidence_refs:
        reasons.append("calibration_quality_evidence_required")
    return reasons


def _reusable_reasons(motif: HarnessProgramMotif, policy: MotifPromotionPolicy) -> list[str]:
    reasons = _provisional_reasons(motif)
    reasons.extend(_reusable_evidence_reasons(motif, policy))
    reasons.extend(_reusable_threshold_reasons(motif, policy))
    return reasons


def _reusable_evidence_reasons(
    motif: HarnessProgramMotif,
    policy: MotifPromotionPolicy,
) -> list[str]:
    reasons: list[str] = []
    if len(motif.supporting_world_lineage_ids) < policy.minimum_supporting_world_lineages:
        reasons.append("insufficient_distinct_world_lineages")
    if any(reference.split != "calibration" for reference in motif.factorial_evidence_refs):
        reasons.append("factorial_evidence_must_use_calibration_split")
    if any(reference.split != "calibration" for reference in motif.quality_evidence_refs):
        reasons.append("quality_evidence_must_use_calibration_split")
    calibration_lineages = {
        lineage
        for reference in motif.factorial_evidence_refs
        if reference.split == "calibration"
        for lineage in reference.world_lineage_ids
    }
    calibration_lineages.update(
        lineage
        for reference in motif.quality_evidence_refs
        if reference.split == "calibration"
        for lineage in reference.world_lineage_ids
    )
    if len(calibration_lineages) < policy.minimum_calibration_world_lineages:
        reasons.append("insufficient_distinct_calibration_world_lineages")
    if not motif.factorial_evidence_refs:
        reasons.append("factorial_evidence_required")
    elif min(float(reference.joint_uplift) for reference in motif.factorial_evidence_refs) < float(
        policy.minimum_joint_uplift
    ):
        reasons.append("minimum_joint_uplift_not_met")
    return reasons


def _reusable_threshold_reasons(
    motif: HarnessProgramMotif,
    policy: MotifPromotionPolicy,
) -> list[str]:
    reasons: list[str] = []
    if motif.factorial_evidence_refs and min(
        float(reference.joint_incremental_uplift) for reference in motif.factorial_evidence_refs
    ) < float(policy.minimum_joint_incremental_uplift):
        reasons.append("minimum_joint_incremental_uplift_not_met")
    if motif.factorial_evidence_refs and min(
        float(reference.joint_incremental_uplift_lower_bound) for reference in motif.factorial_evidence_refs
    ) < float(policy.minimum_joint_incremental_uplift_lower_bound):
        reasons.append("minimum_joint_incremental_uplift_lower_bound_not_met")
    if motif.objective_reward is not None and motif.objective_reward < float(policy.minimum_objective_reward):
        reasons.append("minimum_objective_reward_not_met")
    if motif.validity_rate is not None and motif.validity_rate < float(policy.minimum_validity_rate):
        reasons.append("minimum_validity_rate_not_met")
    if policy.maximum_estimated_cost_usd is not None and motif.estimated_cost_usd > float(
        policy.maximum_estimated_cost_usd
    ):
        reasons.append("maximum_estimated_cost_usd_exceeded")
    return reasons


def _transfer_reasons(motif: HarnessProgramMotif, policy: MotifPromotionPolicy) -> list[str]:
    references = motif.transfer_evidence_refs
    if not references:
        return ["transfer_evidence_required"]

    reasons = _transfer_integrity_reasons(motif, policy)
    reasons.extend(_transfer_threshold_reasons(motif, policy))
    return reasons


def _transfer_integrity_reasons(
    motif: HarnessProgramMotif,
    policy: MotifPromotionPolicy,
) -> list[str]:
    references = motif.transfer_evidence_refs
    reasons: list[str] = []
    lineages = {lineage for reference in references for lineage in reference.world_lineage_ids}
    if lineages.intersection(motif.supporting_world_lineage_ids):
        reasons.append("holdout_world_lineage_seen_during_selection")
    if len(lineages) < policy.minimum_transfer_world_lineages:
        reasons.append("insufficient_transfer_world_lineages")
    if any(not reference.selected_before_holdout for reference in references):
        reasons.append("holdout_selection_leakage")
    if any(not reference.archive_frozen for reference in references):
        reasons.append("holdout_archive_not_frozen")
    return reasons


def _transfer_threshold_reasons(
    motif: HarnessProgramMotif,
    policy: MotifPromotionPolicy,
) -> list[str]:
    references = motif.transfer_evidence_refs
    reasons: list[str] = []
    if min(float(reference.objective_reward) for reference in references) < float(
        policy.minimum_transfer_objective_reward
    ):
        reasons.append("minimum_transfer_objective_reward_not_met")
    if min(float(reference.validity_rate) for reference in references) < float(policy.minimum_transfer_validity_rate):
        reasons.append("minimum_transfer_validity_rate_not_met")
    if min(float(reference.joint_uplift) for reference in references) < float(policy.minimum_transfer_joint_uplift):
        reasons.append("minimum_transfer_joint_uplift_not_met")
    if min(float(reference.joint_incremental_uplift) for reference in references) < float(
        policy.minimum_transfer_joint_incremental_uplift
    ):
        reasons.append("minimum_transfer_joint_incremental_uplift_not_met")
    if min(float(reference.joint_incremental_uplift_lower_bound) for reference in references) < float(
        policy.minimum_transfer_joint_incremental_uplift_lower_bound
    ):
        reasons.append("minimum_transfer_joint_incremental_uplift_lower_bound_not_met")
    transfer_cost = sum(float(reference.estimated_cost_usd) for reference in references)
    if policy.maximum_transfer_estimated_cost_usd is not None and transfer_cost > float(
        policy.maximum_transfer_estimated_cost_usd
    ):
        reasons.append("maximum_transfer_estimated_cost_usd_exceeded")
    return reasons
