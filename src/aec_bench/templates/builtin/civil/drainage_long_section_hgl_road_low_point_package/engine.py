# ABOUTME: Computes SSC-03 drainage long-section, HGL, and road low-point metrics.
# ABOUTME: Combines pipe slope, Manning capacity, HGL, roadway spread, and equipment freeboard.

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
    upstream_invert_m: float,
    downstream_invert_m: float,
    pipe_length_m: float,
    pipe_diameter_m: float,
    design_flow_m3_s: float,
    manning_n: float,
    downstream_tailwater_m: float,
    minor_loss_coefficient: float,
    road_low_point_level_m: float,
    minimum_freeboard_m: float,
    gutter_approach_flow_m3_s: float,
    roadway_spread_factor: float,
    allowable_spread_m: float,
    equipment_threshold_level_m: float,
) -> dict[str, float]:
    """Compute deterministic SSC-03 road low-point HGL metrics."""
    _require_positive(
        pipe_length_m=pipe_length_m,
        pipe_diameter_m=pipe_diameter_m,
        design_flow_m3_s=design_flow_m3_s,
        manning_n=manning_n,
        minor_loss_coefficient=minor_loss_coefficient,
        minimum_freeboard_m=minimum_freeboard_m,
        gutter_approach_flow_m3_s=gutter_approach_flow_m3_s,
        roadway_spread_factor=roadway_spread_factor,
        allowable_spread_m=allowable_spread_m,
    )
    if upstream_invert_m <= downstream_invert_m:
        msg = "upstream_invert_m must exceed downstream_invert_m"
        raise ValueError(msg)

    pipe_slope = (upstream_invert_m - downstream_invert_m) / pipe_length_m
    pipe_area_m2 = math.pi / 4.0 * pipe_diameter_m**2
    hydraulic_radius_m = pipe_diameter_m / 4.0
    pipe_velocity_m_s = design_flow_m3_s / pipe_area_m2
    manning_capacity_m3_s = 1.0 / manning_n * pipe_area_m2 * hydraulic_radius_m ** (2.0 / 3.0) * math.sqrt(pipe_slope)
    capacity_margin_m3_s = manning_capacity_m3_s - design_flow_m3_s
    friction_slope = (design_flow_m3_s * manning_n / (pipe_area_m2 * hydraulic_radius_m ** (2.0 / 3.0))) ** 2
    friction_loss_m = friction_slope * pipe_length_m
    minor_loss_m = minor_loss_coefficient * pipe_velocity_m_s**2 / (2.0 * _G)
    upstream_hgl_m = downstream_tailwater_m + friction_loss_m + minor_loss_m
    low_point_freeboard_m = road_low_point_level_m - upstream_hgl_m
    freeboard_margin_m = low_point_freeboard_m - minimum_freeboard_m
    roadway_spread_m = roadway_spread_factor * math.sqrt(gutter_approach_flow_m3_s)
    spread_margin_m = allowable_spread_m - roadway_spread_m
    equipment_freeboard_m = equipment_threshold_level_m - upstream_hgl_m

    pass_checks = [
        capacity_margin_m3_s >= 0.0,
        freeboard_margin_m >= 0.0,
        spread_margin_m >= 0.0,
        equipment_freeboard_m >= 0.0,
    ]

    return {
        "pipe_slope_percent": round(pipe_slope * 100.0, 3),
        "pipe_velocity_m_s": round(pipe_velocity_m_s, 3),
        "manning_capacity_m3_s": round(manning_capacity_m3_s, 3),
        "capacity_margin_m3_s": round(capacity_margin_m3_s, 3),
        "friction_loss_m": round(friction_loss_m, 3),
        "minor_loss_m": round(minor_loss_m, 3),
        "upstream_hgl_m": round(upstream_hgl_m, 3),
        "low_point_freeboard_m": round(low_point_freeboard_m, 3),
        "freeboard_margin_m": round(freeboard_margin_m, 3),
        "roadway_spread_m": round(roadway_spread_m, 3),
        "spread_margin_m": round(spread_margin_m, 3),
        "equipment_freeboard_m": round(equipment_freeboard_m, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
