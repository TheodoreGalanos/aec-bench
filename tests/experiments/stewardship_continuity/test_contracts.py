# ABOUTME: Tests the frozen provider-free stewardship-continuity study contracts.
# ABOUTME: Proves exact budgets, pairing, counterbalancing, and fixture ineligibility.

from __future__ import annotations

from collections import Counter

import pytest
from pydantic import ValidationError

import aec_bench.experiments.stewardship_continuity as continuity
from aec_bench.experiments.stewardship_continuity import (
    ContinuityConclusion,
    ContinuityFailureKind,
    ContinuityHistoryClass,
    ContinuityObservation,
    ContinuityStudyPhase,
    ContinuityStudyPlan,
    ContinuityStudyReport,
    ContinuityTreatment,
    EvaluationWindow,
    ObservationSource,
    PairIneligibilityReason,
    TreatmentDeliveryStatus,
    analyse_continuity_study,
    build_continuity_plan,
    build_provider_free_fixture_evidence,
    build_provider_free_manifest,
)


def test_provider_free_manifest_freezes_charter_design_and_blocks_outcomes() -> None:
    manifest = build_provider_free_manifest()

    assert manifest.phase is ContinuityStudyPhase.ANALYSIS_FIXTURE
    assert manifest.charter_revision == "ASW-0C-3"
    assert manifest.profile_id == "AU-NSW-LH-SYN-SPS-v1"
    assert manifest.generation_id == "738bc2b31f40ae7ea7831a54826c10c7e1f8084e64a6c0e0883bc6290aa84c8e"
    assert manifest.package_content_id == "642da8bdfad63d7324e0c5886f1f8f3866c9a6bd25f165fa2a5937d68e8a5e16"
    assert manifest.adaptation_mode == "none"
    assert manifest.event_schedule_revision == "pump-station-continuity-event-schedule.v1"
    assert manifest.verifier_revision == "pump-station-stewardship-replay-verifier.v1"
    assert len(manifest.harness_configuration_sha256) == 64
    assert len(manifest.treatment_delivery_configuration_sha256) == 64
    assert manifest.model_condition.execution_kind is continuity.ContinuityExecutionKind.ANALYSIS_FIXTURE
    assert manifest.model_condition.provider_id is None
    assert manifest.model_condition.model_id is None
    assert manifest.model_condition.adapter_id is None
    assert manifest.provider_authorization is None
    assert manifest.provider_calls_allowed == 0
    assert not manifest.study_outcomes_allowed
    assert not manifest.task_reward_mutation_allowed
    assert manifest.logical_budget.max_model_turns == 16
    assert manifest.logical_budget.max_agent_proposals == 12
    assert manifest.logical_budget.max_host_commands == 32
    assert manifest.logical_budget.fresh_agent_handovers == 1
    assert not manifest.logical_budget.temporal_retrieval_allowed
    assert not manifest.logical_budget.evaluation_window_visible
    assert manifest.analysis.bootstrap_replicates == 20_000
    assert manifest.analysis.bootstrap_seed == 20_260_729
    assert manifest.analysis.minimum_meaningful_effect == 0.25
    assert manifest.analysis.minimum_eligible_blocks == 28
    assert manifest.analysis.maximum_host_fault_arm_imbalance == 2


