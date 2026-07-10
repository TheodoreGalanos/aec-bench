# ABOUTME: Computes SSC-14 pipe transient support and foundation package metrics.
# ABOUTME: Combines pipe thrust, support dead load, bearing, anchors, and sliding checks.

from __future__ import annotations

import math
from typing import Literal

_FACTOR_TABLE: tuple[tuple[float, float, float, float], ...] = (
    (0.0, 5.7, 1.0, 0.0),
    (5.0, 7.3, 1.6, 0.5),
    (10.0, 9.6, 2.7, 1.2),
    (15.0, 12.9, 4.4, 2.5),
    (20.0, 17.7, 7.4, 5.0),
    (25.0, 25.1, 12.7, 9.7),
    (30.0, 37.2, 22.5, 19.7),
    (34.0, 52.6, 36.5, 36.0),
    (35.0, 57.8, 41.4, 42.4),
    (40.0, 95.7, 81.3, 100.4),
    (45.0, 172.3, 173.3, 297.5),
    (48.0, 258.3, 287.9, 780.1),
    (50.0, 347.5, 415.1, 1153.2),
)

_GAMMA_W = 9.81


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


def _annulus_area_m2(outer_diameter_mm: float, inner_diameter_mm: float) -> float:
    """Return circular annulus area from diameters in millimetres."""
    return math.pi / 4.0 * ((outer_diameter_mm / 1000.0) ** 2 - (inner_diameter_mm / 1000.0) ** 2)


def _circle_area_m2(diameter_mm: float) -> float:
    """Return circular area from diameter in millimetres."""
    return math.pi / 4.0 * (diameter_mm / 1000.0) ** 2


def _line_load_kn_m(area_m2: float, density_kg_m3: float) -> float:
    """Return gravity line load in kN/m for a material area and density."""
    return area_m2 * density_kg_m3 * 9.81 / 1000.0


def _interpolate_ngamma(phi_deg: float) -> float:
    """Linearly interpolate Terzaghi Ngamma from the local lookup table."""
    clamped_phi = max(0.0, min(50.0, phi_deg))
    for i in range(len(_FACTOR_TABLE) - 1):
        phi_lo = _FACTOR_TABLE[i][0]
        phi_hi = _FACTOR_TABLE[i + 1][0]
        if phi_lo <= clamped_phi <= phi_hi:
            val_lo = _FACTOR_TABLE[i][3]
            val_hi = _FACTOR_TABLE[i + 1][3]
            fraction = (clamped_phi - phi_lo) / (phi_hi - phi_lo)
            return val_lo + fraction * (val_hi - val_lo)
    return _FACTOR_TABLE[-1][3]


def _bearing_factors(phi_deg: float) -> tuple[float, float, float]:
    """Return Terzaghi Nc, Nq, and Ngamma for a friction angle."""
    if phi_deg < 0.0 or phi_deg > 50.0:
        msg = "soil_friction_angle_deg must be between 0 and 50"
        raise ValueError(msg)
    if phi_deg == 0.0:
        return 5.7, 1.0, 0.0

    phi_rad = math.radians(phi_deg)
    exponent = 2.0 * (3.0 * math.pi / 4.0 - phi_rad / 2.0) * math.tan(phi_rad)
    denominator = 2.0 * math.cos(math.radians(45.0) + phi_rad / 2.0) ** 2
    nq = math.exp(exponent) / denominator
    nc = (nq - 1.0) / math.tan(phi_rad)
    return nc, nq, _interpolate_ngamma(phi_deg)


def _water_table_correction(
    *,
    unit_weight_kn_m3: float,
    embedment_depth_m: float,
    footing_width_m: float,
    water_table_depth_m: float,
) -> tuple[float, float]:
    """Return overburden pressure and effective unit weight for bearing."""
    if water_table_depth_m <= embedment_depth_m:
        q_kpa = unit_weight_kn_m3 * water_table_depth_m + (unit_weight_kn_m3 - _GAMMA_W) * (
            embedment_depth_m - water_table_depth_m
        )
        gamma_eff = unit_weight_kn_m3 - _GAMMA_W
    elif water_table_depth_m < embedment_depth_m + footing_width_m:
        q_kpa = unit_weight_kn_m3 * embedment_depth_m
        gamma_eff = (unit_weight_kn_m3 - _GAMMA_W) + (
            (water_table_depth_m - embedment_depth_m) / footing_width_m
        ) * _GAMMA_W
    else:
        q_kpa = unit_weight_kn_m3 * embedment_depth_m
        gamma_eff = unit_weight_kn_m3
    return q_kpa, gamma_eff


