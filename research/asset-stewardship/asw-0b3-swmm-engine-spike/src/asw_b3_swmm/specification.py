# ABOUTME: Loads and validates the disposable ASW-0B3 engine-probe declaration.
# ABOUTME: Enforces the B1 two-pump topology and B2 non-promotion boundary before rendering.

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


class SpecificationError(ValueError):
    """Raised when a research probe declaration crosses the ASW-0B3 boundary."""


@dataclass(frozen=True)
class Authority:
    stage: str
    scope: str
    promotable: bool
    world_parameters_selected: bool
    purpose: str


@dataclass(frozen=True)
class Simulation:
    start: datetime
    horizon_seconds: int
    report_step_seconds: int
    routing_step_seconds: int
    flow_units: str
    routing_model: str
    force_main_equation: str
    threads: int


@dataclass(frozen=True)
class DiagnosticGeometry:
    wet_well_shape: str
    wet_well_invert_m: float
    wet_well_max_depth_m: float
    wet_well_initial_depth_m: float
    wet_well_major_axis_m: float
    wet_well_minor_axis_m: float
    wet_well_side_slope: float
    dry_weather_inflow_lps: float
    discharge_invert_m: float
    discharge_max_depth_m: float
    outfall_invert_m: float
    force_main_length_m: float
    force_main_conduit_roughness: float
    force_main_diameter_m: float
    force_main_absolute_roughness_mm: float

    @property
    def wet_well_plan_area_m2(self) -> float:
        from math import pi

        return pi * self.wet_well_major_axis_m * self.wet_well_minor_axis_m / 4.0


@dataclass(frozen=True)
class Probe:
    probe_id: str
    purpose: str
    active_pump: str
    inactive_pump: str


@dataclass(frozen=True)
class Specification:
    schema_version: str
    authority: Authority
    simulation: Simulation
    diagnostic_geometry: DiagnosticGeometry
    pump_curve: tuple[tuple[float, float], ...]
    components: tuple[str, ...]
    probes: tuple[Probe, ...]

    def probe(self, probe_id: str) -> Probe:
        for probe in self.probes:
            if probe.probe_id == probe_id:
                return probe
        raise SpecificationError(f"unknown probe: {probe_id}")


def _mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SpecificationError(f"{field} must be an object")
    return value


def _exact_keys(mapping: dict[str, Any], expected: set[str], field: str) -> None:
    actual = set(mapping)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise SpecificationError(f"{field} keys differ; missing={missing}, unknown={unknown}")


