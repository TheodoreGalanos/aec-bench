# ABOUTME: Tests the real temporal study scenario and model-execution authority.
# ABOUTME: Proves fixed budgets, paired carrier isolation, and decision scoring.

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.experiments.retrieval_state_continuity import (
    StudyPhase,
    Treatment,
    build_fixture_evidence,
    build_model_manifest,
    build_provider_free_manifest,
    build_study_plan,
)
from aec_bench.experiments.retrieval_state_continuity.contracts import (
    PlannedTrial,
    StudyManifest,
    StudyObservation,
    StudyPlan,
    TreatmentDelivery,
)
from aec_bench.experiments.retrieval_state_continuity.execution import (
    ModelTrialExecution,
    _load_completed_trial_evidence,
    run_model_study,
)
from aec_bench.experiments.retrieval_state_continuity.scenario import (
    prepare_trial_scenario,
    score_trial_scenario,
)
from aec_bench.meta_harness.immutable_artifact_store import (
    EvidenceRepository,
    ImmutableArtifactIntegrityError,
)


def test_model_manifest_binds_real_execution_without_changing_the_study_design() -> None:
    shakedown = build_model_manifest(StudyPhase.SHAKEDOWN)
    confirmatory = build_model_manifest(StudyPhase.CONFIRMATORY)

    assert shakedown.study_outcomes_allowed is False
    assert confirmatory.study_outcomes_allowed is True
    assert shakedown.model_execution == confirmatory.model_execution
    assert shakedown.model_execution is not None
    assert shakedown.model_execution.model_id == "au.anthropic.claude-sonnet-4-6"
    assert shakedown.model_execution.analysis_token_reporting == "not_reported_separately_by_adapter"
    assert shakedown.model_execution.maximum_agent_turns == shakedown.budget.maximum_agent_turns
    assert shakedown.analysis == confirmatory.analysis
    assert shakedown.treatment == confirmatory.treatment
    assert shakedown.content_sha256 != confirmatory.content_sha256


def test_paired_scenario_conserves_budget_and_only_carries_unresolved_state(
    tmp_path: Path,
) -> None:
    manifest = build_model_manifest(StudyPhase.SHAKEDOWN)
    plan = build_study_plan(manifest)
    block = plan.blocks[0]
    by_treatment = {trial.treatment: trial for trial in block.trials}

    absent = prepare_trial_scenario(
        tmp_path / "absent",
        manifest=manifest,
        plan=plan,
        block=block,
        trial=by_treatment[Treatment.RETRIEVAL_STATE_ABSENT],
    )
    preserved = prepare_trial_scenario(
        tmp_path / "preserved",
        manifest=manifest,
        plan=plan,
        block=block,
        trial=by_treatment[Treatment.RETRIEVAL_STATE_PRESERVED],
    )

    assert absent.pre_handover_status == "NO_ACCESSIBLE_RESULT"
    assert preserved.pre_handover_status == "NO_ACCESSIBLE_RESULT"
    assert absent.shared_visible_input_sha256 == preserved.shared_visible_input_sha256
    assert absent.carrier.remaining_budget == preserved.carrier.remaining_budget
    assert absent.carrier.remaining_budget.calls == 2
    assert absent.carrier.access_results == ()
    assert absent.carrier.unresolved_search_ids == ()
    assert len(preserved.carrier.access_results) == 1
    assert len(preserved.carrier.unresolved_search_ids) == 1
    assert absent.session.result.snapshot.state_id == preserved.session.result.snapshot.state_id
    assert absent.session.event_schedule_sha256 == preserved.session.event_schedule_sha256
    assert absent.session.run.state.physical.calendar_seconds == manifest.evidence_available_at_seconds
    assert preserved.session.run.state.physical.calendar_seconds == manifest.evidence_available_at_seconds
    assert absent.handover.history[-1].action_type == "continue_operation"
    assert preserved.handover.history[-1].action_type == "continue_operation"


