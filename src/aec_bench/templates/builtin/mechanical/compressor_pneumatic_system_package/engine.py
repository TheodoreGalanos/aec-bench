# ABOUTME: Computes SSC-06 compressor and pneumatic system metrics.
# ABOUTME: Combines air demand, receiver storage, motor load, feeder drop, and branch pressure checks.

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


def compute(
    connected_air_demand_m3_min: float,
    simultaneity_factor: float,
    leakage_allowance_fraction: float,
    selected_compressor_capacity_m3_min: float,
    receiver_volume_m3: float,
    receiver_pressure_band_kpa: float,
    atmospheric_pressure_kpa_abs: float,
    compressor_specific_power_kw_per_m3_min: float,
    motor_efficiency: float,
    selected_motor_kw: float,
    feeder_voltage_v: float,
    feeder_length_km: float,
    feeder_resistance_ohm_per_km: float,
    feeder_reactance_ohm_per_km: float,
    motor_power_factor: float,
    max_voltage_drop_percent: float,
    branch_pressure_loss_kpa: float,
    max_branch_pressure_loss_kpa: float,
) -> dict[str, float]:
    """Compute source-bound compressor capacity, storage, motor, and feeder metrics."""
    _require_positive(
        connected_air_demand_m3_min=connected_air_demand_m3_min,
        simultaneity_factor=simultaneity_factor,
        selected_compressor_capacity_m3_min=selected_compressor_capacity_m3_min,
        receiver_volume_m3=receiver_volume_m3,
        receiver_pressure_band_kpa=receiver_pressure_band_kpa,
        atmospheric_pressure_kpa_abs=atmospheric_pressure_kpa_abs,
        compressor_specific_power_kw_per_m3_min=compressor_specific_power_kw_per_m3_min,
        motor_efficiency=motor_efficiency,
        selected_motor_kw=selected_motor_kw,
        feeder_voltage_v=feeder_voltage_v,
        feeder_length_km=feeder_length_km,
        motor_power_factor=motor_power_factor,
        max_voltage_drop_percent=max_voltage_drop_percent,
        max_branch_pressure_loss_kpa=max_branch_pressure_loss_kpa,
    )
    _require_nonnegative(
        leakage_allowance_fraction=leakage_allowance_fraction,
        feeder_resistance_ohm_per_km=feeder_resistance_ohm_per_km,
        feeder_reactance_ohm_per_km=feeder_reactance_ohm_per_km,
        branch_pressure_loss_kpa=branch_pressure_loss_kpa,
    )
    if motor_efficiency > 1.0 or motor_power_factor > 1.0:
        msg = "motor efficiency and power factor must be <= 1"
        raise ValueError(msg)

    adjusted_air_demand_m3_min = connected_air_demand_m3_min * simultaneity_factor * (1.0 + leakage_allowance_fraction)
    compressor_capacity_margin_m3_min = selected_compressor_capacity_m3_min - adjusted_air_demand_m3_min
    receiver_storage_runtime_min = (
        receiver_volume_m3 * receiver_pressure_band_kpa / atmospheric_pressure_kpa_abs / adjusted_air_demand_m3_min
    )
    compressor_shaft_power_kw = adjusted_air_demand_m3_min * compressor_specific_power_kw_per_m3_min
    motor_input_power_kw = compressor_shaft_power_kw / motor_efficiency
    motor_size_margin_kw = selected_motor_kw - motor_input_power_kw

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
    pressure_drop_margin_kpa = max_branch_pressure_loss_kpa - branch_pressure_loss_kpa
    overall_pass_score = (
        1.0
        if min(
            compressor_capacity_margin_m3_min,
            motor_size_margin_kw,
            voltage_drop_margin_percent,
            pressure_drop_margin_kpa,
        )
        >= 0.0
        else 0.0
    )

    return {
        "adjusted_air_demand_m3_min": round(adjusted_air_demand_m3_min, 3),
        "compressor_capacity_margin_m3_min": round(compressor_capacity_margin_m3_min, 3),
        "receiver_storage_runtime_min": round(receiver_storage_runtime_min, 3),
        "compressor_shaft_power_kw": round(compressor_shaft_power_kw, 3),
        "motor_input_power_kw": round(motor_input_power_kw, 3),
        "motor_size_margin_kw": round(motor_size_margin_kw, 3),
        "feeder_current_a": round(feeder_current_a, 3),
        "feeder_voltage_drop_percent": round(feeder_voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "pressure_drop_margin_kpa": round(pressure_drop_margin_kpa, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
