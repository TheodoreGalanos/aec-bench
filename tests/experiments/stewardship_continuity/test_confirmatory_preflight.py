# ABOUTME: Tests provider-free confirmatory-study preparation and independent reload.
# ABOUTME: Proves all 32 real pairs are fixed before any model trajectory starts.

from __future__ import annotations

from pathlib import Path

from aec_bench.experiments.stewardship_continuity import (
    ContinuityHistoryClass,
    ObservationSource,
    prepare_asw4c_confirmatory_study,
    reload_asw4c_confirmatory_study,
)


def test_prepares_and_reloads_all_real_confirmatory_pairs(
    tmp_path: Path,
) -> None:
    root = tmp_path / "asw-4c"
    prepared = prepare_asw4c_confirmatory_study(
        root,
        authorization_id="asw-4c-test-approval",
        approved_by="Theo",
    )
    reloaded = reload_asw4c_confirmatory_study(root)

    assert reloaded.index == prepared.index
    assert reloaded.manifest == prepared.manifest
    assert reloaded.plan == prepared.plan
    assert reloaded.prepared_trials == prepared.prepared_trials
    assert reloaded.deliveries == prepared.deliveries
    assert len(prepared.plan.blocks) == 32
    assert len(prepared.plan.trials) == 64
    assert len(prepared.prepared_trials) == 64
    assert len(prepared.deliveries) == 64
    assert all(item.source is ObservationSource.CONFIRMATORY for item in prepared.deliveries)
    assert all(item.provider_call_count == 0 for item in prepared.deliveries)
    assert {item.quantized_scalar_reading for item in prepared.prepared_trials} == {
        "0.0262",
    }

    records = {item.trial_id: item for item in prepared.prepared_trials}
    deliveries = {item.trial_id: item for item in prepared.deliveries}
    for block in prepared.plan.blocks:
        pair = tuple(records[trial.trial_id] for trial in block.trials)
        pair_deliveries = tuple(deliveries[trial.trial_id] for trial in block.trials)

        assert pair[0].history_snapshot_sha256 == pair[1].history_snapshot_sha256
        assert pair[0].event_schedule_sha256 == pair[1].event_schedule_sha256
        assert pair[0].current_state_equivalence_sha256 == pair[1].current_state_equivalence_sha256
        assert pair[0].current_duties_sha256 == pair[1].current_duties_sha256
        assert pair[0].evaluation_end_seconds == pair[1].evaluation_end_seconds
        assert (
            pair_deliveries[0].current_state_equivalence_sha256 == pair_deliveries[1].current_state_equivalence_sha256
        )
        assert pair_deliveries[0].current_duties_sha256 == pair_deliveries[1].current_duties_sha256

    by_history = {
        history_class: tuple(item for item in prepared.prepared_trials if item.history_class is history_class)
        for history_class in ContinuityHistoryClass
    }
    assert all(len(items) == 32 for items in by_history.values())
    assert all(item.open_obligation_count == 0 for item in by_history[ContinuityHistoryClass.H1_STABLE_INSPECTED])
    assert all(item.open_obligation_count == 1 for item in by_history[ContinuityHistoryClass.H2_WORSENING_VERIFICATION])
