# ABOUTME: Tests exact factorial contrasts and deterministic world-clustered uncertainty intervals.
# ABOUTME: Ensures analysis fails closed on incomplete, duplicated, or unplanned trial outcomes.

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from aec_bench.meta_harness.factorial_analysis import FactorialOutcome, analyse_factorial
from aec_bench.meta_harness.factorial_plan import (
    FactorialCandidateReference,
    FactorialCandidateSet,
    FactorialCell,
    FactorialPlan,
    FactorialStudyManifest,
    build_factorial_plan,
)


def test_analysis_computes_exact_main_effects_interaction_and_joint_contrasts() -> None:
    plan = _plan(worlds=("world.alpha", "world.beta"), repetitions=1)
    outcomes = _constant_cell_outcomes(
        plan,
        {
            FactorialCell.H0_P0: 0.2,
            FactorialCell.HX_P0: 0.4,
            FactorialCell.H0_PX: 0.5,
            FactorialCell.HX_PX: 0.9,
        },
    )

    analysis = analyse_factorial(plan, outcomes, bootstrap_replicates=200, bootstrap_seed=19)

    assert analysis.cell_means == {
        FactorialCell.H0_P0: pytest.approx(0.2),
        FactorialCell.HX_P0: pytest.approx(0.4),
        FactorialCell.H0_PX: pytest.approx(0.5),
        FactorialCell.HX_PX: pytest.approx(0.9),
    }
    assert analysis.harness_main_effect.estimate == pytest.approx(0.3)
    assert analysis.program_main_effect.estimate == pytest.approx(0.4)
    assert analysis.interaction.estimate == pytest.approx(0.2)
    assert analysis.joint_uplift.estimate == pytest.approx(0.7)
    assert analysis.joint_incremental_uplift.estimate == pytest.approx(0.4)
    assert analysis.block_count == 2
    assert analysis.world_cluster_count == 2


def test_world_cluster_bootstrap_is_deterministic_and_keeps_repetitions_in_one_cluster() -> None:
    plan = _plan(worlds=("world.alpha", "world.beta", "world.gamma"), repetitions=2)
    outcomes = [
        FactorialOutcome(
            trial_id=trial.trial_id,
            value=_world_value(trial.world_id, trial.cell),
        )
        for trial in reversed(plan.trials)
    ]

    first = analyse_factorial(plan, outcomes, bootstrap_replicates=500, bootstrap_seed=7)
    repeated = analyse_factorial(plan, list(reversed(outcomes)), bootstrap_replicates=500, bootstrap_seed=7)

    assert first == repeated
    assert first.world_cluster_count == 3
    assert first.block_count == 6
    assert first.interaction.interval.method == "cluster_bootstrap_world"
    assert first.interaction.interval.cluster_count == 3
    assert first.interaction.interval.replicates == 500
    assert first.interaction.interval.lower <= first.interaction.estimate <= first.interaction.interval.upper


@pytest.mark.parametrize("mode", ["missing", "duplicate", "unknown"])
def test_analysis_rejects_incomplete_duplicate_or_unknown_outcomes(mode: str) -> None:
    plan = _plan(worlds=("world.alpha",), repetitions=1)
    outcomes = _constant_cell_outcomes(plan, dict.fromkeys(FactorialCell, 0.5))
    if mode == "missing":
        outcomes.pop()
    elif mode == "duplicate":
        outcomes.append(outcomes[0])
    else:
        outcomes[-1] = FactorialOutcome(trial_id="trial-unknown", value=0.5)

    with pytest.raises(ValueError, match="missing|duplicate|unknown"):
        analyse_factorial(plan, outcomes, bootstrap_replicates=20, bootstrap_seed=3)


def test_outcome_rejects_non_finite_values() -> None:
    with pytest.raises(ValidationError):
        FactorialOutcome(trial_id="trial.invalid", value=math.nan)


def test_analysis_requires_positive_bootstrap_replicates_and_valid_confidence() -> None:
    plan = _plan(worlds=("world.alpha",), repetitions=1)
    outcomes = _constant_cell_outcomes(plan, dict.fromkeys(FactorialCell, 0.5))

    with pytest.raises(ValueError, match="bootstrap_replicates"):
        analyse_factorial(plan, outcomes, bootstrap_replicates=0)
    with pytest.raises(ValueError, match="confidence_level"):
        analyse_factorial(plan, outcomes, confidence_level=1.0)


def _plan(*, worlds: tuple[str, ...], repetitions: int) -> FactorialPlan:
    return build_factorial_plan(
        FactorialStudyManifest(
            experiment_id="factorial.analysis",
            randomization_seed=41,
            repetitions=repetitions,
            candidate_sets=tuple(_candidate_set(world_id) for world_id in worlds),
        )
    )


def _constant_cell_outcomes(
    plan: FactorialPlan,
    values: dict[FactorialCell, float],
) -> list[FactorialOutcome]:
    return [FactorialOutcome(trial_id=trial.trial_id, value=values[trial.cell]) for trial in plan.trials]


def _world_value(world_id: str, cell: FactorialCell) -> float:
    baselines = {"world.alpha": 0.1, "world.beta": 0.3, "world.gamma": 0.5}
    harness = {"world.alpha": 0.1, "world.beta": 0.2, "world.gamma": 0.3}
    program = {"world.alpha": 0.2, "world.beta": 0.1, "world.gamma": 0.15}
    interaction = {"world.alpha": 0.05, "world.beta": -0.05, "world.gamma": 0.1}
    value = baselines[world_id]
    if cell in {FactorialCell.HX_P0, FactorialCell.HX_PX}:
        value += harness[world_id]
    if cell in {FactorialCell.H0_PX, FactorialCell.HX_PX}:
        value += program[world_id]
    if cell is FactorialCell.HX_PX:
        value += interaction[world_id]
    return value


def _candidate_set(world_id: str) -> FactorialCandidateSet:
    return FactorialCandidateSet(
        world_id=world_id,
        candidates=tuple(_candidate(world_id, cell) for cell in FactorialCell),
    )


def _candidate(world_id: str, cell: FactorialCell) -> FactorialCandidateReference:
    learned_harness = cell in {FactorialCell.HX_P0, FactorialCell.HX_PX}
    learned_program = cell in {FactorialCell.H0_PX, FactorialCell.HX_PX}
    return FactorialCandidateReference.create(
        cell=cell,
        kernel_sha256=_sha("kernel"),
        kernel_abi_sha256=_sha("abi"),
        policy_sha256=_sha("policy"),
        world_id=world_id,
        world_sha256=_sha(world_id),
        harness_sha256=_sha("hx" if learned_harness else "h0"),
        harness_abi_sha256=_sha("abi"),
        program_sha256=_sha("px" if learned_program else "p0"),
        program_abi_sha256=_sha("abi"),
        resource_sha256=_sha("resource"),
    )


def _sha(label: str) -> str:
    import hashlib

    return hashlib.sha256(label.encode()).hexdigest()
