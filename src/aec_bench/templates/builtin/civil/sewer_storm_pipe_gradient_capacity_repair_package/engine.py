# ABOUTME: Computes SSC-03 sewer/storm pipe gradient and capacity repair metrics.
# ABOUTME: Combines invert consistency, Manning capacity, velocity, cover, and repair checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    scheduled_upstream_invert_m: float,
    scheduled_downstream_invert_m: float,
    long_section_downstream_invert_m: float,
    pipe_length_m: float,
    pipe_diameter_m: float,
    manning_n: float,
    design_flow_m3_s: float,
    invert_conflict_tolerance_m: float,
    surface_level_m: float,
    pipe_outer_diameter_m: float,
    minimum_cover_m: float,
    minimum_velocity_m_s: float,
    maximum_velocity_m_s: float,
) -> dict[str, float]:
    """Compute deterministic SSC-03 pipe repair metrics."""
    _require_positive(
        pipe_length_m=pipe_length_m,
        pipe_diameter_m=pipe_diameter_m,
        manning_n=manning_n,
        design_flow_m3_s=design_flow_m3_s,
        invert_conflict_tolerance_m=invert_conflict_tolerance_m,
        pipe_outer_diameter_m=pipe_outer_diameter_m,
        minimum_cover_m=minimum_cover_m,
        minimum_velocity_m_s=minimum_velocity_m_s,
        maximum_velocity_m_s=maximum_velocity_m_s,
    )
    if scheduled_upstream_invert_m <= scheduled_downstream_invert_m:
        msg = "scheduled_upstream_invert_m must exceed scheduled_downstream_invert_m"
        raise ValueError(msg)

    scheduled_slope = (scheduled_upstream_invert_m - scheduled_downstream_invert_m) / pipe_length_m
    long_section_slope = (scheduled_upstream_invert_m - long_section_downstream_invert_m) / pipe_length_m
    invert_conflict_m = abs(scheduled_downstream_invert_m - long_section_downstream_invert_m)
    pipe_area_m2 = math.pi / 4.0 * pipe_diameter_m**2
    hydraulic_radius_m = pipe_diameter_m / 4.0
    manning_capacity_m3_s = (
        1.0 / manning_n * pipe_area_m2 * hydraulic_radius_m ** (2.0 / 3.0) * math.sqrt(scheduled_slope)
    )
    capacity_margin_m3_s = manning_capacity_m3_s - design_flow_m3_s
    flow_velocity_m_s = design_flow_m3_s / pipe_area_m2
    velocity_low_margin_m_s = flow_velocity_m_s - minimum_velocity_m_s
    velocity_high_margin_m_s = maximum_velocity_m_s - flow_velocity_m_s
    pipe_crown_cover_m = surface_level_m - (scheduled_upstream_invert_m + pipe_outer_diameter_m)
    cover_margin_m = pipe_crown_cover_m - minimum_cover_m

    pass_checks = [
        invert_conflict_m <= invert_conflict_tolerance_m,
        capacity_margin_m3_s >= 0.0,
        velocity_low_margin_m_s >= 0.0,
        velocity_high_margin_m_s >= 0.0,
        cover_margin_m >= 0.0,
    ]

    return {
        "scheduled_slope_percent": round(scheduled_slope * 100.0, 3),
        "long_section_slope_percent": round(long_section_slope * 100.0, 3),
        "invert_conflict_m": round(invert_conflict_m, 3),
        "manning_capacity_m3_s": round(manning_capacity_m3_s, 3),
        "capacity_margin_m3_s": round(capacity_margin_m3_s, 3),
        "flow_velocity_m_s": round(flow_velocity_m_s, 3),
        "velocity_low_margin_m_s": round(velocity_low_margin_m_s, 3),
        "velocity_high_margin_m_s": round(velocity_high_margin_m_s, 3),
        "pipe_crown_cover_m": round(pipe_crown_cover_m, 3),
        "cover_margin_m": round(cover_margin_m, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
