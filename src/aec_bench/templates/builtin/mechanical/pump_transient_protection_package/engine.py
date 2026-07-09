# ABOUTME: Computes SSC-11 pump transient, thrust, support, and protection metrics.
# ABOUTME: Combines source-owned water-hammer, pump head, pipe load, and margin checks.

from __future__ import annotations

import math

_G = 9.81


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


def _circle_area_m2(diameter_mm: float) -> float:
    """Return circular area from diameter in millimetres."""
    diameter_m = diameter_mm / 1000.0
    return math.pi * diameter_m**2 / 4.0


def _annulus_area_m2(outer_diameter_mm: float, inner_diameter_mm: float) -> float:
    """Return circular annulus area from diameters in millimetres."""
    return math.pi / 4.0 * ((outer_diameter_mm / 1000.0) ** 2 - (inner_diameter_mm / 1000.0) ** 2)


def _line_load_kn_m(area_m2: float, density_kg_m3: float) -> float:
    """Return gravity line load in kN/m for a material area and density."""
    return area_m2 * density_kg_m3 * _G / 1000.0


def compute(
    fluid_density_kg_m3: float,
    fluid_bulk_modulus_gpa: float,
    pipe_elastic_modulus_gpa: float,
    pipe_internal_diameter_mm: float,
    pipe_wall_thickness_mm: float,
    pipe_outer_diameter_mm: float,
    pipe_restraint_factor: float,
    flow_rate_l_s: float,
    velocity_change_fraction: float,
    suction_pressure_kpa: float,
    discharge_pressure_kpa: float,
    pipe_friction_loss_kpa: float,
    static_elevation_m: float,
    bend_angle_deg: float,
    steel_density_kg_m3: float,
    insulation_thickness_mm: float,
    insulation_density_kg_m3: float,
    support_span_m: float,
    valve_weight_kn: float,
    actuator_weight_kn: float,
    high_high_trip_setpoint_kpa: float,
    pipe_mawp_kpa: float,
    thrust_allowable_kn: float,
    support_vertical_allowable_kn: float,
) -> dict[str, float]:
    """Compute pump transient and protection metrics for the SSC-11 source pack."""
    _require_positive(
        fluid_density_kg_m3=fluid_density_kg_m3,
        fluid_bulk_modulus_gpa=fluid_bulk_modulus_gpa,
        pipe_elastic_modulus_gpa=pipe_elastic_modulus_gpa,
        pipe_internal_diameter_mm=pipe_internal_diameter_mm,
        pipe_wall_thickness_mm=pipe_wall_thickness_mm,
        pipe_outer_diameter_mm=pipe_outer_diameter_mm,
        pipe_restraint_factor=pipe_restraint_factor,
        flow_rate_l_s=flow_rate_l_s,
        velocity_change_fraction=velocity_change_fraction,
        steel_density_kg_m3=steel_density_kg_m3,
        insulation_density_kg_m3=insulation_density_kg_m3,
        support_span_m=support_span_m,
        high_high_trip_setpoint_kpa=high_high_trip_setpoint_kpa,
        pipe_mawp_kpa=pipe_mawp_kpa,
        thrust_allowable_kn=thrust_allowable_kn,
        support_vertical_allowable_kn=support_vertical_allowable_kn,
    )
    _require_nonnegative(
        suction_pressure_kpa=suction_pressure_kpa,
        discharge_pressure_kpa=discharge_pressure_kpa,
        pipe_friction_loss_kpa=pipe_friction_loss_kpa,
        static_elevation_m=static_elevation_m,
        bend_angle_deg=bend_angle_deg,
        insulation_thickness_mm=insulation_thickness_mm,
        valve_weight_kn=valve_weight_kn,
        actuator_weight_kn=actuator_weight_kn,
    )
    if pipe_internal_diameter_mm >= pipe_outer_diameter_mm:
        msg = "pipe_internal_diameter_mm must be less than pipe_outer_diameter_mm"
        raise ValueError(msg)
    if 2.0 * pipe_wall_thickness_mm >= pipe_outer_diameter_mm:
        msg = "pipe wall thickness must leave a positive internal diameter"
        raise ValueError(msg)
    if not 0.0 < velocity_change_fraction <= 1.0:
        msg = "velocity_change_fraction must be between 0 and 1"
        raise ValueError(msg)
    if bend_angle_deg > 180.0:
        msg = "bend_angle_deg must be between 0 and 180"
        raise ValueError(msg)

    bulk_modulus_pa = fluid_bulk_modulus_gpa * 1_000_000_000.0
    elastic_modulus_pa = pipe_elastic_modulus_gpa * 1_000_000_000.0
    internal_area_m2 = _circle_area_m2(pipe_internal_diameter_mm)

    fluid_only_wave_speed_m_s = math.sqrt(bulk_modulus_pa / fluid_density_kg_m3)
    pipe_flexibility_ratio = (
        bulk_modulus_pa
        / elastic_modulus_pa
        * (pipe_internal_diameter_mm / pipe_wall_thickness_mm)
        * pipe_restraint_factor
    )
    wave_speed_m_s = fluid_only_wave_speed_m_s / math.sqrt(1.0 + pipe_flexibility_ratio)

    flow_rate_m3_s = flow_rate_l_s / 1000.0
    steady_velocity_m_s = flow_rate_m3_s / internal_area_m2
    velocity_change_m_s = steady_velocity_m_s * velocity_change_fraction
    joukowsky_pressure_rise_kpa = fluid_density_kg_m3 * wave_speed_m_s * velocity_change_m_s / 1000.0
    pressure_unit_weight_kpa_m = fluid_density_kg_m3 * _G / 1000.0
    joukowsky_pressure_head_m = joukowsky_pressure_rise_kpa / pressure_unit_weight_kpa_m

    pressure_lift_kpa = discharge_pressure_kpa - suction_pressure_kpa + pipe_friction_loss_kpa
    total_dynamic_head_m = static_elevation_m + pressure_lift_kpa / pressure_unit_weight_kpa_m
    hydraulic_power_kw = fluid_density_kg_m3 * _G * flow_rate_m3_s * total_dynamic_head_m / 1000.0

    peak_transient_pressure_kpa = discharge_pressure_kpa + joukowsky_pressure_rise_kpa
    bend_transient_thrust_kn = (
        2.0 * peak_transient_pressure_kpa * internal_area_m2 * math.sin(math.radians(bend_angle_deg) / 2.0)
    )

    steel_area_m2 = _annulus_area_m2(pipe_outer_diameter_mm, pipe_internal_diameter_mm)
    insulation_outer_diameter_mm = pipe_outer_diameter_mm + 2.0 * insulation_thickness_mm
    insulation_area_m2 = _annulus_area_m2(insulation_outer_diameter_mm, pipe_outer_diameter_mm)
    steel_line_load_kn_m = _line_load_kn_m(steel_area_m2, steel_density_kg_m3)
    contents_line_load_kn_m = _line_load_kn_m(internal_area_m2, fluid_density_kg_m3)
    insulation_line_load_kn_m = _line_load_kn_m(insulation_area_m2, insulation_density_kg_m3)
    operating_line_load_kn_m = steel_line_load_kn_m + contents_line_load_kn_m + insulation_line_load_kn_m
    support_vertical_service_kn = operating_line_load_kn_m * support_span_m + valve_weight_kn + actuator_weight_kn

    pressure_trip_margin_kpa = high_high_trip_setpoint_kpa - peak_transient_pressure_kpa
    pipe_pressure_margin_kpa = pipe_mawp_kpa - peak_transient_pressure_kpa
    thrust_utilization = bend_transient_thrust_kn / thrust_allowable_kn
    support_vertical_utilization = support_vertical_service_kn / support_vertical_allowable_kn
    overall_pass_score = (
        1.0
        if min(
            pressure_trip_margin_kpa,
            pipe_pressure_margin_kpa,
            thrust_allowable_kn - bend_transient_thrust_kn,
            support_vertical_allowable_kn - support_vertical_service_kn,
        )
        >= 0.0
        else 0.0
    )

    return {
        "fluid_only_wave_speed_m_s": round(fluid_only_wave_speed_m_s, 3),
        "pipe_flexibility_ratio": round(pipe_flexibility_ratio, 3),
        "wave_speed_m_s": round(wave_speed_m_s, 3),
        "steady_velocity_m_s": round(steady_velocity_m_s, 3),
        "velocity_change_m_s": round(velocity_change_m_s, 3),
        "joukowsky_pressure_rise_kpa": round(joukowsky_pressure_rise_kpa, 3),
        "joukowsky_pressure_head_m": round(joukowsky_pressure_head_m, 3),
        "total_dynamic_head_m": round(total_dynamic_head_m, 3),
        "hydraulic_power_kw": round(hydraulic_power_kw, 3),
        "peak_transient_pressure_kpa": round(peak_transient_pressure_kpa, 3),
        "bend_transient_thrust_kn": round(bend_transient_thrust_kn, 3),
        "operating_line_load_kn_m": round(operating_line_load_kn_m, 3),
        "support_vertical_service_kn": round(support_vertical_service_kn, 3),
        "pressure_trip_margin_kpa": round(pressure_trip_margin_kpa, 3),
        "pipe_pressure_margin_kpa": round(pipe_pressure_margin_kpa, 3),
        "thrust_utilization": round(thrust_utilization, 3),
        "support_vertical_utilization": round(support_vertical_utilization, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
