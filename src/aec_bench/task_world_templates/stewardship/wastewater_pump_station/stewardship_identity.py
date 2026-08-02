# ABOUTME: Creates canonical runtime identities for pump-station state and evidence.
# ABOUTME: Keeps computed replay identity separate from authored task-world policy.

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, cast

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationStewardshipStateRecord,
)

_V1_FIELD_EXCLUSIONS = {
    "PumpStationStewardshipState": {
        "state_version",
        "dependencies",
        "dependency_waivers",
        "resource_reservations",
    },
    "PumpStationProcess": {
        "remaining_duration_seconds",
        "dependency_ids",
        "suspended_at_seconds",
        "cancelled_at_seconds",
    },
    "PumpStationRestriction": {"parent_restriction_id"},
    "PumpStationCurrentStateView": {
        "state_version",
        "dependencies",
        "dependency_waivers",
        "resource_reservations",
    },
}
_V3_FIELD_EXCLUSIONS = {
    "PumpStationStewardshipState": {
        "evidence_sources",
        "evidence_treatments",
        "pending_evidence",
    },
    "PumpStationEvidence": {"health", "condition_observation"},
    "PumpStationScheduledEvent": {"treatment_id", "evidence_id"},
    "PumpStationTransitionReceipt": {
        "evidence_sources_changed",
        "evidence_treatments_changed",
    },
    "PumpStationCurrentStateView": {"observation_source"},
}
_V4_FIELD_EXCLUSIONS = {
    "PumpStationStewardshipState": {
        "assignment",
        "service_schedule",
        "baseline_schedule",
        "disclosed_through_calendar_seconds",
        "backlog",
        "generation_records",
        "outage_episodes",
        "operating_intervals",
        "collateral_runtime",
        "accepted_evidence_ids",
        "active_restriction_ids",
        "active_liability_ids",
        "created_liability_ids",
        "discharged_liability_ids",
        "pending_start_pump_ids",
        "event_effect_ids",
    },
}


def _field_exclusions(type_name: str, profile: str) -> set[str]:
    exclusions = set(_V3_FIELD_EXCLUSIONS.get(type_name, set())) if profile not in {"v3", "v4"} else set()
    if profile != "v4":
        exclusions.update(_V4_FIELD_EXCLUSIONS.get(type_name, set()))
    if profile == "v1":
        exclusions.update(_V1_FIELD_EXCLUSIONS.get(type_name, set()))
    return exclusions


def _record_profile(value: object) -> str:
    type_name = type(value).__name__
    if type_name in {"PumpStationStewardshipState", "PumpStationCurrentStateView"}:
        version = str(getattr(value, "state_version", ""))
        if version.endswith(".v4"):
            return "v4"
        if version.endswith(".v3"):
            return "v3"
        return "v2" if version.endswith(".v2") else "v1"
    if type_name == "PumpStationActorView":
        return _record_profile(cast(Any, value).current_state)
    if type_name == "PumpStationStructuredHandover":
        return _record_profile(cast(Any, value).current_actor_view)
    if type_name == "PumpStationInformationSet":
        return _record_profile(cast(Any, value).base_view)
    if type_name == "PumpStationTransition":
        return _record_profile(cast(Any, value).state)
    if type_name == "PumpStationTransitionReceipt":
        version = str(getattr(value, "receipt_version", ""))
        if version.endswith(".v4"):
            return "v4"
        if version.endswith(".v3"):
            return "v3"
        return "v2" if version.endswith(".v2") else "v1"
    if type_name == "PumpStationEvidence" and getattr(value, "health", None) is not None:
        return "v3"
    return "v2"


def canonical_stewardship_value(
    value: object,
    *,
    record_profile: str | None = None,
) -> object:
    """Convert supported task-local records into a canonical JSON value."""
    profile = record_profile or _record_profile(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        exclusions = _field_exclusions(type(value).__name__, profile)
        return {
            field.name: canonical_stewardship_value(
                getattr(value, field.name),
                record_profile=profile,
            )
            for field in fields(value)
            if field.name not in exclusions
        }
    if isinstance(value, Mapping):
        return {
            str(key): canonical_stewardship_value(child, record_profile=profile)
            for key, child in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, tuple | list):
        return [canonical_stewardship_value(item, record_profile=profile) for item in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise TypeError(f"unsupported canonical value {type(value).__name__}")


def stewardship_content_id(
    value: object,
    *,
    record_profile: str | None = None,
) -> str:
    """Return the computed SHA-256 identity of one canonical runtime value."""
    payload = json.dumps(
        canonical_stewardship_value(value, record_profile=record_profile),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def stewardship_state_id(state: PumpStationStewardshipStateRecord) -> str:
    """Return the computed identity of one complete stewardship state."""
    return stewardship_content_id(state)
