# ABOUTME: Converts exact pump-station clocks into actor-readable dates and durations.
# ABOUTME: Keeps replay seconds authoritative while presenting local calendar and runtime meaning.

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationObligationStatus,
    PumpStationProcessStatus,
    PumpStationStewardshipState,
)

PUMP_STATION_TIME_ZONE = "Australia/Sydney"
PUMP_STATION_CALENDAR_ORIGIN_DATETIME = "2026-01-01T00:00:00+11:00"
PUMP_STATION_TIME_PROJECTION_POLICY_ID = "pump-station-current-state.v4"
PUMP_STATION_OBLIGATION_DUE_RULE = "calendar deadline or pump runtime limit, whichever occurs first"

_TIME_ZONE = ZoneInfo(PUMP_STATION_TIME_ZONE)
_CALENDAR_ORIGIN = datetime.fromisoformat(PUMP_STATION_CALENDAR_ORIGIN_DATETIME)
_CALENDAR_ORIGIN_UTC = _CALENDAR_ORIGIN.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class PumpStationPumpRuntimeView:
    """Actor-readable operating time for one pump."""

    pump_id: str
    runtime: str


@dataclass(frozen=True, slots=True)
class PumpStationObligationTimeView:
    """Actor-readable calendar and operating limits for one obligation."""

    obligation_id: str
    pump_id: str
    status: PumpStationObligationStatus
    calendar_deadline: str
    calendar_remaining: str
    runtime_limit: str
    runtime_remaining: str
    due_rule: str


@dataclass(frozen=True, slots=True)
class PumpStationProcessTimeView:
    """Actor-readable completion time for one work process."""

    process_id: str
    status: PumpStationProcessStatus
    completion_time: str
    time_remaining: str


@dataclass(frozen=True, slots=True)
class PumpStationTimeContext:
    """Bound actor presentation of the world calendar and tracked durations."""

    time_zone: str
    calendar_origin_datetime: str
    current_datetime: str
    calendar_elapsed: str
    episode_elapsed: str
    tenure_elapsed: str
    pump_runtimes: tuple[PumpStationPumpRuntimeView, ...]
    obligations: tuple[PumpStationObligationTimeView, ...]
    processes: tuple[PumpStationProcessTimeView, ...]


def pump_station_datetime(calendar_seconds: int) -> str:
    """Return the local ISO date for one exact world-clock value."""
    if calendar_seconds < 0:
        raise ValueError("pump-station calendar seconds must be non-negative")
    instant = _CALENDAR_ORIGIN_UTC + timedelta(seconds=calendar_seconds)
    return instant.astimezone(_TIME_ZONE).isoformat(timespec="seconds")


def _units(value: int, unit: str) -> str:
    suffix = unit if value == 1 else f"{unit}s"
    return f"{value:,} {suffix}"


def format_calendar_duration(seconds: int) -> str:
    """Return a compact calendar duration without losing sub-day meaning."""
    if seconds < 0:
        raise ValueError("calendar duration must be non-negative")
    if seconds == 0:
        return "0 seconds"
    parts: list[str] = []
    remaining = seconds
    for unit_seconds, unit in (
        (86_400, "day"),
        (3_600, "hour"),
        (60, "minute"),
        (1, "second"),
    ):
        value, remaining = divmod(remaining, unit_seconds)
        if value:
            parts.append(_units(value, unit))
    return " ".join(parts)


def format_operating_duration(seconds: int) -> str:
    """Return a pump runtime in operating hours, with smaller exact units if needed."""
    if seconds < 0:
        raise ValueError("operating duration must be non-negative")
    if seconds == 0:
        return "0 operating hours"
    hours, remainder = divmod(seconds, 3_600)
    parts = [_units(hours, "operating hour")] if hours else []
    minutes, seconds_remainder = divmod(remainder, 60)
    if minutes:
        parts.append(_units(minutes, "operating minute"))
    if seconds_remainder:
        parts.append(_units(seconds_remainder, "operating second"))
    return " ".join(parts)


def _remaining_calendar_time(deadline: int, now: int) -> str:
    remaining = deadline - now
    if remaining < 0:
        return f"overdue by {format_calendar_duration(-remaining)}"
    if remaining == 0:
        return "due now"
    return format_calendar_duration(remaining)


def _remaining_runtime(limit: int, current: int) -> str:
    remaining = limit - current
    if remaining < 0:
        return f"limit exceeded by {format_operating_duration(-remaining)}"
    if remaining == 0:
        return "runtime limit reached"
    return format_operating_duration(remaining)


def pump_station_time_context(
    state: PumpStationStewardshipState,
    *,
    episode_elapsed_seconds: int,
    tenure_elapsed_seconds: int,
) -> PumpStationTimeContext:
    """Project dates and durations from one exact stewardship state."""
    now = state.physical.calendar_seconds
    runtimes = {pump.pump_id: pump.exposure.runtime_seconds for pump in state.physical.pumps}
    return PumpStationTimeContext(
        time_zone=PUMP_STATION_TIME_ZONE,
        calendar_origin_datetime=PUMP_STATION_CALENDAR_ORIGIN_DATETIME,
        current_datetime=pump_station_datetime(now),
        calendar_elapsed=format_calendar_duration(now),
        episode_elapsed=format_calendar_duration(episode_elapsed_seconds),
        tenure_elapsed=format_calendar_duration(tenure_elapsed_seconds),
        pump_runtimes=tuple(
            PumpStationPumpRuntimeView(
                pump_id=pump.pump_id,
                runtime=format_operating_duration(pump.exposure.runtime_seconds),
            )
            for pump in state.physical.pumps
        ),
        obligations=tuple(
            PumpStationObligationTimeView(
                obligation_id=obligation.obligation_id,
                pump_id=obligation.pump_id,
                status=obligation.status,
                calendar_deadline=pump_station_datetime(obligation.due_calendar_seconds),
                calendar_remaining=_remaining_calendar_time(
                    obligation.due_calendar_seconds,
                    now,
                ),
                runtime_limit=format_operating_duration(obligation.due_runtime_seconds),
                runtime_remaining=_remaining_runtime(
                    obligation.due_runtime_seconds,
                    runtimes[obligation.pump_id],
                ),
                due_rule=PUMP_STATION_OBLIGATION_DUE_RULE,
            )
            for obligation in state.obligations
        ),
        processes=tuple(
            PumpStationProcessTimeView(
                process_id=process.process_id,
                status=process.status,
                completion_time=pump_station_datetime(process.completion_at_seconds),
                time_remaining=format_calendar_duration(
                    max(
                        0,
                        process.remaining_duration_seconds
                        if process.remaining_duration_seconds is not None
                        else process.completion_at_seconds - now,
                    )
                ),
            )
            for process in state.processes
        ),
    )