def _string(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SpecificationError(f"{key} must be a non-empty string")
    return value


def _bool(mapping: dict[str, Any], key: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise SpecificationError(f"{key} must be a boolean")
    return value


def _number(mapping: dict[str, Any], key: str, *, minimum: float | None = None) -> float:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SpecificationError(f"{key} must be numeric")
    result = float(value)
    if minimum is not None and result < minimum:
        raise SpecificationError(f"{key} must be at least {minimum}")
    return result


def _integer(mapping: dict[str, Any], key: str, *, minimum: int = 1) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise SpecificationError(f"{key} must be an integer of at least {minimum}")
    return value


def _load_authority(raw: object) -> Authority:
    mapping = _mapping(raw, "authority")
    _exact_keys(
        mapping,
        {"stage", "scope", "promotable", "world_parameters_selected", "purpose"},
        "authority",
    )
    authority = Authority(
        stage=_string(mapping, "stage"),
        scope=_string(mapping, "scope"),
        promotable=_bool(mapping, "promotable"),
        world_parameters_selected=_bool(mapping, "world_parameters_selected"),
        purpose=_string(mapping, "purpose"),
    )
    if authority.stage != "ASW-0B3" or authority.scope != "spike_only":
        raise SpecificationError("fixture authority must remain ASW-0B3 spike_only")
    if authority.promotable or authority.world_parameters_selected:
        raise SpecificationError("fixture must remain non-promotable and select no world parameters")
    return authority


def _load_simulation(raw: object) -> Simulation:
    mapping = _mapping(raw, "simulation")
    _exact_keys(
        mapping,
        {
            "start",
            "horizon_seconds",
            "report_step_seconds",
            "routing_step_seconds",
            "flow_units",
            "routing_model",
            "force_main_equation",
            "threads",
        },
        "simulation",
    )
    try:
        start = datetime.fromisoformat(_string(mapping, "start"))
    except ValueError as exc:
        raise SpecificationError("simulation start must be ISO-8601") from exc
    simulation = Simulation(
        start=start,
        horizon_seconds=_integer(mapping, "horizon_seconds"),
        report_step_seconds=_integer(mapping, "report_step_seconds"),
        routing_step_seconds=_integer(mapping, "routing_step_seconds"),
        flow_units=_string(mapping, "flow_units"),
        routing_model=_string(mapping, "routing_model"),
        force_main_equation=_string(mapping, "force_main_equation"),
        threads=_integer(mapping, "threads"),
    )
    if simulation.horizon_seconds % simulation.report_step_seconds:
        raise SpecificationError("report step must divide the diagnostic horizon exactly")
    if (
        simulation.flow_units,
        simulation.routing_model,
        simulation.force_main_equation,
        simulation.threads,
    ) != ("LPS", "DYNWAVE", "D-W", 1):
        raise SpecificationError("simulation must use the frozen B3 deterministic engine settings")
    return simulation


def _load_geometry(raw: object) -> DiagnosticGeometry:
    mapping = _mapping(raw, "diagnostic_geometry")
    expected = set(DiagnosticGeometry.__dataclass_fields__)
    _exact_keys(mapping, expected, "diagnostic_geometry")
    geometry = DiagnosticGeometry(
        wet_well_shape=_string(mapping, "wet_well_shape"),
        wet_well_invert_m=_number(mapping, "wet_well_invert_m"),
        wet_well_max_depth_m=_number(mapping, "wet_well_max_depth_m", minimum=0.0),
        wet_well_initial_depth_m=_number(mapping, "wet_well_initial_depth_m", minimum=0.0),
        wet_well_major_axis_m=_number(mapping, "wet_well_major_axis_m", minimum=0.000001),
        wet_well_minor_axis_m=_number(mapping, "wet_well_minor_axis_m", minimum=0.000001),
        wet_well_side_slope=_number(mapping, "wet_well_side_slope", minimum=0.0),
        dry_weather_inflow_lps=_number(mapping, "dry_weather_inflow_lps", minimum=0.0),
        discharge_invert_m=_number(mapping, "discharge_invert_m"),
        discharge_max_depth_m=_number(mapping, "discharge_max_depth_m", minimum=0.0),
        outfall_invert_m=_number(mapping, "outfall_invert_m"),
        force_main_length_m=_number(mapping, "force_main_length_m", minimum=0.000001),
        force_main_conduit_roughness=_number(mapping, "force_main_conduit_roughness", minimum=0.000001),
        force_main_diameter_m=_number(mapping, "force_main_diameter_m", minimum=0.000001),
        force_main_absolute_roughness_mm=_number(
            mapping,
            "force_main_absolute_roughness_mm",
            minimum=0.000001,
        ),
    )
    if geometry.wet_well_shape != "CYLINDRICAL" or geometry.wet_well_side_slope != 0.0:
        raise SpecificationError("B3 uses only a constant-area CYLINDRICAL diagnostic storage")
    if geometry.wet_well_initial_depth_m > geometry.wet_well_max_depth_m:
        raise SpecificationError("wet-well initial depth exceeds maximum depth")
    return geometry


def _load_curve(raw: object) -> tuple[tuple[float, float], ...]:
    if not isinstance(raw, list) or len(raw) < 2:
        raise SpecificationError("pump_curve must contain at least two points")
    points: list[tuple[float, float]] = []
    for index, item in enumerate(raw):
        if (
            not isinstance(item, list)
            or len(item) != 2
            or any(isinstance(value, bool) or not isinstance(value, int | float) for value in item)
        ):
            raise SpecificationError(f"pump_curve point {index} must contain two numbers")
        points.append((float(item[0]), float(item[1])))
    if any(left[0] >= right[0] for left, right in zip(points, points[1:], strict=False)):
        raise SpecificationError("pump_curve head coordinates must increase")
    if any(left[1] < right[1] for left, right in zip(points, points[1:], strict=False)):
        raise SpecificationError("pump_curve flow coordinates must not increase")
    return tuple(points)


def _load_components(raw: object) -> tuple[str, ...]:
    if raw != ["PUMP_A", "PUMP_B"]:
        raise SpecificationError("components must preserve the exact B1 Pump A/Pump B boundary")
    return ("PUMP_A", "PUMP_B")


def _load_probes(raw: object, components: tuple[str, ...]) -> tuple[Probe, ...]:
    if not isinstance(raw, list) or len(raw) != 2:
        raise SpecificationError("B3 requires exactly one mirrored probe for each pump")
    probes: list[Probe] = []
    for index, item in enumerate(raw):
        mapping = _mapping(item, f"probes[{index}]")
        _exact_keys(mapping, {"id", "purpose", "active_pump", "inactive_pump"}, f"probes[{index}]")
        probe = Probe(
            probe_id=_string(mapping, "id"),
            purpose=_string(mapping, "purpose"),
            active_pump=_string(mapping, "active_pump"),
            inactive_pump=_string(mapping, "inactive_pump"),
        )
        if {probe.active_pump, probe.inactive_pump} != set(components):
            raise SpecificationError("each probe must activate one B1 pump and inactivate the other")
        probes.append(probe)
    expected = {
        ("a_duty", "PUMP_A", "PUMP_B"),
        ("b_duty_label_probe", "PUMP_B", "PUMP_A"),
    }
    actual = {(probe.probe_id, probe.active_pump, probe.inactive_pump) for probe in probes}
    if actual != expected:
        raise SpecificationError("B3 requires exactly one mirrored probe for each B1 pump")
    return tuple(probes)


def load_specification(path: Path) -> Specification:
    """Load the exact research fixture and enforce its non-authoritative boundary."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SpecificationError(f"cannot load probe declaration: {exc}") from exc
    mapping = _mapping(raw, "root")
    _exact_keys(
        mapping,
        {
            "schema_version",
            "authority",
            "simulation",
            "diagnostic_geometry",
            "pump_curve",
            "components",
            "probes",
        },
        "root",
    )
    schema_version = _string(mapping, "schema_version")
    if schema_version != "asw-0b3.spike-probes.v1":
        raise SpecificationError("unsupported research fixture schema")
    components = _load_components(mapping["components"])
    return Specification(
        schema_version=schema_version,
        authority=_load_authority(mapping["authority"]),
        simulation=_load_simulation(mapping["simulation"]),
        diagnostic_geometry=_load_geometry(mapping["diagnostic_geometry"]),
        pump_curve=_load_curve(mapping["pump_curve"]),
        components=components,
        probes=_load_probes(mapping["probes"], components),
    )
