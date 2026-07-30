# ABOUTME: Tests paired continuity reduction, exact coverage, and uncertainty rules.
# ABOUTME: Keeps generated analysis fixtures separate from confirmatory conclusions.

from __future__ import annotations

import pytest

from aec_bench.experiments.stewardship_continuity import (
    ContinuityConclusion,
    ContinuityExecutionKind,
    ContinuityModelCondition,
    ContinuityObservation,
    ContinuityProviderAuthorization,
    ContinuityStudyManifest,
    ContinuityStudyPhase,
    ContinuityStudyPlan,
    ObservationSource,
    PairIneligibilityReason,
    TreatmentDeliveryRecord,
    analyse_continuity_study,
    build_continuity_plan,
    build_provider_free_fixture_evidence,
    build_provider_free_manifest,
)


def test_provider_free_fixture_exercises_paired_bootstrap_without_study_claim() -> None:
    manifest = build_provider_free_manifest()
    plan = build_continuity_plan(manifest)
    evidence = build_provider_free_fixture_evidence(manifest=manifest, plan=plan)

    report = analyse_continuity_study(
        manifest=manifest,
        plan=plan,
        deliveries=evidence.deliveries,
        observations=evidence.observations,
    )

    assert report.conclusion is ContinuityConclusion.ANALYSIS_FIXTURE
    assert report.fixture_rule_result is ContinuityConclusion.SUPPORTED
    assert report.provider_call_count == 0
    assert report.study_outcome_count == 0
    assert report.fixture_observation_count == 64
    assert report.task_reward_mutation_count == 0
    assert report.coverage.exact
    assert report.coverage.planned_trial_count == 64
    assert report.coverage.observed_trial_count == 64
    assert report.coverage.complete_block_count == 32
    assert report.coverage.analyzable_block_count == 32
    assert report.point_estimate == -0.5
    assert report.confidence_interval is not None
    assert report.confidence_interval.lower < report.point_estimate
    assert report.confidence_interval.upper < 0
    assert report.bootstrap_replicates == 20_000
    assert report.bootstrap_seed == 20_260_729
    assert (
        analyse_continuity_study(
            manifest=manifest,
            plan=plan,
            deliveries=evidence.deliveries,
            observations=evidence.observations,
        )
        == report
    )


def test_missing_arm_stays_in_coverage_and_blocks_exact_coverage() -> None:
    manifest = build_provider_free_manifest()
    plan = build_continuity_plan(manifest)
    evidence = build_provider_free_fixture_evidence(manifest=manifest, plan=plan)
    missing = evidence.observations[0]

    report = analyse_continuity_study(
        manifest=manifest,
        plan=plan,
        deliveries=evidence.deliveries,
        observations=evidence.observations[1:],
    )

    assert not report.coverage.exact
    assert report.coverage.missing_trial_ids == (missing.trial_id,)
    assert report.coverage.complete_block_count == 31
    assert report.coverage.analyzable_block_count == 31
    excluded = next(item for item in report.coverage.blocks if item.block_id == missing.block_id)
    assert excluded.ineligibility_reason is PairIneligibilityReason.MISSING_ARM
    assert report.conclusion is ContinuityConclusion.ANALYSIS_FIXTURE


def test_duplicate_or_unplanned_observations_fail_closed() -> None:
    manifest = build_provider_free_manifest()
    plan = build_continuity_plan(manifest)
    evidence = build_provider_free_fixture_evidence(manifest=manifest, plan=plan)

    with pytest.raises(ValueError, match="duplicate observation"):
        analyse_continuity_study(
            manifest=manifest,
            plan=plan,
            deliveries=evidence.deliveries,
            observations=(*evidence.observations, evidence.observations[0]),
        )

    payload = evidence.observations[0].model_dump(mode="json")
    payload["content_sha256"] = ""
    payload["trial_id"] = "unplanned-trial"
    unplanned = ContinuityObservation.model_validate(payload)
    with pytest.raises(ValueError, match="unplanned observation"):
        analyse_continuity_study(
            manifest=manifest,
            plan=plan,
            deliveries=evidence.deliveries,
            observations=(*evidence.observations[1:], unplanned),
        )


def test_evidence_input_order_does_not_change_the_report_identity() -> None:
    manifest = build_provider_free_manifest()
    plan = build_continuity_plan(manifest)
    evidence = build_provider_free_fixture_evidence(manifest=manifest, plan=plan)

    ordered = analyse_continuity_study(
        manifest=manifest,
        plan=plan,
        deliveries=evidence.deliveries,
        observations=evidence.observations,
    )
    reversed_inputs = analyse_continuity_study(
        manifest=manifest,
        plan=plan,
        deliveries=tuple(reversed(evidence.deliveries)),
        observations=tuple(reversed(evidence.observations)),
    )

    assert reversed_inputs == ordered


