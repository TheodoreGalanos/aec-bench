# ABOUTME: Computes SSC-05 mechanical-load feeder and voltage metrics.
# ABOUTME: Combines load demand, power-factor correction, ampacity, breaker, and voltage-drop checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _require_fraction(name: str, value: float) -> None:
    """Raise ValueError unless a value is in the inclusive 0..1 range."""
    if value < 0.0 or value > 1.0:
        msg = f"{name} must be between 0 and 1"
        raise ValueError(msg)


def compute(
    pump_motor_kw: float,
    pump_quantity: float,
    pump_demand_factor: float,
    ahu_motor_kw: float,
    ahu_quantity: float,
    ahu_demand_factor: float,
    dosing_pump_kw: float,
    dosing_quantity: float,
    dosing_demand_factor: float,
    future_allowance_pct: float,
    initial_power_factor: float,
    target_power_factor: float,
    selected_capacitor_kvar: float,
    feeder_voltage_v: float,
    feeder_length_m: float,
    feeder_voltage_drop_mv_per_a_m: float,
    base_cable_ampacity_a: float,
    ambient_derating_factor: float,
    grouping_derating_factor: float,
    installation_derating_factor: float,
    breaker_trip_a: float,
    breaker_continuous_factor: float,
    max_voltage_drop_percent: float,
) -> dict[str, float]:
    """Compute source-bound load, PFC, feeder, cable, and breaker metrics."""
    _require_positive(
        pump_motor_kw=pump_motor_kw,
        pump_quantity=pump_quantity,
        ahu_motor_kw=ahu_motor_kw,
        ahu_quantity=ahu_quantity,
        dosing_pump_kw=dosing_pump_kw,
        dosing_quantity=dosing_quantity,
        selected_capacitor_kvar=selected_capacitor_kvar,
        feeder_voltage_v=feeder_voltage_v,
        feeder_length_m=feeder_length_m,
        feeder_voltage_drop_mv_per_a_m=feeder_voltage_drop_mv_per_a_m,
        base_cable_ampacity_a=base_cable_ampacity_a,
        breaker_trip_a=breaker_trip_a,
        max_voltage_drop_percent=max_voltage_drop_percent,
    )
    if future_allowance_pct < 0.0:
        msg = "future_allowance_pct must be >= 0"
        raise ValueError(msg)
    for name, value in {
        "pump_demand_factor": pump_demand_factor,
        "ahu_demand_factor": ahu_demand_factor,
        "dosing_demand_factor": dosing_demand_factor,
        "ambient_derating_factor": ambient_derating_factor,
        "grouping_derating_factor": grouping_derating_factor,
        "installation_derating_factor": installation_derating_factor,
        "breaker_continuous_factor": breaker_continuous_factor,
    }.items():
        _require_fraction(name, value)
    if not 0.0 < initial_power_factor < 1.0:
        msg = "initial_power_factor must be between 0 and 1"
        raise ValueError(msg)
    if not 0.0 < target_power_factor < 1.0:
        msg = "target_power_factor must be between 0 and 1"
        raise ValueError(msg)
    if target_power_factor <= initial_power_factor:
        msg = "target_power_factor must be greater than initial_power_factor"
        raise ValueError(msg)

    pump_connected_kw = pump_motor_kw * pump_quantity
    ahu_connected_kw = ahu_motor_kw * ahu_quantity
    dosing_connected_kw = dosing_pump_kw * dosing_quantity
    connected_load_kw = pump_connected_kw + ahu_connected_kw + dosing_connected_kw

    demand_load_kw = (
        pump_connected_kw * pump_demand_factor
        + ahu_connected_kw * ahu_demand_factor
        + dosing_connected_kw * dosing_demand_factor
    )
    future_allowance_kw = demand_load_kw * future_allowance_pct / 100.0
    design_load_kw = demand_load_kw + future_allowance_kw

    initial_reactive_power_kvar = design_load_kw * math.tan(math.acos(initial_power_factor))
    target_reactive_power_kvar = design_load_kw * math.tan(math.acos(target_power_factor))
    required_capacitor_kvar = initial_reactive_power_kvar - target_reactive_power_kvar
    selected_capacitor_margin_kvar = selected_capacitor_kvar - required_capacitor_kvar

    corrected_apparent_power_kva = design_load_kw / target_power_factor
    feeder_current_a = corrected_apparent_power_kva * 1000.0 / (math.sqrt(3.0) * feeder_voltage_v)

    derated_cable_ampacity_a = (
        base_cable_ampacity_a * ambient_derating_factor * grouping_derating_factor * installation_derating_factor
    )
    ampacity_margin_a = derated_cable_ampacity_a - feeder_current_a
    breaker_allowable_current_a = breaker_trip_a * breaker_continuous_factor
    breaker_margin_a = breaker_allowable_current_a - feeder_current_a

    voltage_drop_v = feeder_voltage_drop_mv_per_a_m * feeder_current_a * feeder_length_m / 1000.0
    feeder_voltage_drop_percent = voltage_drop_v / feeder_voltage_v * 100.0
    voltage_drop_margin_percent = max_voltage_drop_percent - feeder_voltage_drop_percent

    overall_pass_score = (
        1.0
        if min(
            selected_capacitor_margin_kvar,
            ampacity_margin_a,
            breaker_margin_a,
            voltage_drop_margin_percent,
        )
        >= 0.0
        else 0.0
    )

    return {
        "connected_load_kw": round(connected_load_kw, 3),
        "demand_load_kw": round(demand_load_kw, 3),
        "future_allowance_kw": round(future_allowance_kw, 3),
        "design_load_kw": round(design_load_kw, 3),
        "initial_reactive_power_kvar": round(initial_reactive_power_kvar, 3),
        "required_capacitor_kvar": round(required_capacitor_kvar, 3),
        "selected_capacitor_margin_kvar": round(selected_capacitor_margin_kvar, 3),
        "corrected_apparent_power_kva": round(corrected_apparent_power_kva, 3),
        "feeder_current_a": round(feeder_current_a, 3),
        "derated_cable_ampacity_a": round(derated_cable_ampacity_a, 3),
        "ampacity_margin_a": round(ampacity_margin_a, 3),
        "breaker_allowable_current_a": round(breaker_allowable_current_a, 3),
        "breaker_margin_a": round(breaker_margin_a, 3),
        "voltage_drop_v": round(voltage_drop_v, 3),
        "feeder_voltage_drop_percent": round(feeder_voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
