# ABOUTME: Computes SSC-01 roadside cabinet flood, heat, and backup energy metrics.
# ABOUTME: Combines flood freeboard, thermal derating, battery/BESS, feeder, and AECI checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    cabinet_pad_level_m: float,
    hgl_level_m: float,
    inundation_level_m: float,
    minimum_freeboard_m: float,
    enclosure_capacity_w_at_reference_temp: float,
    reference_temperature_c: float,
    event_temperature_c: float,
    derate_pct_per_c: float,
    critical_load_w: float,
    battery_capacity_kwh: float,
    battery_efficiency: float,
    required_backup_h: float,
    bess_inverter_capacity_kw: float,
    feeder_length_km: float,
    conductor_resistance_ohm_km: float,
    feeder_voltage_v: float,
    power_factor: float,
    allowable_voltage_drop_pct: float,
    road_lighting_power_w: float,
    annual_operating_hours: float,
    lit_area_m2: float,
) -> dict[str, float]:
    """Compute deterministic SSC-01 roadside cabinet flood, heat, and backup energy metrics."""
    _require_positive(
        enclosure_capacity_w_at_reference_temp=enclosure_capacity_w_at_reference_temp,
        derate_pct_per_c=derate_pct_per_c,
        critical_load_w=critical_load_w,
        battery_capacity_kwh=battery_capacity_kwh,
        battery_efficiency=battery_efficiency,
        required_backup_h=required_backup_h,
        bess_inverter_capacity_kw=bess_inverter_capacity_kw,
        feeder_length_km=feeder_length_km,
        conductor_resistance_ohm_km=conductor_resistance_ohm_km,
        feeder_voltage_v=feeder_voltage_v,
        power_factor=power_factor,
        allowable_voltage_drop_pct=allowable_voltage_drop_pct,
        road_lighting_power_w=road_lighting_power_w,
        annual_operating_hours=annual_operating_hours,
        lit_area_m2=lit_area_m2,
    )
    controlling_water_level_m = max(hgl_level_m, inundation_level_m)
    cabinet_freeboard_m = cabinet_pad_level_m - controlling_water_level_m
    flood_freeboard_margin_m = cabinet_freeboard_m - minimum_freeboard_m
    derate_fraction = derate_pct_per_c / 100.0 * (event_temperature_c - reference_temperature_c)
    thermal_derated_capacity_w = enclosure_capacity_w_at_reference_temp * (1.0 - derate_fraction)
    thermal_margin_w = thermal_derated_capacity_w - critical_load_w
    thermal_utilization = critical_load_w / thermal_derated_capacity_w
    battery_runtime_h = battery_capacity_kwh * battery_efficiency / (critical_load_w / 1000.0)
    battery_margin_h = battery_runtime_h - required_backup_h
    bess_power_margin_kw = bess_inverter_capacity_kw - critical_load_w / 1000.0
    bess_energy_margin_kwh = battery_capacity_kwh * battery_efficiency - critical_load_w / 1000.0 * required_backup_h
    feeder_current_a = critical_load_w / (feeder_voltage_v * power_factor)
    feeder_voltage_drop_percent = (
        2.0 * feeder_length_km * conductor_resistance_ohm_km * feeder_current_a / feeder_voltage_v * 100.0
    )
    voltage_drop_margin_percent = allowable_voltage_drop_pct - feeder_voltage_drop_percent
    road_lighting_aeci_kwh_m2_y = road_lighting_power_w * annual_operating_hours / 1000.0 / lit_area_m2

    pass_checks = [
        flood_freeboard_margin_m >= 0.0,
        thermal_margin_w >= 0.0,
        battery_margin_h >= 0.0,
        bess_power_margin_kw >= 0.0,
        bess_energy_margin_kwh >= 0.0,
        voltage_drop_margin_percent >= 0.0,
    ]

    return {
        "cabinet_freeboard_m": round(cabinet_freeboard_m, 3),
        "flood_freeboard_margin_m": round(flood_freeboard_margin_m, 3),
        "thermal_derated_capacity_w": round(thermal_derated_capacity_w, 3),
        "thermal_margin_w": round(thermal_margin_w, 3),
        "thermal_utilization": round(thermal_utilization, 3),
        "battery_runtime_h": round(battery_runtime_h, 3),
        "battery_margin_h": round(battery_margin_h, 3),
        "bess_power_margin_kw": round(bess_power_margin_kw, 3),
        "bess_energy_margin_kwh": round(bess_energy_margin_kwh, 3),
        "feeder_voltage_drop_percent": round(feeder_voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "road_lighting_aeci_kwh_m2_y": round(road_lighting_aeci_kwh_m2_y, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
