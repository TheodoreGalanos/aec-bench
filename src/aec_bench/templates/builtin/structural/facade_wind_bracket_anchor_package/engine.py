# ABOUTME: Computes SSC-09 facade wind, bracket, anchor, and tolerance metrics.
# ABOUTME: Combines wind-zone demand, bracket capacity, anchor checks, and setout margin.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _require_nonnegative(**values: float) -> None:
    """Raise ValueError when any supplied value is negative."""
    for name, value in values.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)


def _combined_utilization(tension_utilization: float, shear_utilization: float) -> float:
    """Return source-pack combined anchor utilization."""
    return math.hypot(tension_utilization, shear_utilization)


def compute(
    basic_wind_speed_m_s: float,
    source_velocity_pressure_kpa: float,
    body_pressure_coefficient: float,
    edge_pressure_coefficient: float,
    corner_pressure_coefficient: float,
    tributary_width_m: float,
    tributary_height_m: float,
    facade_dead_load_kpa: float,
    bracket_horizontal_resistance_kn: float,
    bracket_vertical_resistance_kn: float,
    anchor_tension_resistance_kn: float,
    anchor_shear_resistance_kn: float,
    anchor_embedment_mm: float,
    minimum_anchor_embedment_mm: float,
    corner_anchor_edge_distance_x_mm: float,
    corner_anchor_edge_distance_y_mm: float,
    minimum_anchor_edge_distance_mm: float,
    corner_nearest_anchor_spacing_mm: float,
    minimum_anchor_spacing_mm: float,
    nominal_cavity_depth_mm: float,
    measured_wall_offset_mm: float,
    minimum_bracket_projection_mm: float,
    maximum_bracket_projection_mm: float,
    installation_tolerance_allowance_mm: float,
    fixed_point_count: int,
    sliding_point_count: int,
) -> dict[str, float]:
    """Compute facade fixing metrics for the SSC-09 task-owned source pack."""
    _require_positive(
        basic_wind_speed_m_s=basic_wind_speed_m_s,
        source_velocity_pressure_kpa=source_velocity_pressure_kpa,
        tributary_width_m=tributary_width_m,
        tributary_height_m=tributary_height_m,
        bracket_horizontal_resistance_kn=bracket_horizontal_resistance_kn,
        bracket_vertical_resistance_kn=bracket_vertical_resistance_kn,
        anchor_tension_resistance_kn=anchor_tension_resistance_kn,
        anchor_shear_resistance_kn=anchor_shear_resistance_kn,
        minimum_anchor_embedment_mm=minimum_anchor_embedment_mm,
        minimum_anchor_edge_distance_mm=minimum_anchor_edge_distance_mm,
        minimum_anchor_spacing_mm=minimum_anchor_spacing_mm,
        maximum_bracket_projection_mm=maximum_bracket_projection_mm,
    )
    _require_nonnegative(
        body_pressure_coefficient=body_pressure_coefficient,
        edge_pressure_coefficient=edge_pressure_coefficient,
        corner_pressure_coefficient=corner_pressure_coefficient,
        facade_dead_load_kpa=facade_dead_load_kpa,
        anchor_embedment_mm=anchor_embedment_mm,
        corner_anchor_edge_distance_x_mm=corner_anchor_edge_distance_x_mm,
        corner_anchor_edge_distance_y_mm=corner_anchor_edge_distance_y_mm,
        corner_nearest_anchor_spacing_mm=corner_nearest_anchor_spacing_mm,
        nominal_cavity_depth_mm=nominal_cavity_depth_mm,
        measured_wall_offset_mm=measured_wall_offset_mm,
        minimum_bracket_projection_mm=minimum_bracket_projection_mm,
        installation_tolerance_allowance_mm=installation_tolerance_allowance_mm,
    )
    if minimum_bracket_projection_mm >= maximum_bracket_projection_mm:
        msg = "minimum_bracket_projection_mm must be less than maximum_bracket_projection_mm"
        raise ValueError(msg)
    if fixed_point_count <= 0:
        msg = "fixed_point_count must be > 0"
        raise ValueError(msg)
    if sliding_point_count <= 0:
        msg = "sliding_point_count must be > 0"
        raise ValueError(msg)

    velocity_pressure_kpa = source_velocity_pressure_kpa
    body_pressure_kpa = velocity_pressure_kpa * body_pressure_coefficient
    edge_pressure_kpa = velocity_pressure_kpa * edge_pressure_coefficient
    corner_pressure_kpa = velocity_pressure_kpa * corner_pressure_coefficient

    tributary_area_m2 = tributary_width_m * tributary_height_m
    body_wind_load_kn = body_pressure_kpa * tributary_area_m2
    edge_wind_load_kn = edge_pressure_kpa * tributary_area_m2
    corner_wind_load_kn = corner_pressure_kpa * tributary_area_m2
    dead_load_per_bracket_kn = facade_dead_load_kpa * tributary_area_m2

    body_anchor_combined_utilization = _combined_utilization(
        body_wind_load_kn / anchor_tension_resistance_kn,
        dead_load_per_bracket_kn / anchor_shear_resistance_kn,
    )
    edge_anchor_combined_utilization = _combined_utilization(
        edge_wind_load_kn / anchor_tension_resistance_kn,
        dead_load_per_bracket_kn / anchor_shear_resistance_kn,
    )
    corner_anchor_tension_utilization = corner_wind_load_kn / anchor_tension_resistance_kn
    corner_anchor_shear_utilization = dead_load_per_bracket_kn / anchor_shear_resistance_kn
    corner_anchor_combined_utilization = _combined_utilization(
        corner_anchor_tension_utilization,
        corner_anchor_shear_utilization,
    )
    corner_bracket_horizontal_utilization = corner_wind_load_kn / bracket_horizontal_resistance_kn
    corner_bracket_vertical_utilization = dead_load_per_bracket_kn / bracket_vertical_resistance_kn
    governing_utilization = max(
        body_anchor_combined_utilization,
        edge_anchor_combined_utilization,
        corner_anchor_combined_utilization,
        corner_bracket_horizontal_utilization,
        corner_bracket_vertical_utilization,
    )

    anchor_embedment_margin_mm = anchor_embedment_mm - minimum_anchor_embedment_mm
    anchor_edge_margin_mm = (
        min(
            corner_anchor_edge_distance_x_mm,
            corner_anchor_edge_distance_y_mm,
        )
        - minimum_anchor_edge_distance_mm
    )
    anchor_spacing_margin_mm = corner_nearest_anchor_spacing_mm - minimum_anchor_spacing_mm

    required_projection_mm = nominal_cavity_depth_mm + measured_wall_offset_mm
    projection_margin_mm = min(
        required_projection_mm - minimum_bracket_projection_mm,
        maximum_bracket_projection_mm - required_projection_mm,
    )
    fixed_point_vertical_margin_kn = bracket_vertical_resistance_kn - dead_load_per_bracket_kn
    governing_row_is_corner_score = 1.0 if corner_anchor_combined_utilization >= governing_utilization else 0.0

    overall_pass_score = (
        1.0
        if (
            governing_utilization <= 1.0
            and anchor_embedment_margin_mm >= 0.0
            and anchor_edge_margin_mm >= 0.0
            and anchor_spacing_margin_mm >= 0.0
            and projection_margin_mm >= installation_tolerance_allowance_mm
            and fixed_point_vertical_margin_kn >= 0.0
            and governing_row_is_corner_score == 1.0
        )
        else 0.0
    )

    return {
        "velocity_pressure_kpa": round(velocity_pressure_kpa, 3),
        "body_pressure_kpa": round(body_pressure_kpa, 3),
        "edge_pressure_kpa": round(edge_pressure_kpa, 3),
        "corner_pressure_kpa": round(corner_pressure_kpa, 3),
        "tributary_area_m2": round(tributary_area_m2, 3),
        "body_wind_load_kn": round(body_wind_load_kn, 3),
        "edge_wind_load_kn": round(edge_wind_load_kn, 3),
        "corner_wind_load_kn": round(corner_wind_load_kn, 3),
        "dead_load_per_bracket_kn": round(dead_load_per_bracket_kn, 3),
        "corner_bracket_horizontal_utilization": round(corner_bracket_horizontal_utilization, 3),
        "corner_bracket_vertical_utilization": round(corner_bracket_vertical_utilization, 3),
        "body_anchor_combined_utilization": round(body_anchor_combined_utilization, 3),
        "edge_anchor_combined_utilization": round(edge_anchor_combined_utilization, 3),
        "corner_anchor_combined_utilization": round(corner_anchor_combined_utilization, 3),
        "governing_utilization": round(governing_utilization, 3),
        "anchor_embedment_margin_mm": round(anchor_embedment_margin_mm, 3),
        "anchor_edge_margin_mm": round(anchor_edge_margin_mm, 3),
        "anchor_spacing_margin_mm": round(anchor_spacing_margin_mm, 3),
        "required_projection_mm": round(required_projection_mm, 3),
        "projection_margin_mm": round(projection_margin_mm, 3),
        "fixed_point_vertical_margin_kn": round(fixed_point_vertical_margin_kn, 3),
        "governing_row_is_corner_score": round(governing_row_is_corner_score, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
