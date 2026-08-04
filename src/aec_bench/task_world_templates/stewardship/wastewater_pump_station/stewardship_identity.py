# ABOUTME: Creates canonical runtime identities for pump-station state and evidence.
# ABOUTME: Keeps computed replay identity separate from authored task-world policy.

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from decimal import Decimal
from enum import Enum

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationStewardshipState,
)


def canonical_stewardship_value(value: object) -> object:
    """Convert one current task-local value into a canonical JSON value."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: canonical_stewardship_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {
            str(key): canonical_stewardship_value(child)
            for key, child in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, tuple | list):
        return [canonical_stewardship_value(item) for item in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise TypeError(f"unsupported canonical value {type(value).__name__}")


def stewardship_content_id(value: object) -> str:
    """Return the computed SHA-256 identity of one canonical runtime value."""
    payload = json.dumps(
        canonical_stewardship_value(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def stewardship_state_id(state: PumpStationStewardshipState) -> str:
    """Return the computed identity of one complete stewardship state."""
    return stewardship_content_id(state)
