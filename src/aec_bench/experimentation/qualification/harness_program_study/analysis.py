# ABOUTME: Computes exact four-cell treatment effects from one complete content-addressed study plan.
# ABOUTME: Produces deterministic uncertainty intervals by resampling whole task-set clusters.

from __future__ import annotations

import random
from collections import defaultdict
from statistics import fmean
from typing import Literal

from pydantic import Field, FiniteFloat, PositiveInt, model_validator

from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.experimentation.qualification.harness_program_study.plan import HarnessProgramCell, HarnessProgramPlan

ContrastName = Literal[
    "harness_main_effect",
    "program_main_effect",
    "interaction",
    "joint_uplift",
    "joint_incremental_uplift",
]


class HarnessProgramOutcome(StrictModel):
    """One finite scalar outcome bound to a planned harness-program trial."""

    trial_id: NonEmptyStr
    value: FiniteFloat


class BootstrapInterval(StrictModel):
    """A deterministic percentile interval from whole-task-set cluster resampling."""

    method: Literal["cluster_bootstrap_task_set"] = "cluster_bootstrap_task_set"
    confidence_level: float = Field(gt=0.0, lt=1.0)
    lower: FiniteFloat
    upper: FiniteFloat
    cluster_count: PositiveInt
    replicates: PositiveInt
    seed: int

    @model_validator(mode="after")
    def validate_bounds(self) -> BootstrapInterval:
        if self.lower > self.upper:
            raise ValueError("bootstrap interval lower bound cannot exceed its upper bound")
        return self


class ContrastEstimate(StrictModel):
    """One named harness-program contrast and its task-set-clustered interval."""

    name: ContrastName
    estimate: FiniteFloat
    interval: BootstrapInterval


class HarnessProgramAnalysis(StrictModel):
    """Complete cell means and planned contrasts for one harness-program plan."""

    schema_version: Literal["1"] = "1"
    plan_sha256: NonEmptyStr
    observation_count: PositiveInt
    block_count: PositiveInt
    task_set_cluster_count: PositiveInt
    cell_means: dict[HarnessProgramCell, FiniteFloat]
    harness_main_effect: ContrastEstimate
    program_main_effect: ContrastEstimate
    interaction: ContrastEstimate
    joint_uplift: ContrastEstimate
    joint_incremental_uplift: ContrastEstimate

    @model_validator(mode="after")
    def validate_complete_effects(self) -> HarnessProgramAnalysis:
        if set(self.cell_means) != set(HarnessProgramCell):
            raise ValueError("harness-program analysis requires all four cell means")
        expected_names = {
            "harness_main_effect": self.harness_main_effect,
            "program_main_effect": self.program_main_effect,
            "interaction": self.interaction,
            "joint_uplift": self.joint_uplift,
            "joint_incremental_uplift": self.joint_incremental_uplift,
        }
        if any(estimate.name != name for name, estimate in expected_names.items()):
            raise ValueError("harness-program contrast names must match their analysis fields")
        return self


