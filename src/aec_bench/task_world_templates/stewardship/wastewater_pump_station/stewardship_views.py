# ABOUTME: Defines the current actor-visible pump view and information-set binding.
# ABOUTME: Contains no session handover, historical actor view, or compatibility projection.

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_work import (
    PumpStationBacklogItem,
    PumpStationCoupledProcess,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpStationPumpAvailability,
    PumpStationPumpBoundary,
    PumpStationServiceRequirement,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    stewardship_content_id,
)


class PumpStationContinuityCarrier(StrEnum):
    """Actor-visible continuity material supplied with one current decision."""

    CURRENT_ACTOR_VIEW = "current_actor_view"


@dataclass(frozen=True, slots=True)
class PumpStationCoupledActorView:
    """Current actor view with exact world, tenure, and public planning identity."""

    view_id: str
    episode_id: str
    world_branch_id: str
    actor_id: str
    agent_tenure_id: str
    source_artifact_ids: tuple[str, ...]
    projection_policy_id: str
    observation_schema_id: str
    information_boundary_id: str
    state_id: str
    sequence: int
    time_zone: str
    current_datetime: str
    calendar_seconds: int
    service_schedule: tuple[PumpStationServiceRequirement, ...]
    disclosed_through_calendar_seconds: int
    service_schedule_disclosed_through_datetime: str
    resource_schedule_disclosed_through_datetime: str
    service_schedule_local: tuple[tuple[str, str, int], ...]
    resource_availability_local: tuple[tuple[str, tuple[tuple[str, str], ...]], ...]
    assignment_pump_ids: tuple[str, ...]
    service_running_pump_ids: tuple[str, ...]
    test_running_pump_ids: tuple[str, ...]
    required_service_scu: int
    available_assured_scu: int
    assigned_operating_scu: int
    served_scu: int
    unserved_scu: int
    surplus_scu: int
    pump_clocks: tuple[tuple[str, int, int], ...]
    pump_runtime_display: tuple[tuple[str, str], ...]
    pump_boundaries: tuple[PumpStationPumpBoundary, ...]
    pump_availability: tuple[PumpStationPumpAvailability, ...]
    resource_quantities: tuple[tuple[str, int, int], ...]
    ranked_backlog: tuple[PumpStationBacklogItem, ...]
    processes: tuple[PumpStationCoupledProcess, ...]
    active_restriction_ids: tuple[str, ...]
    active_liability_ids: tuple[str, ...]
    accepted_evidence_ids: tuple[str, ...]
    evidence_health: tuple[tuple[str, str, str, bool], ...]

    def __post_init__(self) -> None:
        expected_view_id = coupled_actor_view_id(self)
        if self.view_id == "pending":
            object.__setattr__(self, "view_id", expected_view_id)
        elif self.view_id != expected_view_id:
            raise ValueError("actor view identity differs from its complete content")


def coupled_actor_view_id(view: PumpStationCoupledActorView) -> str:
    """Return the identity of every actor-visible view field."""
    identity_payload = {field.name: getattr(view, field.name) for field in fields(view) if field.name != "view_id"}
    return stewardship_content_id(identity_payload)


@dataclass(frozen=True, slots=True)
class PumpStationObservationHistory:
    """Manifest of views shown during the current actor tenure."""

    agent_tenure_id: str
    view_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text(self.agent_tenure_id, "agent_tenure_id")
        if not self.view_ids:
            raise ValueError("view_ids must not be empty")
        for view_id in self.view_ids:
            _require_text(view_id, "view_ids")


@dataclass(frozen=True, slots=True)
class PumpStationCurrentContext:
    """Exact non-world material visible when an actor submits an action."""

    continuity_carrier: PumpStationContinuityCarrier
    conversation_prefix_id: str | None
    workspace_tool_ids: tuple[str, ...]
    visible_material_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.conversation_prefix_id is not None:
            _require_text(self.conversation_prefix_id, "conversation_prefix_id")
        _require_distinct_text(self.workspace_tool_ids, "workspace_tool_ids")
        _require_distinct_text(self.visible_material_ids, "visible_material_ids", allow_empty=True)


@dataclass(frozen=True, slots=True)
class PumpStationInformationSet:
    """Content identity of the current view and exact actor-visible context."""

    information_set_id: str
    base_view: PumpStationCoupledActorView
    observation_history: PumpStationObservationHistory
    current_context: PumpStationCurrentContext


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _require_distinct_text(
    values: tuple[str, ...],
    field_name: str,
    *,
    allow_empty: bool = False,
) -> None:
    if not values and not allow_empty:
        raise ValueError(f"{field_name} must not be empty")
    for value in values:
        _require_text(value, field_name)
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must not contain duplicates")


def _information_set_id(
    base_view: PumpStationCoupledActorView,
    observation_history: PumpStationObservationHistory,
    current_context: PumpStationCurrentContext,
) -> str:
    return stewardship_content_id(
        {
            "base_view_id": base_view.view_id,
            "observation_history": observation_history,
            "current_context": current_context,
        },
    )


def bind_information_set(
    base_view: PumpStationCoupledActorView,
    observation_history: PumpStationObservationHistory,
    current_context: PumpStationCurrentContext,
) -> PumpStationInformationSet:
    """Bind the exact view, tenure history, and visible commitment context."""
    if observation_history.agent_tenure_id != base_view.agent_tenure_id:
        raise ValueError("observation history belongs to a different actor tenure")
    if observation_history.view_ids[-1] != base_view.view_id:
        raise ValueError("latest observation must be the base view")
    return PumpStationInformationSet(
        information_set_id=_information_set_id(base_view, observation_history, current_context),
        base_view=base_view,
        observation_history=observation_history,
        current_context=current_context,
    )


__all__ = [
    "PumpStationContinuityCarrier",
    "PumpStationCoupledActorView",
    "PumpStationCurrentContext",
    "PumpStationInformationSet",
    "PumpStationObservationHistory",
    "bind_information_set",
    "coupled_actor_view_id",
]
