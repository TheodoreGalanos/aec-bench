# ABOUTME: Reduces retrieval-state study evidence with integrity-first paired analysis.
# ABOUTME: Clusters uncertainty by independent world history and retains failed runs.

from __future__ import annotations

import random
from collections import defaultdict
from statistics import fmean
from typing import Literal

from aec_bench.experiments.retrieval_state_continuity.contracts import (
    ConfidenceInterval,
    CoverageReport,
    ObservationSource,
    PairCoverage,
    PairIneligibilityReason,
    StudyBlock,
    StudyConclusion,
    StudyManifest,
    StudyObservation,
    StudyPhase,
    StudyPlan,
    StudyReport,
    Treatment,
    TreatmentDelivery,
    TreatmentDeliveryStatus,
)


def analyse_study(
    *,
    manifest: StudyManifest,
    plan: StudyPlan,
    deliveries: tuple[TreatmentDelivery, ...],
    observations: tuple[StudyObservation, ...],
) -> StudyReport:
    """Recompute the ordered study gates from exact retained evidence."""

    selected_manifest = StudyManifest.model_validate(manifest.model_dump(mode="json"))
    selected_plan = StudyPlan.model_validate(plan.model_dump(mode="json"))
    if selected_plan.manifest_content_sha256 != selected_manifest.content_sha256:
        raise ValueError("study plan does not belong to the supplied manifest")
    delivery_by_trial = _unique_delivery_map(deliveries)
    observation_by_trial = _unique_observation_map(observations)
    planned_ids = tuple(trial.trial_id for trial in selected_plan.trials)
    planned_id_set = set(planned_ids)
    _reject_unplanned(set(delivery_by_trial), planned_id_set, label="delivery")
    _reject_unplanned(set(observation_by_trial), planned_id_set, label="observation")
    ordered_deliveries = tuple(delivery_by_trial[item] for item in planned_ids if item in delivery_by_trial)
    ordered_observations = tuple(observation_by_trial[item] for item in planned_ids if item in observation_by_trial)
    _validate_phase_evidence(selected_manifest, ordered_deliveries, ordered_observations)

    coverages: list[PairCoverage] = []
    differences_by_history: dict[int, list[int]] = defaultdict(list)
    complete_pair_count = 0
    for block in selected_plan.blocks:
        block_observations = tuple(
            observation_by_trial[trial.trial_id] for trial in block.trials if trial.trial_id in observation_by_trial
        )
        if len(block_observations) == 2:
            complete_pair_count += 1
        reason = _pair_ineligibility(
            block=block,
            delivery_by_trial=delivery_by_trial,
            observation_by_trial=observation_by_trial,
        )
        observed_ids = tuple(trial.trial_id for trial in block.trials if trial.trial_id in observation_by_trial)
        if reason is not None:
            coverages.append(
                PairCoverage(
                    block_id=block.block_id,
                    world_history_seed=block.world_history_seed,
                    observed_trial_ids=observed_ids,
                    analyzable=False,
                    ineligibility_reason=reason,
                    paired_difference=None,
                )
            )
            continue
        by_treatment = {item.treatment: item for item in block_observations}
        absent = by_treatment[Treatment.RETRIEVAL_STATE_ABSENT].epistemic_decision_failure
        preserved = by_treatment[Treatment.RETRIEVAL_STATE_PRESERVED].epistemic_decision_failure
        if absent is None or preserved is None:
            raise ValueError("analyzable pair lacks a binary endpoint")
        difference: Literal[-1, 0, 1]
        if absent == preserved:
            difference = 0
        elif absent:
            difference = 1
        else:
            difference = -1
        differences_by_history[block.world_history_seed].append(difference)
        coverages.append(
            PairCoverage(
                block_id=block.block_id,
                world_history_seed=block.world_history_seed,
                observed_trial_ids=observed_ids,
                analyzable=True,
                ineligibility_reason=None,
                paired_difference=difference,
            )
        )

    paired_differences = tuple(value for values in differences_by_history.values() for value in values)
    missing_trial_ids = tuple(item for item in planned_ids if item not in observation_by_trial)
    coverage = CoverageReport(
        exact=not missing_trial_ids and len(observation_by_trial) == len(planned_ids),
        planned_trial_count=len(planned_ids),
        observed_trial_count=len(observation_by_trial),
        missing_trial_ids=missing_trial_ids,
        complete_pair_count=complete_pair_count,
        analyzable_pair_count=len(paired_differences),
        eligible_world_history_count=len(differences_by_history),
        pairs=tuple(coverages),
    )
    validity_passed = (
        coverage.analyzable_pair_count >= selected_manifest.analysis.minimum_eligible_pairs
        and coverage.eligible_world_history_count >= selected_manifest.analysis.minimum_eligible_world_histories
    )
    point_estimate = fmean(paired_differences) if paired_differences else None
    confidence_interval = _clustered_bootstrap_interval(
        differences_by_history,
        replicates=selected_manifest.analysis.bootstrap_replicates,
        seed=selected_manifest.analysis.bootstrap_seed,
        confidence_level=selected_manifest.analysis.confidence_level,
    )
    rule_result = _classify(
        manifest=selected_manifest,
        validity_passed=validity_passed,
        point_estimate=point_estimate,
        confidence_interval=confidence_interval,
    )
    if selected_manifest.phase is StudyPhase.ANALYSIS_FIXTURE:
        conclusion = StudyConclusion.ANALYSIS_FIXTURE
        fixture_rule_result: StudyConclusion | None = rule_result
    elif selected_manifest.phase is StudyPhase.SHAKEDOWN:
        conclusion = StudyConclusion.SHAKEDOWN
        fixture_rule_result = None
    else:
        conclusion = rule_result
        fixture_rule_result = None

    reported_analysis_values = tuple(
        item.reported_analysis_token_count
        for item in ordered_observations
        if item.reported_analysis_token_count is not None
    )
    currencies = {item.spend_currency for item in ordered_observations if item.spend_currency is not None}
    if len(currencies) > 1:
        raise ValueError("study observations use more than one spend currency")
    return StudyReport(
        manifest_content_sha256=selected_manifest.content_sha256,
        plan_content_sha256=selected_plan.content_sha256,
        phase=selected_manifest.phase,
        gate_order=("integrity", "validity", "endpoint"),
        integrity_passed=True,
        validity_passed=validity_passed,
        conclusion=conclusion,
        fixture_rule_result=fixture_rule_result,
        coverage=coverage,
        point_estimate=point_estimate,
        confidence_interval=confidence_interval,
        provider_call_count=sum(item.provider_call_count for item in ordered_observations),
        input_token_count=sum(item.input_token_count for item in ordered_observations),
        output_token_count=sum(item.output_token_count for item in ordered_observations),
        reported_analysis_token_count=(sum(reported_analysis_values) if reported_analysis_values else None),
        analysis_tokens_included_in_output=any(
            item.analysis_tokens_included_in_output for item in ordered_observations
        ),
        total_token_count=sum(item.total_token_count for item in ordered_observations),
        spend_currency=next(iter(currencies), None),
        spend_microunits=sum(item.spend_microunits for item in ordered_observations),
        study_outcome_count=sum(item.study_outcome_eligible for item in ordered_observations),
        fixture_observation_count=sum(
            item.source is ObservationSource.GENERATED_ANALYSIS_FIXTURE for item in ordered_observations
        ),
        task_reward_mutation_count=sum(item.task_reward_mutation_count for item in ordered_observations),
        promotion_permitted=False,
        delivery_content_sha256=tuple(item.content_sha256 for item in ordered_deliveries),
        observation_content_sha256=tuple(item.content_sha256 for item in ordered_observations),
    )


