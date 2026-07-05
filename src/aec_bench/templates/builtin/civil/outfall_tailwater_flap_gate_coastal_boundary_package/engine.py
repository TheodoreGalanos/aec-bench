# ABOUTME: Computes SSC-03 outfall tailwater, flap-gate, and coastal boundary metrics.
# ABOUTME: Combines Manning friction, flap-gate loss, submergence, HGL clearance, and freeboard.

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
    outfall_invert_m: float,
    flap_gate_loss_coefficient: float,
    minor_loss_coefficient: float,
    upstream_rim_level_m: float,
    minimum_hgl_clearance_m: float,
    coastal_crest_level_m: float,
    required_coastal_freeboard_m: float,
) -> dict[str, float]:
    """Compute deterministic SSC-03 outfall and coastal-boundary metrics."""
    _require_positive(
        pipe_diameter_m=pipe_diameter_m,
        design_flow_m3_s=design_flow_m3_s,
        pipe_length_m=pipe_length_m,
        manning_n=manning_n,
        flap_gate_loss_coefficient=flap_gate_loss_coefficient,
        minor_loss_coefficient=minor_loss_coefficient,
        minimum_hgl_clearance_m=minimum_hgl_clearance_m,
        required_coastal_freeboard_m=required_coastal_freeboard_m,
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
    outfall_submergence_m = tailwater_level_m - (outfall_invert_m + pipe_diameter_m)
    hgl_clearance_m = upstream_rim_level_m - upstream_hgl_m
    hgl_clearance_margin_m = hgl_clearance_m - minimum_hgl_clearance_m
    coastal_freeboard_margin_m = coastal_crest_level_m - tailwater_level_m - required_coastal_freeboard_m

    pass_checks = [
        hgl_clearance_margin_m >= 0.0,
        coastal_freeboard_margin_m >= 0.0,
    ]

    return {
        "pipe_velocity_m_s": round(pipe_velocity_m_s, 3),
        "friction_loss_m": round(friction_loss_m, 3),
        "flap_gate_headloss_m": round(flap_gate_headloss_m, 3),
        "minor_loss_m": round(minor_loss_m, 3),
        "upstream_hgl_m": round(upstream_hgl_m, 3),
        "outfall_submergence_m": round(outfall_submergence_m, 3),
        "hgl_clearance_m": round(hgl_clearance_m, 3),
        "hgl_clearance_margin_m": round(hgl_clearance_margin_m, 3),
        "coastal_freeboard_margin_m": round(coastal_freeboard_margin_m, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
