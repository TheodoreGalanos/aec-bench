# ABOUTME: Computes SSC-11 fire-main hydraulic and seismic support package metrics.
# ABOUTME: Combines fire-flow loss, remote pressure, pipe support, and seismic reactions.

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
    fire_flow_l_s: float,
    main_length_m: float,
    pipe_internal_diameter_mm: float,
    hazen_williams_c: float,
    riser_elevation_m: float,
    remote_head_flow_l_min: float,
    remote_head_count: float,
    source_residual_pressure_kpa: float,
    pump_boost_pressure_kpa: float,
    required_remote_pressure_kpa: float,
    support_span_m: float,
    pipe_outer_diameter_mm: float,
    pipe_wall_thickness_mm: float,
    water_density_kg_m3: float,
    steel_density_kg_m3: float,
    seismic_horizontal_coefficient: float,
    support_vertical_allowable_kn: float,
    support_horizontal_allowable_kn: float,
) -> dict[str, float]:
    """Compute deterministic SSC-11 fire-main and support metrics."""
    _require_positive(
        fire_flow_l_s=fire_flow_l_s,
        main_length_m=main_length_m,
        pipe_internal_diameter_mm=pipe_internal_diameter_mm,
        hazen_williams_c=hazen_williams_c,
        remote_head_flow_l_min=remote_head_flow_l_min,
        remote_head_count=remote_head_count,
        source_residual_pressure_kpa=source_residual_pressure_kpa,
        pump_boost_pressure_kpa=pump_boost_pressure_kpa,
        required_remote_pressure_kpa=required_remote_pressure_kpa,
        support_span_m=support_span_m,
        pipe_outer_diameter_mm=pipe_outer_diameter_mm,
        pipe_wall_thickness_mm=pipe_wall_thickness_mm,
        water_density_kg_m3=water_density_kg_m3,
        steel_density_kg_m3=steel_density_kg_m3,
        seismic_horizontal_coefficient=seismic_horizontal_coefficient,
        support_vertical_allowable_kn=support_vertical_allowable_kn,
        support_horizontal_allowable_kn=support_horizontal_allowable_kn,
    )
    if pipe_internal_diameter_mm >= pipe_outer_diameter_mm:
        msg = "pipe_internal_diameter_mm must be less than pipe_outer_diameter_mm"
        raise ValueError(msg)

    flow_m3_s = fire_flow_l_s / 1000.0
    diameter_m = pipe_internal_diameter_mm / 1000.0
    hazen_williams_loss_m = 10.67 * main_length_m * flow_m3_s**1.852 / (hazen_williams_c**1.852 * diameter_m**4.871)
    friction_loss_kpa = hazen_williams_loss_m * _G
    remote_flow_demand_l_s = remote_head_flow_l_min * remote_head_count / 60.0
    fire_flow_margin_l_s = fire_flow_l_s - remote_flow_demand_l_s
    remote_pressure_kpa = (
        source_residual_pressure_kpa + pump_boost_pressure_kpa - friction_loss_kpa - riser_elevation_m * _G
    )
    remote_pressure_margin_kpa = remote_pressure_kpa - required_remote_pressure_kpa

    inner_pipe_diameter_m = (pipe_outer_diameter_mm - 2.0 * pipe_wall_thickness_mm) / 1000.0
    outer_pipe_diameter_m = pipe_outer_diameter_mm / 1000.0
    steel_area_m2 = math.pi / 4.0 * (outer_pipe_diameter_m**2 - inner_pipe_diameter_m**2)
    water_area_m2 = math.pi / 4.0 * inner_pipe_diameter_m**2
    support_line_load_kn_m = (steel_area_m2 * steel_density_kg_m3 + water_area_m2 * water_density_kg_m3) * _G / 1000.0
    support_vertical_reaction_kn = support_line_load_kn_m * support_span_m
    seismic_horizontal_reaction_kn = support_vertical_reaction_kn * seismic_horizontal_coefficient
    support_vertical_utilization = support_vertical_reaction_kn / support_vertical_allowable_kn
    support_horizontal_utilization = seismic_horizontal_reaction_kn / support_horizontal_allowable_kn

    pass_checks = [
        fire_flow_margin_l_s >= 0.0,
        remote_pressure_margin_kpa >= 0.0,
        support_vertical_utilization <= 1.0,
        support_horizontal_utilization <= 1.0,
    ]

    return {
        "hazen_williams_loss_m": round(hazen_williams_loss_m, 3),
        "friction_loss_kpa": round(friction_loss_kpa, 3),
        "remote_flow_demand_l_s": round(remote_flow_demand_l_s, 3),
        "fire_flow_margin_l_s": round(fire_flow_margin_l_s, 3),
        "remote_pressure_kpa": round(remote_pressure_kpa, 3),
        "remote_pressure_margin_kpa": round(remote_pressure_margin_kpa, 3),
        "support_line_load_kn_m": round(support_line_load_kn_m, 3),
        "support_vertical_reaction_kn": round(support_vertical_reaction_kn, 3),
        "seismic_horizontal_reaction_kn": round(seismic_horizontal_reaction_kn, 3),
        "support_vertical_utilization": round(support_vertical_utilization, 3),
        "support_horizontal_utilization": round(support_horizontal_utilization, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
