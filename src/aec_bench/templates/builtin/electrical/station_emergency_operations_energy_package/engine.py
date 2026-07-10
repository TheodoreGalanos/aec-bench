# ABOUTME: Computes SSC-17 station emergency operations energy metrics.
# ABOUTME: Combines life-safety loads, generator/BESS autonomy, load shedding, and feeder checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    emergency_lighting_kw: float,
    alarm_nac_kw: float,
    ventilation_kw: float,
    lift_kw: float,
    communications_kw: float,
    outage_duration_hr: float,
    generator_kw: float,
    generator_runtime_hr: float,
    bess_nominal_kwh: float,
    max_depth_of_discharge: float,
    inverter_efficiency: float,
    noncritical_load_shed_kw: float,
    feeder_voltage_v: float,
    feeder_length_m: float,
    feeder_current_a: float,
    conductor_resistance_ohm_km: float,
    max_voltage_drop_percent: float,
) -> dict[str, float]:
    """Compute deterministic SSC-17 station emergency operations energy metrics."""
    _require_positive(
        emergency_lighting_kw=emergency_lighting_kw,
        alarm_nac_kw=alarm_nac_kw,
        ventilation_kw=ventilation_kw,
        lift_kw=lift_kw,
        communications_kw=communications_kw,
        outage_duration_hr=outage_duration_hr,
        generator_kw=generator_kw,
        generator_runtime_hr=generator_runtime_hr,
        bess_nominal_kwh=bess_nominal_kwh,
        max_depth_of_discharge=max_depth_of_discharge,
        inverter_efficiency=inverter_efficiency,
        noncritical_load_shed_kw=noncritical_load_shed_kw,
        feeder_voltage_v=feeder_voltage_v,
        feeder_length_m=feeder_length_m,
        feeder_current_a=feeder_current_a,
        conductor_resistance_ohm_km=conductor_resistance_ohm_km,
        max_voltage_drop_percent=max_voltage_drop_percent,
    )
    if max(max_depth_of_discharge, inverter_efficiency) > 1.0:
        msg = "fractional storage values must be <= 1"
        raise ValueError(msg)

    emergency_load_kw = emergency_lighting_kw + alarm_nac_kw + ventilation_kw + lift_kw + communications_kw
    required_energy_kwh = emergency_load_kw * outage_duration_hr
    generator_energy_kwh = generator_kw * generator_runtime_hr
    usable_bess_energy_kwh = bess_nominal_kwh * max_depth_of_discharge * inverter_efficiency
    backup_energy_available_kwh = generator_energy_kwh + usable_bess_energy_kwh
    backup_energy_margin_kwh = backup_energy_available_kwh - required_energy_kwh
    battery_only_runtime_hr = usable_bess_energy_kwh / emergency_load_kw
    generator_capacity_margin_kw = generator_kw - emergency_load_kw
    load_shed_kw = noncritical_load_shed_kw
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
        backup_energy_margin_kwh >= 0.0,
        generator_capacity_margin_kw >= 0.0,
        load_shed_kw >= 0.0,
        voltage_drop_margin_percent >= 0.0,
    ]

    return {
        "emergency_load_kw": round(emergency_load_kw, 3),
        "required_energy_kwh": round(required_energy_kwh, 3),
        "generator_energy_kwh": round(generator_energy_kwh, 3),
        "usable_bess_energy_kwh": round(usable_bess_energy_kwh, 3),
        "backup_energy_available_kwh": round(backup_energy_available_kwh, 3),
        "backup_energy_margin_kwh": round(backup_energy_margin_kwh, 3),
        "battery_only_runtime_hr": round(battery_only_runtime_hr, 3),
        "generator_capacity_margin_kw": round(generator_capacity_margin_kw, 3),
        "load_shed_kw": round(load_shed_kw, 3),
        "feeder_voltage_drop_percent": round(feeder_voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
