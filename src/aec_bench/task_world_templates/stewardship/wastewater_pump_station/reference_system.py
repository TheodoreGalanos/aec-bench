# ABOUTME: Loads the closed ASW-8 reference-system artifacts and constructs their exact opening state.
# ABOUTME: Keeps scenario timing and opening records separate from certified station-data bytes.

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any, NoReturn, cast

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpCondition,
    PumpExposure,
    PumpState,
    PumpStationBoundaryAvailability,
    PumpStationCoupledPhysicalState,
    PumpStationPumpBoundary,
    PumpStationPumpMode,
)

PUMP_STATION_REFERENCE_SYSTEM_ID = "pump-station-reference-system.asw-8-rs1.v1"
PUMP_STATION_REFERENCE_SYSTEM_DESCRIPTOR_SCHEMA = "pump-station-reference-system-descriptor.v1"
PUMP_STATION_ASW_8_INITIAL_STATE_SPECIFICATION_ID = "pump-station-asw-8-rs1-initial-state.v1"
PUMP_STATION_ASW_8_EVENT_SCHEDULE_ID = "pump-station-asw-8-rs1-event-schedule.v1"
PUMP_STATION_ASW_8_TEMPORAL_TEMPLATE_ID = "pump-station-asw-8-rs1-temporal-template.v1"
PUMP_STATION_ASW_8_TEMPORAL_BUILDER_ID = "pump-station-asw-8-temporal-builder.v1"
_REFERENCE_SYSTEM_FILES = {
    "descriptor.json": "6ad5471178737739fa9aeea64158971987ed576e7d3d0415a8979fea2735386f",
    "event-schedule.json": "3188afedbb8da98ad2a042dacb2a4094f2218cfd6482ae7cf98e16e74457af71",
    "initial-state.json": "1c3f82766c0dc03f31048aa5e12388f7e173bf907606c21f5b150914f874066a",
    "temporal-template.json": "daadc4183abd93b82f478c8af839a0590ed7ddd8dd941d5cce25a879582acd2d",
}


class PumpStationReferenceSystemError(ValueError):
    """Raised when the closed ASW-8 reference-system binding differs."""

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
class PumpStationReferenceSystem:
    """Exact descriptor and immutable scenario artifacts for one closed system."""

    descriptor_id: str
    descriptor_content_id: str
    station_data_profile_id: str
    descriptor: MappingProxyType[str, Any]
    opening_state: MappingProxyType[str, Any]
    event_schedule: MappingProxyType[str, Any]
    temporal_template: MappingProxyType[str, Any]


def bundled_reference_system_root() -> Path:
    """Return the closed production artifact directory for ASW-8 RS1."""
    return Path(__file__).with_name("reference_system") / "asw-8-rs1"


