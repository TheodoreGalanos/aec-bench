# ABOUTME: Tests post-mutation paired repair decisions for adaptive harness candidates.
# ABOUTME: Ensures only rerun child evidence on identical blocks can be accepted.

from __future__ import annotations

import hashlib
from typing import Literal

import pytest
from pydantic import ValidationError

from aec_bench.contracts.harness_kernel import KernelRef
from aec_bench.evolution.paired_repair import (
    PairedRepairAttempt,
    RepairAcceptancePolicy,
    RepairMutationScope,
    RepairTrialOutcome,
    decide_repair,
)


def test_positive_post_mutation_paired_improvement_is_accepted() -> None:
    attempt = _attempt(
        parent_rewards=(0.2, 0.4, 0.6),
        candidate_rewards=(0.5, 0.7, 0.8),
    )

    decision = decide_repair(
        attempt,
        RepairAcceptancePolicy(
            minimum_mean_reward_delta=0.1,
            require_positive_lower_bound=False,
        ),
    )

    assert decision.accepted is True
    assert decision.mean_reward_delta == pytest.approx(0.2666666667)
    assert decision.parent_candidate_id == "candidate.parent"
    assert decision.child_candidate_id == "candidate.child"
    assert decision.reasons == ()


def test_candidate_must_be_rerun_on_exact_parent_blocks() -> None:
    parent = _outcomes((0.2, 0.4), candidate_id="candidate.parent")
    candidate = list(_outcomes((0.5, 0.7), candidate_id="candidate.child"))
    candidate[-1] = candidate[-1].model_copy(update={"block_id": "block.other"})

    with pytest.raises(ValidationError, match="identical paired blocks"):
        PairedRepairAttempt(
            attempt_id="repair.1",
            iteration=1,
            mutation_scope=RepairMutationScope.PROGRAM,
            parent_candidate_id="candidate.parent",
            child_candidate_id="candidate.child",
            parent_outcomes=parent,
            child_outcomes=tuple(candidate),
        )


@pytest.mark.parametrize(
    ("candidate", "evidence_field", "expected_reason"),
    [
        ("parent", "complete", "parent_outcomes_incomplete"),
        ("parent", "valid", "parent_outcomes_invalid"),
        ("child", "complete", "child_outcomes_incomplete"),
        ("child", "valid", "child_outcomes_invalid"),
    ],
)
def test_repair_rejects_incomplete_or_invalid_evidence_from_either_candidate(
    candidate: Literal["parent", "child"],
    evidence_field: Literal["complete", "valid"],
    expected_reason: str,
) -> None:
    parent = list(_outcomes((0.2, 0.4), candidate_id="candidate.parent"))
    child = list(_outcomes((0.5, 0.7), candidate_id="candidate.child"))
    evidence = parent if candidate == "parent" else child
    evidence[0] = evidence[0].model_copy(update={evidence_field: False})

    decision = decide_repair(
        _attempt_with_evidence(parent=tuple(parent), child=tuple(child)),
        RepairAcceptancePolicy(require_positive_lower_bound=False),
    )

    assert decision.accepted is False
    assert decision.reasons == (expected_reason,)


def test_repair_rejection_reasons_have_stable_policy_order() -> None:
    parent = [
        outcome.model_copy(update={"complete": False, "valid": False, "cost": None})
        for outcome in _outcomes((0.8, 0.9), candidate_id="candidate.parent")
    ]
    child = [
        outcome.model_copy(
            update={
                "complete": False,
                "valid": False,
                "retention_score": 0.5,
                "interference_score": 0.4,
                "guard_reward": 0.1,
            }
        )
        for outcome in _outcomes((0.2, 0.3), candidate_id="candidate.child")
    ]

    decision = decide_repair(
        _attempt_with_evidence(
            parent=tuple(parent),
            child=tuple(child),
            iteration=4,
        ),
        RepairAcceptancePolicy(
            maximum_attempts=3,
            maximum_retention_regression=0.1,
            maximum_interference_increase=0.1,
            maximum_guard_reward_regression=0.1,
        ),
    )

    assert decision.accepted is False
    assert decision.reasons == (
        "cost_evidence_incomplete",
        "maximum_attempts_exceeded",
        "parent_outcomes_incomplete",
        "parent_outcomes_invalid",
        "child_outcomes_incomplete",
        "child_outcomes_invalid",
        "minimum_reward_delta_not_met",
        "reward_delta_lower_bound_not_positive",
        "retention_regression_exceeded",
        "interference_increase_exceeded",
        "guard_reward_regression_exceeded",
    )