def test_plan_has_exact_paired_coverage_and_counterbalanced_order() -> None:
    manifest = build_provider_free_manifest()
    plan = build_continuity_plan(manifest)

    assert plan.manifest_content_sha256 == manifest.content_sha256
    assert len(plan.blocks) == 32
    assert len(plan.trials) == 64
    assert len({trial.trial_id for trial in plan.trials}) == 64
    assert tuple(trial for block in plan.blocks for trial in block.trials) == plan.trials

    history_counts = Counter(block.history_class for block in plan.blocks)
    assert history_counts == {
        ContinuityHistoryClass.H1_STABLE_INSPECTED: 16,
        ContinuityHistoryClass.H2_WORSENING_VERIFICATION: 16,
    }
    for history_class in ContinuityHistoryClass:
        selected = [block for block in plan.blocks if block.history_class is history_class]
        assert Counter(block.evaluation_window for block in selected) == {
            EvaluationWindow.THREE_DIAGNOSTIC_PERIODS: 8,
            EvaluationWindow.FOUR_DIAGNOSTIC_PERIODS: 8,
        }
        assert Counter(block.trials[0].treatment for block in selected) == {
            ContinuityTreatment.CURRENT_ACTOR_VIEW: 8,
            ContinuityTreatment.STRUCTURED_HANDOVER: 8,
        }
        for evaluation_window in EvaluationWindow:
            window_blocks = [block for block in selected if block.evaluation_window is evaluation_window]
            assert Counter(block.trials[0].treatment for block in window_blocks) == {
                ContinuityTreatment.CURRENT_ACTOR_VIEW: 4,
                ContinuityTreatment.STRUCTURED_HANDOVER: 4,
            }

    assert {tuple(trial.treatment for trial in block.trials) for block in plan.blocks} == {
        (
            ContinuityTreatment.CURRENT_ACTOR_VIEW,
            ContinuityTreatment.STRUCTURED_HANDOVER,
        ),
        (
            ContinuityTreatment.STRUCTURED_HANDOVER,
            ContinuityTreatment.CURRENT_ACTOR_VIEW,
        ),
    }
    assert {trial.evaluation_window_seconds for trial in plan.trials} == {
        86_400,
        115_200,
    }
    assert all(len(block.history_snapshot_sha256) == 64 for block in plan.blocks)
    assert all(len(block.event_schedule_sha256) == 64 for block in plan.blocks)
    assert build_continuity_plan(manifest) == plan


def test_plan_rejects_a_missing_trial_even_with_a_recomputed_content_id() -> None:
    plan = build_continuity_plan(build_provider_free_manifest())
    payload = plan.model_dump(mode="json")
    payload["content_sha256"] = ""
    payload["trials"] = payload["trials"][:-1]

    with pytest.raises(ValidationError, match="ordered block trials"):
        ContinuityStudyPlan.model_validate(payload)


def test_provider_free_evidence_is_explicitly_not_a_study_outcome() -> None:
    manifest = build_provider_free_manifest()
    plan = build_continuity_plan(manifest)
    evidence = build_provider_free_fixture_evidence(manifest=manifest, plan=plan)

    assert len(evidence.deliveries) == 64
    assert len(evidence.observations) == 64
    assert {delivery.provider_call_count for delivery in evidence.deliveries} == {0}
    assert {delivery.status for delivery in evidence.deliveries} == {
        TreatmentDeliveryStatus.DELIVERED,
    }
    assert {observation.source for observation in evidence.observations} == {
        ObservationSource.GENERATED_ANALYSIS_FIXTURE,
    }
    assert {observation.input_token_count for observation in evidence.observations} == {0}
    assert {observation.output_token_count for observation in evidence.observations} == {0}
    assert {observation.spend_microunits for observation in evidence.observations} == {0}
    assert {observation.spend_currency for observation in evidence.observations} == {None}
    assert not any(observation.study_outcome_eligible for observation in evidence.observations)
    assert all(observation.continuity_failure is not None for observation in evidence.observations)

    for block in plan.blocks:
        deliveries = [delivery for delivery in evidence.deliveries if delivery.block_id == block.block_id]
        assert len(deliveries) == 2
        assert len({delivery.current_state_equivalence_sha256 for delivery in deliveries}) == 1
        assert len({delivery.carrier_content_sha256 for delivery in deliveries}) == 2
        assert len({delivery.current_duties_sha256 for delivery in deliveries}) == 1


