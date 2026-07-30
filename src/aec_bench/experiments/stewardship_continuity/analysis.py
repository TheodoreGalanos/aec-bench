# ABOUTME: Reduces matched continuity evidence with exact coverage and paired uncertainty.
# ABOUTME: Prevents provider-free fixtures from becoming study conclusions.

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterable
from statistics import fmean
from typing import Literal

from aec_bench.experiments.stewardship_continuity.contracts import (
    BlockCoverage,
    ConfidenceInterval,
    ContinuityBlock,
    ContinuityConclusion,
    ContinuityCoverageReport,
    ContinuityObservation,
    ContinuityStudyManifest,
    ContinuityStudyPhase,
    ContinuityStudyPlan,
    ContinuityStudyReport,
    ContinuityTreatment,
    ObservationSource,
    PairIneligibilityReason,
    TreatmentDeliveryRecord,
    TreatmentDeliveryStatus,
)


def analyse_continuity_study(
    *,
    manifest: ContinuityStudyManifest,
    plan: ContinuityStudyPlan,
    deliveries: tuple[TreatmentDeliveryRecord, ...],
    observations: tuple[ContinuityObservation, ...],
) -> ContinuityStudyReport:
    """Recompute one paired report from exact retained evidence."""

    selected_manifest = ContinuityStudyManifest.model_validate(
        manifest.model_dump(mode="json"),
    )
    selected_plan = ContinuityStudyPlan.model_validate(
        plan.model_dump(mode="json"),
    )
    if selected_plan.manifest_content_sha256 != selected_manifest.content_sha256:
        raise ValueError("continuity plan does not belong to the supplied manifest")

    planned_ids = tuple(trial.trial_id for trial in selected_plan.trials)
    planned_id_set = set(planned_ids)
    delivery_by_trial = _unique_delivery_map(deliveries)
    observation_by_trial = _unique_observation_map(observations)
    _reject_unplanned(
        label="delivery",
        observed_ids=set(delivery_by_trial),
        planned_ids=planned_id_set,
    )
    _reject_unplanned(
        label="observation",
        observed_ids=set(observation_by_trial),
        planned_ids=planned_id_set,
    )
    ordered_deliveries = tuple(delivery_by_trial[trial_id] for trial_id in planned_ids if trial_id in delivery_by_trial)
    ordered_observations = tuple(
        observation_by_trial[trial_id] for trial_id in planned_ids if trial_id in observation_by_trial
    )
    _validate_phase_evidence(
        selected_manifest,
        deliveries=ordered_deliveries,
        observations=ordered_observations,
    )

    host_fault_counts: Counter[ContinuityTreatment] = Counter()
    for observation in ordered_observations:
        if observation.is_host_fault:
            host_fault_counts[observation.treatment] += 1

    block_coverage: list[BlockCoverage] = []
    paired_differences: list[int] = []
    complete_block_count = 0
    for block in selected_plan.blocks:
        block_observations = tuple(
            observation_by_trial[trial.trial_id] for trial in block.trials if trial.trial_id in observation_by_trial
        )
        if len(block_observations) == 2:
            complete_block_count += 1
        reason = _block_ineligibility(
            manifest=selected_manifest,
            plan=selected_plan,
            block=block,
            delivery_by_trial=delivery_by_trial,
            observation_by_trial=observation_by_trial,
        )
        observed_trial_ids = tuple(trial.trial_id for trial in block.trials if trial.trial_id in observation_by_trial)
        if reason is not None:
            block_coverage.append(
                BlockCoverage(
                    block_id=block.block_id,
                    observed_trial_ids=observed_trial_ids,
                    analyzable=False,
                    ineligibility_reason=reason,
                    paired_difference=None,
                )
            )
            continue

        by_treatment = {observation.treatment: observation for observation in block_observations}
        current_failure = by_treatment[ContinuityTreatment.CURRENT_ACTOR_VIEW].continuity_failure
        structured_failure = by_treatment[ContinuityTreatment.STRUCTURED_HANDOVER].continuity_failure
        if current_failure is None or structured_failure is None:
            raise ValueError("analyzable continuity pair lacks a binary endpoint")
        difference: Literal[-1, 0, 1]
        if structured_failure == current_failure:
            difference = 0
        elif structured_failure:
            difference = 1
        else:
            difference = -1
        paired_differences.append(difference)
        block_coverage.append(
            BlockCoverage(
                block_id=block.block_id,
                observed_trial_ids=observed_trial_ids,
                analyzable=True,
                ineligibility_reason=None,
                paired_difference=difference,
            )
        )

    missing_trial_ids = tuple(trial_id for trial_id in planned_ids if trial_id not in observation_by_trial)
    observed_trial_count = len(observation_by_trial)
    host_fault_count_by_treatment = {treatment: host_fault_counts[treatment] for treatment in ContinuityTreatment}
    host_fault_arm_imbalance = abs(
        host_fault_count_by_treatment[ContinuityTreatment.CURRENT_ACTOR_VIEW]
        - host_fault_count_by_treatment[ContinuityTreatment.STRUCTURED_HANDOVER]
    )
    coverage = ContinuityCoverageReport(
        exact=not missing_trial_ids and observed_trial_count == len(planned_ids),
        planned_trial_count=len(planned_ids),
        observed_trial_count=observed_trial_count,
        missing_trial_ids=missing_trial_ids,
        complete_block_count=complete_block_count,
        analyzable_block_count=len(paired_differences),
        host_fault_count_by_treatment=host_fault_count_by_treatment,
        host_fault_arm_imbalance=host_fault_arm_imbalance,
        blocks=tuple(block_coverage),
    )
    point_estimate = fmean(paired_differences) if paired_differences else None
    confidence_interval = _paired_bootstrap_interval(
        paired_differences,
        replicates=selected_manifest.analysis.bootstrap_replicates,
        seed=selected_manifest.analysis.bootstrap_seed,
    )
    rule_result = _classify(
        manifest=selected_manifest,
        coverage=coverage,
        point_estimate=point_estimate,
        confidence_interval=confidence_interval,
    )
    if selected_manifest.phase is ContinuityStudyPhase.ANALYSIS_FIXTURE:
        conclusion = ContinuityConclusion.ANALYSIS_FIXTURE
        fixture_rule_result: ContinuityConclusion | None = rule_result
    elif selected_manifest.phase is ContinuityStudyPhase.SHAKEDOWN:
        conclusion = ContinuityConclusion.SHAKEDOWN
        fixture_rule_result = None
    else:
        conclusion = rule_result
        fixture_rule_result = None

    return ContinuityStudyReport(
        manifest_content_sha256=selected_manifest.content_sha256,
        plan_content_sha256=selected_plan.content_sha256,
        phase=selected_manifest.phase,
        conclusion=conclusion,
        fixture_rule_result=fixture_rule_result,
        coverage=coverage,
        point_estimate=point_estimate,
        confidence_interval=confidence_interval,
        bootstrap_replicates=selected_manifest.analysis.bootstrap_replicates,
        bootstrap_seed=selected_manifest.analysis.bootstrap_seed,
        provider_call_count=sum(observation.provider_call_count for observation in ordered_observations),
        input_token_count=sum(observation.input_token_count for observation in ordered_observations),
        output_token_count=sum(observation.output_token_count for observation in ordered_observations),
        maximum_input_tokens_in_one_call=max(
            (observation.maximum_input_tokens_in_one_call for observation in ordered_observations),
            default=0,
        ),
        maximum_output_tokens_in_one_call=max(
            (observation.maximum_output_tokens_in_one_call for observation in ordered_observations),
            default=0,
        ),
        spend_currency=(
            selected_manifest.provider_authorization.spend_currency
            if selected_manifest.provider_authorization is not None
            else None
        ),
        spend_microunits=sum(observation.spend_microunits for observation in ordered_observations),
        study_outcome_count=sum(observation.study_outcome_eligible for observation in ordered_observations),
        fixture_observation_count=sum(
            observation.source is ObservationSource.GENERATED_ANALYSIS_FIXTURE for observation in ordered_observations
        ),
        task_reward_mutation_count=sum(observation.task_reward_mutation_count for observation in ordered_observations),
        delivery_content_sha256=tuple(delivery.content_sha256 for delivery in ordered_deliveries),
        observation_content_sha256=tuple(observation.content_sha256 for observation in ordered_observations),
    )


