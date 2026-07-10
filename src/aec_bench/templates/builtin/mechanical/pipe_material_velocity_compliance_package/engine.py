# ABOUTME: Computes SSC-11 pipe material and velocity compliance package metrics.
# ABOUTME: Combines velocity, pressure loss, pressure class, certificate, and support checks.

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
    flow_l_s: float,
    pipe_internal_diameter_mm: float,
    maximum_velocity_m_s: float,
    pipe_length_m: float,
    darcy_friction_factor: float,
    maximum_pressure_loss_kpa: float,
    design_pressure_kpa: float,
    pipe_pressure_class_kpa: float,
    lining_max_velocity_m_s: float,
    carbon_percent: float,
    manganese_percent: float,
    chromium_percent: float,
    molybdenum_percent: float,
    vanadium_percent: float,
    nickel_percent: float,
    copper_percent: float,
    carbon_equivalent_limit: float,
    required_certificate_items: float,
    matching_certificate_items: float,
    support_span_m: float,
    pipe_outer_diameter_mm: float,
    pipe_wall_thickness_mm: float,
    steel_density_kg_m3: float,
    contents_density_kg_m3: float,
    support_vertical_allowable_kn: float,
) -> dict[str, float]:
    """Compute deterministic SSC-11 pipe product compliance metrics."""
    _require_positive(
        flow_l_s=flow_l_s,
        pipe_internal_diameter_mm=pipe_internal_diameter_mm,
        maximum_velocity_m_s=maximum_velocity_m_s,
        pipe_length_m=pipe_length_m,
        darcy_friction_factor=darcy_friction_factor,
        maximum_pressure_loss_kpa=maximum_pressure_loss_kpa,
        design_pressure_kpa=design_pressure_kpa,
        pipe_pressure_class_kpa=pipe_pressure_class_kpa,
        lining_max_velocity_m_s=lining_max_velocity_m_s,
        carbon_equivalent_limit=carbon_equivalent_limit,
        required_certificate_items=required_certificate_items,
        matching_certificate_items=matching_certificate_items,
        support_span_m=support_span_m,
        pipe_outer_diameter_mm=pipe_outer_diameter_mm,
        pipe_wall_thickness_mm=pipe_wall_thickness_mm,
        steel_density_kg_m3=steel_density_kg_m3,
        contents_density_kg_m3=contents_density_kg_m3,
        support_vertical_allowable_kn=support_vertical_allowable_kn,
    )

    flow_m3_s = flow_l_s / 1000.0
    internal_diameter_m = pipe_internal_diameter_mm / 1000.0
    pipe_area_m2 = math.pi / 4.0 * internal_diameter_m**2
    pipe_velocity_m_s = flow_m3_s / pipe_area_m2
    velocity_margin_m_s = maximum_velocity_m_s - pipe_velocity_m_s
    velocity_head_m = pipe_velocity_m_s**2 / (2.0 * _G)
    pressure_loss_kpa = darcy_friction_factor * (pipe_length_m / internal_diameter_m) * velocity_head_m * _G
    pressure_loss_margin_kpa = maximum_pressure_loss_kpa - pressure_loss_kpa
    pressure_class_margin_kpa = pipe_pressure_class_kpa - design_pressure_kpa
    lining_velocity_margin_m_s = lining_max_velocity_m_s - pipe_velocity_m_s
    carbon_equivalent = (
        carbon_percent
        + manganese_percent / 6.0
        + (chromium_percent + molybdenum_percent + vanadium_percent) / 5.0
        + (nickel_percent + copper_percent) / 15.0
    )
    carbon_equivalent_margin = carbon_equivalent_limit - carbon_equivalent
    certificate_match_percent = matching_certificate_items / required_certificate_items * 100.0
    outer_diameter_m = pipe_outer_diameter_mm / 1000.0
    inner_pipe_diameter_m = (pipe_outer_diameter_mm - 2.0 * pipe_wall_thickness_mm) / 1000.0
    steel_area_m2 = math.pi / 4.0 * (outer_diameter_m**2 - inner_pipe_diameter_m**2)
    contents_area_m2 = math.pi / 4.0 * inner_pipe_diameter_m**2
    support_line_load_kn_m = steel_area_m2 * steel_density_kg_m3 + contents_area_m2 * contents_density_kg_m3
    support_line_load_kn_m *= _G / 1000.0
    support_vertical_reaction_kn = support_line_load_kn_m * support_span_m
    support_margin_kn = support_vertical_allowable_kn - support_vertical_reaction_kn

    pass_checks = [
        velocity_margin_m_s >= 0.0,
        pressure_loss_margin_kpa >= 0.0,
        pressure_class_margin_kpa >= 0.0,
        lining_velocity_margin_m_s >= 0.0,
        carbon_equivalent_margin >= 0.0,
        certificate_match_percent >= 100.0,
        support_margin_kn >= 0.0,
    ]

    return {
        "pipe_velocity_m_s": round(pipe_velocity_m_s, 3),
        "velocity_margin_m_s": round(velocity_margin_m_s, 3),
        "pressure_loss_kpa": round(pressure_loss_kpa, 3),
        "pressure_loss_margin_kpa": round(pressure_loss_margin_kpa, 3),
        "pressure_class_margin_kpa": round(pressure_class_margin_kpa, 3),
        "lining_velocity_margin_m_s": round(lining_velocity_margin_m_s, 3),
        "carbon_equivalent": round(carbon_equivalent, 3),
        "carbon_equivalent_margin": round(carbon_equivalent_margin, 3),
        "certificate_match_percent": round(certificate_match_percent, 3),
        "support_vertical_reaction_kn": round(support_vertical_reaction_kn, 3),
        "support_margin_kn": round(support_margin_kn, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
