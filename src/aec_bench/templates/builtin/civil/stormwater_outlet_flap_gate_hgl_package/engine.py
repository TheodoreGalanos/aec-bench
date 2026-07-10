# ABOUTME: Computes SSC-11 stormwater outlet flap gate and pipe HGL metrics.
# ABOUTME: Combines full-pipe friction, flap-gate loss, HGL clearance, and support checks.

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
    pipe_diameter_m: float,
    design_flow_m3_s: float,
    pipe_length_m: float,
    manning_n: float,
    tailwater_level_m: float,
    flap_gate_loss_coefficient: float,
    minor_loss_coefficient: float,
    upstream_invert_m: float,
    road_surface_level_m: float,
    pipe_support_line_load_kn_m: float,
    support_span_m: float,
    flap_gate_weight_kn: float,
    support_allowable_kn: float,
) -> dict[str, float]:
    """Compute deterministic SSC-11 stormwater outlet metrics."""
    _require_positive(
        pipe_diameter_m=pipe_diameter_m,
        design_flow_m3_s=design_flow_m3_s,
        pipe_length_m=pipe_length_m,
        manning_n=manning_n,
        flap_gate_loss_coefficient=flap_gate_loss_coefficient,
        support_span_m=support_span_m,
        support_allowable_kn=support_allowable_kn,
    )

    pipe_area_m2 = math.pi / 4.0 * pipe_diameter_m**2
    hydraulic_radius_m = pipe_diameter_m / 4.0
    pipe_velocity_m_s = design_flow_m3_s / pipe_area_m2
    velocity_head_m = pipe_velocity_m_s**2 / (2.0 * _G)
    friction_slope = (design_flow_m3_s * manning_n / (pipe_area_m2 * hydraulic_radius_m ** (2.0 / 3.0))) ** 2
    friction_loss_m = friction_slope * pipe_length_m
    flap_gate_headloss_m = flap_gate_loss_coefficient * velocity_head_m
    minor_loss_m = minor_loss_coefficient * velocity_head_m
    upstream_hgl_m = tailwater_level_m + friction_loss_m + flap_gate_headloss_m + minor_loss_m
    hgl_clearance_to_surface_m = road_surface_level_m - upstream_hgl_m
    pipe_crown_margin_to_surface_m = road_surface_level_m - (upstream_invert_m + pipe_diameter_m)
    outfall_support_reaction_kn = pipe_support_line_load_kn_m * support_span_m + flap_gate_weight_kn
    support_utilization = outfall_support_reaction_kn / support_allowable_kn

    pass_checks = [
        hgl_clearance_to_surface_m >= 0.0,
        pipe_crown_margin_to_surface_m >= 0.0,
        support_utilization <= 1.0,
    ]

    return {
        "pipe_velocity_m_s": round(pipe_velocity_m_s, 3),
        "friction_loss_m": round(friction_loss_m, 3),
        "flap_gate_headloss_m": round(flap_gate_headloss_m, 3),
        "minor_loss_m": round(minor_loss_m, 3),
        "upstream_hgl_m": round(upstream_hgl_m, 3),
        "hgl_clearance_to_surface_m": round(hgl_clearance_to_surface_m, 3),
        "pipe_crown_margin_to_surface_m": round(pipe_crown_margin_to_surface_m, 3),
        "outfall_support_reaction_kn": round(outfall_support_reaction_kn, 3),
        "support_utilization": round(support_utilization, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
