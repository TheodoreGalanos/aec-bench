# ABOUTME: Computes SSC-11 pump station rising main energy and surge package metrics.
# ABOUTME: Combines steady losses, pump power, surge pressure, trip margin, and feeder drop.

from __future__ import annotations

import math

_G = 9.81


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    flow_l_s: float,
    static_head_m: float,
    rising_main_length_m: float,
    pipe_internal_diameter_mm: float,
    hazen_williams_c: float,
    pump_efficiency: float,
    motor_efficiency: float,
    velocity_change_fraction: float,
    wave_speed_m_s: float,
    fluid_density_kg_m3: float,
    base_pressure_kpa: float,
    pipe_pressure_class_kpa: float,
    high_high_trip_setpoint_kpa: float,
    feeder_voltage_v: float,
    motor_power_factor: float,
    feeder_length_km: float,
    conductor_resistance_ohm_km: float,
    allowable_voltage_drop_percent: float,
) -> dict[str, float]:
    """Compute deterministic SSC-11 rising-main energy and surge metrics."""
    _require_positive(
        flow_l_s=flow_l_s,
        static_head_m=static_head_m,
        rising_main_length_m=rising_main_length_m,
        pipe_internal_diameter_mm=pipe_internal_diameter_mm,
        hazen_williams_c=hazen_williams_c,
        pump_efficiency=pump_efficiency,
        motor_efficiency=motor_efficiency,
        velocity_change_fraction=velocity_change_fraction,
        wave_speed_m_s=wave_speed_m_s,
        fluid_density_kg_m3=fluid_density_kg_m3,
        base_pressure_kpa=base_pressure_kpa,
        pipe_pressure_class_kpa=pipe_pressure_class_kpa,
        high_high_trip_setpoint_kpa=high_high_trip_setpoint_kpa,
        feeder_voltage_v=feeder_voltage_v,
        motor_power_factor=motor_power_factor,
        feeder_length_km=feeder_length_km,
        conductor_resistance_ohm_km=conductor_resistance_ohm_km,
        allowable_voltage_drop_percent=allowable_voltage_drop_percent,
    )

    flow_m3_s = flow_l_s / 1000.0
    diameter_m = pipe_internal_diameter_mm / 1000.0
    hazen_williams_loss_m = (
        10.67 * rising_main_length_m * flow_m3_s**1.852 / (hazen_williams_c**1.852 * diameter_m**4.871)
    )
    total_dynamic_head_m = static_head_m + hazen_williams_loss_m
    hydraulic_power_kw = fluid_density_kg_m3 * _G * flow_m3_s * total_dynamic_head_m / 1000.0
    motor_input_power_kw = hydraulic_power_kw / (pump_efficiency * motor_efficiency)
    pipe_area_m2 = math.pi / 4.0 * diameter_m**2
    steady_velocity_m_s = flow_m3_s / pipe_area_m2
    velocity_change_m_s = steady_velocity_m_s * velocity_change_fraction
    surge_pressure_rise_kpa = fluid_density_kg_m3 * wave_speed_m_s * velocity_change_m_s / 1000.0
    peak_transient_pressure_kpa = base_pressure_kpa + surge_pressure_rise_kpa
    pressure_trip_margin_kpa = high_high_trip_setpoint_kpa - peak_transient_pressure_kpa
    pipe_pressure_margin_kpa = pipe_pressure_class_kpa - peak_transient_pressure_kpa
    feeder_current_a = motor_input_power_kw * 1000.0 / (math.sqrt(3.0) * feeder_voltage_v * motor_power_factor)
    feeder_voltage_drop_percent = (
        math.sqrt(3.0) * feeder_current_a * conductor_resistance_ohm_km * feeder_length_km / feeder_voltage_v * 100.0
    )
    voltage_drop_margin_percent = allowable_voltage_drop_percent - feeder_voltage_drop_percent

    pass_checks = [
        pressure_trip_margin_kpa >= 0.0,
        pipe_pressure_margin_kpa >= 0.0,
        voltage_drop_margin_percent >= 0.0,
    ]

    return {
        "hazen_williams_loss_m": round(hazen_williams_loss_m, 3),
        "total_dynamic_head_m": round(total_dynamic_head_m, 3),
        "hydraulic_power_kw": round(hydraulic_power_kw, 3),
        "motor_input_power_kw": round(motor_input_power_kw, 3),
        "steady_velocity_m_s": round(steady_velocity_m_s, 3),
        "surge_pressure_rise_kpa": round(surge_pressure_rise_kpa, 3),
        "peak_transient_pressure_kpa": round(peak_transient_pressure_kpa, 3),
        "pressure_trip_margin_kpa": round(pressure_trip_margin_kpa, 3),
        "pipe_pressure_margin_kpa": round(pipe_pressure_margin_kpa, 3),
        "feeder_current_a": round(feeder_current_a, 3),
        "feeder_voltage_drop_percent": round(feeder_voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
