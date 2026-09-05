# ABOUTME: Defines the public facts required for a pump continuation handover.
# ABOUTME: Assesses omitted, contradicted, invented, and stale facts without exposing hidden state.

from __future__ import annotations

from pydantic import JsonValue

from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.contracts.world_interface import WorldActorObservation


class PumpHandover(StrictModel):
    source_view_id: NonEmptyStr
    facts: dict[str, JsonValue]


class PumpHandoverAssessment(StrictModel):
    source_current: bool
    omitted: tuple[str, ...]
    contradicted: tuple[str, ...]
    invented: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return self.source_current and not (self.omitted or self.contradicted or self.invented)


def required_pump_handover(observation: WorldActorObservation) -> PumpHandover:
    """Extract continuation facts exclusively from an already released actor observation."""
    view = observation.view
    view_id = view.get("view_id")
    if not isinstance(view_id, str):
        raise ValueError("pump handover requires a pump actor view")
    facts: dict[str, JsonValue] = {}
    for name in (
        "calendar_seconds",
        "assignment_pump_ids",
        "active_restriction_ids",
        "active_liability_ids",
        "accepted_evidence_ids",
        "pump_clocks",
        "resource_quantities",
        "service_schedule",
        "resource_availability_local",
        "evidence_health",
    ):
        facts[name] = view[name]
    for name, identity in (("ranked_backlog", "item_id"), ("processes", "process_id"), ("pump_boundaries", "pump_id")):
        rows = view[name]
        if not isinstance(rows, list):
            raise ValueError(f"pump actor view {name} must be a list")
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get(identity), str):
                raise ValueError(f"pump actor view {name} has no {identity}")
            facts[f"{name}/{row[identity]}"] = row
    return PumpHandover(source_view_id=view_id, facts=facts)


def assess_pump_handover(observation: WorldActorObservation, submitted: PumpHandover) -> PumpHandoverAssessment:
    """Compare a handover with its exact released source view, not with private authority."""
    expected = required_pump_handover(observation)
    expected_keys, actual_keys = set(expected.facts), set(submitted.facts)
    return PumpHandoverAssessment(
        source_current=submitted.source_view_id == expected.source_view_id,
        omitted=tuple(sorted(expected_keys - actual_keys)),
        contradicted=tuple(sorted(k for k in expected_keys & actual_keys if expected.facts[k] != submitted.facts[k])),
        invented=tuple(sorted(actual_keys - expected_keys)),
    )