def _read_artifact(path: Path, expected_sha256: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        _fail("reference-system-read", f"{path.name}: {error}")
    canonical = (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode()
    if not isinstance(value, dict) or canonical != raw:
        _fail("reference-system-canonical-json", path.name)
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        _fail("reference-system-content-drift", path.name)
    return cast(dict[str, Any], value), raw


def load_reference_system(
    *,
    reference_system_id: str = PUMP_STATION_REFERENCE_SYSTEM_ID,
    root: Path | None = None,
) -> PumpStationReferenceSystem:
    """Load the one registered descriptor and verify all bound artifact bytes."""
    if reference_system_id != PUMP_STATION_REFERENCE_SYSTEM_ID:
        _fail("unknown-reference-system", reference_system_id)
    selected_root = bundled_reference_system_root() if root is None else root
    try:
        names = {path.name for path in selected_root.iterdir() if path.is_file()}
    except OSError as error:
        _fail("reference-system-read", str(error))
    if names != set(_REFERENCE_SYSTEM_FILES):
        _fail("reference-system-inventory", "artifact file set differs")
    values: dict[str, dict[str, Any]] = {}
    raw_files: dict[str, bytes] = {}
    for name, expected_sha256 in _REFERENCE_SYSTEM_FILES.items():
        values[name], raw_files[name] = _read_artifact(selected_root / name, expected_sha256)
    descriptor = values["descriptor.json"]
    opening = values["initial-state.json"]
    schedule = values["event-schedule.json"]
    temporal = values["temporal-template.json"]
    if (
        descriptor.get("schema_id") != PUMP_STATION_REFERENCE_SYSTEM_DESCRIPTOR_SCHEMA
        or descriptor.get("descriptor_id") != PUMP_STATION_REFERENCE_SYSTEM_ID
        or opening.get("specification_id") != PUMP_STATION_ASW_8_INITIAL_STATE_SPECIFICATION_ID
        or schedule.get("event_schedule_id") != PUMP_STATION_ASW_8_EVENT_SCHEDULE_ID
        or temporal.get("template_id") != PUMP_STATION_ASW_8_TEMPORAL_TEMPLATE_ID
        or temporal.get("builder_id") != PUMP_STATION_ASW_8_TEMPORAL_BUILDER_ID
    ):
        _fail("reference-system-identity", "registered artifact identity differs")
    opening_binding = cast(dict[str, Any], descriptor.get("opening_state"))
    schedule_binding = cast(dict[str, Any], descriptor.get("event_schedule"))
    temporal_binding = cast(dict[str, Any], descriptor.get("temporal_template"))
    if (
        opening_binding.get("content_sha256") != hashlib.sha256(raw_files["initial-state.json"]).hexdigest()
        or schedule_binding.get("content_sha256") != hashlib.sha256(raw_files["event-schedule.json"]).hexdigest()
        or temporal_binding.get("content_sha256") != hashlib.sha256(raw_files["temporal-template.json"]).hexdigest()
    ):
        _fail("reference-system-binding", "descriptor artifact hash differs")
    station_data = cast(dict[str, Any], descriptor.get("station_data"))
    if station_data.get("profile_id") != "AU-NSW-LH-SYN-SPS-v2":
        _fail("reference-system-binding", "station-data profile differs")
    return PumpStationReferenceSystem(
        descriptor_id=PUMP_STATION_REFERENCE_SYSTEM_ID,
        descriptor_content_id=hashlib.sha256(raw_files["descriptor.json"]).hexdigest(),
        station_data_profile_id=str(station_data["profile_id"]),
        descriptor=cast(MappingProxyType[str, Any], _freeze(descriptor)),
        opening_state=cast(MappingProxyType[str, Any], _freeze(opening)),
        event_schedule=cast(MappingProxyType[str, Any], _freeze(schedule)),
        temporal_template=cast(MappingProxyType[str, Any], _freeze(temporal)),
    )


def create_asw_8_opening_physical_state() -> PumpStationCoupledPhysicalState:
    """Construct the exact three-pump physical opening state at Day 0 06:00."""
    return PumpStationCoupledPhysicalState(
        calendar_seconds=21_600,
        pumps=(
            PumpState(
                pump_id="pump-a",
                condition=PumpCondition(
                    obstruction=Decimal("0.02039999999998400"),
                    clearance_loss=Decimal("0.00011999999998800"),
                ),
                exposure=PumpExposure(runtime_seconds=3_600, completed_starts=1),
            ),
            PumpState(
                pump_id="pump-b",
                condition=PumpCondition(
                    obstruction=Decimal("0.70"),
                    clearance_loss=Decimal("0.00"),
                ),
                exposure=PumpExposure.zero(),
            ),
            PumpState(
                pump_id="pump-c",
                condition=PumpCondition(
                    obstruction=Decimal("0.00015"),
                    clearance_loss=Decimal("0.00"),
                ),
                exposure=PumpExposure(runtime_seconds=0, completed_starts=1),
            ),
        ),
        pump_boundaries=(
            PumpStationPumpBoundary(
                pump_id="pump-a",
                mode=PumpStationPumpMode.RUN_IN_SERVICE,
                source_permit_or_evidence_id="initial-a-provisional-return",
                effective_transition_id="initial-a-provisional-return",
            ),
            PumpStationPumpBoundary(
                pump_id="pump-b",
                mode=PumpStationPumpMode.ISOLATED_FOR_WORK,
                source_permit_or_evidence_id="initial-b-inspection-accepted",
                effective_transition_id="initial-b-inspection-accepted",
            ),
            PumpStationPumpBoundary(
                pump_id="pump-c",
                mode=PumpStationPumpMode.SERVICE_AVAILABLE,
                source_permit_or_evidence_id="initial-c-assurance-accepted",
                effective_transition_id="initial-c-assurance-accepted",
            ),
        ),
        common_boundary=PumpStationBoundaryAvailability(
            power_available=True,
            discharge_available=True,
            source_transition_id="initial-common-boundaries-available",
        ),
        service_running_pump_ids=("pump-c",),
        test_running_pump_ids=(),
    )