def _unique_delivery_map(
    deliveries: tuple[TreatmentDeliveryRecord, ...],
) -> dict[str, TreatmentDeliveryRecord]:
    selected: dict[str, TreatmentDeliveryRecord] = {}
    for delivery in deliveries:
        if delivery.trial_id in selected:
            raise ValueError(f"duplicate delivery for trial: {delivery.trial_id}")
        selected[delivery.trial_id] = delivery
    return selected


def _unique_observation_map(
    observations: tuple[ContinuityObservation, ...],
) -> dict[str, ContinuityObservation]:
    selected: dict[str, ContinuityObservation] = {}
    for observation in observations:
        if observation.trial_id in selected:
            raise ValueError(
                f"duplicate observation for trial: {observation.trial_id}",
            )
        selected[observation.trial_id] = observation
    return selected


def _reject_unplanned(
    *,
    label: str,
    observed_ids: set[str],
    planned_ids: set[str],
) -> None:
    unexpected = tuple(sorted(observed_ids - planned_ids))
    if unexpected:
        raise ValueError(
            f"unplanned {label}: {', '.join(unexpected)}",
        )


def _validate_phase_evidence(
    manifest: ContinuityStudyManifest,
    *,
    deliveries: tuple[TreatmentDeliveryRecord, ...],
    observations: tuple[ContinuityObservation, ...],
) -> None:
    expected_source = {
        ContinuityStudyPhase.ANALYSIS_FIXTURE: ObservationSource.GENERATED_ANALYSIS_FIXTURE,
        ContinuityStudyPhase.SHAKEDOWN: ObservationSource.SHAKEDOWN,
        ContinuityStudyPhase.CONFIRMATORY: ObservationSource.CONFIRMATORY,
    }[manifest.phase]
    if any(delivery.source is not expected_source for delivery in deliveries):
        raise ValueError(f"{manifest.phase.value} deliveries must use {expected_source.value}")
    if any(observation.source is not expected_source for observation in observations):
        raise ValueError(f"{manifest.phase.value} observations must use {expected_source.value}")
    if not manifest.study_outcomes_allowed and any(observation.study_outcome_eligible for observation in observations):
        raise ValueError(f"{manifest.phase.value} evidence cannot contain study outcomes")
    if manifest.phase is ContinuityStudyPhase.CONFIRMATORY and any(
        observation.study_outcome_eligible != (observation.ineligibility_reason is None) for observation in observations
    ):
        raise ValueError("confirmatory outcome eligibility must match the retained endpoint")
    if any(observation.task_reward_mutation_count for observation in observations):
        raise ValueError("continuity evidence cannot change task reward")
    if (
        sum(observation.provider_call_count for observation in observations) > manifest.provider_calls_allowed
        or sum(delivery.provider_call_count for delivery in deliveries) > manifest.provider_calls_allowed
    ):
        raise ValueError("continuity evidence exceeds provider-call authority")
    if manifest.provider_authorization is not None:
        authority = manifest.provider_authorization
        if any(
            observation.spend_currency != authority.spend_currency
            for observation in observations
            if observation.provider_call_count
        ):
            raise ValueError("continuity evidence uses an unauthorized spend currency")
        if (
            any(
                observation.maximum_input_tokens_in_one_call > authority.maximum_input_tokens_per_call
                or observation.maximum_output_tokens_in_one_call > authority.maximum_output_tokens_per_call
                for observation in observations
            )
            or sum(observation.input_token_count + observation.output_token_count for observation in observations)
            > authority.maximum_total_tokens
        ):
            raise ValueError("continuity evidence exceeds token authority")
        if sum(observation.spend_microunits for observation in observations) > authority.maximum_spend_microunits:
            raise ValueError("continuity evidence exceeds spend authority")


