# ABOUTME: Computes SSC-09 canopy, signage, lighting, and envelope fixing metrics.
# ABOUTME: Combines wind/dead load, fixing capacity, anchor group margin, lighting current, and voltage drop.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    sign_area_m2: float,
    canopy_area_m2: float,
    wind_pressure_kpa: float,
    sign_dead_load_kpa: float,
    canopy_dead_load_kpa: float,
    fixing_capacity_kn: float,
    anchor_count: float,
    anchor_capacity_kn: float,
    lighting_load_w: float,
    driver_load_w: float,
    sign_control_load_w: float,
    feeder_voltage_v: float,
    cable_length_m: float,
    conductor_resistance_ohm_km: float,
    max_voltage_drop_percent: float,
) -> dict[str, float]:
    """Compute deterministic canopy signage lighting and fixing metrics."""
    _require_positive(
        sign_area_m2=sign_area_m2,
        canopy_area_m2=canopy_area_m2,
        wind_pressure_kpa=wind_pressure_kpa,
        fixing_capacity_kn=fixing_capacity_kn,
        anchor_count=anchor_count,
        anchor_capacity_kn=anchor_capacity_kn,
        lighting_load_w=lighting_load_w,
        feeder_voltage_v=feeder_voltage_v,
        cable_length_m=cable_length_m,
        conductor_resistance_ohm_km=conductor_resistance_ohm_km,
        max_voltage_drop_percent=max_voltage_drop_percent,
    )

    wind_load_kn = (sign_area_m2 + canopy_area_m2) * wind_pressure_kpa
    dead_load_kn = sign_area_m2 * sign_dead_load_kpa + canopy_area_m2 * canopy_dead_load_kpa
    combined_fixing_demand_kn = math.hypot(wind_load_kn, dead_load_kn)
    fixing_capacity_margin_kn = fixing_capacity_kn - combined_fixing_demand_kn
    anchor_group_margin_kn = anchor_count * anchor_capacity_kn - combined_fixing_demand_kn
    lighting_connected_load_w = lighting_load_w + driver_load_w + sign_control_load_w
    lighting_current_a = lighting_connected_load_w / feeder_voltage_v
    voltage_drop_percent = (
        2.0 * lighting_current_a * cable_length_m * conductor_resistance_ohm_km / 1000.0 / feeder_voltage_v * 100.0
    )
    voltage_drop_margin_percent = max_voltage_drop_percent - voltage_drop_percent

    pass_checks = [
        fixing_capacity_margin_kn >= 0.0,
        anchor_group_margin_kn >= 0.0,
        voltage_drop_margin_percent >= 0.0,
    ]

    return {
        "wind_load_kn": round(wind_load_kn, 3),
        "dead_load_kn": round(dead_load_kn, 3),
        "combined_fixing_demand_kn": round(combined_fixing_demand_kn, 3),
        "fixing_capacity_margin_kn": round(fixing_capacity_margin_kn, 3),
        "anchor_group_margin_kn": round(anchor_group_margin_kn, 3),
        "lighting_connected_load_w": round(lighting_connected_load_w, 3),
        "lighting_current_a": round(lighting_current_a, 3),
        "voltage_drop_percent": round(voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
