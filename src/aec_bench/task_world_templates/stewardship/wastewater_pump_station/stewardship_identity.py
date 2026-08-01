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
    PumpStationStewardshipState,
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


def _record_profile(value: object) -> str:
    type_name = type(value).__name__
    if type_name in {"PumpStationStewardshipState", "PumpStationCurrentStateView"}:
        return "v2" if str(getattr(value, "state_version", "")).endswith(".v2") else "v1"
    if type_name == "PumpStationActorView":
        return _record_profile(cast(Any, value).current_state)
    if type_name == "PumpStationStructuredHandover":
        return _record_profile(cast(Any, value).current_actor_view)
    if type_name == "PumpStationInformationSet":
        return _record_profile(cast(Any, value).base_view)
    if type_name == "PumpStationTransition":
        return _record_profile(cast(Any, value).state)
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
        exclusions = _V1_FIELD_EXCLUSIONS.get(type(value).__name__, set()) if profile == "v1" else set()
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


def stewardship_state_id(state: PumpStationStewardshipState) -> str:
    """Return the computed identity of one complete stewardship state."""
    return stewardship_content_id(state)
