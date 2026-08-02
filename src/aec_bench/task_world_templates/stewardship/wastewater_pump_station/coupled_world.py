# ABOUTME: Applies ASW-8 service, outage, and assignment rules to the coupled pump state.
# ABOUTME: Uses only actor-visible schedules for planned-work admission and ignores hidden events.

from __future__ import annotations

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpStationCoupledPhysicalState,
    PumpStationServiceRequirement,
)


def planned_outage_admissible(
    state: PumpStationCoupledPhysicalState,
    *,
    target_pump_id: str,
    start_calendar_seconds: int,
    completion_calendar_seconds: int,
    visible_service_schedule: tuple[PumpStationServiceRequirement, ...],
    disclosed_through_calendar_seconds: int,
) -> bool:
    """Return whether assured non-target capacity covers each disclosed work interval."""
    if completion_calendar_seconds > disclosed_through_calendar_seconds:
        return False
    if target_pump_id in state.service_running_pump_ids or target_pump_id in state.test_running_pump_ids:
        return False
    assured_non_target = sum(
        state.availability(pump.pump_id).assured_for_outage_planning
        for pump in state.pumps
        if pump.pump_id != target_pump_id
    )
    relevant = tuple(
        requirement
        for requirement in visible_service_schedule
        if requirement.start_calendar_seconds < completion_calendar_seconds
        and requirement.end_calendar_seconds > start_calendar_seconds
    )
    if not relevant:
        return False
    cursor = start_calendar_seconds
    for requirement in sorted(relevant, key=lambda item: item.start_calendar_seconds):
        if requirement.start_calendar_seconds > cursor:
            return False
        if requirement.required_service_scu > assured_non_target:
            return False
        cursor = max(cursor, min(requirement.end_calendar_seconds, completion_calendar_seconds))
    return cursor >= completion_calendar_seconds
