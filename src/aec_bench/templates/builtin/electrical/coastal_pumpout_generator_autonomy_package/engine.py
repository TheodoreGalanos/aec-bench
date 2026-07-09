# ABOUTME: Computes SSC-04 coastal pump-out and generator autonomy metrics.
# ABOUTME: Combines flood volume, pump duty, emergency load, generator, fuel, BESS, and access checks.

from __future__ import annotations


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
    inflow_rate_m3_s: float,
    event_duration_h: float,
    pump_discharge_m3_s: float,
    available_storage_m3: float,
    flood_level_m: float,
    sump_low_level_m: float,
    piping_losses_m: float,
    pump_efficiency: float,
    motor_efficiency: float,
    active_pump_count: float,
    controls_load_kw: float,
    lighting_load_kw: float,
    generator_capacity_kw: float,
    generator_derate_factor: float,
    fuel_volume_l: float,
    fuel_consumption_l_h: float,
    required_runtime_h: float,
    bess_capacity_kwh: float,
    bess_usable_fraction: float,
    minimum_bess_runtime_h: float,
    access_elevation_m: float,
    required_access_freeboard_m: float,
) -> dict[str, float]:
    """Compute deterministic coastal pump-out generator autonomy metrics."""
    _require_positive(
        inflow_rate_m3_s=inflow_rate_m3_s,
        event_duration_h=event_duration_h,
        pump_discharge_m3_s=pump_discharge_m3_s,
        available_storage_m3=available_storage_m3,
        flood_level_m=flood_level_m,
        pump_efficiency=pump_efficiency,
        motor_efficiency=motor_efficiency,
        active_pump_count=active_pump_count,
        generator_capacity_kw=generator_capacity_kw,
        generator_derate_factor=generator_derate_factor,
        fuel_volume_l=fuel_volume_l,
        fuel_consumption_l_h=fuel_consumption_l_h,
        required_runtime_h=required_runtime_h,
        bess_capacity_kwh=bess_capacity_kwh,
        bess_usable_fraction=bess_usable_fraction,
        minimum_bess_runtime_h=minimum_bess_runtime_h,
        access_elevation_m=access_elevation_m,
        required_access_freeboard_m=required_access_freeboard_m,
    )
    _require_nonnegative(
        sump_low_level_m=sump_low_level_m,
        piping_losses_m=piping_losses_m,
        controls_load_kw=controls_load_kw,
        lighting_load_kw=lighting_load_kw,
    )

    inflow_volume_m3 = inflow_rate_m3_s * event_duration_h * 3600.0
    pumped_volume_m3 = pump_discharge_m3_s * event_duration_h * 3600.0
    storage_margin_m3 = available_storage_m3 + pumped_volume_m3 - inflow_volume_m3
    pump_total_dynamic_head_m = flood_level_m - sump_low_level_m + piping_losses_m
    pump_input_power_kw = (
        1000.0 * 9.81 * pump_discharge_m3_s * pump_total_dynamic_head_m / 1000.0 / (pump_efficiency * motor_efficiency)
    )
    emergency_load_kw = pump_input_power_kw * active_pump_count + controls_load_kw + lighting_load_kw
    generator_capacity_margin_kw = generator_capacity_kw * generator_derate_factor - emergency_load_kw
    fuel_runtime_margin_h = fuel_volume_l / fuel_consumption_l_h - required_runtime_h
    bess_runtime_h = bess_capacity_kwh * bess_usable_fraction / emergency_load_kw
    access_freeboard_margin_m = access_elevation_m - (flood_level_m + required_access_freeboard_m)

    pass_checks = [
        storage_margin_m3 >= 0.0,
        generator_capacity_margin_kw >= 0.0,
        fuel_runtime_margin_h >= 0.0,
        bess_runtime_h >= minimum_bess_runtime_h,
        access_freeboard_margin_m >= 0.0,
    ]

    return {
        "inflow_volume_m3": round(inflow_volume_m3, 3),
        "pumped_volume_m3": round(pumped_volume_m3, 3),
        "storage_margin_m3": round(storage_margin_m3, 3),
        "pump_total_dynamic_head_m": round(pump_total_dynamic_head_m, 3),
        "pump_input_power_kw": round(pump_input_power_kw, 3),
        "emergency_load_kw": round(emergency_load_kw, 3),
        "generator_capacity_margin_kw": round(generator_capacity_margin_kw, 3),
        "fuel_runtime_margin_h": round(fuel_runtime_margin_h, 3),
        "bess_runtime_h": round(bess_runtime_h, 3),
        "access_freeboard_margin_m": round(access_freeboard_margin_m, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
