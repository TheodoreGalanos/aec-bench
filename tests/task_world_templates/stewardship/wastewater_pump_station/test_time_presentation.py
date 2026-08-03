# ABOUTME: Tests current actor-readable pump dates and durations.
# ABOUTME: Keeps exact replay seconds authoritative without historical projection branches.

from __future__ import annotations

from pathlib import Path

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.episode_runtime import (
    PumpStationEpisodeHost,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.time_presentation import (
    format_calendar_duration,
    format_operating_duration,
    pump_station_datetime,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)


def test_current_time_formatting_is_exact() -> None:
    assert pump_station_datetime(0) == "2026-01-01T00:00:00+11:00"
    assert format_calendar_duration(90_061) == "1 day 1 hour 1 minute 1 second"
    assert format_operating_duration(7_261) == "2 operating hours 1 operating minute 1 operating second"


def test_current_actor_view_presents_the_replay_clock(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="time-run",
        episode_id="time-episode",
        world_branch_id="time-branch",
    )

    view = PumpStationEpisodeHost(root).observe().view

    assert view["calendar_seconds"] == run.state.calendar_seconds
    assert view["current_datetime"] == pump_station_datetime(run.state.calendar_seconds)
    assert view["time_zone"] == "Australia/Sydney"
