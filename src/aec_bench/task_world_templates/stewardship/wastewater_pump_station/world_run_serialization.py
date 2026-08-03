# ABOUTME: Serializes durable pump-station artifacts as strict canonical JSON.
# ABOUTME: Rebuilds only declared task-owned dataclasses, enums, decimals, and tuples.

from __future__ import annotations

import hashlib
import json
import types
from dataclasses import MISSING, fields, is_dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, NoReturn, TypeVar, cast, get_args, get_origin, get_type_hints, overload

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PUMP_STATION_SERIALIZATION_VERSION as _PUMP_STATION_SERIALIZATION_VERSION,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationWorldRunError,
)

PUMP_STATION_SERIALIZATION_VERSION = _PUMP_STATION_SERIALIZATION_VERSION
PUMP_STATION_TRANSPORT_FIELD_EXCLUSIONS: tuple[str, ...] = ()

ArtifactT = TypeVar("ArtifactT")

_V1 = "v1"
_V2 = "v2"
_V3 = "v3"
_V4 = "v4"
_MANIFEST_V1 = "manifest-v1"
_MANIFEST_V2 = "manifest-v2"
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
    "PumpStationCurrentStateView": {
        "observation_source",
    },
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
    "PumpStationActorView": {"time_context"},
    "RequestInspection": {"backlog_item_id"},
    "RequestObstructionClearance": {"backlog_item_id"},
    "RequestVerification": {"backlog_item_id"},
}


def _field_exclusions(type_name: str, profile: str) -> set[str]:
    exclusions = set(_V3_FIELD_EXCLUSIONS.get(type_name, set())) if profile not in {_V3, _V4} else set()
    if profile != _V4:
        exclusions.update(_V4_FIELD_EXCLUSIONS.get(type_name, set()))
    if profile == _V1:
        exclusions.update(_V1_FIELD_EXCLUSIONS.get(type_name, set()))
    return exclusions


def _fail(code: str, detail: str) -> NoReturn:
    raise PumpStationWorldRunError(code, detail)


def _record_profile(value: object) -> str:
    type_name = type(value).__name__
    if type_name in {
        "PumpStationCommandV4",
        "PumpStationTransitionReceiptV4",
        "PumpStationTransitionV4",
        "PumpStationWorldRunCommitV2",
        "PumpStationStagedTransitionV4",
    }:
        return _V4
    if type_name == "PumpStationWorldRunManifest":
        return _MANIFEST_V1
    if type_name == "PumpStationWorldRunManifestV2":
        return _MANIFEST_V2
    if type_name == "PumpStationStewardshipState":
        version = str(getattr(value, "state_version", ""))
        if version.endswith(".v4"):
            return _V4
        if version.endswith(".v3"):
            return _V3
        return _V2 if version.endswith(".v2") else _V1
    if type_name == "PumpStationCurrentStateView":
        version = str(getattr(value, "state_version", ""))
        if version.endswith(".v3"):
            return _V3
        return _V2 if version.endswith(".v2") else _V1
    if type_name == "PumpStationCoupledActorView":
        return _V4
    if type_name in {"PumpStationActorView", "PumpStationStructuredHandover"}:
        actor_view = value if type_name == "PumpStationActorView" else getattr(value, "current_actor_view", None)
        if str(getattr(actor_view, "projection_policy_id", "")).endswith(".v4"):
            return _V4
        current = getattr(actor_view, "current_state", None)
        if current is not None:
            return _record_profile(current)
    if type_name == "PumpStationInformationSet":
        return _record_profile(cast(Any, value).base_view)
    if type_name == "PumpStationTransitionReceipt":
        version = str(getattr(value, "receipt_version", ""))
        if version.endswith(".v3"):
            return _V3
        return _V2 if version.endswith(".v2") else _V1
    if type_name == "PumpStationEvidence" and getattr(value, "health", None) is not None:
        return _V3
    return _V2


