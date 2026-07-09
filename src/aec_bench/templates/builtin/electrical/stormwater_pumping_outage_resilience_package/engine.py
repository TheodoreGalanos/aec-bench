# ABOUTME: Computes SSC-17 stormwater pumping outage resilience package metrics.
# ABOUTME: Combines inflow/storage, pump power, backup energy, and feeder voltage checks.

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


def _require_nonnegative(**values: float) -> None:
    """Raise ValueError when any supplied value is negative."""
    for name, value in values.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)


def compute(
    storm_inflow_m3_s: float,
    outage_duration_hr: float,
    pump_capacity_m3_s: float,
    allowed_pump_runtime_hr: float,
    available_storage_volume_m3: float,
    pump_total_head_m: float,
    pump_efficiency: float,
    controls_load_kw: float,
    telemetry_load_kw: float,
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
    """Compute source-bound stormwater pumping outage resilience metrics."""
    _require_positive(
        storm_inflow_m3_s=storm_inflow_m3_s,
        outage_duration_hr=outage_duration_hr,
        pump_capacity_m3_s=pump_capacity_m3_s,
        allowed_pump_runtime_hr=allowed_pump_runtime_hr,
        available_storage_volume_m3=available_storage_volume_m3,
        pump_total_head_m=pump_total_head_m,
        pump_efficiency=pump_efficiency,
        bess_nominal_kwh=bess_nominal_kwh,
        max_depth_of_discharge=max_depth_of_discharge,
        inverter_efficiency=inverter_efficiency,
        feeder_voltage_v=feeder_voltage_v,
        feeder_length_m=feeder_length_m,
        feeder_current_a=feeder_current_a,
        conductor_resistance_ohm_km=conductor_resistance_ohm_km,
        max_voltage_drop_percent=max_voltage_drop_percent,
    )
    _require_nonnegative(
        controls_load_kw=controls_load_kw,
        telemetry_load_kw=telemetry_load_kw,
        generator_kw=generator_kw,
        generator_runtime_hr=generator_runtime_hr,
    )
    if pump_efficiency > 1.0:
        msg = "pump_efficiency must be <= 1"
        raise ValueError(msg)
    if max_depth_of_discharge > 1.0:
        msg = "max_depth_of_discharge must be <= 1"
        raise ValueError(msg)
    if inverter_efficiency > 1.0:
        msg = "inverter_efficiency must be <= 1"
        raise ValueError(msg)
    if allowed_pump_runtime_hr > outage_duration_hr:
        msg = "allowed_pump_runtime_hr must be <= outage_duration_hr"
        raise ValueError(msg)

    storm_inflow_volume_m3 = storm_inflow_m3_s * outage_duration_hr * 3600.0
    pumpable_volume_m3 = pump_capacity_m3_s * allowed_pump_runtime_hr * 3600.0
    residual_storage_volume_m3 = max(storm_inflow_volume_m3 - pumpable_volume_m3, 0.0)
    storage_margin_m3 = available_storage_volume_m3 - residual_storage_volume_m3

    pump_hydraulic_power_kw = _WATER_DENSITY_KG_M3 * _G * pump_capacity_m3_s * pump_total_head_m / 1000.0
    pump_input_power_kw = pump_hydraulic_power_kw / pump_efficiency
    controls_and_telemetry_kw = controls_load_kw + telemetry_load_kw
    critical_mixed_load_kw = pump_input_power_kw + controls_and_telemetry_kw

    pump_energy_required_kwh = pump_input_power_kw * allowed_pump_runtime_hr
    controls_energy_required_kwh = controls_and_telemetry_kw * outage_duration_hr
    total_energy_required_kwh = pump_energy_required_kwh + controls_energy_required_kwh

    usable_bess_energy_kwh = bess_nominal_kwh * max_depth_of_discharge * inverter_efficiency
    generator_energy_kwh = generator_kw * generator_runtime_hr
    backup_energy_available_kwh = usable_bess_energy_kwh + generator_energy_kwh
    backup_energy_margin_kwh = backup_energy_available_kwh - total_energy_required_kwh
    battery_only_mixed_load_runtime_hr = usable_bess_energy_kwh / critical_mixed_load_kw

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

    overall_pass_score = (
        1.0 if min(storage_margin_m3, backup_energy_margin_kwh, voltage_drop_margin_percent) >= 0.0 else 0.0
    )

    return {
        "storm_inflow_volume_m3": round(storm_inflow_volume_m3, 3),
        "pumpable_volume_m3": round(pumpable_volume_m3, 3),
        "residual_storage_volume_m3": round(residual_storage_volume_m3, 3),
        "storage_margin_m3": round(storage_margin_m3, 3),
        "pump_hydraulic_power_kw": round(pump_hydraulic_power_kw, 3),
        "pump_input_power_kw": round(pump_input_power_kw, 3),
        "critical_mixed_load_kw": round(critical_mixed_load_kw, 3),
        "pump_energy_required_kwh": round(pump_energy_required_kwh, 3),
        "controls_energy_required_kwh": round(controls_energy_required_kwh, 3),
        "total_energy_required_kwh": round(total_energy_required_kwh, 3),
        "usable_bess_energy_kwh": round(usable_bess_energy_kwh, 3),
        "generator_energy_kwh": round(generator_energy_kwh, 3),
        "backup_energy_available_kwh": round(backup_energy_available_kwh, 3),
        "backup_energy_margin_kwh": round(backup_energy_margin_kwh, 3),
        "battery_only_mixed_load_runtime_hr": round(battery_only_mixed_load_runtime_hr, 3),
        "feeder_voltage_drop_percent": round(feeder_voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