def test_failure_taxonomy_separates_host_faults_from_post_delivery_failures() -> None:
    manifest = build_provider_free_manifest()
    plan = build_continuity_plan(manifest)
    evidence = build_provider_free_fixture_evidence(manifest=manifest, plan=plan)
    observation = evidence.observations[0]

    timeout_payload = observation.model_dump(mode="json")
    timeout_payload["content_sha256"] = ""
    timeout_payload["failure_kind"] = ContinuityFailureKind.MODEL_TIMEOUT
    timeout_payload["continuity_failure"] = True
    timeout_payload["ineligibility_reason"] = None
    timeout = ContinuityObservation.model_validate(timeout_payload)
    assert timeout.continuity_failure
    assert timeout.ineligibility_reason is None

    host_payload = observation.model_dump(mode="json")
    host_payload["content_sha256"] = ""
    host_payload["failure_kind"] = ContinuityFailureKind.HOST_FAILURE_AFTER_DELIVERY
    host_payload["continuity_failure"] = None
    host_payload["ineligibility_reason"] = PairIneligibilityReason.HOST_FAILURE
    host_fault = ContinuityObservation.model_validate(host_payload)
    assert host_fault.continuity_failure is None
    assert host_fault.ineligibility_reason is PairIneligibilityReason.HOST_FAILURE

    invalid_payload = observation.model_dump(mode="json")
    invalid_payload["content_sha256"] = ""
    invalid_payload["failure_kind"] = ContinuityFailureKind.MODEL_EMPTY_OUTPUT
    invalid_payload["continuity_failure"] = None
    with pytest.raises(ValidationError, match="must count as continuity failure"):
        ContinuityObservation.model_validate(invalid_payload)


def test_model_phase_requires_exact_provider_model_token_and_spend_authority() -> None:
    model_condition = continuity.ContinuityModelCondition(
        execution_kind=continuity.ContinuityExecutionKind.PROVIDER_MODEL,
        provider_id="test-provider",
        model_id="test-model",
        adapter_id="test-adapter",
        model_configuration_sha256="a" * 64,
    )
    provider_authorization = continuity.ContinuityProviderAuthorization(
        authorization_id="test-shakedown-approval",
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
    payload = build_provider_free_manifest().model_dump(mode="json")
    payload.update(
        {
            "content_sha256": "",
            "phase": ContinuityStudyPhase.SHAKEDOWN,
            "model_condition": model_condition.model_dump(mode="json"),
            "provider_authorization": provider_authorization.model_dump(mode="json"),
            "study_outcomes_allowed": False,
        }
    )

    manifest = continuity.ContinuityStudyManifest.model_validate(payload)

    assert manifest.provider_calls_allowed == 1
    assert manifest.provider_authorization == provider_authorization

    mismatched_authorization_payload = provider_authorization.model_dump(mode="json")
    mismatched_authorization_payload["content_sha256"] = ""
    mismatched_authorization_payload["model_condition_sha256"] = "f" * 64
    mismatched_payload = {
        **payload,
        "provider_authorization": mismatched_authorization_payload,
    }
    with pytest.raises(ValidationError, match="model condition"):
        continuity.ContinuityStudyManifest.model_validate(mismatched_payload)


@pytest.mark.parametrize(
    ("phase", "conclusion"),
    [
        (ContinuityStudyPhase.SHAKEDOWN, ContinuityConclusion.SUPPORTED),
        (ContinuityStudyPhase.CONFIRMATORY, ContinuityConclusion.ANALYSIS_FIXTURE),
    ],
)
def test_report_rejects_a_conclusion_from_another_phase(
    phase: ContinuityStudyPhase,
    conclusion: ContinuityConclusion,
) -> None:
    manifest = build_provider_free_manifest()
    plan = build_continuity_plan(manifest)
    evidence = build_provider_free_fixture_evidence(manifest=manifest, plan=plan)
    report = analyse_continuity_study(
        manifest=manifest,
        plan=plan,
        deliveries=evidence.deliveries,
        observations=evidence.observations,
    )
    payload = report.model_dump(mode="json")
    payload.update(
        {
            "content_sha256": "",
            "phase": phase,
            "conclusion": conclusion,
            "fixture_rule_result": None,
        }
    )

    with pytest.raises(ValidationError, match=phase.value):
        ContinuityStudyReport.model_validate(payload)
