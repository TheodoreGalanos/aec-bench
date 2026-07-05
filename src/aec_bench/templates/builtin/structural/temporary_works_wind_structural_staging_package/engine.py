# ABOUTME: Computes SSC-16 temporary works wind and structural staging metrics.
# ABOUTME: Combines wind pressure, anchor demand, ballast stability, and tolerance checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    regional_wind_speed_m_s: float,
    terrain_multiplier: float,
    direction_multiplier: float,
    shielding_multiplier: float,
    air_density_kg_m3: float,
    force_coefficient: float,
    temporary_panel_area_m2: float,
    anchor_count: float,
    anchor_load_factor: float,
    selected_anchor_capacity_kn: float,
    wind_centroid_height_m: float,
    ballast_weight_kn: float,
    ballast_arm_m: float,
    required_stability_ratio: float,
    provided_slot_length_mm: float,
    required_movement_mm: float,
    allowed_vertical_tolerance_mm: float,
    measured_vertical_tolerance_mm: float,
) -> dict[str, float]:
    """Compute deterministic temporary works wind and staging checks."""
    _require_positive(
        regional_wind_speed_m_s=regional_wind_speed_m_s,
        terrain_multiplier=terrain_multiplier,
        direction_multiplier=direction_multiplier,
        shielding_multiplier=shielding_multiplier,
        air_density_kg_m3=air_density_kg_m3,
        force_coefficient=force_coefficient,
        temporary_panel_area_m2=temporary_panel_area_m2,
        anchor_count=anchor_count,
        anchor_load_factor=anchor_load_factor,
        selected_anchor_capacity_kn=selected_anchor_capacity_kn,
        wind_centroid_height_m=wind_centroid_height_m,
        ballast_weight_kn=ballast_weight_kn,
        ballast_arm_m=ballast_arm_m,
        required_stability_ratio=required_stability_ratio,
        provided_slot_length_mm=provided_slot_length_mm,
        required_movement_mm=required_movement_mm,
        allowed_vertical_tolerance_mm=allowed_vertical_tolerance_mm,
    )
    if measured_vertical_tolerance_mm < 0:
        msg = "measured_vertical_tolerance_mm must be >= 0"
        raise ValueError(msg)

    site_wind_speed_m_s = regional_wind_speed_m_s * terrain_multiplier * direction_multiplier * shielding_multiplier
    wind_pressure_kpa = 0.5 * air_density_kg_m3 * site_wind_speed_m_s**2 / 1000.0
    temporary_panel_wind_force_kn = wind_pressure_kpa * force_coefficient * temporary_panel_area_m2
    anchor_demand_kn = temporary_panel_wind_force_kn * anchor_load_factor / anchor_count
    anchor_capacity_margin_kn = selected_anchor_capacity_kn - anchor_demand_kn
    overturning_moment_knm = temporary_panel_wind_force_kn * wind_centroid_height_m
    resisting_moment_knm = ballast_weight_kn * ballast_arm_m
    stability_ratio = resisting_moment_knm / overturning_moment_knm
    stability_margin = stability_ratio - required_stability_ratio
    slot_length_margin_mm = provided_slot_length_mm - required_movement_mm
    inspection_tolerance_margin_mm = allowed_vertical_tolerance_mm - measured_vertical_tolerance_mm

    pass_checks = [
        anchor_capacity_margin_kn >= 0.0,
        stability_margin >= 0.0,
        slot_length_margin_mm >= 0.0,
        inspection_tolerance_margin_mm >= 0.0,
    ]

    return {
        "site_wind_speed_m_s": round(site_wind_speed_m_s, 3),
        "wind_pressure_kpa": round(wind_pressure_kpa, 3),
        "temporary_panel_wind_force_kn": round(temporary_panel_wind_force_kn, 3),
        "anchor_demand_kn": round(anchor_demand_kn, 3),
        "anchor_capacity_margin_kn": round(anchor_capacity_margin_kn, 3),
        "overturning_moment_knm": round(overturning_moment_knm, 3),
        "stability_ratio": round(stability_ratio, 3),
        "stability_margin": round(stability_margin, 3),
        "slot_length_margin_mm": round(slot_length_margin_mm, 3),
        "inspection_tolerance_margin_mm": round(inspection_tolerance_margin_mm, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