def analyse_harness_program_study(
    plan: HarnessProgramPlan,
    outcomes: list[HarnessProgramOutcome],
    *,
    confidence_level: float = 0.95,
    bootstrap_replicates: int = 2_000,
    bootstrap_seed: int = 42,
) -> HarnessProgramAnalysis:
    """Analyse one complete plan and fail closed on missing or unplanned outcomes."""

    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be strictly between zero and one")
    if bootstrap_replicates < 1 or isinstance(bootstrap_replicates, bool):
        raise ValueError("bootstrap_replicates must be a positive integer")

    normalized = [HarnessProgramOutcome.model_validate(outcome.model_dump(mode="json")) for outcome in outcomes]
    outcome_ids = [outcome.trial_id for outcome in normalized]
    if len(outcome_ids) != len(set(outcome_ids)):
        raise ValueError("duplicate harness-program outcome trial ids")

    planned = {trial.trial_id: trial for trial in plan.trials}
    unknown = sorted(set(outcome_ids) - set(planned))
    if unknown:
        raise ValueError(f"unknown harness-program outcome trial ids: {', '.join(unknown)}")
    missing = sorted(set(planned) - set(outcome_ids))
    if missing:
        raise ValueError(f"missing harness-program outcome trial ids: {', '.join(missing)}")

    value_by_trial = {outcome.trial_id: float(outcome.value) for outcome in normalized}
    cell_values: dict[HarnessProgramCell, list[float]] = defaultdict(list)
    task_set_values: dict[str, list[tuple[HarnessProgramCell, float]]] = defaultdict(list)
    for trial in plan.trials:
        value = value_by_trial[trial.trial_id]
        cell_values[trial.cell].append(value)
        task_set_values[trial.task_set_id].append((trial.cell, value))

    cell_means = {cell: fmean(cell_values[cell]) for cell in HarnessProgramCell}
    point_estimates = _contrasts(cell_means)
    bootstrap = _cluster_bootstrap(
        task_set_values=task_set_values,
        confidence_level=confidence_level,
        replicates=bootstrap_replicates,
        seed=bootstrap_seed,
    )

    estimates = {
        name: ContrastEstimate(
            name=name,
            estimate=point_estimates[name],
            interval=BootstrapInterval(
                confidence_level=confidence_level,
                lower=interval[0],
                upper=interval[1],
                cluster_count=len(task_set_values),
                replicates=bootstrap_replicates,
                seed=bootstrap_seed,
            ),
        )
        for name, interval in bootstrap.items()
    }
    return HarnessProgramAnalysis(
        plan_sha256=plan.plan_sha256,
        observation_count=len(normalized),
        block_count=len(plan.blocks),
        task_set_cluster_count=len(task_set_values),
        cell_means=cell_means,
        harness_main_effect=estimates["harness_main_effect"],
        program_main_effect=estimates["program_main_effect"],
        interaction=estimates["interaction"],
        joint_uplift=estimates["joint_uplift"],
        joint_incremental_uplift=estimates["joint_incremental_uplift"],
    )


def _cluster_bootstrap(
    *,
    task_set_values: dict[str, list[tuple[HarnessProgramCell, float]]],
    confidence_level: float,
    replicates: int,
    seed: int,
) -> dict[ContrastName, tuple[float, float]]:
    task_set_ids = sorted(task_set_values)
    if not task_set_ids:
        raise ValueError("harness-program analysis requires at least one task-set cluster")
    randomizer = random.Random(seed)
    samples: dict[ContrastName, list[float]] = defaultdict(list)
    for _ in range(replicates):
        sampled_task_sets = randomizer.choices(task_set_ids, k=len(task_set_ids))
        values_by_cell: dict[HarnessProgramCell, list[float]] = defaultdict(list)
        for task_set_id in sampled_task_sets:
            for cell, value in task_set_values[task_set_id]:
                values_by_cell[cell].append(value)
        cell_means = {cell: fmean(values_by_cell[cell]) for cell in HarnessProgramCell}
        for name, estimate in _contrasts(cell_means).items():
            samples[name].append(estimate)

    tail = (1.0 - confidence_level) / 2.0
    return {name: (_percentile(values, tail), _percentile(values, 1.0 - tail)) for name, values in samples.items()}


def _contrasts(cell_means: dict[HarnessProgramCell, float]) -> dict[ContrastName, float]:
    h0_p0 = cell_means[HarnessProgramCell.H0_P0]
    hx_p0 = cell_means[HarnessProgramCell.HX_P0]
    h0_px = cell_means[HarnessProgramCell.H0_PX]
    hx_px = cell_means[HarnessProgramCell.HX_PX]
    return {
        "harness_main_effect": ((hx_p0 - h0_p0) + (hx_px - h0_px)) / 2.0,
        "program_main_effect": ((h0_px - h0_p0) + (hx_px - hx_p0)) / 2.0,
        "interaction": hx_px - hx_p0 - h0_px + h0_p0,
        "joint_uplift": hx_px - h0_p0,
        "joint_incremental_uplift": hx_px - max(hx_p0, h0_px),
    }


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    fraction = position - lower_index
    return ordered[lower_index] + (ordered[upper_index] - ordered[lower_index]) * fraction