def _block_ineligibility(
    *,
    manifest: ContinuityStudyManifest,
    plan: ContinuityStudyPlan,
    block: ContinuityBlock,
    delivery_by_trial: dict[str, TreatmentDeliveryRecord],
    observation_by_trial: dict[str, ContinuityObservation],
) -> PairIneligibilityReason | None:
    if any(trial.trial_id not in observation_by_trial for trial in block.trials):
        return PairIneligibilityReason.MISSING_ARM
    if any(trial.trial_id not in delivery_by_trial for trial in block.trials):
        return PairIneligibilityReason.MISSING_DELIVERY

    deliveries = tuple(delivery_by_trial[trial.trial_id] for trial in block.trials)
    observations = tuple(observation_by_trial[trial.trial_id] for trial in block.trials)
    for trial, delivery, observation in zip(
        block.trials,
        deliveries,
        observations,
        strict=True,
    ):
        if (
            delivery.manifest_content_sha256 != manifest.content_sha256
            or observation.manifest_content_sha256 != manifest.content_sha256
            or delivery.plan_content_sha256 != plan.content_sha256
            or observation.plan_content_sha256 != plan.content_sha256
            or delivery.block_id != block.block_id
            or observation.block_id != block.block_id
            or delivery.trial_id != trial.trial_id
            or observation.trial_id != trial.trial_id
            or delivery.treatment is not trial.treatment
            or observation.treatment is not trial.treatment
            or observation.delivery_content_sha256 != delivery.content_sha256
            or observation.history_snapshot_sha256 != block.history_snapshot_sha256
            or observation.event_schedule_sha256 != block.event_schedule_sha256
            or observation.logical_budget_sha256 != trial.logical_budget_sha256
            or observation.model_condition_sha256 != manifest.model_condition.content_sha256
        ):
            return PairIneligibilityReason.IDENTITY_DRIFT
        if delivery.status is TreatmentDeliveryStatus.CORRUPT:
            return PairIneligibilityReason.TREATMENT_DELIVERY_CORRUPTION
        if delivery.status is not TreatmentDeliveryStatus.DELIVERED:
            return PairIneligibilityReason.MISSING_DELIVERY
        if observation.ineligibility_reason is not None:
            return observation.ineligibility_reason

    if not _all_equal(delivery.current_state_equivalence_sha256 for delivery in deliveries) or not _all_equal(
        delivery.current_duties_sha256 for delivery in deliveries
    ):
        return PairIneligibilityReason.PAIR_IDENTITY_DRIFT
    for field_name in (
        "history_snapshot_sha256",
        "event_schedule_sha256",
        "logical_budget_sha256",
        "model_condition_sha256",
    ):
        if not _all_equal(getattr(observation, field_name) for observation in observations):
            return PairIneligibilityReason.PAIR_IDENTITY_DRIFT
    return None