def _unique_delivery_map(items: tuple[TreatmentDelivery, ...]) -> dict[str, TreatmentDelivery]:
    selected: dict[str, TreatmentDelivery] = {}
    for item in items:
        if item.trial_id in selected:
            raise ValueError(f"duplicate delivery for trial: {item.trial_id}")
        selected[item.trial_id] = item
    return selected


def _unique_observation_map(items: tuple[StudyObservation, ...]) -> dict[str, StudyObservation]:
    selected: dict[str, StudyObservation] = {}
    for item in items:
        if item.trial_id in selected:
            raise ValueError(f"duplicate observation for trial: {item.trial_id}")
        selected[item.trial_id] = item
    return selected


def _reject_unplanned(observed: set[str], planned: set[str], *, label: str) -> None:
    unexpected = tuple(sorted(observed - planned))
    if unexpected:
        raise ValueError(f"unplanned {label}: {', '.join(unexpected)}")


def _validate_phase_evidence(
    manifest: StudyManifest,
    deliveries: tuple[TreatmentDelivery, ...],
    observations: tuple[StudyObservation, ...],
) -> None:
    expected = {
        StudyPhase.ANALYSIS_FIXTURE: ObservationSource.GENERATED_ANALYSIS_FIXTURE,
        StudyPhase.SHAKEDOWN: ObservationSource.SHAKEDOWN,
        StudyPhase.CONFIRMATORY: ObservationSource.CONFIRMATORY,
    }[manifest.phase]
    if any(item.source is not expected for item in (*deliveries, *observations)):
        raise ValueError(f"{manifest.phase.value} evidence must use {expected.value}")
    if any(item.task_reward_mutation_count for item in observations):
        raise ValueError("study evidence cannot change task reward")
    if sum(item.provider_call_count for item in observations) > manifest.provider_calls_allowed:
        raise ValueError("study evidence exceeds provider-call authority")
    if not manifest.study_outcomes_allowed and any(item.study_outcome_eligible for item in observations):
        raise ValueError("study evidence contains outcomes without authority")