def test_pair_identity_drift_remains_visible_and_ineligible() -> None:
    manifest = build_provider_free_manifest()
    plan = build_continuity_plan(manifest)
    evidence = build_provider_free_fixture_evidence(manifest=manifest, plan=plan)
    selected = evidence.observations[0]
    payload = selected.model_dump(mode="json")
    payload["content_sha256"] = ""
    payload["history_snapshot_sha256"] = "f" * 64
    drifted = ContinuityObservation.model_validate(payload)
    observations = (drifted, *evidence.observations[1:])

    report = analyse_continuity_study(
        manifest=manifest,
        plan=plan,
        deliveries=evidence.deliveries,
        observations=observations,
    )

    block = next(item for item in report.coverage.blocks if item.block_id == selected.block_id)
    assert block.ineligibility_reason is PairIneligibilityReason.IDENTITY_DRIFT
    assert report.coverage.analyzable_block_count == 31


@pytest.mark.parametrize(
    "field_name",
    [
        "history_snapshot_sha256",
        "event_schedule_sha256",
        "logical_budget_sha256",
        "model_condition_sha256",
    ],
)
def test_matching_pair_values_still_fail_when_they_drift_from_the_plan(
    field_name: str,
) -> None:
    manifest = build_provider_free_manifest()
    plan = build_continuity_plan(manifest)
    evidence = build_provider_free_fixture_evidence(manifest=manifest, plan=plan)
    selected_block = plan.blocks[0]
    replacements: list[ContinuityObservation] = []
    for observation in evidence.observations[:2]:
        payload = observation.model_dump(mode="json")
        payload["content_sha256"] = ""
        payload[field_name] = "f" * 64
        replacements.append(ContinuityObservation.model_validate(payload))

    report = analyse_continuity_study(
        manifest=manifest,
        plan=plan,
        deliveries=evidence.deliveries,
        observations=(*replacements, *evidence.observations[2:]),
    )

    coverage = next(item for item in report.coverage.blocks if item.block_id == selected_block.block_id)
    assert coverage.ineligibility_reason is PairIneligibilityReason.IDENTITY_DRIFT


def test_shakedown_analysis_cannot_make_a_confirmatory_conclusion() -> None:
    manifest, plan, deliveries, observations = _build_shakedown_inputs()

    report = analyse_continuity_study(
        manifest=manifest,
        plan=plan,
        deliveries=deliveries,
        observations=observations,
    )

    assert report.phase is ContinuityStudyPhase.SHAKEDOWN
    assert report.conclusion is ContinuityConclusion.SHAKEDOWN
    assert report.fixture_rule_result is None
    assert report.study_outcome_count == 0
    assert report.input_token_count == 0
    assert report.output_token_count == 0
    assert report.spend_currency == "USD"
    assert report.spend_microunits == 0


def test_analysis_enforces_shakedown_authority_and_source() -> None:
    manifest, plan, deliveries, observations = _build_shakedown_inputs()

    outcome_payload = observations[0].model_dump(mode="json")
    outcome_payload["content_sha256"] = ""
    outcome_payload["study_outcome_eligible"] = True
    outcome = ContinuityObservation.model_validate(outcome_payload)
    with pytest.raises(ValueError, match="study outcomes"):
        analyse_continuity_study(
            manifest=manifest,
            plan=plan,
            deliveries=deliveries,
            observations=(outcome, *observations[1:]),
        )

    reward_payload = observations[0].model_dump(mode="json")
    reward_payload["content_sha256"] = ""
    reward_payload["task_reward_mutation_count"] = 1
    reward_mutation = ContinuityObservation.model_validate(reward_payload)
    with pytest.raises(ValueError, match="task reward"):
        analyse_continuity_study(
            manifest=manifest,
            plan=plan,
            deliveries=deliveries,
            observations=(reward_mutation, *observations[1:]),
        )

    provider_payload = observations[0].model_dump(mode="json")
    provider_payload["content_sha256"] = ""
    provider_payload["provider_call_count"] = 2
    provider_payload["spend_currency"] = "USD"
    provider_overrun = ContinuityObservation.model_validate(provider_payload)
    with pytest.raises(ValueError, match="provider-call authority"):
        analyse_continuity_study(
            manifest=manifest,
            plan=plan,
            deliveries=deliveries,
            observations=(provider_overrun, *observations[1:]),
        )

    token_payload = observations[0].model_dump(mode="json")
    token_payload.update(
        {
            "content_sha256": "",
            "provider_call_count": 1,
            "input_token_count": 10_001,
            "maximum_input_tokens_in_one_call": 10_001,
            "spend_currency": "USD",
        }
    )
    token_overrun = ContinuityObservation.model_validate(token_payload)
    with pytest.raises(ValueError, match="token authority"):
        analyse_continuity_study(
            manifest=manifest,
            plan=plan,
            deliveries=deliveries,
            observations=(token_overrun, *observations[1:]),
        )

    spend_payload = observations[0].model_dump(mode="json")
    spend_payload.update(
        {
            "content_sha256": "",
            "provider_call_count": 1,
            "spend_currency": "USD",
            "spend_microunits": 1_000_001,
        }
    )
    spend_overrun = ContinuityObservation.model_validate(spend_payload)
    with pytest.raises(ValueError, match="spend authority"):
        analyse_continuity_study(
            manifest=manifest,
            plan=plan,
            deliveries=deliveries,
            observations=(spend_overrun, *observations[1:]),
        )

    delivery_payload = deliveries[0].model_dump(mode="json")
    delivery_payload["content_sha256"] = ""
    delivery_payload["source"] = ObservationSource.CONFIRMATORY
    wrong_source = TreatmentDeliveryRecord.model_validate(delivery_payload)
    with pytest.raises(ValueError, match="shakedown deliveries"):
        analyse_continuity_study(
            manifest=manifest,
            plan=plan,
            deliveries=(wrong_source, *deliveries[1:]),
            observations=observations,
        )


