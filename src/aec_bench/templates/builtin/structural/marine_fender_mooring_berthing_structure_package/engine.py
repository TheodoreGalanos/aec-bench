# ABOUTME: Computes SSC-14 marine fender mooring and berthing structure metrics.
# ABOUTME: Combines berthing energy, fender, mooring, water-level, and support load checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    vessel_displacement_t: float,
    berthing_velocity_m_s: float,
    berthing_coefficient: float,
    fender_demand_factor: float,
    fender_energy_capacity_kj: float,
    fender_stroke_m: float,
    wind_pressure_kpa: float,
    vessel_projected_area_m2: float,
    wind_drag_coefficient: float,
    active_mooring_line_count: int,
    mooring_line_angle_deg: float,
    mooring_line_capacity_kn: float,
    design_water_level_m: float,
    deck_level_m: float,
    required_freeboard_m: float,
    vertical_support_load_kn: float,
    vertical_load_factor: float,
    fender_reaction_combination_factor: float,
) -> dict[str, float]:
    """Compute deterministic SSC-14 marine fender and mooring metrics."""
    _require_positive(
        vessel_displacement_t=vessel_displacement_t,
        berthing_velocity_m_s=berthing_velocity_m_s,
        berthing_coefficient=berthing_coefficient,
        fender_demand_factor=fender_demand_factor,
        fender_energy_capacity_kj=fender_energy_capacity_kj,
        fender_stroke_m=fender_stroke_m,
        wind_pressure_kpa=wind_pressure_kpa,
        vessel_projected_area_m2=vessel_projected_area_m2,
        wind_drag_coefficient=wind_drag_coefficient,
        mooring_line_capacity_kn=mooring_line_capacity_kn,
        vertical_support_load_kn=vertical_support_load_kn,
        vertical_load_factor=vertical_load_factor,
        fender_reaction_combination_factor=fender_reaction_combination_factor,
    )
    if active_mooring_line_count <= 0:
        msg = "active_mooring_line_count must be > 0"
        raise ValueError(msg)

    berthing_energy_kj = 0.5 * vessel_displacement_t * 1000.0 * berthing_velocity_m_s**2 / 1000.0
    berthing_energy_kj *= berthing_coefficient
    fender_energy_demand_kj = berthing_energy_kj * fender_demand_factor
    fender_energy_utilization = fender_energy_demand_kj / fender_energy_capacity_kj
    fender_reaction_kn = fender_energy_demand_kj / fender_stroke_m
    mooring_wind_force_kn = wind_pressure_kpa * vessel_projected_area_m2 * wind_drag_coefficient
    mooring_line_demand_kn = mooring_wind_force_kn / (
        active_mooring_line_count * math.cos(math.radians(mooring_line_angle_deg))
    )
    mooring_utilization = mooring_line_demand_kn / mooring_line_capacity_kn
    water_level_margin_m = deck_level_m - design_water_level_m - required_freeboard_m
    combined_support_load_kn = (
        vertical_support_load_kn * vertical_load_factor + fender_reaction_kn * fender_reaction_combination_factor
    )

    pass_checks = [
        fender_energy_utilization <= 1.0,
        mooring_utilization <= 1.0,
        water_level_margin_m >= 0.0,
    ]

    return {
        "berthing_energy_kj": round(berthing_energy_kj, 3),
        "fender_energy_demand_kj": round(fender_energy_demand_kj, 3),
        "fender_energy_utilization": round(fender_energy_utilization, 3),
        "fender_reaction_kn": round(fender_reaction_kn, 3),
        "mooring_wind_force_kn": round(mooring_wind_force_kn, 3),
        "mooring_line_demand_kn": round(mooring_line_demand_kn, 3),
        "mooring_utilization": round(mooring_utilization, 3),
        "water_level_margin_m": round(water_level_margin_m, 3),
        "combined_support_load_kn": round(combined_support_load_kn, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