def _pair_ineligibility(
    *,
    block: StudyBlock,
    delivery_by_trial: dict[str, TreatmentDelivery],
    observation_by_trial: dict[str, StudyObservation],
) -> PairIneligibilityReason | None:
    if any(trial.trial_id not in observation_by_trial for trial in block.trials):
        return PairIneligibilityReason.MISSING_ARM
    if any(trial.trial_id not in delivery_by_trial for trial in block.trials):
        return PairIneligibilityReason.MISSING_DELIVERY
    deliveries = tuple(delivery_by_trial[trial.trial_id] for trial in block.trials)
    observations = tuple(observation_by_trial[trial.trial_id] for trial in block.trials)
    for trial, delivery, observation in zip(block.trials, deliveries, observations, strict=True):
        if delivery.status is TreatmentDeliveryStatus.CORRUPT:
            return PairIneligibilityReason.TREATMENT_DELIVERY_CORRUPTION
        if delivery.status is not TreatmentDeliveryStatus.DELIVERED:
            return PairIneligibilityReason.MISSING_DELIVERY
        if (
            delivery.block_id != block.block_id
            or delivery.trial_id != trial.trial_id
            or delivery.treatment is not trial.treatment
            or observation.block_id != block.block_id
            or observation.trial_id != trial.trial_id
            or observation.treatment is not trial.treatment
            or observation.delivery_content_sha256 != delivery.content_sha256
            or observation.world_history_seed != block.world_history_seed
            or observation.sampling_replicate != block.sampling_replicate
            or observation.history_snapshot_sha256 != block.history_snapshot_sha256
            or observation.event_schedule_sha256 != block.event_schedule_sha256
            or observation.budget_sha256 != trial.budget_sha256
        ):
            return PairIneligibilityReason.IDENTITY_DRIFT
        if observation.ineligibility_reason is not None:
            return observation.ineligibility_reason
    shared_fields = (
        "non_treatment_input_sha256",
        "current_actor_view_sha256",
        "history_snapshot_sha256",
        "event_schedule_sha256",
        "base_carrier_sha256",
    )
    if any(len({getattr(item, field) for item in deliveries}) != 1 for field in shared_fields):
        return PairIneligibilityReason.PAIR_IDENTITY_DRIFT
    if any(getattr(deliveries[0], field) != getattr(block, field) for field in shared_fields):
        return PairIneligibilityReason.PAIR_IDENTITY_DRIFT
    return None


def _clustered_bootstrap_interval(
    differences_by_history: dict[int, list[int]],
    *,
    replicates: int,
    seed: int,
    confidence_level: float,
) -> ConfidenceInterval | None:
    if not differences_by_history:
        return None
    history_means = tuple(fmean(values) for _, values in sorted(differences_by_history.items()))
    randomizer = random.Random(seed)
    estimates = sorted(fmean(randomizer.choice(history_means) for _ in history_means) for _ in range(replicates))
    alpha = 1.0 - confidence_level
    return ConfidenceInterval(
        lower=_linear_percentile(estimates, alpha / 2.0),
        upper=_linear_percentile(estimates, 1.0 - alpha / 2.0),
        confidence_level=confidence_level,
    )


def _linear_percentile(values: list[float], probability: float) -> float:
    position = probability * (len(values) - 1)
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(values) - 1)
    fraction = position - lower_index
    return values[lower_index] + fraction * (values[upper_index] - values[lower_index])


def _classify(
    *,
    manifest: StudyManifest,
    validity_passed: bool,
    point_estimate: float | None,
    confidence_interval: ConfidenceInterval | None,
) -> StudyConclusion:
    if not validity_passed or point_estimate is None or confidence_interval is None:
        return StudyConclusion.COVERAGE_BLOCKED
    threshold = manifest.analysis.minimum_meaningful_effect
    if point_estimate >= threshold and confidence_interval.lower > 0.0:
        return StudyConclusion.SUPPORTED
    if confidence_interval.upper < threshold:
        return StudyConclusion.REFUTED
    return StudyConclusion.INCONCLUSIVE
