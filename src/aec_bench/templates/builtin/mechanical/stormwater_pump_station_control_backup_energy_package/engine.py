# ABOUTME: Computes SSC-03 stormwater pump control and backup-energy metrics.
# ABOUTME: Combines pump capacity, rising-main losses, power, battery autonomy, and wet-well freeboard.

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
    pump_capacity_l_s: float,
    pump_count: float,
    inflow_peak_l_s: float,
    static_head_m: float,
    rising_main_length_m: float,
    pipe_internal_diameter_mm: float,
    hazen_williams_c: float,
    pump_efficiency: float,
    motor_efficiency: float,
    fluid_density_kg_m3: float,
    control_panel_load_kw: float,
    telemetry_load_kw: float,
    outage_duration_hr: float,
    usable_battery_energy_kwh: float,
    wetwell_high_water_level_m: float,
    access_level_m: float,
    minimum_wetwell_freeboard_m: float,
) -> dict[str, float]:
    """Compute deterministic SSC-03 stormwater pump station metrics."""
    _require_positive(
        pump_capacity_l_s=pump_capacity_l_s,
        pump_count=pump_count,
        inflow_peak_l_s=inflow_peak_l_s,
        static_head_m=static_head_m,
        rising_main_length_m=rising_main_length_m,
        pipe_internal_diameter_mm=pipe_internal_diameter_mm,
        hazen_williams_c=hazen_williams_c,
        pump_efficiency=pump_efficiency,
        motor_efficiency=motor_efficiency,
        fluid_density_kg_m3=fluid_density_kg_m3,
        outage_duration_hr=outage_duration_hr,
        usable_battery_energy_kwh=usable_battery_energy_kwh,
        minimum_wetwell_freeboard_m=minimum_wetwell_freeboard_m,
    )

    total_pump_capacity_l_s = pump_capacity_l_s * pump_count
    pump_capacity_margin_l_s = total_pump_capacity_l_s - inflow_peak_l_s
    flow_m3_s = pump_capacity_l_s / 1000.0
    diameter_m = pipe_internal_diameter_mm / 1000.0
    hazen_williams_loss_m = (
        10.67 * rising_main_length_m * flow_m3_s**1.852 / (hazen_williams_c**1.852 * diameter_m**4.871)
    )
    total_dynamic_head_m = static_head_m + hazen_williams_loss_m
    rising_main_velocity_m_s = flow_m3_s / (math.pi / 4.0 * diameter_m**2)
    hydraulic_power_kw = fluid_density_kg_m3 * _G * flow_m3_s * total_dynamic_head_m / 1000.0
    motor_input_power_kw = hydraulic_power_kw / (pump_efficiency * motor_efficiency)
    control_load_kw = control_panel_load_kw + telemetry_load_kw
    backup_energy_required_kwh = control_load_kw * outage_duration_hr
    backup_energy_margin_kwh = usable_battery_energy_kwh - backup_energy_required_kwh
    wetwell_freeboard_m = access_level_m - wetwell_high_water_level_m
    wetwell_freeboard_margin_m = wetwell_freeboard_m - minimum_wetwell_freeboard_m

    pass_checks = [
        pump_capacity_margin_l_s >= 0.0,
        backup_energy_margin_kwh >= 0.0,
        wetwell_freeboard_margin_m >= 0.0,
    ]

    return {
        "total_pump_capacity_l_s": round(total_pump_capacity_l_s, 3),
        "pump_capacity_margin_l_s": round(pump_capacity_margin_l_s, 3),
        "hazen_williams_loss_m": round(hazen_williams_loss_m, 3),
        "total_dynamic_head_m": round(total_dynamic_head_m, 3),
        "rising_main_velocity_m_s": round(rising_main_velocity_m_s, 3),
        "hydraulic_power_kw": round(hydraulic_power_kw, 3),
        "motor_input_power_kw": round(motor_input_power_kw, 3),
        "control_load_kw": round(control_load_kw, 3),
        "backup_energy_required_kwh": round(backup_energy_required_kwh, 3),
        "backup_energy_margin_kwh": round(backup_energy_margin_kwh, 3),
        "wetwell_freeboard_m": round(wetwell_freeboard_m, 3),
        "wetwell_freeboard_margin_m": round(wetwell_freeboard_margin_m, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