def _terzaghi_allowable_bearing_kpa(
    *,
    cohesion_kpa: float,
    soil_friction_angle_deg: float,
    soil_unit_weight_kn_m3: float,
    footing_width_m: float,
    embedment_depth_m: float,
    footing_shape: Literal["strip", "square", "circular"],
    water_table_depth_m: float,
    bearing_factor_of_safety: float,
) -> float:
    """Return allowable Terzaghi bearing capacity for the source footing."""
    _require_nonnegative(cohesion_kpa=cohesion_kpa, embedment_depth_m=embedment_depth_m)
    _require_positive(
        soil_unit_weight_kn_m3=soil_unit_weight_kn_m3,
        footing_width_m=footing_width_m,
        bearing_factor_of_safety=bearing_factor_of_safety,
    )
    shape_factors = {
        "strip": (1.0, 0.5),
        "square": (1.3, 0.4),
        "circular": (1.3, 0.3),
    }
    if footing_shape not in shape_factors:
        msg = f"footing_shape must be one of {list(shape_factors)}"
        raise ValueError(msg)

    nc, nq, ngamma = _bearing_factors(soil_friction_angle_deg)
    sc, sg = shape_factors[footing_shape]
    q_kpa, gamma_eff = _water_table_correction(
        unit_weight_kn_m3=soil_unit_weight_kn_m3,
        embedment_depth_m=embedment_depth_m,
        footing_width_m=footing_width_m,
        water_table_depth_m=water_table_depth_m,
    )
    ultimate_bearing_kpa = cohesion_kpa * nc * sc + q_kpa * nq + gamma_eff * footing_width_m * sg * ngamma
    return ultimate_bearing_kpa / bearing_factor_of_safety


