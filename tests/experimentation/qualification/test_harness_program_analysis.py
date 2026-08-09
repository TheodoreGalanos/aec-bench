# ABOUTME: Tests exact treatment contrasts and deterministic task-set uncertainty intervals.
# ABOUTME: Ensures analysis fails closed on incomplete, duplicated, or unplanned trial outcomes.

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from aec_bench.experimentation.qualification.harness_program_study.analysis import (
    HarnessProgramOutcome,
    analyse_harness_program_study,
)
from aec_bench.experimentation.qualification.harness_program_study.plan import (
    HarnessProgramCandidateReference,
    HarnessProgramCandidateSet,
    HarnessProgramCell,
    HarnessProgramPlan,
    HarnessProgramStudyManifest,
    build_harness_program_plan,
)


def test_analysis_computes_exact_main_effects_interaction_and_joint_contrasts() -> None:
    plan = _plan(task_sets=("task-set.alpha", "task-set.beta"), repetitions=1)
    outcomes = _constant_cell_outcomes(
        plan,
        {
            HarnessProgramCell.H0_P0: 0.2,
            HarnessProgramCell.HX_P0: 0.4,
            HarnessProgramCell.H0_PX: 0.5,
            HarnessProgramCell.HX_PX: 0.9,
        },
    )

    analysis = analyse_harness_program_study(plan, outcomes, bootstrap_replicates=200, bootstrap_seed=19)

    assert analysis.cell_means == {
        HarnessProgramCell.H0_P0: pytest.approx(0.2),
        HarnessProgramCell.HX_P0: pytest.approx(0.4),
        HarnessProgramCell.H0_PX: pytest.approx(0.5),
        HarnessProgramCell.HX_PX: pytest.approx(0.9),
    }
    assert analysis.harness_main_effect.estimate == pytest.approx(0.3)
    assert analysis.program_main_effect.estimate == pytest.approx(0.4)
    assert analysis.interaction.estimate == pytest.approx(0.2)
    assert analysis.joint_uplift.estimate == pytest.approx(0.7)
    assert analysis.joint_incremental_uplift.estimate == pytest.approx(0.4)
    assert analysis.block_count == 2
    assert analysis.task_set_cluster_count == 2


def test_task_set_cluster_bootstrap_is_deterministic_and_keeps_repetitions_in_one_cluster() -> None:
    plan = _plan(task_sets=("task-set.alpha", "task-set.beta", "task-set.gamma"), repetitions=2)
    outcomes = [
        HarnessProgramOutcome(
            trial_id=trial.trial_id,
            value=_task_set_value(trial.task_set_id, trial.cell),
        )
        for trial in reversed(plan.trials)
    ]

    first = analyse_harness_program_study(plan, outcomes, bootstrap_replicates=500, bootstrap_seed=7)
    repeated = analyse_harness_program_study(plan, list(reversed(outcomes)), bootstrap_replicates=500, bootstrap_seed=7)

    assert first == repeated
    assert first.task_set_cluster_count == 3
    assert first.block_count == 6
    assert first.interaction.interval.method == "cluster_bootstrap_task_set"
    assert first.interaction.interval.cluster_count == 3
    assert first.interaction.interval.replicates == 500
    assert first.interaction.interval.lower <= first.interaction.estimate <= first.interaction.interval.upper


@pytest.mark.parametrize("mode", ["missing", "duplicate", "unknown"])
def test_analysis_rejects_incomplete_duplicate_or_unknown_outcomes(mode: str) -> None:
    plan = _plan(task_sets=("task-set.alpha",), repetitions=1)
    outcomes = _constant_cell_outcomes(plan, dict.fromkeys(HarnessProgramCell, 0.5))
    if mode == "missing":
        outcomes.pop()
    elif mode == "duplicate":
        outcomes.append(outcomes[0])
    else:
        outcomes[-1] = HarnessProgramOutcome(trial_id="trial-unknown", value=0.5)

    with pytest.raises(ValueError, match="missing|duplicate|unknown"):
        analyse_harness_program_study(plan, outcomes, bootstrap_replicates=20, bootstrap_seed=3)


