# ABOUTME: Tests the real matched histories and hidden endpoints for ASW-4C.
# ABOUTME: Uses the durable pump-station world without making provider calls.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from aec_bench.experiments.stewardship_continuity import (
    ASW4C_MODEL_ID,
    ASW4C_STUDY_GENERATION_ID,
    ContinuityExecutionKind,
    ContinuityHistoryClass,
    ContinuityStudyPhase,
    ContinuityTreatment,
    EvaluationWindow,
    PreparedAsw4cHistory,
    advance_asw4c_to_evaluation_end,
    asw4c_world_continuity_failure,
    build_asw4c_confirmatory_manifest,
    calculate_asw4c_spend_microunits,
    confirmatory_execution,
    maximum_asw4c_spend_microunits,
    prepare_asw4c_history,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    ContinueOperation,
    RequestVerification,
)


def _current(prepared: PreparedAsw4cHistory) -> dict[str, Any]:
    payload = cast(
        dict[str, Any],
        json.loads(prepared.session.observe_pump_station()),
    )
    return cast(dict[str, Any], payload["current_state"])


def test_confirmatory_manifest_binds_the_exact_proposed_phase_limits() -> None:
    manifest = build_asw4c_confirmatory_manifest(
        authorization_id="asw-4c-test-approval",
        approved_by="Theo",
    )
    authority = manifest.provider_authorization

    assert manifest.study_generation_id == ASW4C_STUDY_GENERATION_ID
    assert manifest.phase is ContinuityStudyPhase.CONFIRMATORY
    assert manifest.study_outcomes_allowed
    assert manifest.model_condition.execution_kind is ContinuityExecutionKind.PROVIDER_MODEL
    assert manifest.model_condition.provider_id == "amazon-bedrock-au-geographic"
    assert manifest.model_condition.model_id == ASW4C_MODEL_ID
    assert manifest.model_condition.adapter_id == "tool_loop"
    assert authority is not None
    assert authority.approved_by == "Theo"
    assert authority.maximum_provider_calls == 1_024
    assert authority.maximum_input_tokens_per_call == 500_000
    assert authority.maximum_output_tokens_per_call == 2_048
    assert authority.maximum_total_tokens == 2_560_000
    assert authority.spend_currency == "USD"
    assert authority.maximum_spend_microunits == 37_000_000
    assert maximum_asw4c_spend_microunits() == 36_130_407
    assert maximum_asw4c_spend_microunits() < authority.maximum_spend_microunits
    assert (
        calculate_asw4c_spend_microunits(
            input_tokens=462_848,
            output_tokens=2_097_152,
        )
        == 36_130_407
    )


def test_real_h1_and_h2_histories_match_the_quantized_scalar(
    tmp_path: Path,
) -> None:
    h1 = prepare_asw4c_history(
        tmp_path / "h1",
        history_slot_id="h1_stable_inspected-01",
        history_class=ContinuityHistoryClass.H1_STABLE_INSPECTED,
        evaluation_window=EvaluationWindow.THREE_DIAGNOSTIC_PERIODS,
        treatment=ContinuityTreatment.CURRENT_ACTOR_VIEW,
    )
    h2 = prepare_asw4c_history(
        tmp_path / "h2",
        history_slot_id="h2_worsening_verification-01",
        history_class=ContinuityHistoryClass.H2_WORSENING_VERIFICATION,
        evaluation_window=EvaluationWindow.THREE_DIAGNOSTIC_PERIODS,
        treatment=ContinuityTreatment.CURRENT_ACTOR_VIEW,
    )
    h1_current = _current(h1)
    h2_current = _current(h2)

    assert h1.verification.valid
    assert h2.verification.valid
    assert h1_current["observation"]["active_pump_flow_m3_s"] == "0.0262"
    assert h2_current["observation"]["active_pump_flow_m3_s"] == "0.0262"
    assert h1_current["observation"]["active_pump_flow_m3_s"] == h2_current["observation"]["active_pump_flow_m3_s"]
    assert h1_current["restrictions"] == []
    assert h1_current["obligations"] == []
    assert [item["kind"] for item in h1_current["evidence"]] == ["inspection"]
    assert [item["kind"] for item in h2_current["restrictions"]] == [
        "post_maintenance_run_in",
    ]
    assert [item["kind"] for item in h2_current["obligations"]] == [
        "post_maintenance_verification",
    ]


def test_independent_treatment_branches_have_equal_state_and_duties(
    tmp_path: Path,
) -> None:
    prepared = tuple(
        prepare_asw4c_history(
            tmp_path / treatment.value,
            history_slot_id="h2_worsening_verification-02",
            history_class=ContinuityHistoryClass.H2_WORSENING_VERIFICATION,
            evaluation_window=EvaluationWindow.FOUR_DIAGNOSTIC_PERIODS,
            treatment=treatment,
        )
        for treatment in ContinuityTreatment
    )

    assert prepared[0].history_snapshot_sha256 == prepared[1].history_snapshot_sha256
    assert prepared[0].event_schedule_sha256 == prepared[1].event_schedule_sha256
    assert prepared[0].current_state_equivalence_sha256 == prepared[1].current_state_equivalence_sha256
    assert prepared[0].current_duties_sha256 == prepared[1].current_duties_sha256
    assert prepared[0].evaluation_end_seconds == prepared[1].evaluation_end_seconds
    assert prepared[0].handover is None
    assert prepared[1].handover is not None
    assert prepared[0].carrier_content_sha256 != prepared[1].carrier_content_sha256


