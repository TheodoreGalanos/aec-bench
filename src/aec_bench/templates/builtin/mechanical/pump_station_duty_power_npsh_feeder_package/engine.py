# ABOUTME: Computes SSC-06 pump station duty, power, NPSH, and feeder metrics.
# ABOUTME: Combines rising-main losses, pump curve margin, motor power, NPSH, and voltage drop.

from __future__ import annotations

import math

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
    design_flow_l_s: float,
    static_lift_m: float,
    rising_main_length_m: float,
    rising_main_diameter_mm: float,
    hazen_williams_c: float,
    minor_loss_coefficient: float,
    pump_curve_head_at_duty_m: float,
    fluid_density_kg_m3: float,
    pump_efficiency_pct: float,
    motor_efficiency_pct: float,
    motor_service_factor: float,
    selected_motor_kw: float,
    atmospheric_pressure_kpa_abs: float,
    vapor_pressure_kpa_abs: float,
    wetwell_min_level_above_pump_m: float,
    suction_loss_m: float,
    npsh_required_m: float,
    feeder_voltage_v: float,
    feeder_length_km: float,
    feeder_resistance_ohm_per_km: float,
    feeder_reactance_ohm_per_km: float,
    motor_power_factor: float,
    max_voltage_drop_percent: float,
) -> dict[str, float]:
    """Compute source-bound pump duty, motor, NPSH, and feeder metrics."""
    _require_positive(
        design_flow_l_s=design_flow_l_s,
        static_lift_m=static_lift_m,
        rising_main_length_m=rising_main_length_m,
        rising_main_diameter_mm=rising_main_diameter_mm,
        hazen_williams_c=hazen_williams_c,
        pump_curve_head_at_duty_m=pump_curve_head_at_duty_m,
        fluid_density_kg_m3=fluid_density_kg_m3,
        pump_efficiency_pct=pump_efficiency_pct,
        motor_efficiency_pct=motor_efficiency_pct,
        motor_service_factor=motor_service_factor,
        selected_motor_kw=selected_motor_kw,
        atmospheric_pressure_kpa_abs=atmospheric_pressure_kpa_abs,
        npsh_required_m=npsh_required_m,
        feeder_voltage_v=feeder_voltage_v,
        feeder_length_km=feeder_length_km,
        motor_power_factor=motor_power_factor,
        max_voltage_drop_percent=max_voltage_drop_percent,
    )
    _require_nonnegative(
        minor_loss_coefficient=minor_loss_coefficient,
        vapor_pressure_kpa_abs=vapor_pressure_kpa_abs,
        wetwell_min_level_above_pump_m=wetwell_min_level_above_pump_m,
        suction_loss_m=suction_loss_m,
        feeder_resistance_ohm_per_km=feeder_resistance_ohm_per_km,
        feeder_reactance_ohm_per_km=feeder_reactance_ohm_per_km,
    )
    if pump_efficiency_pct > 100.0:
        msg = "pump_efficiency_pct must be <= 100"
        raise ValueError(msg)
    if motor_efficiency_pct > 100.0:
        msg = "motor_efficiency_pct must be <= 100"
        raise ValueError(msg)
    if motor_service_factor < 1.0:
        msg = "motor_service_factor must be >= 1"
        raise ValueError(msg)
    if vapor_pressure_kpa_abs >= atmospheric_pressure_kpa_abs:
        msg = "vapor_pressure_kpa_abs must be < atmospheric_pressure_kpa_abs"
        raise ValueError(msg)
    if motor_power_factor > 1.0:
        msg = "motor_power_factor must be <= 1"
        raise ValueError(msg)

    design_flow_m3_s = design_flow_l_s / 1000.0
    rising_main_diameter_m = rising_main_diameter_mm / 1000.0
    hazen_williams_headloss_m = (
        10.67
        * rising_main_length_m
        * design_flow_m3_s**1.852
        / (hazen_williams_c**1.852 * rising_main_diameter_m**4.87)
    )
    flow_area_m2 = math.pi * rising_main_diameter_m**2 / 4.0
    flow_velocity_m_s = design_flow_m3_s / flow_area_m2
    minor_loss_m = minor_loss_coefficient * flow_velocity_m_s**2 / (2.0 * _G)
    total_dynamic_head_m = static_lift_m + hazen_williams_headloss_m + minor_loss_m
    pump_curve_head_margin_m = pump_curve_head_at_duty_m - total_dynamic_head_m

    pump_efficiency = pump_efficiency_pct / 100.0
    motor_efficiency = motor_efficiency_pct / 100.0
    hydraulic_power_kw = fluid_density_kg_m3 * _G * design_flow_m3_s * total_dynamic_head_m / 1000.0
    shaft_power_kw = hydraulic_power_kw / pump_efficiency
    motor_input_power_kw = shaft_power_kw / motor_efficiency
    required_motor_power_kw = shaft_power_kw * motor_service_factor
    motor_size_margin_kw = selected_motor_kw - required_motor_power_kw

    pressure_head_m = (atmospheric_pressure_kpa_abs - vapor_pressure_kpa_abs) * 1000.0 / (fluid_density_kg_m3 * _G)
    npsh_available_m = pressure_head_m + wetwell_min_level_above_pump_m - suction_loss_m
    npsh_margin_m = npsh_available_m - npsh_required_m
    npsh_margin_ratio = npsh_available_m / npsh_required_m

    load_reactive_power_kvar = motor_input_power_kw * math.tan(math.acos(motor_power_factor))
    apparent_power_kva = math.hypot(motor_input_power_kw, load_reactive_power_kvar)
    feeder_current_a = apparent_power_kva * 1000.0 / (math.sqrt(3.0) * feeder_voltage_v)
    reactive_factor = load_reactive_power_kvar / apparent_power_kva
    voltage_drop_v = (
        math.sqrt(3.0)
        * feeder_current_a
        * feeder_length_km
        * (feeder_resistance_ohm_per_km * motor_power_factor + feeder_reactance_ohm_per_km * reactive_factor)
    )
    feeder_voltage_drop_percent = voltage_drop_v / feeder_voltage_v * 100.0
    voltage_drop_margin_percent = max_voltage_drop_percent - feeder_voltage_drop_percent

    overall_pass_score = (
        1.0
        if min(pump_curve_head_margin_m, npsh_margin_m, motor_size_margin_kw, voltage_drop_margin_percent) >= 0.0
        else 0.0
    )

    return {
        "hazen_williams_headloss_m": round(hazen_williams_headloss_m, 3),
        "flow_velocity_m_s": round(flow_velocity_m_s, 3),
        "minor_loss_m": round(minor_loss_m, 3),
        "total_dynamic_head_m": round(total_dynamic_head_m, 3),
        "pump_curve_head_margin_m": round(pump_curve_head_margin_m, 3),
        "hydraulic_power_kw": round(hydraulic_power_kw, 3),
        "shaft_power_kw": round(shaft_power_kw, 3),
        "motor_input_power_kw": round(motor_input_power_kw, 3),
        "required_motor_power_kw": round(required_motor_power_kw, 3),
        "motor_size_margin_kw": round(motor_size_margin_kw, 3),
        "npsh_available_m": round(npsh_available_m, 3),
        "npsh_margin_m": round(npsh_margin_m, 3),
        "npsh_margin_ratio": round(npsh_margin_ratio, 3),
        "load_reactive_power_kvar": round(load_reactive_power_kvar, 3),
        "feeder_current_a": round(feeder_current_a, 3),
        "feeder_voltage_drop_percent": round(feeder_voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