def compute(
    transient_pressure_kpa: float,
    pipe_internal_diameter_mm: float,
    bend_angle_deg: float,
    pipe_outer_diameter_mm: float,
    pipe_wall_thickness_mm: float,
    steel_density_kg_m3: float,
    contents_density_kg_m3: float,
    insulation_thickness_mm: float,
    insulation_density_kg_m3: float,
    support_span_m: float,
    valve_weight_kn: float,
    saddle_weight_kn: float,
    foundation_length_along_thrust_m: float,
    foundation_width_transverse_m: float,
    foundation_depth_m: float,
    concrete_unit_weight_kn_m3: float,
    pipe_centerline_height_m: float,
    vertical_load_factor: float,
    horizontal_load_factor: float,
    cohesion_kpa: float,
    soil_friction_angle_deg: float,
    soil_unit_weight_kn_m3: float,
    embedment_depth_m: float,
    footing_shape: Literal["strip", "square", "circular"],
    water_table_depth_m: float,
    bearing_factor_of_safety: float,
    sliding_friction_coefficient: float,
    anchor_bolt_count: int,
    anchor_allowable_shear_per_bolt_kn: float,
) -> dict[str, float]:
    """Compute pipe transient support and foundation metrics for the SSC-14 source pack."""
    _require_nonnegative(transient_pressure_kpa=transient_pressure_kpa, bend_angle_deg=bend_angle_deg)
    _require_positive(
        pipe_internal_diameter_mm=pipe_internal_diameter_mm,
        pipe_outer_diameter_mm=pipe_outer_diameter_mm,
        pipe_wall_thickness_mm=pipe_wall_thickness_mm,
        steel_density_kg_m3=steel_density_kg_m3,
        contents_density_kg_m3=contents_density_kg_m3,
        insulation_density_kg_m3=insulation_density_kg_m3,
        support_span_m=support_span_m,
        foundation_length_along_thrust_m=foundation_length_along_thrust_m,
        foundation_width_transverse_m=foundation_width_transverse_m,
        foundation_depth_m=foundation_depth_m,
        concrete_unit_weight_kn_m3=concrete_unit_weight_kn_m3,
        pipe_centerline_height_m=pipe_centerline_height_m,
        vertical_load_factor=vertical_load_factor,
        horizontal_load_factor=horizontal_load_factor,
        anchor_allowable_shear_per_bolt_kn=anchor_allowable_shear_per_bolt_kn,
    )
    _require_nonnegative(
        insulation_thickness_mm=insulation_thickness_mm,
        valve_weight_kn=valve_weight_kn,
        saddle_weight_kn=saddle_weight_kn,
        sliding_friction_coefficient=sliding_friction_coefficient,
    )
    if bend_angle_deg > 180.0:
        msg = "bend_angle_deg must be between 0 and 180"
        raise ValueError(msg)
    if pipe_internal_diameter_mm >= pipe_outer_diameter_mm:
        msg = "pipe_internal_diameter_mm must be less than pipe_outer_diameter_mm"
        raise ValueError(msg)
    if 2.0 * pipe_wall_thickness_mm >= pipe_outer_diameter_mm:
        msg = "pipe wall thickness must leave a positive internal diameter"
        raise ValueError(msg)
    if anchor_bolt_count <= 0:
        msg = "anchor_bolt_count must be > 0"
        raise ValueError(msg)

    pipe_internal_area_m2 = _circle_area_m2(pipe_internal_diameter_mm)
    pressure_force_kn = transient_pressure_kpa * pipe_internal_area_m2
    transient_thrust_kn = 2.0 * pressure_force_kn * math.sin(math.radians(bend_angle_deg) / 2.0)

    pipe_dead_load_inner_diameter_mm = pipe_outer_diameter_mm - 2.0 * pipe_wall_thickness_mm
    insulation_outer_diameter_mm = pipe_outer_diameter_mm + 2.0 * insulation_thickness_mm
    steel_area_m2 = _annulus_area_m2(pipe_outer_diameter_mm, pipe_dead_load_inner_diameter_mm)
    contents_area_m2 = _circle_area_m2(pipe_dead_load_inner_diameter_mm)
    insulation_area_m2 = _annulus_area_m2(insulation_outer_diameter_mm, pipe_outer_diameter_mm)
    operating_line_load_kn_m = (
        _line_load_kn_m(steel_area_m2, steel_density_kg_m3)
        + _line_load_kn_m(contents_area_m2, contents_density_kg_m3)
        + _line_load_kn_m(insulation_area_m2, insulation_density_kg_m3)
    )
    support_vertical_service_kn = operating_line_load_kn_m * support_span_m + valve_weight_kn + saddle_weight_kn

    foundation_self_weight_kn = (
        foundation_length_along_thrust_m
        * foundation_width_transverse_m
        * foundation_depth_m
        * concrete_unit_weight_kn_m3
    )
    terzaghi_allowable_bearing_kpa = _terzaghi_allowable_bearing_kpa(
        cohesion_kpa=cohesion_kpa,
        soil_friction_angle_deg=soil_friction_angle_deg,
        soil_unit_weight_kn_m3=soil_unit_weight_kn_m3,
        footing_width_m=foundation_width_transverse_m,
        embedment_depth_m=embedment_depth_m,
        footing_shape=footing_shape,
        water_table_depth_m=water_table_depth_m,
        bearing_factor_of_safety=bearing_factor_of_safety,
    )

    factored_vertical_load_kn = vertical_load_factor * (support_vertical_service_kn + foundation_self_weight_kn)
    factored_horizontal_load_kn = horizontal_load_factor * transient_thrust_kn
    overturning_moment_knm = factored_horizontal_load_kn * pipe_centerline_height_m
    bearing_eccentricity_m = overturning_moment_knm / factored_vertical_load_kn
    middle_third_limit_m = foundation_length_along_thrust_m / 6.0
    base_area_m2 = foundation_length_along_thrust_m * foundation_width_transverse_m
    average_bearing_kpa = factored_vertical_load_kn / base_area_m2
    maximum_bearing_kpa = average_bearing_kpa * (1.0 + 6.0 * bearing_eccentricity_m / foundation_length_along_thrust_m)
    bearing_utilization = maximum_bearing_kpa / terzaghi_allowable_bearing_kpa
    anchor_shear_per_bolt_kn = factored_horizontal_load_kn / anchor_bolt_count
    anchor_shear_utilization = anchor_shear_per_bolt_kn / anchor_allowable_shear_per_bolt_kn
    sliding_margin_kn = sliding_friction_coefficient * factored_vertical_load_kn - factored_horizontal_load_kn
    overall_pass_score = (
        1.0
        if (
            bearing_eccentricity_m <= middle_third_limit_m
            and bearing_utilization <= 1.0
            and anchor_shear_utilization <= 1.0
            and sliding_margin_kn >= 0.0
        )
        else 0.0
    )

    return {
        "pipe_internal_area_m2": round(pipe_internal_area_m2, 3),
        "pressure_force_kn": round(pressure_force_kn, 3),
        "transient_thrust_kn": round(transient_thrust_kn, 3),
        "operating_line_load_kn_m": round(operating_line_load_kn_m, 3),
        "support_vertical_service_kn": round(support_vertical_service_kn, 3),
        "foundation_self_weight_kn": round(foundation_self_weight_kn, 3),
        "terzaghi_allowable_bearing_kpa": round(terzaghi_allowable_bearing_kpa, 3),
        "factored_vertical_load_kn": round(factored_vertical_load_kn, 3),
        "factored_horizontal_load_kn": round(factored_horizontal_load_kn, 3),
        "overturning_moment_knm": round(overturning_moment_knm, 3),
        "bearing_eccentricity_m": round(bearing_eccentricity_m, 3),
        "middle_third_limit_m": round(middle_third_limit_m, 3),
        "maximum_bearing_kpa": round(maximum_bearing_kpa, 3),
        "bearing_utilization": round(bearing_utilization, 3),
        "anchor_shear_per_bolt_kn": round(anchor_shear_per_bolt_kn, 3),
        "anchor_shear_utilization": round(anchor_shear_utilization, 3),
        "sliding_margin_kn": round(sliding_margin_kn, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