def test_hidden_endpoint_distinguishes_unresolved_and_completed_verification(
    tmp_path: Path,
) -> None:
    unresolved = prepare_asw4c_history(
        tmp_path / "unresolved",
        history_slot_id="h2_worsening_verification-03",
        history_class=ContinuityHistoryClass.H2_WORSENING_VERIFICATION,
        evaluation_window=EvaluationWindow.THREE_DIAGNOSTIC_PERIODS,
        treatment=ContinuityTreatment.CURRENT_ACTOR_VIEW,
    )
    completed = prepare_asw4c_history(
        tmp_path / "completed",
        history_slot_id="h2_worsening_verification-03",
        history_class=ContinuityHistoryClass.H2_WORSENING_VERIFICATION,
        evaluation_window=EvaluationWindow.THREE_DIAGNOSTIC_PERIODS,
        treatment=ContinuityTreatment.STRUCTURED_HANDOVER,
    )

    completed.session.request_post_maintenance_verification(
        "asw-4c-model-verification",
        "Discharge the open independent verification duty.",
        "pump-a",
    )
    advance_asw4c_to_evaluation_end(unresolved)
    advance_asw4c_to_evaluation_end(completed)

    assert unresolved.session.actor_view.current_state.calendar_seconds == unresolved.evaluation_end_seconds
    assert completed.session.actor_view.current_state.calendar_seconds == completed.evaluation_end_seconds
    assert asw4c_world_continuity_failure(unresolved.session) is True
    assert asw4c_world_continuity_failure(completed.session) is False
    assert unresolved.session.verify().valid
    assert completed.session.verify().valid


def test_h1_reaches_hidden_endpoint_without_a_continuity_failure(
    tmp_path: Path,
) -> None:
    prepared = prepare_asw4c_history(
        tmp_path / "h1",
        history_slot_id="h1_stable_inspected-04",
        history_class=ContinuityHistoryClass.H1_STABLE_INSPECTED,
        evaluation_window=EvaluationWindow.FOUR_DIAGNOSTIC_PERIODS,
        treatment=ContinuityTreatment.STRUCTURED_HANDOVER,
    )

    advance_asw4c_to_evaluation_end(prepared)

    assert prepared.session.actor_view.current_state.calendar_seconds == prepared.evaluation_end_seconds
    assert asw4c_world_continuity_failure(prepared.session) is False
    assert prepared.session.verify().valid


def test_world_owned_blocked_operation_is_an_early_continuity_failure(
    tmp_path: Path,
) -> None:
    prepared = prepare_asw4c_history(
        tmp_path / "h1-blocked",
        history_slot_id="h1_stable_inspected-05",
        history_class=ContinuityHistoryClass.H1_STABLE_INSPECTED,
        evaluation_window=EvaluationWindow.FOUR_DIAGNOSTIC_PERIODS,
        treatment=ContinuityTreatment.STRUCTURED_HANDOVER,
    )
    prepared.session.request_conditional_deferral(
        "asw-4c-model-deferral",
        "Create the declared transfer-then-isolate restriction.",
        "pump-b",
    )

    advance_asw4c_to_evaluation_end(prepared)

    assert prepared.session.actor_view.current_state.calendar_seconds < prepared.evaluation_end_seconds
    assert prepared.session.actor_history[-1].proposal_id == "asw-4c-host-window-01"
    assert prepared.session.actor_history[-1].execution == "cancelled"
    assert asw4c_world_continuity_failure(prepared.session) is True
    assert prepared.session.verify().valid


def test_forensic_prefix_stops_before_a_stale_parallel_commit(
    tmp_path: Path,
) -> None:
    root = tmp_path / "h1-concurrent"
    prepared = prepare_asw4c_history(
        root,
        history_slot_id="h1_stable_inspected-06",
        history_class=ContinuityHistoryClass.H1_STABLE_INSPECTED,
        evaluation_window=EvaluationWindow.FOUR_DIAGNOSTIC_PERIODS,
        treatment=ContinuityTreatment.CURRENT_ACTOR_VIEW,
    )
    start_snapshot = prepared.session.result.snapshot
    information_set = prepared.session._information_set
    continued = ContinueOperation(
        context=prepared.session._proposal_context(
            "parallel-continue",
            "Create one valid transition from the shared view.",
        ),
    )
    verification = RequestVerification(
        context=prepared.session._proposal_context(
            "parallel-verification",
            "Create one stale transition from the shared view.",
        ),
        pump_id="pump-b",
    )
    prepared.session._run.apply(
        continued,
        information_set=information_set,
    )
    prepared.session._run.apply(
        verification,
        information_set=information_set,
    )

    world_repository = confirmatory_execution.PumpStationWorldRunRepository(
        root / "world-run",
    )
    forensics = confirmatory_execution._forensic_world_prefix(
        repository=world_repository,
        start_snapshot=start_snapshot,
    )
    evaluation = confirmatory_execution._evaluate_forensic_world_prefix(
        world_root=root / "world-run",
        snapshot=forensics.last_valid_snapshot,
    )

    assert forensics.selected_snapshot.sequence == 7
    assert forensics.last_valid_snapshot.sequence == 6
    assert forensics.invalid_commit.sequence == 7
    assert set(forensics.selected_post_start_proposal_ids) == {
        "parallel-continue",
        "parallel-verification",
    }
    assert evaluation.evidence.terminal_state_id == forensics.last_valid_snapshot.state_id
