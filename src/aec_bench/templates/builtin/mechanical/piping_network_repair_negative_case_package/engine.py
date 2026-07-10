# ABOUTME: Computes SSC-11 piping network repair and negative-case portfolio metrics.
# ABOUTME: Combines baseline and variant hydraulics, thrust, support shift, and case capture.

from __future__ import annotations

import math

_G = 9.81


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _velocity_and_headloss(
    *,
    flow_l_s: float,
    pipe_area_m2: float,
    darcy_friction_factor: float,
    pipe_length_m: float,
    pipe_internal_diameter_m: float,
    valve_loss_coefficient: float,
) -> tuple[float, float]:
    """Return pipe velocity and combined major/minor headloss."""
    velocity_m_s = (flow_l_s / 1000.0) / pipe_area_m2
    velocity_head_m = velocity_m_s**2 / (2.0 * _G)
    headloss_m = darcy_friction_factor * (pipe_length_m / pipe_internal_diameter_m) * velocity_head_m
    headloss_m += valve_loss_coefficient * velocity_head_m
    return velocity_m_s, headloss_m


def compute(
    baseline_flow_l_s: float,
    variant_flow_l_s: float,
    pipe_internal_diameter_mm: float,
    pipe_length_m: float,
    darcy_friction_factor: float,
    baseline_valve_loss_coefficient: float,
    variant_valve_loss_coefficient: float,
    measured_support_shift_m: float,
    allowed_support_shift_m: float,
    bend_pressure_kpa: float,
    bend_angle_deg: float,
    thrust_allowable_kn: float,
    expected_negative_cases: float,
    localized_negative_cases: float,
    unresolved_repair_count: float,
    maximum_variant_velocity_m_s: float,
) -> dict[str, float]:
    """Compute deterministic SSC-11 piping repair and negative-case metrics."""
    _require_positive(
        baseline_flow_l_s=baseline_flow_l_s,
        variant_flow_l_s=variant_flow_l_s,
        pipe_internal_diameter_mm=pipe_internal_diameter_mm,
        pipe_length_m=pipe_length_m,
        darcy_friction_factor=darcy_friction_factor,
        baseline_valve_loss_coefficient=baseline_valve_loss_coefficient,
        variant_valve_loss_coefficient=variant_valve_loss_coefficient,
        allowed_support_shift_m=allowed_support_shift_m,
        bend_pressure_kpa=bend_pressure_kpa,
        thrust_allowable_kn=thrust_allowable_kn,
        expected_negative_cases=expected_negative_cases,
        localized_negative_cases=localized_negative_cases,
        maximum_variant_velocity_m_s=maximum_variant_velocity_m_s,
    )

    pipe_internal_diameter_m = pipe_internal_diameter_mm / 1000.0
    pipe_area_m2 = math.pi / 4.0 * pipe_internal_diameter_m**2
    baseline_velocity_m_s, baseline_headloss_m = _velocity_and_headloss(
        flow_l_s=baseline_flow_l_s,
        pipe_area_m2=pipe_area_m2,
        darcy_friction_factor=darcy_friction_factor,
        pipe_length_m=pipe_length_m,
        pipe_internal_diameter_m=pipe_internal_diameter_m,
        valve_loss_coefficient=baseline_valve_loss_coefficient,
    )
    variant_velocity_m_s, variant_headloss_m = _velocity_and_headloss(
        flow_l_s=variant_flow_l_s,
        pipe_area_m2=pipe_area_m2,
        darcy_friction_factor=darcy_friction_factor,
        pipe_length_m=pipe_length_m,
        pipe_internal_diameter_m=pipe_internal_diameter_m,
        valve_loss_coefficient=variant_valve_loss_coefficient,
    )
    velocity_delta_m_s = variant_velocity_m_s - baseline_velocity_m_s
    headloss_delta_m = variant_headloss_m - baseline_headloss_m
    bend_thrust_kn = 2.0 * bend_pressure_kpa * pipe_area_m2 * math.sin(math.radians(bend_angle_deg) / 2.0)
    thrust_utilization = bend_thrust_kn / thrust_allowable_kn
    support_shift_margin_m = allowed_support_shift_m - measured_support_shift_m
    negative_case_capture_percent = localized_negative_cases / expected_negative_cases * 100.0

    pass_checks = [
        variant_velocity_m_s <= maximum_variant_velocity_m_s,
        thrust_utilization <= 1.0,
        support_shift_margin_m >= 0.0,
        negative_case_capture_percent >= 100.0,
        unresolved_repair_count == 0.0,
    ]

    return {
        "baseline_velocity_m_s": round(baseline_velocity_m_s, 3),
        "variant_velocity_m_s": round(variant_velocity_m_s, 3),
        "velocity_delta_m_s": round(velocity_delta_m_s, 3),
        "baseline_headloss_m": round(baseline_headloss_m, 3),
        "variant_headloss_m": round(variant_headloss_m, 3),
        "headloss_delta_m": round(headloss_delta_m, 3),
        "bend_thrust_kn": round(bend_thrust_kn, 3),
        "thrust_utilization": round(thrust_utilization, 3),
        "support_shift_margin_m": round(support_shift_margin_m, 3),
        "negative_case_capture_percent": round(negative_case_capture_percent, 3),
        "unresolved_repair_count": round(unresolved_repair_count, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