def test_repair_rejects_kernel_drifted_evidence() -> None:
    drifted = list(_outcomes((0.5, 0.7), candidate_id="candidate.child"))
    drifted[0] = drifted[0].model_copy(update={"kernel_ref": KernelRef(kernel_id="other-kernel", version="1.0.0")})

    with pytest.raises(ValidationError, match="kernel"):
        _attempt_with_evidence(child=tuple(drifted))


def test_repair_enforces_cost_retention_interference_and_guard_limits() -> None:
    parent = _outcomes((0.3, 0.4), candidate_id="candidate.parent", cost=1.0)
    child = _outcomes(
        (0.8, 0.9),
        candidate_id="candidate.child",
        cost=2.0,
        retention=0.5,
        interference=0.4,
        guard_reward=0.1,
    )
    attempt = PairedRepairAttempt(
        attempt_id="repair.1",
        iteration=1,
        mutation_scope=RepairMutationScope.JOINT,
        parent_candidate_id="candidate.parent",
        child_candidate_id="candidate.child",
        parent_outcomes=parent,
        child_outcomes=child,
    )

    decision = decide_repair(
        attempt,
        RepairAcceptancePolicy(
            require_positive_lower_bound=False,
            maximum_cost_ratio=1.25,
            maximum_retention_regression=0.1,
            maximum_interference_increase=0.1,
            maximum_guard_reward_regression=0.1,
        ),
    )

    assert decision.accepted is False
    assert decision.reasons == (
        "cost_ratio_exceeded",
        "retention_regression_exceeded",
        "interference_increase_exceeded",
        "guard_reward_regression_exceeded",
    )


def test_unknown_cost_evidence_is_preserved_and_rejects_repair() -> None:
    parent = _outcomes((0.2, 0.4), candidate_id="candidate.parent", cost=None)
    child = _outcomes((0.8, 0.9), candidate_id="candidate.child", cost=2.0)
    attempt = PairedRepairAttempt(
        attempt_id="repair.unknown-cost",
        iteration=1,
        mutation_scope=RepairMutationScope.PROGRAM,
        parent_candidate_id="candidate.parent",
        child_candidate_id="candidate.child",
        parent_outcomes=parent,
        child_outcomes=child,
    )

    decision = decide_repair(
        attempt,
        RepairAcceptancePolicy(require_positive_lower_bound=False),
    )

    assert decision.accepted is False
    assert "cost_evidence_incomplete" in decision.reasons
    assert decision.parent_mean_cost is None
    assert decision.child_mean_cost == pytest.approx(2.0)
    assert decision.cost_ratio is None


def test_holdout_evidence_and_excess_repair_attempts_are_rejected() -> None:
    holdout = _outcome(
        block_id="block.1",
        candidate_id="candidate.parent",
        reward=0.2,
        split="holdout",
    )
    with pytest.raises(ValidationError, match="holdout"):
        PairedRepairAttempt(
            attempt_id="repair.1",
            iteration=1,
            mutation_scope=RepairMutationScope.HARNESS,
            parent_candidate_id="candidate.parent",
            child_candidate_id="candidate.child",
            parent_outcomes=(holdout,),
            child_outcomes=(holdout.model_copy(update={"candidate_id": "candidate.child", "reward": 0.8}),),
        )

    decision = decide_repair(
        _attempt(iteration=4),
        RepairAcceptancePolicy(maximum_attempts=3, require_positive_lower_bound=False),
    )
    assert decision.accepted is False
    assert decision.reasons == ("maximum_attempts_exceeded",)