def _document_profile(value: object) -> str:
    if isinstance(value, dict):
        type_name = value.get("$type")
        if type_name in {
            "PumpStationCommandV4",
            "PumpStationTransitionReceiptV4",
            "PumpStationTransitionV4",
            "PumpStationWorldRunCommitV2",
            "PumpStationStagedTransitionV4",
        }:
            return _V4
        if type_name == "PumpStationWorldRunManifest":
            return _MANIFEST_V1
        if type_name == "PumpStationWorldRunManifestV2":
            return _MANIFEST_V2
        if type_name == "PumpStationActorView" and str(value.get("projection_policy_id", "")).endswith(".v4"):
            return _V4
        if type_name == "PumpStationCoupledActorView":
            return _V4
        if type_name in {"PumpStationStewardshipState", "PumpStationCurrentStateView"}:
            version = str(value.get("state_version", ""))
            if version.endswith(".v4"):
                return _V4
            if version.endswith(".v3"):
                return _V3
            return _V2 if version.endswith(".v2") else _V1
        if type_name == "PumpStationTransitionReceipt":
            version = str(value.get("receipt_version", ""))
            if version.endswith(".v3"):
                return _V3
            return _V2 if version.endswith(".v2") else _V1
        if type_name == "PumpStationEvidence" and value.get("health") is not None:
            return _V3
        profiles = tuple(_document_profile(child) for child in value.values())
        if _V1 in profiles:
            return _V1
        if _V2 in profiles:
            return _V2
        if _V4 in profiles:
            return _V4
    if isinstance(value, list):
        profiles = tuple(_document_profile(child) for child in value)
        if _V1 in profiles:
            return _V1
        if _V2 in profiles:
            return _V2
        if _V4 in profiles:
            return _V4
    return _V3


def _encoded(value: object, profile: str) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        exclusions = _field_exclusions(type(value).__name__, profile)
        return {
            "$type": type(value).__name__,
            **{
                field.name: _encoded(getattr(value, field.name), profile)
                for field in fields(value)
                if field.name not in exclusions
            },
        }
    if isinstance(value, tuple):
        return [_encoded(item, profile) for item in value]
    if value is None or type(value) in {str, int, bool}:
        return value
    _fail("artifact-type", f"unsupported value {type(value).__name__}")
    raise AssertionError("unreachable")


def pump_station_artifact_bytes(
    value: object,
    *,
    record_profile: str | None = None,
) -> bytes:
    """Return one canonical, newline-terminated task artifact."""
    profile = record_profile or _record_profile(value)
    return (
        json.dumps(
            _encoded(value, profile),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def pump_station_artifact_id(
    value: object,
    *,
    record_profile: str | None = None,
) -> str:
    """Return the content identity of one canonical task artifact."""
    return hashlib.sha256(pump_station_artifact_bytes(value, record_profile=record_profile)).hexdigest()


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, child in pairs:
        if key in value:
            _fail("canonical-json", f"duplicate field {key}")
        value[key] = child
    return value


def _reject_number(value: str) -> NoReturn:
    _fail("canonical-json", f"unsupported JSON number {value}")


def _expected_value(expected: object) -> object:
    return getattr(expected, "__value__", expected)


def _decode_union(value: object, expected: object, profile: str) -> object:
    options = get_args(expected)
    if value is None and type(None) in options:
        return None
    if isinstance(value, dict) and isinstance(value.get("$type"), str):
        type_name = value["$type"]
        for option in options:
            candidate = _expected_value(option)
            if isinstance(candidate, type) and is_dataclass(candidate) and candidate.__name__ == type_name:
                return _decode(value, candidate, profile)
        _fail("artifact-type", f"unknown stored type {type_name}")
    failures: list[PumpStationWorldRunError] = []
    for option in options:
        if option is type(None):
            continue
        try:
            return _decode(value, option, profile)
        except PumpStationWorldRunError as error:
            failures.append(error)
    detail = failures[0] if failures else "no matching union member"
    _fail("artifact-type", str(detail))
    raise AssertionError("unreachable")


def _profile_selected_type_hints(expected: type[Any], profile: str) -> dict[str, object]:
    """Resolve generic state fields to the record types selected by its profile."""
    type_hints = cast(dict[str, object], get_type_hints(expected))
    if expected.__name__ != "PumpStationStewardshipState":
        return type_hints
    from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_work import (
        PumpStationCoupledProcess,
        PumpStationPoolReservation,
        PumpStationResourceState,
    )
    from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
        PumpStationCoupledEnvironment,
        PumpStationCoupledPhysicalState,
        PumpStationEnvironment,
        PumpStationState,
    )
    from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
        PumpStationProcess,
        PumpStationResourceReservation,
        PumpStationWorkResources,
    )

    if profile == _V4:
        type_hints.update(
            {
                "physical": PumpStationCoupledPhysicalState,
                "environment": PumpStationCoupledEnvironment,
                "resources": PumpStationResourceState,
                "processes": tuple[PumpStationCoupledProcess, ...],
                "resource_reservations": tuple[PumpStationPoolReservation, ...],
            }
        )
    else:
        type_hints.update(
            {
                "physical": PumpStationState,
                "environment": PumpStationEnvironment,
                "resources": PumpStationWorkResources,
                "processes": tuple[PumpStationProcess, ...],
                "resource_reservations": tuple[PumpStationResourceReservation, ...],
            }
        )
    return type_hints


