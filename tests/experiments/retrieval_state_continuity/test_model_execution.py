# ABOUTME: Tests the real temporal study scenario and model-execution authority.
# ABOUTME: Proves fixed budgets, paired carrier isolation, and decision scoring.

from __future__ import annotations

import json
from pathlib import Path

from aec_bench.experiments.retrieval_state_continuity import (
    StudyPhase,
    Treatment,
    build_model_manifest,
    build_study_plan,
)
from aec_bench.experiments.retrieval_state_continuity.scenario import (
    prepare_trial_scenario,
    score_trial_scenario,
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

    prepared.tools.continue_operation(
        proposal_id="advance-to-window",
        reason="Advance to the next declared decision point.",
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


def test_scenario_accepts_independent_verification_as_conservative_action(
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
    prepared.tools.continue_operation(
        proposal_id="advance-to-window",
        reason="Advance to the next declared decision point.",
    )
    prepared.tools.request_post_maintenance_verification(
        proposal_id="verify-pump-a",
        reason="Keep Pump A restricted and schedule independent verification.",
        pump_id="pump-a",
    )

    score = score_trial_scenario(prepared)

    assert score.epistemic_decision_failure is False
    assert score.conservative_action is True