def test_scenario_scores_a_post_availability_conservative_decision(
    tmp_path: Path,
) -> None:
    manifest = build_model_manifest(StudyPhase.SHAKEDOWN)
    plan = build_study_plan(manifest)
    block = plan.blocks[0]
    trial = next(item for item in block.trials if item.treatment is Treatment.RETRIEVAL_STATE_PRESERVED)
    prepared = prepare_trial_scenario(
        tmp_path / "world",
        manifest=manifest,
        plan=plan,
        block=block,
        trial=trial,
    )

    search_payload = json.loads(
        prepared.tools.search_evidence(
            request_id="review-current-records",
            query="condition inspection obstruction indicator",
            scope="condition",
            limit=5,
        )
    )
    material = next(
        item
        for item in search_payload["receipt"]["references"]
        if item["version_id"] == manifest.material_evidence_version_id
    )
    prepared.tools.fetch_evidence(
        request_id="read-current-record",
        reference=material["opaque_reference"],
    )
    prepared.tools.request_condition_check(
        proposal_id="check-pump-a",
        reason="Check Pump A before any return-to-service decision.",
        pump_id="pump-a",
        relied_on_evidence_refs=(material["opaque_reference"],),
    )

    score = score_trial_scenario(prepared)

    assert score.epistemic_decision_failure is False
    assert score.material_evidence_acquired is True
    assert score.material_evidence_used is True
    assert score.conservative_action is True
    assert score.search_call_count == 2
    assert score.fetch_call_count == 1


def test_model_tool_rejection_is_returned_for_agent_correction(tmp_path: Path) -> None:
    manifest = build_model_manifest(StudyPhase.SHAKEDOWN)
    plan = build_study_plan(manifest)
    block = plan.blocks[0]
    prepared = prepare_trial_scenario(
        tmp_path / "world",
        manifest=manifest,
        plan=plan,
        block=block,
        trial=block.trials[0],
    )
    tool = next(
        item for item in prepared.tools.native_tools if item.__name__ == "request_post_maintenance_verification"
    )

    payload = json.loads(
        tool(
            proposal_id="invalid-reference",
            reason="Verify the current Pump A condition.",
            pump_id="pump-a",
            relied_on_evidence_refs=("evidence-0000-functional-checks-pump-a",),
        )
    )

    assert payload["status"] == "rejected"
    assert payload["error_code"] == "actor-evidence-reliance-invalid"


def test_scenario_rejects_independent_verification_without_the_material_report_action(
    tmp_path: Path,
) -> None:
    manifest = build_model_manifest(StudyPhase.SHAKEDOWN)
    plan = build_study_plan(manifest)
    block = plan.blocks[0]
    prepared = prepare_trial_scenario(
        tmp_path / "world",
        manifest=manifest,
        plan=plan,
        block=block,
        trial=block.trials[0],
    )
    prepared.tools.request_post_maintenance_verification(
        proposal_id="verify-pump-a",
        reason="Keep Pump A restricted and schedule independent verification.",
        pump_id="pump-a",
    )

    score = score_trial_scenario(prepared)

    assert score.epistemic_decision_failure is True
    assert score.conservative_action is False


def test_scenario_requires_material_report_reliance_for_the_condition_check(
    tmp_path: Path,
) -> None:
    manifest = build_model_manifest(StudyPhase.SHAKEDOWN)
    plan = build_study_plan(manifest)
    block = plan.blocks[0]
    prepared = prepare_trial_scenario(
        tmp_path / "world",
        manifest=manifest,
        plan=plan,
        block=block,
        trial=block.trials[0],
    )
    prepared.tools.request_condition_check(
        proposal_id="check-without-report",
        reason="Check the current Pump A condition.",
        pump_id="pump-a",
    )

    score = score_trial_scenario(prepared)

    assert score.epistemic_decision_failure is True
    assert score.material_evidence_used is False
    assert score.conservative_action is False


