# ABOUTME: Tests the exact shakedown authority, price ceiling, and H2 handover history.
# ABOUTME: Uses the real pump-station state machine without making a provider call.

from __future__ import annotations

import json
from pathlib import Path

from aec_bench.experiments.stewardship_continuity import (
    ASW4B_MODEL_ID,
    ASW4B_STUDY_GENERATION_ID,
    ContinuityExecutionKind,
    ContinuityHistoryClass,
    ContinuityStudyPhase,
    ContinuityTreatment,
    build_asw4b_shakedown_manifest,
    build_continuity_plan,
    calculate_asw4b_spend_microunits,
    maximum_asw4b_spend_microunits,
    prepare_asw4b_h2_history,
    select_asw4b_shakedown_trial,
)


def test_shakedown_manifest_matches_approved_authority() -> None:
    manifest = build_asw4b_shakedown_manifest()
    authority = manifest.provider_authorization

    assert manifest.study_generation_id == ASW4B_STUDY_GENERATION_ID
    assert manifest.phase is ContinuityStudyPhase.SHAKEDOWN
    assert manifest.model_condition.execution_kind is ContinuityExecutionKind.PROVIDER_MODEL
    assert manifest.model_condition.provider_id == "amazon-bedrock-au-geographic"
    assert manifest.model_condition.model_id == ASW4B_MODEL_ID
    assert manifest.model_condition.adapter_id == "tool_loop"
    assert authority is not None
    assert authority.approved_by == "Theo"
    assert authority.maximum_provider_calls == 16
    assert authority.maximum_input_tokens_per_call == 500_000
    assert authority.maximum_output_tokens_per_call == 2_048
    assert authority.maximum_total_tokens == 500_000
    assert authority.spend_currency == "USD"
    assert authority.maximum_spend_microunits == 2_500_000
    assert manifest.logical_budget.max_model_turns == 16
    assert manifest.logical_budget.max_agent_proposals == 12
    assert manifest.logical_budget.max_host_commands == 32
    assert manifest.logical_budget.fresh_agent_handovers == 1
    assert not manifest.study_outcomes_allowed
    assert not manifest.task_reward_mutation_allowed


def test_shakedown_price_ceiling_stays_inside_approved_spend() -> None:
    assert maximum_asw4b_spend_microunits() == 2_082_538
    assert maximum_asw4b_spend_microunits() < 2_500_000
    assert (
        calculate_asw4b_spend_microunits(
            input_tokens=467_232,
            output_tokens=32_768,
        )
        == 2_082_538
    )


def test_h2_history_reaches_exact_half_period_handover_with_live_duties(
    tmp_path: Path,
) -> None:
    prepared = prepare_asw4b_h2_history(tmp_path / "history")
    current = json.loads(prepared.session.observe_pump_station())["current_state"]

    assert prepared.verification.valid
    assert prepared.history_class is ContinuityHistoryClass.H2_WORSENING_VERIFICATION
    assert (
        prepared.handover.created_at_seconds
        == prepared.provisional_closure_seconds + prepared.diagnostic_period_seconds // 2
    )
    assert prepared.handover.to_tenure_id == "asw-4b-fresh-tenure"
    assert prepared.handover.from_tenure_id == "asw-4b-history-tenure"
    assert len(prepared.handover.history) == 11
    assert prepared.history_snapshot_sha256 == prepared.session.result.snapshot.state_id
    assert len(prepared.event_schedule_sha256) == 64
    assert [item["kind"] for item in current["restrictions"]] == [
        "post_maintenance_run_in",
    ]
    assert [item["kind"] for item in current["obligations"]] == [
        "post_maintenance_verification",
    ]
    assert current["obligations"][0]["due_calendar_seconds"] - current["calendar_seconds"] == (
        3 * prepared.diagnostic_period_seconds // 2
    )
    assert current["work_orders"][0]["status"] == "provisionally_closed"


def test_shakedown_plan_selects_only_the_real_h2_structured_handover(
    tmp_path: Path,
) -> None:
    prepared = prepare_asw4b_h2_history(tmp_path / "history")
    manifest = build_asw4b_shakedown_manifest()
    plan = build_continuity_plan(
        manifest,
        history_snapshot_sha256_by_slot={
            "h2_worsening_verification-01": prepared.history_snapshot_sha256,
        },
        event_schedule_sha256_by_slot={
            "h2_worsening_verification-01": prepared.event_schedule_sha256,
        },
    )

    block, trial = select_asw4b_shakedown_trial(plan)

    assert block.history_class is ContinuityHistoryClass.H2_WORSENING_VERIFICATION
    assert block.repetition == 1
    assert block.history_snapshot_sha256 == prepared.history_snapshot_sha256
    assert block.event_schedule_sha256 == prepared.event_schedule_sha256
    assert trial.treatment is ContinuityTreatment.STRUCTURED_HANDOVER
    assert trial.block_id == block.block_id
