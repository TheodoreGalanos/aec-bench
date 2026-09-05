# ABOUTME: Tests delayed pump obligations and public handover completeness with canonical replay.
# ABOUTME: Keeps operational consequences separate from the validity of execution evidence.

from pathlib import Path

from aec_bench.experimentation.engineering_decisions.pump_continuation import run_pump_continuation
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import PumpStationEpisodeHost
from aec_bench.worlds.stewardship.wastewater_pump_station.handover import (
    PumpHandover,
    assess_pump_handover,
    required_pump_handover,
)


def test_same_opening_service_can_leave_different_future_obligations(tmp_path: Path) -> None:
    complete = run_pump_continuation(tmp_path / "complete")
    omitted = run_pump_continuation(tmp_path / "omitted", omit_verification_work=True)
    assert complete["opening_state_id"] == omitted["opening_state_id"]
    assert complete["immediate_service"] == omitted["immediate_service"]
    assert complete["horizon_seconds"] == omitted["horizon_seconds"]
    assert complete["replay_valid"] and omitted["replay_valid"]
    assert complete["evaluation"]["valid"] and omitted["evaluation"]["valid"]
    assert complete["handover_complete"] and not omitted["handover_complete"]
    good = complete["evaluation"]["metrics"]["terminal_liability"]
    bad = omitted["evaluation"]["metrics"]["terminal_liability"]
    assert good["overdue_calendar_seconds"] == 0
    assert bad["overdue_calendar_seconds"] > 0
    assert bad["unresolved_verification_count"] > good["unresolved_verification_count"]
    # A new host reads canonical state. Public handover evidence is independently assessable.
    observation = PumpStationEpisodeHost(tmp_path / "complete").observe()
    handover = required_pump_handover(observation)
    assert assess_pump_handover(observation, handover).complete
    tampered = PumpHandover(source_view_id="stale", facts={**handover.facts, "calendar_seconds": 0, "approval": True})
    assessment = assess_pump_handover(observation, tampered)
    assert not assessment.source_current
    assert assessment.contradicted == ("calendar_seconds",)
    assert assessment.invented == ("approval",)
