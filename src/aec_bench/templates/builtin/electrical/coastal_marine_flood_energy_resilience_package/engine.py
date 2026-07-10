# ABOUTME: Computes SSC-17 coastal or marine flood energy resilience metrics.
# ABOUTME: Combines flood level, equipment freeboard, outfall submergence, pump energy, and feeder checks.

from __future__ import annotations

import math

_WATER_DENSITY_KG_M3 = 1000.0
_G = 9.81


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    tide_level_m: float,
    slr_allowance_m: float,
    storm_surge_m: float,
    wave_allowance_m: float,
    electrical_equipment_elevation_m: float,
    required_equipment_freeboard_m: float,
    outfall_obvert_level_m: float,
    allowable_submergence_m: float,
    pump_flow_m3_s: float,
    pump_head_m: float,
    pump_efficiency: float,
    pump_runtime_hr: float,
    controls_load_kw: float,
    outage_duration_hr: float,
    bess_nominal_kwh: float,
    max_depth_of_discharge: float,
    inverter_efficiency: float,
    generator_kw: float,
    generator_runtime_hr: float,
    feeder_voltage_v: float,
    feeder_length_m: float,
    feeder_current_a: float,
    conductor_resistance_ohm_km: float,
    max_voltage_drop_percent: float,
) -> dict[str, float]:
    """Compute deterministic SSC-17 coastal flood energy resilience metrics."""
    _require_positive(
        tide_level_m=tide_level_m,
        slr_allowance_m=slr_allowance_m,
        storm_surge_m=storm_surge_m,
        wave_allowance_m=wave_allowance_m,
        electrical_equipment_elevation_m=electrical_equipment_elevation_m,
        required_equipment_freeboard_m=required_equipment_freeboard_m,
        outfall_obvert_level_m=outfall_obvert_level_m,
        allowable_submergence_m=allowable_submergence_m,
        pump_flow_m3_s=pump_flow_m3_s,
        pump_head_m=pump_head_m,
        pump_efficiency=pump_efficiency,
        pump_runtime_hr=pump_runtime_hr,
        controls_load_kw=controls_load_kw,
        outage_duration_hr=outage_duration_hr,
        bess_nominal_kwh=bess_nominal_kwh,
        max_depth_of_discharge=max_depth_of_discharge,
        inverter_efficiency=inverter_efficiency,
        generator_kw=generator_kw,
        generator_runtime_hr=generator_runtime_hr,
        feeder_voltage_v=feeder_voltage_v,
        feeder_length_m=feeder_length_m,
        feeder_current_a=feeder_current_a,
        conductor_resistance_ohm_km=conductor_resistance_ohm_km,
        max_voltage_drop_percent=max_voltage_drop_percent,
    )
    if max(pump_efficiency, max_depth_of_discharge, inverter_efficiency) > 1.0:
        msg = "fractional pump and storage values must be <= 1"
        raise ValueError(msg)

    design_flood_level_m = tide_level_m + slr_allowance_m + storm_surge_m + wave_allowance_m
    equipment_freeboard_m = electrical_equipment_elevation_m - design_flood_level_m
    equipment_freeboard_margin_m = equipment_freeboard_m - required_equipment_freeboard_m
    outfall_submergence_m = design_flood_level_m - outfall_obvert_level_m
    outfall_submergence_margin_m = allowable_submergence_m - outfall_submergence_m
    pump_input_power_kw = _WATER_DENSITY_KG_M3 * _G * pump_flow_m3_s * pump_head_m / 1000.0 / pump_efficiency
    backup_energy_required_kwh = pump_input_power_kw * pump_runtime_hr + controls_load_kw * outage_duration_hr
    usable_bess_energy_kwh = bess_nominal_kwh * max_depth_of_discharge * inverter_efficiency
    generator_energy_kwh = generator_kw * generator_runtime_hr
    backup_energy_available_kwh = usable_bess_energy_kwh + generator_energy_kwh
    backup_energy_margin_kwh = backup_energy_available_kwh - backup_energy_required_kwh
    feeder_voltage_drop_percent = (
        math.sqrt(3.0)
        * feeder_current_a
        * feeder_length_m
        * conductor_resistance_ohm_km
        / 1000.0
        / feeder_voltage_v
        * 100.0
    )
    voltage_drop_margin_percent = max_voltage_drop_percent - feeder_voltage_drop_percent

    pass_checks = [
        equipment_freeboard_margin_m >= 0.0,
        outfall_submergence_margin_m >= 0.0,
        backup_energy_margin_kwh >= 0.0,
        voltage_drop_margin_percent >= 0.0,
    ]

    return {
        "design_flood_level_m": round(design_flood_level_m, 3),
        "equipment_freeboard_m": round(equipment_freeboard_m, 3),
        "equipment_freeboard_margin_m": round(equipment_freeboard_margin_m, 3),
        "outfall_submergence_m": round(outfall_submergence_m, 3),
        "outfall_submergence_margin_m": round(outfall_submergence_margin_m, 3),
        "pump_input_power_kw": round(pump_input_power_kw, 3),
        "backup_energy_required_kwh": round(backup_energy_required_kwh, 3),
        "usable_bess_energy_kwh": round(usable_bess_energy_kwh, 3),
        "generator_energy_kwh": round(generator_energy_kwh, 3),
        "backup_energy_available_kwh": round(backup_energy_available_kwh, 3),
        "backup_energy_margin_kwh": round(backup_energy_margin_kwh, 3),
        "feeder_voltage_drop_percent": round(feeder_voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