def test_existing_policy_preregisters_cost_efficiency_with_reward_non_inferiority() -> None:
    attempt = PairedRepairAttempt(
        attempt_id="repair.cost-noninferiority",
        iteration=1,
        mutation_scope=RepairMutationScope.HARNESS,
        parent_candidate_id="candidate.parent",
        child_candidate_id="candidate.child",
        parent_outcomes=_outcomes((0.80, 0.82), candidate_id="candidate.parent", cost=2.0),
        child_outcomes=_outcomes((0.79, 0.80), candidate_id="candidate.child", cost=1.0),
    )

    decision = decide_repair(
        attempt,
        RepairAcceptancePolicy(
            minimum_mean_reward_delta=-0.02,
            require_positive_lower_bound=False,
            maximum_cost_ratio=0.75,
        ),
    )

    assert decision.accepted is True
    assert decision.mean_reward_delta == pytest.approx(-0.015)
    assert decision.cost_ratio == pytest.approx(0.5)


def _attempt(
    *,
    parent_rewards: tuple[float, ...] = (0.2, 0.4),
    candidate_rewards: tuple[float, ...] = (0.5, 0.7),
    iteration: int = 1,
) -> PairedRepairAttempt:
    return PairedRepairAttempt(
        attempt_id=f"repair.{iteration}",
        iteration=iteration,
        mutation_scope=RepairMutationScope.PROGRAM,
        parent_candidate_id="candidate.parent",
        child_candidate_id="candidate.child",
        parent_outcomes=_outcomes(parent_rewards, candidate_id="candidate.parent"),
        child_outcomes=_outcomes(candidate_rewards, candidate_id="candidate.child"),
    )


def _attempt_with_evidence(
    *,
    parent: tuple[RepairTrialOutcome, ...] | None = None,
    child: tuple[RepairTrialOutcome, ...] | None = None,
    iteration: int = 1,
) -> PairedRepairAttempt:
    return PairedRepairAttempt(
        attempt_id=f"repair.{iteration}",
        iteration=iteration,
        mutation_scope=RepairMutationScope.PROGRAM,
        parent_candidate_id="candidate.parent",
        child_candidate_id="candidate.child",
        parent_outcomes=parent or _outcomes((0.2, 0.4), candidate_id="candidate.parent"),
        child_outcomes=child or _outcomes((0.5, 0.7), candidate_id="candidate.child"),
    )


def _outcomes(
    rewards: tuple[float, ...],
    *,
    candidate_id: str,
    cost: float | None = 1.0,
    retention: float = 1.0,
    interference: float = 0.0,
    guard_reward: float = 0.8,
) -> tuple[RepairTrialOutcome, ...]:
    return tuple(
        _outcome(
            block_id=f"block.{index}",
            candidate_id=candidate_id,
            reward=reward,
            cost=cost,
            retention=retention,
            interference=interference,
            guard_reward=guard_reward,
        )
        for index, reward in enumerate(rewards, start=1)
    )


def _outcome(
    *,
    block_id: str,
    candidate_id: str,
    reward: float,
    split: Literal["discovery", "repair_gate", "calibration", "holdout"] = "repair_gate",
    cost: float | None = 1.0,
    retention: float = 1.0,
    interference: float = 0.0,
    guard_reward: float = 0.8,
) -> RepairTrialOutcome:
    return RepairTrialOutcome(
        block_id=block_id,
        task_world_id=f"world.{block_id}",
        repetition=1,
        split=split,
        candidate_id=candidate_id,
        kernel_ref=KernelRef(kernel_id="kernel", version="1.0.0"),
        resource_sha256=_sha("resource"),
        review_lineage_sha256=_sha(f"review:{block_id}"),
        reward=reward,
        complete=True,
        valid=True,
        cost=cost,
        retention_score=retention,
        interference_score=interference,
        guard_reward=guard_reward,
    )


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()