def _build_shakedown_inputs() -> tuple[
    ContinuityStudyManifest,
    ContinuityStudyPlan,
    tuple[TreatmentDeliveryRecord, ...],
    tuple[ContinuityObservation, ...],
]:
    fixture_manifest = build_provider_free_manifest()
    fixture_plan = build_continuity_plan(fixture_manifest)
    fixture_evidence = build_provider_free_fixture_evidence(
        manifest=fixture_manifest,
        plan=fixture_plan,
    )
    model_condition = ContinuityModelCondition(
        execution_kind=ContinuityExecutionKind.PROVIDER_MODEL,
        provider_id="test-provider",
        model_id="test-model",
        adapter_id="test-adapter",
        model_configuration_sha256="a" * 64,
    )
    provider_authorization = ContinuityProviderAuthorization(
        authorization_id="test-provider-approval",
        authorized_phase=ContinuityStudyPhase.SHAKEDOWN,
        approved_by="Theo",
        model_condition_sha256=model_condition.content_sha256,
        maximum_provider_calls=1,
        maximum_input_tokens_per_call=10_000,
        maximum_output_tokens_per_call=2_000,
        maximum_total_tokens=12_000,
        spend_currency="USD",
        maximum_spend_microunits=1_000_000,
    )
    manifest_payload = fixture_manifest.model_dump(mode="json")
    manifest_payload.update(
        {
            "content_sha256": "",
            "phase": ContinuityStudyPhase.SHAKEDOWN,
            "model_condition": model_condition.model_dump(mode="json"),
            "provider_authorization": provider_authorization.model_dump(mode="json"),
            "study_outcomes_allowed": False,
        }
    )
    manifest = ContinuityStudyManifest.model_validate(manifest_payload)
    plan = build_continuity_plan(manifest)
    assert tuple(block.block_id for block in plan.blocks) == tuple(block.block_id for block in fixture_plan.blocks)

    deliveries: list[TreatmentDeliveryRecord] = []
    observations: list[ContinuityObservation] = []
    for fixture_delivery, fixture_observation in zip(
        fixture_evidence.deliveries,
        fixture_evidence.observations,
        strict=True,
    ):
        delivery_payload = fixture_delivery.model_dump(mode="json")
        delivery_payload.update(
            {
                "content_sha256": "",
                "manifest_content_sha256": manifest.content_sha256,
                "plan_content_sha256": plan.content_sha256,
                "source": ObservationSource.SHAKEDOWN,
            }
        )
        delivery = TreatmentDeliveryRecord.model_validate(delivery_payload)
        deliveries.append(delivery)

        observation_payload = fixture_observation.model_dump(mode="json")
        observation_payload.update(
            {
                "content_sha256": "",
                "manifest_content_sha256": manifest.content_sha256,
                "plan_content_sha256": plan.content_sha256,
                "source": ObservationSource.SHAKEDOWN,
                "delivery_content_sha256": delivery.content_sha256,
                "model_condition_sha256": model_condition.content_sha256,
            }
        )
        observations.append(ContinuityObservation.model_validate(observation_payload))

    return manifest, plan, tuple(deliveries), tuple(observations)
