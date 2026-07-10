# ABOUTME: Computes SSC-01 culvert, driveway access, and safety continuity metrics.
# ABOUTME: Combines driveway grade, culvert capacity, freeboard, spread, and sight-distance checks.

from __future__ import annotations

import math

_G = 9.81
_GUTTER_KU_SI = 0.376


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    driveway_low_level_m: float,
    driveway_high_level_m: float,
    driveway_length_m: float,
    allowable_driveway_grade_pct: float,
    culvert_diameter_m: float,
    culvert_mannings_n: float,
    culvert_slope_pct: float,
    design_flow_m3_s: float,
    tailwater_level_m: float,
    headwater_base_depth_m: float,
    headwater_loss_factor_m: float,
    road_edge_level_m: float,
    minimum_freeboard_m: float,
    gutter_flow_m3_s: float,
    cross_slope_pct: float,
    longitudinal_slope_pct: float,
    gutter_mannings_n: float,
    allowable_spread_m: float,
    access_speed_kmh: float,
    sight_reaction_time_s: float,
    braking_friction_coefficient: float,
    access_grade_pct: float,
    available_sight_distance_m: float,
) -> dict[str, float]:
    """Compute deterministic SSC-01 culvert driveway access metrics."""
    _require_positive(
        driveway_length_m=driveway_length_m,
        allowable_driveway_grade_pct=allowable_driveway_grade_pct,
        culvert_diameter_m=culvert_diameter_m,
        culvert_mannings_n=culvert_mannings_n,
        culvert_slope_pct=culvert_slope_pct,
        design_flow_m3_s=design_flow_m3_s,
        headwater_base_depth_m=headwater_base_depth_m,
        cross_slope_pct=cross_slope_pct,
        longitudinal_slope_pct=longitudinal_slope_pct,
        gutter_mannings_n=gutter_mannings_n,
        allowable_spread_m=allowable_spread_m,
        access_speed_kmh=access_speed_kmh,
        sight_reaction_time_s=sight_reaction_time_s,
        braking_friction_coefficient=braking_friction_coefficient,
        available_sight_distance_m=available_sight_distance_m,
    )
    driveway_grade_percent = (driveway_high_level_m - driveway_low_level_m) / driveway_length_m * 100.0
    driveway_grade_margin_percent = allowable_driveway_grade_pct - abs(driveway_grade_percent)

    area_m2 = math.pi * culvert_diameter_m**2 / 4.0
    hydraulic_radius_m = culvert_diameter_m / 4.0
    culvert_capacity_m3_s = (
        area_m2 * hydraulic_radius_m ** (2.0 / 3.0) * math.sqrt(culvert_slope_pct / 100.0) / culvert_mannings_n
    )
    culvert_capacity_margin_m3_s = culvert_capacity_m3_s - design_flow_m3_s
    flow_capacity_ratio = design_flow_m3_s / culvert_capacity_m3_s
    headwater_depth_m = headwater_base_depth_m + headwater_loss_factor_m * flow_capacity_ratio**2
    headwater_level_m = tailwater_level_m + headwater_depth_m
    freeboard_m = road_edge_level_m - headwater_level_m
    freeboard_margin_m = freeboard_m - minimum_freeboard_m

    spread_width_m = (
        gutter_flow_m3_s
        * gutter_mannings_n
        / (_GUTTER_KU_SI * (cross_slope_pct / 100.0) ** (5.0 / 3.0) * math.sqrt(longitudinal_slope_pct / 100.0))
    ) ** (3.0 / 8.0)
    spread_margin_m = allowable_spread_m - spread_width_m

    access_speed_m_s = access_speed_kmh / 3.6
    grade_fraction = access_grade_pct / 100.0
    sight_distance_required_m = access_speed_m_s * sight_reaction_time_s + access_speed_m_s**2 / (
        2.0 * _G * (braking_friction_coefficient + grade_fraction)
    )
    sight_distance_margin_m = available_sight_distance_m - sight_distance_required_m

    pass_checks = [
        driveway_grade_margin_percent >= 0.0,
        culvert_capacity_margin_m3_s >= 0.0,
        freeboard_margin_m >= 0.0,
        spread_margin_m >= 0.0,
        sight_distance_margin_m >= 0.0,
    ]

    return {
        "driveway_grade_percent": round(driveway_grade_percent, 3),
        "driveway_grade_margin_percent": round(driveway_grade_margin_percent, 3),
        "culvert_capacity_m3_s": round(culvert_capacity_m3_s, 3),
        "culvert_capacity_margin_m3_s": round(culvert_capacity_margin_m3_s, 3),
        "headwater_level_m": round(headwater_level_m, 3),
        "freeboard_m": round(freeboard_m, 3),
        "freeboard_margin_m": round(freeboard_margin_m, 3),
        "roadway_spread_m": round(spread_width_m, 3),
        "spread_margin_m": round(spread_margin_m, 3),
        "sight_distance_required_m": round(sight_distance_required_m, 3),
        "sight_distance_margin_m": round(sight_distance_margin_m, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