def _all_equal(values: Iterable[object]) -> bool:
    selected = tuple(values)
    return bool(selected) and all(value == selected[0] for value in selected[1:])


def _paired_bootstrap_interval(
    differences: list[int],
    *,
    replicates: int,
    seed: int,
) -> ConfidenceInterval | None:
    if not differences:
        return None
    randomizer = random.Random(seed)
    sample_size = len(differences)
    means = sorted(
        fmean(differences[randomizer.randrange(sample_size)] for _ in range(sample_size)) for _ in range(replicates)
    )
    return ConfidenceInterval(
        lower=_linear_quantile(means, 0.025),
        upper=_linear_quantile(means, 0.975),
    )


def _linear_quantile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("quantile requires at least one value")
    position = (len(values) - 1) * probability
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(values) - 1)
    fraction = position - lower_index
    return values[lower_index] + (values[upper_index] - values[lower_index]) * fraction


def _classify(
    *,
    manifest: ContinuityStudyManifest,
    coverage: ContinuityCoverageReport,
    point_estimate: float | None,
    confidence_interval: ConfidenceInterval | None,
) -> ContinuityConclusion:
    if (
        not coverage.exact
        or coverage.analyzable_block_count < manifest.analysis.minimum_eligible_blocks
        or coverage.host_fault_arm_imbalance > manifest.analysis.maximum_host_fault_arm_imbalance
        or point_estimate is None
        or confidence_interval is None
    ):
        return ContinuityConclusion.COVERAGE_BLOCKED
    threshold = manifest.analysis.minimum_meaningful_effect
    if confidence_interval.upper < 0 and point_estimate <= -threshold:
        return ContinuityConclusion.SUPPORTED
    if confidence_interval.lower > 0 and point_estimate >= threshold:
        return ContinuityConclusion.REFUTED
    return ContinuityConclusion.INCONCLUSIVE