def _decode_dataclass(value: object, expected: type[Any], profile: str) -> object:
    if not isinstance(value, dict):
        _fail("artifact-shape", f"{expected.__name__} must be an object")
    if value.get("$type") != expected.__name__:
        _fail(
            "artifact-type",
            f"expected {expected.__name__}, received {value.get('$type')!r}",
        )
    declared_fields = fields(expected)
    exclusions = _field_exclusions(expected.__name__, profile)
    expected_keys = {
        "$type",
        *(field.name for field in declared_fields if field.name not in exclusions),
    }
    if set(value) != expected_keys:
        _fail("artifact-shape", f"{expected.__name__} fields differ")
    type_hints = _profile_selected_type_hints(expected, profile)
    decoded: dict[str, object] = {}
    for field in declared_fields:
        if field.name in value:
            decoded[field.name] = _decode(
                value[field.name],
                type_hints[field.name],
                profile,
            )
        elif field.name in exclusions and field.default is not MISSING:
            decoded[field.name] = field.default
        elif field.name in exclusions and field.default_factory is not MISSING:
            decoded[field.name] = field.default_factory()
        else:
            _fail("artifact-shape", f"{expected.__name__} lacks {field.name}")
    try:
        return expected(**decoded)
    except PumpStationWorldRunError:
        raise
    except (TypeError, ValueError) as error:
        _fail("artifact-shape", f"{expected.__name__}: {error}")
    raise AssertionError("unreachable")


def _decode_tuple(value: object, expected: object, profile: str) -> tuple[object, ...]:
    if not isinstance(value, list):
        _fail("artifact-shape", "tuple value must be a JSON array")
    members = get_args(expected)
    if len(members) == 2 and members[1] is Ellipsis:
        return tuple(_decode(item, members[0], profile) for item in value)
    if len(value) != len(members):
        _fail("artifact-shape", "fixed tuple length differs")
    return tuple(_decode(item, member, profile) for item, member in zip(value, members, strict=True))


def _decode(value: object, expected: object, profile: str) -> object:
    expected = _expected_value(expected)
    origin = get_origin(expected)
    if origin is types.UnionType or isinstance(expected, types.UnionType):
        return _decode_union(value, expected, profile)
    if origin is tuple:
        return _decode_tuple(value, expected, profile)
    if isinstance(expected, type) and is_dataclass(expected):
        return _decode_dataclass(value, expected, profile)
    if isinstance(expected, type) and issubclass(expected, Enum):
        try:
            return expected(value)
        except (TypeError, ValueError):
            _fail("artifact-type", f"invalid {expected.__name__} value")
    if expected is Decimal:
        if not isinstance(value, str):
            _fail("artifact-type", "decimal must be stored as text")
        try:
            decoded_decimal = Decimal(value)
        except (InvalidOperation, ValueError):
            _fail("artifact-type", "invalid decimal text")
        if not decoded_decimal.is_finite():
            _fail("artifact-type", "decimal must be finite")
        return decoded_decimal
    if expected in {str, int, bool}:
        if type(value) is not expected:
            _fail(
                "artifact-type",
                f"expected {cast(type[object], expected).__name__}",
            )
        return value
    if expected is type(None) and value is None:
        return None
    _fail("artifact-type", f"unsupported declared type {expected!r}")
    raise AssertionError("unreachable")


@overload
def load_pump_station_artifact(
    payload: bytes,
    expected_type: type[ArtifactT],
    *,
    record_profile: str | None = None,
) -> ArtifactT: ...


@overload
def load_pump_station_artifact(
    payload: bytes,
    expected_type: object,
    *,
    record_profile: str | None = None,
) -> object: ...


def load_pump_station_artifact(
    payload: bytes,
    expected_type: object,
    *,
    record_profile: str | None = None,
) -> object:
    """Strictly rebuild one declared task artifact from canonical bytes."""
    try:
        text = payload.decode("utf-8")
        document = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
    except PumpStationWorldRunError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        _fail("canonical-json", str(error))
    profile = record_profile or _document_profile(document)
    restored = _decode(document, expected_type, profile)
    if pump_station_artifact_bytes(restored, record_profile=profile) != payload:
        _fail("canonical-json", "stored bytes are not canonical")
    return restored