def test_outcome_rejects_non_finite_values() -> None:
    with pytest.raises(ValidationError):
        HarnessProgramOutcome(trial_id="trial.invalid", value=math.nan)


def test_analysis_requires_positive_bootstrap_replicates_and_valid_confidence() -> None:
    plan = _plan(task_sets=("task-set.alpha",), repetitions=1)
    outcomes = _constant_cell_outcomes(plan, dict.fromkeys(HarnessProgramCell, 0.5))

    with pytest.raises(ValueError, match="bootstrap_replicates"):
        analyse_harness_program_study(plan, outcomes, bootstrap_replicates=0)
    with pytest.raises(ValueError, match="confidence_level"):
        analyse_harness_program_study(plan, outcomes, confidence_level=1.0)


def _plan(*, task_sets: tuple[str, ...], repetitions: int) -> HarnessProgramPlan:
    return build_harness_program_plan(
        HarnessProgramStudyManifest(
            experiment_id="harness-program.analysis",
            randomization_seed=41,
            repetitions=repetitions,
            candidate_sets=tuple(_candidate_set(task_set_id) for task_set_id in task_sets),
        )
    )


def _constant_cell_outcomes(
    plan: HarnessProgramPlan,
    values: dict[HarnessProgramCell, float],
) -> list[HarnessProgramOutcome]:
    return [HarnessProgramOutcome(trial_id=trial.trial_id, value=values[trial.cell]) for trial in plan.trials]


def _task_set_value(task_set_id: str, cell: HarnessProgramCell) -> float:
    baselines = {"task-set.alpha": 0.1, "task-set.beta": 0.3, "task-set.gamma": 0.5}
    harness = {"task-set.alpha": 0.1, "task-set.beta": 0.2, "task-set.gamma": 0.3}
    program = {"task-set.alpha": 0.2, "task-set.beta": 0.1, "task-set.gamma": 0.15}
    interaction = {"task-set.alpha": 0.05, "task-set.beta": -0.05, "task-set.gamma": 0.1}
    value = baselines[task_set_id]
    if cell in {HarnessProgramCell.HX_P0, HarnessProgramCell.HX_PX}:
        value += harness[task_set_id]
    if cell in {HarnessProgramCell.H0_PX, HarnessProgramCell.HX_PX}:
        value += program[task_set_id]
    if cell is HarnessProgramCell.HX_PX:
        value += interaction[task_set_id]
    return value


def _candidate_set(task_set_id: str) -> HarnessProgramCandidateSet:
    return HarnessProgramCandidateSet(
        task_set_id=task_set_id,
        candidates=tuple(_candidate(task_set_id, cell) for cell in HarnessProgramCell),
    )


def _candidate(task_set_id: str, cell: HarnessProgramCell) -> HarnessProgramCandidateReference:
    learned_harness = cell in {HarnessProgramCell.HX_P0, HarnessProgramCell.HX_PX}
    learned_program = cell in {HarnessProgramCell.H0_PX, HarnessProgramCell.HX_PX}
    return HarnessProgramCandidateReference.create(
        cell=cell,
        kernel_sha256=_sha("kernel"),
        kernel_abi_sha256=_sha("abi"),
        policy_sha256=_sha("policy"),
        task_set_id=task_set_id,
        task_set_sha256=_sha(task_set_id),
        harness_sha256=_sha("hx" if learned_harness else "h0"),
        harness_abi_sha256=_sha("abi"),
        program_sha256=_sha("px" if learned_program else "p0"),
        program_abi_sha256=_sha("abi"),
        resource_sha256=_sha("resource"),
    )


def _sha(label: str) -> str:
    import hashlib

    return hashlib.sha256(label.encode()).hexdigest()
