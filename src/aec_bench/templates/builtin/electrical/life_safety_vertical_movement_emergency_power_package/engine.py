# ABOUTME: Computes SSC-08 life-safety and vertical-movement emergency-power metrics.
# ABOUTME: Combines connected load, generator derating, battery bridge, feeder drop, and load-shed checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    critical_lift_load_kw: float,
    escalator_recovery_load_kw: float,
    alarm_load_kw: float,
    smoke_control_load_kw: float,
    emergency_lighting_load_kw: float,
    diversity_factor: float,
    generator_capacity_kw: float,
    generator_derate_factor: float,
    control_load_kw: float,
    bridge_duration_h: float,
    battery_usable_fraction: float,
    selected_battery_capacity_kwh: float,
    voltage_v: float,
    power_factor: float,
    feeder_length_km: float,
    feeder_resistance_ohm_per_km: float,
    feeder_reactance_ohm_per_km: float,
    allowable_voltage_drop_percent: float,
    shedable_load_kw: float,
    required_shed_kw: float,
) -> dict[str, float]:
    """Compute deterministic emergency-power metrics for the SSC-08 source pack."""
    _require_positive(
        critical_lift_load_kw=critical_lift_load_kw,
        escalator_recovery_load_kw=escalator_recovery_load_kw,
        alarm_load_kw=alarm_load_kw,
        smoke_control_load_kw=smoke_control_load_kw,
        emergency_lighting_load_kw=emergency_lighting_load_kw,
        diversity_factor=diversity_factor,
        generator_capacity_kw=generator_capacity_kw,
        generator_derate_factor=generator_derate_factor,
        bridge_duration_h=bridge_duration_h,
        battery_usable_fraction=battery_usable_fraction,
        selected_battery_capacity_kwh=selected_battery_capacity_kwh,
        voltage_v=voltage_v,
        power_factor=power_factor,
        feeder_length_km=feeder_length_km,
        feeder_resistance_ohm_per_km=feeder_resistance_ohm_per_km,
        feeder_reactance_ohm_per_km=feeder_reactance_ohm_per_km,
        allowable_voltage_drop_percent=allowable_voltage_drop_percent,
        shedable_load_kw=shedable_load_kw,
        required_shed_kw=required_shed_kw,
    )
    if power_factor > 1.0:
        msg = "power_factor must be <= 1"
        raise ValueError(msg)

    critical_connected_load_kw = (
        critical_lift_load_kw
        + escalator_recovery_load_kw
        + alarm_load_kw
        + smoke_control_load_kw
        + emergency_lighting_load_kw
    )
    diversified_emergency_load_kw = critical_connected_load_kw * diversity_factor
    available_generator_capacity_kw = generator_capacity_kw * generator_derate_factor
    generator_capacity_margin_kw = available_generator_capacity_kw - diversified_emergency_load_kw
    battery_bridge_load_kw = alarm_load_kw + emergency_lighting_load_kw + control_load_kw
    required_battery_capacity_kwh = battery_bridge_load_kw * bridge_duration_h / battery_usable_fraction
    battery_capacity_margin_kwh = selected_battery_capacity_kwh - required_battery_capacity_kwh
    emergency_feeder_current_a = diversified_emergency_load_kw * 1000.0 / (math.sqrt(3.0) * voltage_v * power_factor)
    sine_factor = math.sqrt(1.0 - power_factor**2)
    feeder_voltage_drop_percent = (
        math.sqrt(3.0)
        * emergency_feeder_current_a
        * (feeder_resistance_ohm_per_km * power_factor + feeder_reactance_ohm_per_km * sine_factor)
        * feeder_length_km
        / voltage_v
        * 100.0
    )
    voltage_drop_margin_percent = allowable_voltage_drop_percent - feeder_voltage_drop_percent
    load_shed_margin_kw = shedable_load_kw - required_shed_kw

    pass_checks = [
        generator_capacity_margin_kw >= 0.0,
        battery_capacity_margin_kwh >= 0.0,
        voltage_drop_margin_percent >= 0.0,
        load_shed_margin_kw >= 0.0,
    ]

    return {
        "critical_connected_load_kw": round(critical_connected_load_kw, 3),
        "diversified_emergency_load_kw": round(diversified_emergency_load_kw, 3),
        "available_generator_capacity_kw": round(available_generator_capacity_kw, 3),
        "generator_capacity_margin_kw": round(generator_capacity_margin_kw, 3),
        "battery_bridge_load_kw": round(battery_bridge_load_kw, 3),
        "required_battery_capacity_kwh": round(required_battery_capacity_kwh, 3),
        "battery_capacity_margin_kwh": round(battery_capacity_margin_kwh, 3),
        "emergency_feeder_current_a": round(emergency_feeder_current_a, 3),
        "feeder_voltage_drop_percent": round(feeder_voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "load_shed_margin_kw": round(load_shed_margin_kw, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
