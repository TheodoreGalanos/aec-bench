# ABOUTME: Defines verifier-guided paired repair evidence and acceptance decisions.
# ABOUTME: Gates post-mutation candidates against identical parent task blocks and runtime identities.

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import StrEnum
from statistics import mean
from typing import Literal

from pydantic import Field, NonNegativeFloat, PositiveInt, field_validator, model_validator

from aec_bench.contracts.harness_kernel import KernelRef
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.contracts.validators import NonEmptyStr, StrictModel


class RepairMutationScope(StrEnum):
    HARNESS = "harness"
    PROGRAM = "program"
    JOINT = "joint"


class RepairTrialOutcome(StrictModel):
    block_id: NonEmptyStr
    task_world_id: NonEmptyStr
    repetition: PositiveInt
    split: Literal["discovery", "repair_gate", "calibration", "holdout"]
    candidate_id: NonEmptyStr
    kernel_ref: KernelRef
    resource_sha256: NonEmptyStr
    review_lineage_sha256: NonEmptyStr
    reward: float
    complete: bool
    valid: bool
    cost: NonNegativeFloat | None = None
    retention_score: float = Field(default=1.0, ge=0.0, le=1.0)
    interference_score: float = Field(default=0.0, ge=0.0, le=1.0)
    guard_reward: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("resource_sha256", "review_lineage_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)

    @field_validator("reward")
    @classmethod
    def validate_finite_reward(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("reward must be finite")
        return value


class PairedRepairAttempt(StrictModel):
    attempt_id: NonEmptyStr
    iteration: PositiveInt
    mutation_scope: RepairMutationScope
    parent_candidate_id: NonEmptyStr
    child_candidate_id: NonEmptyStr
    parent_outcomes: tuple[RepairTrialOutcome, ...] = Field(min_length=1)
    child_outcomes: tuple[RepairTrialOutcome, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_paired_evidence(self) -> PairedRepairAttempt:
        _validate_candidate_bindings(self)
        _validate_repair_splits(self)
        for parent, child in _paired_outcomes(self):
            _validate_block_identity(parent, child)
            _validate_kernel_identity(parent, child)
            _validate_resource_identity(parent, child)
            _validate_review_lineage_identity(parent, child)
        return self


class RepairAcceptancePolicy(StrictModel):
    minimum_mean_reward_delta: float = 0.0
    require_positive_lower_bound: bool = True
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    bootstrap_replicates: PositiveInt = 1_000
    bootstrap_seed: int = 0
    maximum_cost_ratio: float | None = Field(default=None, ge=0.0)
    maximum_retention_regression: float = Field(default=0.0, ge=0.0)
    maximum_interference_increase: float = Field(default=0.0, ge=0.0)
    maximum_guard_reward_regression: float = Field(default=0.0, ge=0.0)
    require_all_complete_and_valid: bool = True
    maximum_attempts: PositiveInt = 3


class RepairDecision(StrictModel):
    attempt_id: NonEmptyStr
    parent_candidate_id: NonEmptyStr
    child_candidate_id: NonEmptyStr
    accepted: bool
    reasons: tuple[NonEmptyStr, ...]
    paired_block_count: PositiveInt
    parent_mean_reward: float
    child_mean_reward: float
    mean_reward_delta: float
    reward_delta_lower_bound: float
    parent_mean_cost: NonNegativeFloat | None
    child_mean_cost: NonNegativeFloat | None
    cost_ratio: NonNegativeFloat | None
    retention_regression: float
    interference_increase: float
    guard_reward_regression: float


@dataclass(frozen=True, slots=True)
class _RepairMetrics:
    paired_block_count: int
    parent_mean_reward: float
    child_mean_reward: float
    mean_reward_delta: float
    reward_delta_lower_bound: float
    parent_mean_cost: float | None
    child_mean_cost: float | None
    cost_ratio: float | None
    parent_outcomes_complete: bool
    parent_outcomes_valid: bool
    child_outcomes_complete: bool
    child_outcomes_valid: bool
    retention_regression: float
    interference_increase: float
    guard_reward_regression: float

    @property
    def cost_evidence_complete(self) -> bool:
        return self.parent_mean_cost is not None and self.child_mean_cost is not None


def decide_repair(attempt: PairedRepairAttempt, policy: RepairAcceptancePolicy) -> RepairDecision:
    metrics = _repair_metrics(attempt, policy)
    reasons = _repair_rejection_reasons(attempt, policy, metrics)
    return RepairDecision(
        attempt_id=attempt.attempt_id,
        parent_candidate_id=attempt.parent_candidate_id,
        child_candidate_id=attempt.child_candidate_id,
        accepted=not reasons,
        reasons=reasons,
        paired_block_count=metrics.paired_block_count,
        parent_mean_reward=metrics.parent_mean_reward,
        child_mean_reward=metrics.child_mean_reward,
        mean_reward_delta=metrics.mean_reward_delta,
        reward_delta_lower_bound=metrics.reward_delta_lower_bound,
        parent_mean_cost=metrics.parent_mean_cost,
        child_mean_cost=metrics.child_mean_cost,
        cost_ratio=metrics.cost_ratio,
        retention_regression=metrics.retention_regression,
        interference_increase=metrics.interference_increase,
        guard_reward_regression=metrics.guard_reward_regression,
    )


def _repair_metrics(attempt: PairedRepairAttempt, policy: RepairAcceptancePolicy) -> _RepairMetrics:
    parent_by_block = _outcomes_by_block(attempt.parent_outcomes)
    child_by_block = _outcomes_by_block(attempt.child_outcomes)
    block_ids = sorted(parent_by_block)
    parent = [parent_by_block[block_id] for block_id in block_ids]
    child = [child_by_block[block_id] for block_id in block_ids]
    deltas = [child_item.reward - parent_item.reward for parent_item, child_item in zip(parent, child, strict=True)]

    parent_reward = mean(item.reward for item in parent)
    child_reward = mean(item.reward for item in child)
    reward_delta = mean(deltas)
    lower_bound = _bootstrap_lower_bound(
        deltas,
        confidence_level=policy.confidence_level,
        replicates=policy.bootstrap_replicates,
        seed=policy.bootstrap_seed,
    )
    parent_cost = _mean_complete_cost(parent)
    child_cost = _mean_complete_cost(child)
    cost_ratio = _cost_ratio(parent_cost, child_cost) if parent_cost is not None and child_cost is not None else None
    retention_regression = mean(item.retention_score for item in parent) - mean(item.retention_score for item in child)
    interference_increase = mean(item.interference_score for item in child) - mean(
        item.interference_score for item in parent
    )
    guard_regression = mean(item.guard_reward for item in parent) - mean(item.guard_reward for item in child)

    return _RepairMetrics(
        paired_block_count=len(block_ids),
        parent_mean_reward=parent_reward,
        child_mean_reward=child_reward,
        mean_reward_delta=reward_delta,
        reward_delta_lower_bound=lower_bound,
        parent_mean_cost=parent_cost,
        child_mean_cost=child_cost,
        cost_ratio=cost_ratio,
        parent_outcomes_complete=all(item.complete for item in parent),
        parent_outcomes_valid=all(item.valid for item in parent),
        child_outcomes_complete=all(item.complete for item in child),
        child_outcomes_valid=all(item.valid for item in child),
        retention_regression=retention_regression,
        interference_increase=interference_increase,
        guard_reward_regression=guard_regression,
    )


def _repair_rejection_reasons(
    attempt: PairedRepairAttempt,
    policy: RepairAcceptancePolicy,
    metrics: _RepairMetrics,
) -> tuple[str, ...]:
    return (
        *_admission_reasons(attempt, policy, metrics),
        *_performance_reasons(policy, metrics),
        *_safety_reasons(policy, metrics),
    )


def _admission_reasons(
    attempt: PairedRepairAttempt,
    policy: RepairAcceptancePolicy,
    metrics: _RepairMetrics,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not metrics.cost_evidence_complete:
        reasons.append("cost_evidence_incomplete")
    if attempt.iteration > policy.maximum_attempts:
        reasons.append("maximum_attempts_exceeded")
    if policy.require_all_complete_and_valid:
        reasons.extend(_evidence_quality_reasons(metrics))
    return tuple(reasons)


def _evidence_quality_reasons(metrics: _RepairMetrics) -> tuple[str, ...]:
    reasons: list[str] = []
    if not metrics.parent_outcomes_complete:
        reasons.append("parent_outcomes_incomplete")
    if not metrics.parent_outcomes_valid:
        reasons.append("parent_outcomes_invalid")
    if not metrics.child_outcomes_complete:
        reasons.append("child_outcomes_incomplete")
    if not metrics.child_outcomes_valid:
        reasons.append("child_outcomes_invalid")
    return tuple(reasons)


def _performance_reasons(policy: RepairAcceptancePolicy, metrics: _RepairMetrics) -> tuple[str, ...]:
    reasons: list[str] = []
    if metrics.mean_reward_delta < policy.minimum_mean_reward_delta:
        reasons.append("minimum_reward_delta_not_met")
    if policy.require_positive_lower_bound and metrics.reward_delta_lower_bound <= 0.0:
        reasons.append("reward_delta_lower_bound_not_positive")
    if (
        policy.maximum_cost_ratio is not None
        and metrics.cost_ratio is not None
        and metrics.cost_ratio > policy.maximum_cost_ratio
    ):
        reasons.append("cost_ratio_exceeded")
    return tuple(reasons)


def _safety_reasons(policy: RepairAcceptancePolicy, metrics: _RepairMetrics) -> tuple[str, ...]:
    reasons: list[str] = []
    if metrics.retention_regression > policy.maximum_retention_regression:
        reasons.append("retention_regression_exceeded")
    if metrics.interference_increase > policy.maximum_interference_increase:
        reasons.append("interference_increase_exceeded")
    if metrics.guard_reward_regression > policy.maximum_guard_reward_regression:
        reasons.append("guard_reward_regression_exceeded")
    return tuple(reasons)


def _validate_candidate_bindings(attempt: PairedRepairAttempt) -> None:
    if attempt.parent_candidate_id == attempt.child_candidate_id:
        raise ValueError("repair child candidate must differ from its parent")
    if any(outcome.candidate_id != attempt.parent_candidate_id for outcome in attempt.parent_outcomes):
        raise ValueError("parent outcomes must identify the parent candidate")
    if any(outcome.candidate_id != attempt.child_candidate_id for outcome in attempt.child_outcomes):
        raise ValueError("child outcomes must identify the child candidate")


def _validate_repair_splits(attempt: PairedRepairAttempt) -> None:
    if any(outcome.split == "holdout" for outcome in (*attempt.parent_outcomes, *attempt.child_outcomes)):
        raise ValueError("holdout evidence cannot participate in repair")


def _paired_outcomes(
    attempt: PairedRepairAttempt,
) -> tuple[tuple[RepairTrialOutcome, RepairTrialOutcome], ...]:
    parent_by_block = _outcomes_by_block(attempt.parent_outcomes)
    child_by_block = _outcomes_by_block(attempt.child_outcomes)
    if parent_by_block.keys() != child_by_block.keys():
        raise ValueError("parent and child must run on identical paired blocks")
    return tuple((parent_by_block[block_id], child_by_block[block_id]) for block_id in sorted(parent_by_block))


def _validate_block_identity(parent: RepairTrialOutcome, child: RepairTrialOutcome) -> None:
    if (parent.task_world_id, parent.repetition, parent.split) != (
        child.task_world_id,
        child.repetition,
        child.split,
    ):
        raise ValueError("parent and child must run on identical paired blocks")


def _validate_kernel_identity(parent: RepairTrialOutcome, child: RepairTrialOutcome) -> None:
    if parent.kernel_ref != child.kernel_ref:
        raise ValueError("parent and child kernel identities must match")


def _validate_resource_identity(parent: RepairTrialOutcome, child: RepairTrialOutcome) -> None:
    if parent.resource_sha256 != child.resource_sha256:
        raise ValueError("parent and child resource identities must match")


def _validate_review_lineage_identity(parent: RepairTrialOutcome, child: RepairTrialOutcome) -> None:
    if parent.review_lineage_sha256 != child.review_lineage_sha256:
        raise ValueError("parent and child review lineage identities must match")


def _outcomes_by_block(outcomes: tuple[RepairTrialOutcome, ...]) -> dict[str, RepairTrialOutcome]:
    by_block = {outcome.block_id: outcome for outcome in outcomes}
    if len(by_block) != len(outcomes):
        raise ValueError("repair outcomes must contain unique paired blocks")
    return by_block


def _bootstrap_lower_bound(
    deltas: list[float],
    *,
    confidence_level: float,
    replicates: int,
    seed: int,
) -> float:
    if len(deltas) == 1:
        return deltas[0]
    rng = random.Random(seed)
    estimates = sorted(mean(rng.choice(deltas) for _ in deltas) for _ in range(replicates))
    alpha = 1.0 - confidence_level
    index = max(0, min(len(estimates) - 1, int((alpha / 2.0) * len(estimates))))
    return estimates[index]


def _cost_ratio(parent_cost: float, child_cost: float) -> float:
    if parent_cost == 0.0:
        return 0.0 if child_cost == 0.0 else math.inf
    return child_cost / parent_cost


def _mean_complete_cost(outcomes: list[RepairTrialOutcome]) -> float | None:
    costs = [float(item.cost) for item in outcomes if item.cost is not None]
    return mean(costs) if len(costs) == len(outcomes) else None
