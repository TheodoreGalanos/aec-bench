# ABOUTME: Computes SSC-11 process piping valve and control package metrics.
# ABOUTME: Combines valve Cv, velocity, signal scaling, pressure loss, and thrust checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    process_flow_m3_h: float,
    liquid_specific_gravity: float,
    valve_pressure_drop_kpa: float,
    installed_valve_cv: float,
    pipe_internal_diameter_mm: float,
    maximum_velocity_m_s: float,
    maximum_pressure_loss_kpa: float,
    line_pressure_kpa: float,
    signal_low_value: float,
    signal_high_value: float,
    process_value: float,
    signal_low_ma: float,
    signal_high_ma: float,
    bend_angle_deg: float,
    thrust_allowable_kn: float,
) -> dict[str, float]:
    """Compute deterministic SSC-11 process piping valve and control metrics."""
    _require_positive(
        process_flow_m3_h=process_flow_m3_h,
        liquid_specific_gravity=liquid_specific_gravity,
        valve_pressure_drop_kpa=valve_pressure_drop_kpa,
        installed_valve_cv=installed_valve_cv,
        pipe_internal_diameter_mm=pipe_internal_diameter_mm,
        maximum_velocity_m_s=maximum_velocity_m_s,
        maximum_pressure_loss_kpa=maximum_pressure_loss_kpa,
        line_pressure_kpa=line_pressure_kpa,
        signal_high_value=signal_high_value,
        signal_high_ma=signal_high_ma,
        thrust_allowable_kn=thrust_allowable_kn,
    )

    flow_gpm = process_flow_m3_h * 4.4028675
    pressure_drop_psi = valve_pressure_drop_kpa * 0.145038
    required_valve_cv = flow_gpm * math.sqrt(liquid_specific_gravity / pressure_drop_psi)
    valve_cv_margin = installed_valve_cv - required_valve_cv
    pipe_area_m2 = math.pi / 4.0 * (pipe_internal_diameter_mm / 1000.0) ** 2
    pipe_velocity_m_s = (process_flow_m3_h / 3600.0) / pipe_area_m2
    velocity_margin_m_s = maximum_velocity_m_s - pipe_velocity_m_s
    pressure_loss_margin_kpa = maximum_pressure_loss_kpa - valve_pressure_drop_kpa
    control_signal_ma = signal_low_ma + (process_value - signal_low_value) / (signal_high_value - signal_low_value) * (
        signal_high_ma - signal_low_ma
    )
    bend_thrust_kn = 2.0 * line_pressure_kpa * pipe_area_m2 * math.sin(math.radians(bend_angle_deg) / 2.0)
    thrust_utilization = bend_thrust_kn / thrust_allowable_kn

    pass_checks = [
        valve_cv_margin >= 0.0,
        velocity_margin_m_s >= 0.0,
        pressure_loss_margin_kpa >= 0.0,
        thrust_utilization <= 1.0,
    ]

    return {
        "required_valve_cv": round(required_valve_cv, 3),
        "valve_cv_margin": round(valve_cv_margin, 3),
        "pipe_velocity_m_s": round(pipe_velocity_m_s, 3),
        "velocity_margin_m_s": round(velocity_margin_m_s, 3),
        "pressure_loss_margin_kpa": round(pressure_loss_margin_kpa, 3),
        "control_signal_ma": round(control_signal_ma, 3),
        "bend_thrust_kn": round(bend_thrust_kn, 3),
        "thrust_utilization": round(thrust_utilization, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
