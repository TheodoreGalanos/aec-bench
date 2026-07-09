# ABOUTME: Computes SSC-04 coastal flood outfall pump elevation package metrics.
# ABOUTME: Combines tide submergence, flood level, pump storage, and feeder checks.

from __future__ import annotations

import math


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


def _submergence_fraction(
    *,
    invert_level_m: float,
    mean_sea_level_m: float,
    tidal_amplitude_m: float,
) -> float:
    """Return sinusoidal tide fraction above the outfall invert."""
    if tidal_amplitude_m == 0.0:
        return 1.0 if mean_sea_level_m > invert_level_m else 0.0

    tide_ratio = (invert_level_m - mean_sea_level_m) / tidal_amplitude_m
    if tide_ratio >= 1.0:
        return 0.0
    if tide_ratio <= -1.0:
        return 1.0
    return 0.5 - math.asin(tide_ratio) / math.pi


def compute(
    present_mean_sea_level_m: float,
    tidal_amplitude_m: float,
    sea_level_rise_allowance_m: float,
    storm_surge_allowance_m: float,
    wave_runup_allowance_m: float,
    equipment_freeboard_allowance_m: float,
    outfall_invert_level_m: float,
    peak_inflow_m3_s: float,
    tide_locked_duration_h: float,
    pump_discharge_m3_s: float,
    available_storage_m3: float,
    wetwell_low_operating_level_m: float,
    pipe_and_valve_losses_m: float,
    pump_efficiency: float,
    motor_efficiency: float,
    selected_motor_power_kw: float,
    switchboard_elevation_m: float,
    controls_elevation_m: float,
    feeder_voltage_v: float,
    motor_power_factor: float,
    feeder_resistance_ohm_km: float,
    feeder_reactance_ohm_km: float,
    feeder_length_km: float,
    voltage_drop_limit_percent: float,
) -> dict[str, float]:
    """Compute coastal flood/outfall/pump/electrical metrics for the SSC-04 source pack."""
    _require_positive(
        tidal_amplitude_m=tidal_amplitude_m,
        peak_inflow_m3_s=peak_inflow_m3_s,
        tide_locked_duration_h=tide_locked_duration_h,
        pump_discharge_m3_s=pump_discharge_m3_s,
        available_storage_m3=available_storage_m3,
        pump_efficiency=pump_efficiency,
        motor_efficiency=motor_efficiency,
        selected_motor_power_kw=selected_motor_power_kw,
        feeder_voltage_v=feeder_voltage_v,
        motor_power_factor=motor_power_factor,
        feeder_resistance_ohm_km=feeder_resistance_ohm_km,
        feeder_reactance_ohm_km=feeder_reactance_ohm_km,
        feeder_length_km=feeder_length_km,
        voltage_drop_limit_percent=voltage_drop_limit_percent,
    )
    _require_nonnegative(
        sea_level_rise_allowance_m=sea_level_rise_allowance_m,
        storm_surge_allowance_m=storm_surge_allowance_m,
        wave_runup_allowance_m=wave_runup_allowance_m,
        equipment_freeboard_allowance_m=equipment_freeboard_allowance_m,
        pipe_and_valve_losses_m=pipe_and_valve_losses_m,
    )
    if pump_efficiency > 1.0 or motor_efficiency > 1.0:
        msg = "pump_efficiency and motor_efficiency must be <= 1.0"
        raise ValueError(msg)
    if motor_power_factor <= 0.0 or motor_power_factor > 1.0:
        msg = "motor_power_factor must be > 0 and <= 1.0"
        raise ValueError(msg)

    present_submergence_fraction = _submergence_fraction(
        invert_level_m=outfall_invert_level_m,
        mean_sea_level_m=present_mean_sea_level_m,
        tidal_amplitude_m=tidal_amplitude_m,
    )
    future_submergence_fraction = _submergence_fraction(
        invert_level_m=outfall_invert_level_m,
        mean_sea_level_m=present_mean_sea_level_m + sea_level_rise_allowance_m,
        tidal_amplitude_m=tidal_amplitude_m,
    )

    design_stillwater_level_m = (
        present_mean_sea_level_m + tidal_amplitude_m + sea_level_rise_allowance_m + storm_surge_allowance_m
    )
    design_flood_level_m = design_stillwater_level_m + wave_runup_allowance_m
    minimum_equipment_elevation_m = design_flood_level_m + equipment_freeboard_allowance_m

    event_seconds = tide_locked_duration_h * 3600.0
    inflow_volume_m3 = peak_inflow_m3_s * event_seconds
    pumped_volume_m3 = pump_discharge_m3_s * event_seconds
    storage_margin_m3 = available_storage_m3 + pumped_volume_m3 - inflow_volume_m3

    pump_total_dynamic_head_m = design_flood_level_m - wetwell_low_operating_level_m + pipe_and_valve_losses_m
    pump_hydraulic_power_kw = 1000.0 * 9.81 * pump_discharge_m3_s * pump_total_dynamic_head_m / 1000.0
    pump_motor_input_kw = pump_hydraulic_power_kw / (pump_efficiency * motor_efficiency)
    pump_motor_margin_kw = selected_motor_power_kw - pump_motor_input_kw

    switchboard_freeboard_margin_m = switchboard_elevation_m - minimum_equipment_elevation_m
    controls_freeboard_margin_m = controls_elevation_m - minimum_equipment_elevation_m

    feeder_current_a = pump_motor_input_kw * 1000.0 / (math.sqrt(3.0) * feeder_voltage_v * motor_power_factor)
    sin_phi = math.sqrt(1.0 - motor_power_factor**2)
    feeder_voltage_drop_percent = (
        math.sqrt(3.0)
        * feeder_current_a
        * (feeder_resistance_ohm_km * motor_power_factor + feeder_reactance_ohm_km * sin_phi)
        * feeder_length_km
        / feeder_voltage_v
        * 100.0
    )
    voltage_drop_margin_percent = voltage_drop_limit_percent - feeder_voltage_drop_percent

    overall_pass_score = (
        1.0
        if (
            storage_margin_m3 >= 0.0
            and pump_motor_margin_kw >= 0.0
            and switchboard_freeboard_margin_m >= 0.0
            and controls_freeboard_margin_m >= 0.0
            and voltage_drop_margin_percent >= 0.0
        )
        else 0.0
    )

    return {
        "present_submergence_percent": round(present_submergence_fraction * 100.0, 3),
        "future_submergence_percent": round(future_submergence_fraction * 100.0, 3),
        "submergence_increase_percent": round(
            (future_submergence_fraction - present_submergence_fraction) * 100.0,
            3,
        ),
        "design_stillwater_level_m": round(design_stillwater_level_m, 3),
        "design_flood_level_m": round(design_flood_level_m, 3),
        "minimum_equipment_elevation_m": round(minimum_equipment_elevation_m, 3),
        "inflow_volume_m3": round(inflow_volume_m3, 3),
        "pumped_volume_m3": round(pumped_volume_m3, 3),
        "storage_margin_m3": round(storage_margin_m3, 3),
        "pump_total_dynamic_head_m": round(pump_total_dynamic_head_m, 3),
        "pump_hydraulic_power_kw": round(pump_hydraulic_power_kw, 3),
        "pump_motor_input_kw": round(pump_motor_input_kw, 3),
        "pump_motor_margin_kw": round(pump_motor_margin_kw, 3),
        "switchboard_freeboard_margin_m": round(switchboard_freeboard_margin_m, 3),
        "controls_freeboard_margin_m": round(controls_freeboard_margin_m, 3),
        "feeder_current_a": round(feeder_current_a, 3),
        "feeder_voltage_drop_percent": round(feeder_voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
