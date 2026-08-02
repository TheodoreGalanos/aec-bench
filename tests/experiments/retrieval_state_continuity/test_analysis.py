# ABOUTME: Tests provider-free retrieval-state continuity analysis and failure rules.
# ABOUTME: Keeps generated fixture values separate from confirmatory study outcomes.

from __future__ import annotations

from aec_bench.experiments.retrieval_state_continuity import (
    FailureKind,
    PairIneligibilityReason,
    StudyConclusion,
    analyse_study,
    build_fixture_evidence,
    build_provider_free_manifest,
    build_study_plan,
)


def test_fixture_exercises_clustered_analysis_without_making_a_study_claim() -> None:
    manifest = build_provider_free_manifest()
    plan = build_study_plan(manifest)
    evidence = build_fixture_evidence(manifest=manifest, plan=plan)
    report = analyse_study(
        manifest=manifest,
        plan=plan,
        deliveries=evidence.deliveries,
        observations=evidence.observations,
    )

    assert report.gate_order == ("integrity", "validity", "endpoint")
    assert report.integrity_passed
    assert report.validity_passed
    assert report.coverage.exact
    assert report.coverage.analyzable_pair_count == 32
    assert report.coverage.eligible_world_history_count == 8
    assert report.point_estimate == 0.5
    assert report.confidence_interval is not None
    assert report.confidence_interval.lower == 0.5
    assert report.confidence_interval.upper == 0.5
    assert report.fixture_rule_result is StudyConclusion.SUPPORTED
    assert report.conclusion is StudyConclusion.ANALYSIS_FIXTURE
    assert report.provider_call_count == 0
    assert report.input_token_count == 0
    assert report.output_token_count == 0
    assert report.reported_analysis_token_count is None
    assert report.study_outcome_count == 0
    assert report.fixture_observation_count == 64
    assert not report.promotion_permitted


def test_post_delivery_agent_failure_is_an_outcome_not_an_exclusion() -> None:
    manifest = build_provider_free_manifest()
    plan = build_study_plan(manifest)
    evidence = build_fixture_evidence(manifest=manifest, plan=plan)
    original = evidence.observations[0]
    payload = original.model_dump(mode="json")
    payload.update(
        {
            "content_sha256": "",
            "failure_kind": FailureKind.SEARCH_TOOL_FAILURE,
            "epistemic_decision_failure": True,
            "ineligibility_reason": None,
        }
    )
    failed = type(original).model_validate(payload)

    assert failed.epistemic_decision_failure
    assert failed.ineligibility_reason is None


def test_pre_delivery_host_failure_is_excluded_with_a_typed_reason() -> None:
    manifest = build_provider_free_manifest()
    plan = build_study_plan(manifest)
    evidence = build_fixture_evidence(manifest=manifest, plan=plan)
    original = evidence.observations[0]
    payload = original.model_dump(mode="json")
    payload.update(
        {
            "content_sha256": "",
            "failure_kind": FailureKind.HOST_FAILURE_BEFORE_DELIVERY,
            "epistemic_decision_failure": None,
            "ineligibility_reason": PairIneligibilityReason.HOST_FAILURE,
        }
    )
    failed = type(original).model_validate(payload)

    assert failed.epistemic_decision_failure is None
    assert failed.ineligibility_reason is PairIneligibilityReason.HOST_FAILURE