def test_verified_resume_loads_only_complete_joined_trial_evidence(tmp_path: Path) -> None:
    manifest = build_provider_free_manifest()
    plan = build_study_plan(manifest)
    fixture = build_fixture_evidence(manifest=manifest, plan=plan)
    trial = plan.trials[0]
    delivery = fixture.deliveries[0]
    observation = fixture.observations[0]
    execution = _fixture_trial_execution(manifest, plan, trial, delivery, observation)
    repository = EvidenceRepository(tmp_path / "study", host_private=True)
    repository.publish_content_addressed_model(
        collection="treatment-deliveries",
        filename="treatment-delivery.json",
        model=delivery,
        adapter=TypeAdapter(type(delivery)),
    )
    repository.publish_content_addressed_model(
        collection="observations",
        filename="observation.json",
        model=observation,
        adapter=TypeAdapter(type(observation)),
    )
    repository.publish_content_addressed_model(
        collection="trial-executions",
        filename="trial-execution.json",
        model=execution,
        adapter=TypeAdapter(ModelTrialExecution),
    )

    progress = _load_completed_trial_evidence(
        repository=repository,
        manifest=manifest,
        plan=plan,
        selected_trials=(trial,),
    )

    assert progress.deliveries == (delivery,)
    assert progress.observations == (observation,)
    assert progress.executions == (execution,)
    assert progress.completed_trial_ids == frozenset({trial.trial_id})


def test_verified_resume_rejects_incomplete_published_trial_evidence(tmp_path: Path) -> None:
    manifest = build_provider_free_manifest()
    plan = build_study_plan(manifest)
    fixture = build_fixture_evidence(manifest=manifest, plan=plan)
    trial = plan.trials[0]
    delivery = fixture.deliveries[0]
    repository = EvidenceRepository(tmp_path / "study", host_private=True)
    repository.publish_content_addressed_model(
        collection="treatment-deliveries",
        filename="treatment-delivery.json",
        model=delivery,
        adapter=TypeAdapter(type(delivery)),
    )

    with pytest.raises(ImmutableArtifactIntegrityError, match="incomplete published trial evidence"):
        _load_completed_trial_evidence(
            repository=repository,
            manifest=manifest,
            plan=plan,
            selected_trials=(trial,),
        )


def test_verified_resume_stops_before_repeating_an_interrupted_trial(tmp_path: Path) -> None:
    manifest = build_model_manifest(StudyPhase.SHAKEDOWN)
    plan = build_study_plan(manifest)
    trial = plan.blocks[0].trials[0]
    destination = tmp_path / "study"
    interrupted = destination / "runs" / f"{trial.execution_position:03d}-{trial.trial_id}"
    interrupted.mkdir(parents=True, mode=0o700)
    destination.chmod(0o700)

    with pytest.raises(ImmutableArtifactIntegrityError, match="requires explicit recovery"):
        run_model_study(destination, phase=StudyPhase.SHAKEDOWN)


def _fixture_trial_execution(
    manifest: StudyManifest,
    plan: StudyPlan,
    trial: PlannedTrial,
    delivery: TreatmentDelivery,
    observation: StudyObservation,
) -> ModelTrialExecution:
    digest = canonical_content_sha256({"fixture": "verified-resume"})
    assert delivery.delivered_carrier_sha256 is not None
    return ModelTrialExecution(
        manifest_content_sha256=manifest.content_sha256,
        plan_content_sha256=plan.content_sha256,
        block_id=trial.block_id,
        trial_id=trial.trial_id,
        treatment=trial.treatment,
        phase=manifest.phase,
        provider_id="provider-free-fixture",
        credential_profile_id="no-credentials",
        model_id="provider-free-fixture",
        resolved_model="provider-free-fixture",
        adapter_id="provider-free-fixture",
        adapter_status="completed",
        adapter_failure_kind=None,
        start_state_sha256=digest,
        final_state_sha256=digest,
        event_schedule_sha256=digest,
        structured_handover_sha256=digest,
        delivered_carrier_sha256=delivery.delivered_carrier_sha256,
        shared_visible_input_sha256=digest,
        output_sha256=digest,
        conversation_sha256=digest,
        trajectory_sha256=digest,
        provider_call_count=0,
        agent_turn_count=observation.agent_turn_count,
        input_token_count=0,
        output_token_count=0,
        reported_analysis_token_count=None,
        total_token_count=0,
        maximum_input_tokens_in_one_call=0,
        maximum_output_tokens_in_one_call=0,
        spend_microunits=0,
        search_call_count=observation.search_call_count,
        fetch_call_count=observation.fetch_call_count,
        material_evidence_acquired=observation.material_evidence_acquired,
        material_evidence_used=observation.material_evidence_used,
        conservative_action=observation.conservative_action,
        epistemic_decision_failure=observation.epistemic_decision_failure,
        world_verification_valid=True,
        temporal_verification_valid=True,
    )
