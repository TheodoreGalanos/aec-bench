# ABOUTME: Loads content-pinned pump-station reference profiles and compiles their scenario schedules.
# ABOUTME: Keeps scenario data separate from reusable pump-world rules and certified station-data bytes.

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any, NoReturn, cast

from aec_bench.worlds.stewardship.wastewater_pump_station.coupled_work import (
    PumpStationAvailabilityInterval,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.physical_models import (
    PumpCondition,
    PumpExposure,
    PumpState,
    PumpStationBoundaryAvailability,
    PumpStationCoupledPhysicalState,
    PumpStationPumpBoundary,
    PumpStationPumpMode,
    PumpStationServiceRequirement,
)

PUMP_STATION_REFERENCE_SYSTEM_ID = "pump-station-reference-system.asw-8-rs1.v1"
PUMP_STATION_REFERENCE_SYSTEM_RS2_ID = "pump-station-reference-system.asw-8-rs2.v1"
PUMP_STATION_REFERENCE_SYSTEM_DESCRIPTOR_SCHEMA = "pump-station-reference-system-descriptor.v1"
PUMP_STATION_TEMPORAL_TEMPLATE_SCHEMA = "pump-station-temporal-evidence-template.v1"
_REFERENCE_SYSTEM_FILES = frozenset(
    {
        "descriptor.json",
        "event-schedule.json",
        "initial-state.json",
        "temporal-template.json",
    }
)
_HOST_EVENT_TYPES = frozenset(
    {
        "backlog_due",
        "backlog_priority",
        "document_review_point",
        "resource_availability",
        "resource_withdrawal",
        "service_requirement_change",
    }
)


class PumpStationReferenceSystemError(ValueError):
    """Raised when one pump reference-system profile is invalid."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> NoReturn:
    raise PumpStationReferenceSystemError(code, detail)


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(child) for key, child in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(child) for child in value)
    return value


@dataclass(frozen=True, slots=True)
class PumpStationScheduledEvent:
    """One immutable event declared by a pump scenario profile."""

    event_id: str
    event_type: str
    time: int
    refreshes_observation: bool


@dataclass(frozen=True, slots=True)
class PumpStationEventSchedule:
    """Typed service, resource, baseline, and host-event schedule for one profile."""

    event_schedule_id: str
    disclosed_through_calendar_seconds: int
    service_requirements: tuple[PumpStationServiceRequirement, ...]
    baseline_assignments: tuple[tuple[int, int, tuple[str, ...]], ...]
    resource_windows: tuple[PumpStationAvailabilityInterval, ...]
    host_events: tuple[PumpStationScheduledEvent, ...]


@dataclass(frozen=True, slots=True)
class PumpStationReferenceSystem:
    """Exact descriptor and immutable scenario values for one pump profile."""

    descriptor_id: str
    descriptor_content_id: str
    station_data_profile_id: str
    descriptor: MappingProxyType[str, Any]
    opening_state: MappingProxyType[str, Any]
    event_schedule: PumpStationEventSchedule
    temporal_template: MappingProxyType[str, Any]


def _reference_system_base() -> Path:
    return Path(__file__).with_name("reference_system")


def _read_artifact(path: Path, expected_sha256: str | None = None) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        _fail("reference-system-read", f"{path.name}: {error}")
    canonical = (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode()
    if not isinstance(value, dict) or canonical != raw:
        _fail("reference-system-canonical-json", path.name)
    if expected_sha256 is not None and hashlib.sha256(raw).hexdigest() != expected_sha256:
        _fail("reference-system-content-drift", path.name)
    return cast(dict[str, Any], value), raw


def _reference_system_index() -> dict[str, Path]:
    index: dict[str, Path] = {}
    try:
        directories = tuple(path for path in _reference_system_base().iterdir() if path.is_dir())
    except OSError as error:
        _fail("reference-system-read", str(error))
    for directory in sorted(directories):
        descriptor_path = directory / "descriptor.json"
        if not descriptor_path.is_file():
            continue
        descriptor, _ = _read_artifact(descriptor_path)
        descriptor_id = descriptor.get("descriptor_id")
        if not isinstance(descriptor_id, str) or not descriptor_id.strip():
            _fail("reference-system-identity", f"{directory.name}: descriptor identity is missing")
        if descriptor_id in index:
            _fail("reference-system-identity", f"duplicate descriptor identity: {descriptor_id}")
        index[descriptor_id] = directory
    if not index:
        _fail("reference-system-inventory", "no bundled reference systems were found")
    return index


def list_reference_system_ids() -> tuple[str, ...]:
    """Return stable IDs for all bundled pump scenario profiles."""
    return tuple(sorted(_reference_system_index()))


def bundled_reference_system_root(
    reference_system_id: str = PUMP_STATION_REFERENCE_SYSTEM_ID,
) -> Path:
    """Return the bundled artifact directory for one pump scenario profile."""
    root = _reference_system_index().get(reference_system_id)
    if root is None:
        _fail("unknown-reference-system", reference_system_id)
    return root


def _binding(descriptor: Mapping[str, Any], name: str) -> tuple[str, str]:
    value = descriptor.get(name)
    if not isinstance(value, Mapping):
        _fail("reference-system-binding", f"descriptor lacks {name}")
    identity = value.get("id")
    content_sha256 = value.get("content_sha256")
    if not isinstance(identity, str) or not identity.strip():
        _fail("reference-system-binding", f"descriptor {name} identity differs")
    if not isinstance(content_sha256, str) or len(content_sha256) != 64:
        _fail("reference-system-binding", f"descriptor {name} hash differs")
    return identity, content_sha256


def _compile_event_schedule(value: Mapping[str, Any], expected_id: str) -> PumpStationEventSchedule:
    try:
        schedule_id = str(value["event_schedule_id"])
        disclosed_through = int(value["disclosed_through_calendar_seconds"])
        service = tuple(
            PumpStationServiceRequirement(int(item["start"]), int(item["end"]), int(item["required_scu"]))
            for item in cast(tuple[Mapping[str, Any], ...], value["service_requirements"])
        )
        baseline = tuple(
            (
                int(item["start"]),
                int(item["end"]),
                tuple(str(pump_id) for pump_id in item["ordered_pump_ids"]),
            )
            for item in cast(tuple[Mapping[str, Any], ...], value["baseline_assignments"])
        )
        windows = tuple(
            PumpStationAvailabilityInterval(
                int(item["start_calendar_seconds"]),
                int(item["end_calendar_seconds"]),
            )
            for item in cast(tuple[Mapping[str, Any], ...], value["resource_windows"])
        )
        events = tuple(
            PumpStationScheduledEvent(
                event_id=str(item["event_id"]),
                event_type=str(item["event_type"]),
                time=int(item["time"]),
                refreshes_observation=bool(item.get("refreshes_observation", True)),
            )
            for item in cast(tuple[Mapping[str, Any], ...], value["host_events"])
        )
    except (KeyError, TypeError, ValueError) as error:
        _fail("reference-system-schedule", str(error))
    if schedule_id != expected_id or value.get("schema_id") != expected_id:
        _fail("reference-system-identity", "event-schedule identity differs")
    if not service or not baseline or not windows:
        _fail("reference-system-schedule", "service, baseline, and resource schedules must not be empty")
    service_ranges = tuple((item.start_calendar_seconds, item.end_calendar_seconds) for item in service)
    baseline_ranges = tuple((start, end) for start, end, _ in baseline)
    if service_ranges != baseline_ranges:
        _fail("reference-system-schedule", "service and baseline ranges differ")
    if any(start >= end for start, end in service_ranges) or any(
        left[1] != right[0] for left, right in zip(service_ranges, service_ranges[1:], strict=False)
    ):
        _fail("reference-system-schedule", "service ranges must be positive and contiguous")
    window_ranges = tuple((item.start_calendar_seconds, item.end_calendar_seconds) for item in windows)
    if any(start >= end for start, end in window_ranges) or any(
        left[1] > right[0] for left, right in zip(window_ranges, window_ranges[1:], strict=False)
    ):
        _fail("reference-system-schedule", "resource windows must be positive and non-overlapping")
    if service_ranges[-1][1] != disclosed_through or window_ranges[-1][1] != disclosed_through:
        _fail("reference-system-schedule", "schedule horizon differs")
    if len({event.event_id for event in events}) != len(events) or any(
        event.event_type not in _HOST_EVENT_TYPES for event in events
    ):
        _fail("reference-system-schedule", "host event identity or type differs")
    if tuple(event.time for event in events) != tuple(sorted(event.time for event in events)):
        _fail("reference-system-schedule", "host events must use stable time order")
    return PumpStationEventSchedule(
        event_schedule_id=schedule_id,
        disclosed_through_calendar_seconds=disclosed_through,
        service_requirements=service,
        baseline_assignments=baseline,
        resource_windows=windows,
        host_events=events,
    )


def load_reference_system(
    *,
    reference_system_id: str = PUMP_STATION_REFERENCE_SYSTEM_ID,
    root: Path | None = None,
) -> PumpStationReferenceSystem:
    """Load one reference-system profile and verify its exact artifact bindings."""
    selected_root = bundled_reference_system_root(reference_system_id) if root is None else root
    try:
        names = {path.name for path in selected_root.iterdir() if path.is_file()}
    except OSError as error:
        _fail("reference-system-read", str(error))
    if names != _REFERENCE_SYSTEM_FILES:
        _fail("reference-system-inventory", "artifact file set differs")
    descriptor, descriptor_raw = _read_artifact(selected_root / "descriptor.json")
    if (
        descriptor.get("schema_id") != PUMP_STATION_REFERENCE_SYSTEM_DESCRIPTOR_SCHEMA
        or descriptor.get("descriptor_id") != reference_system_id
    ):
        _fail("reference-system-identity", "descriptor identity differs")
    opening_id, opening_sha256 = _binding(descriptor, "opening_state")
    schedule_id, schedule_sha256 = _binding(descriptor, "event_schedule")
    temporal_id, temporal_sha256 = _binding(descriptor, "temporal_template")
    opening, _ = _read_artifact(selected_root / "initial-state.json", opening_sha256)
    schedule, _ = _read_artifact(selected_root / "event-schedule.json", schedule_sha256)
    temporal, _ = _read_artifact(selected_root / "temporal-template.json", temporal_sha256)
    temporal_binding = descriptor.get("temporal_template")
    if (
        opening.get("specification_id") != opening_id
        or opening.get("schema_id") != opening_id
        or temporal.get("template_id") != temporal_id
        or temporal.get("schema_id") != PUMP_STATION_TEMPORAL_TEMPLATE_SCHEMA
        or not isinstance(temporal_binding, Mapping)
        or temporal.get("builder_id") != temporal_binding.get("builder_id")
    ):
        _fail("reference-system-identity", "bound artifact identity differs")
    station_data = descriptor.get("station_data")
    if not isinstance(station_data, Mapping):
        _fail("reference-system-binding", "station-data binding is missing")
    station_profile_id = station_data.get("profile_id")
    package_content_id = station_data.get("package_content_id")
    if not isinstance(station_profile_id, str) or not station_profile_id.strip():
        _fail("reference-system-binding", "station-data profile differs")
    if not isinstance(package_content_id, str) or len(package_content_id) != 64:
        _fail("reference-system-binding", "station-data package hash differs")
    if opening.get("profile_id") != station_profile_id or temporal.get("station_data_profile_id") != station_profile_id:
        _fail("reference-system-binding", "scenario artifacts use another station-data profile")
    return PumpStationReferenceSystem(
        descriptor_id=reference_system_id,
        descriptor_content_id=hashlib.sha256(descriptor_raw).hexdigest(),
        station_data_profile_id=station_profile_id,
        descriptor=cast(MappingProxyType[str, Any], _freeze(descriptor)),
        opening_state=cast(MappingProxyType[str, Any], _freeze(opening)),
        event_schedule=_compile_event_schedule(schedule, schedule_id),
        temporal_template=cast(MappingProxyType[str, Any], _freeze(temporal)),
    )


def create_opening_physical_state(
    reference_system: PumpStationReferenceSystem | None = None,
) -> PumpStationCoupledPhysicalState:
    """Compile the selected profile's three-pump physical opening state."""
    opening = (reference_system or load_reference_system()).opening_state
    try:
        pumps_value = cast(Mapping[str, Mapping[str, Any]], opening["pumps"])
        boundaries_value = cast(Mapping[str, Mapping[str, Any]], opening["pump_boundaries"])
        common = cast(Mapping[str, Any], opening["common_boundary"])
        pumps = tuple(
            PumpState(
                pump_id=pump_id,
                condition=PumpCondition(
                    obstruction=Decimal(str(value["obstruction"])),
                    clearance_loss=Decimal(str(value["clearance_loss"])),
                ),
                exposure=PumpExposure(
                    runtime_seconds=int(value["runtime_seconds"]),
                    completed_starts=int(value["completed_starts"]),
                ),
            )
            for pump_id, value in pumps_value.items()
        )
        boundaries = tuple(
            PumpStationPumpBoundary(
                pump_id=pump_id,
                mode=PumpStationPumpMode(str(value["mode"])),
                source_permit_or_evidence_id=str(value["source_id"]),
                effective_transition_id=str(value["source_id"]),
            )
            for pump_id, value in boundaries_value.items()
        )
        if len(pumps) != 3 or len(boundaries) != 3:
            raise ValueError("the current station model requires exactly three pumps")
        return PumpStationCoupledPhysicalState(
            calendar_seconds=int(opening["calendar_seconds"]),
            pumps=pumps,
            pump_boundaries=boundaries,
            common_boundary=PumpStationBoundaryAvailability(
                power_available=bool(common["power_available"]),
                discharge_available=bool(common["discharge_available"]),
                source_transition_id="initial-common-boundaries-available",
            ),
            service_running_pump_ids=tuple(str(value) for value in opening["service_running_pump_ids"]),
            test_running_pump_ids=tuple(str(value) for value in opening["test_running_pump_ids"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        _fail("opening-state-shape", str(error))
