# ABOUTME: Computes SSC-05 pump station MCC, cable, and protection metrics.
# ABOUTME: Combines motor current, starting duty, cable derating, voltage-drop, and protection margins.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _require_fraction(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        msg = f"{name} must be between 0 and 1"
        raise ValueError(msg)


def compute(
    pump_motor_kw: float,
    feeder_voltage_v: float,
    motor_efficiency: float,
    motor_power_factor: float,
    starting_multiplier: float,
    base_cable_ampacity_a: float,
    ambient_derating_factor: float,
    grouping_derating_factor: float,
    installation_derating_factor: float,
    voltage_drop_mv_per_a_m: float,
    feeder_length_m: float,
    max_voltage_drop_percent: float,
    overload_setting_a: float,
    available_fault_current_ka: float,
    breaker_interrupt_rating_ka: float,
) -> dict[str, float]:
    """Compute source-bound MCC motor, cable, voltage-drop, and protection metrics."""
    _require_positive(
        pump_motor_kw=pump_motor_kw,
        feeder_voltage_v=feeder_voltage_v,
        motor_efficiency=motor_efficiency,
        motor_power_factor=motor_power_factor,
        starting_multiplier=starting_multiplier,
        base_cable_ampacity_a=base_cable_ampacity_a,
        voltage_drop_mv_per_a_m=voltage_drop_mv_per_a_m,
        feeder_length_m=feeder_length_m,
        max_voltage_drop_percent=max_voltage_drop_percent,
        overload_setting_a=overload_setting_a,
        available_fault_current_ka=available_fault_current_ka,
        breaker_interrupt_rating_ka=breaker_interrupt_rating_ka,
    )
    for name, value in {
        "motor_efficiency": motor_efficiency,
        "motor_power_factor": motor_power_factor,
        "ambient_derating_factor": ambient_derating_factor,
        "grouping_derating_factor": grouping_derating_factor,
        "installation_derating_factor": installation_derating_factor,
    }.items():
        _require_fraction(name, value)

    running_current_a = (
        pump_motor_kw * 1000.0 / (math.sqrt(3.0) * feeder_voltage_v * motor_efficiency * motor_power_factor)
    )
    starting_current_a = running_current_a * starting_multiplier
    derated_cable_ampacity_a = (
        base_cable_ampacity_a * ambient_derating_factor * grouping_derating_factor * installation_derating_factor
    )
    ampacity_margin_a = derated_cable_ampacity_a - running_current_a
    voltage_drop_v = voltage_drop_mv_per_a_m * running_current_a * feeder_length_m / 1000.0
    voltage_drop_percent = voltage_drop_v / feeder_voltage_v * 100.0
    voltage_drop_margin_percent = max_voltage_drop_percent - voltage_drop_percent
    overload_setting_margin_a = overload_setting_a - running_current_a
    short_circuit_margin_ka = breaker_interrupt_rating_ka - available_fault_current_ka

    overall_pass_score = (
        1.0
        if min(ampacity_margin_a, voltage_drop_margin_percent, overload_setting_margin_a, short_circuit_margin_ka)
        >= 0.0
        else 0.0
    )

    return {
        "running_current_a": round(running_current_a, 3),
        "starting_current_a": round(starting_current_a, 3),
        "derated_cable_ampacity_a": round(derated_cable_ampacity_a, 3),
        "ampacity_margin_a": round(ampacity_margin_a, 3),
        "voltage_drop_percent": round(voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "overload_setting_margin_a": round(overload_setting_margin_a, 3),
        "short_circuit_margin_ka": round(short_circuit_margin_ka, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
