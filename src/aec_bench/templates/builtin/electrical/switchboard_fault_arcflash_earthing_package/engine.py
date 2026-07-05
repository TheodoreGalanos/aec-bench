# ABOUTME: Computes SSC-05 switchboard fault, arc-flash, and earthing metrics.
# ABOUTME: Combines source fault level, protection clearing, grid resistance, and busbar checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    utility_fault_mva: float,
    switchboard_voltage_v: float,
    transformer_contribution_ka: float,
    motor_contribution_ka: float,
    switchboard_fault_rating_ka: float,
    arcing_current_factor: float,
    clearing_time_s: float,
    incident_energy_factor: float,
    working_distance_m: float,
    allowable_incident_energy_cal_cm2: float,
    earth_grid_resistance_ohm: float,
    touch_voltage_limit_v: float,
    busbar_force_factor: float,
    busbar_force_rating_kn: float,
) -> dict[str, float]:
    """Compute source-bound fault-duty, arc-flash, earthing, and busbar metrics."""
    _require_positive(
        utility_fault_mva=utility_fault_mva,
        switchboard_voltage_v=switchboard_voltage_v,
        transformer_contribution_ka=transformer_contribution_ka,
        motor_contribution_ka=motor_contribution_ka,
        switchboard_fault_rating_ka=switchboard_fault_rating_ka,
        arcing_current_factor=arcing_current_factor,
        clearing_time_s=clearing_time_s,
        incident_energy_factor=incident_energy_factor,
        working_distance_m=working_distance_m,
        allowable_incident_energy_cal_cm2=allowable_incident_energy_cal_cm2,
        earth_grid_resistance_ohm=earth_grid_resistance_ohm,
        touch_voltage_limit_v=touch_voltage_limit_v,
        busbar_force_factor=busbar_force_factor,
        busbar_force_rating_kn=busbar_force_rating_kn,
    )

    utility_fault_current_ka = utility_fault_mva * 1000.0 / (math.sqrt(3.0) * switchboard_voltage_v)
    total_fault_current_ka = utility_fault_current_ka + transformer_contribution_ka + motor_contribution_ka
    fault_rating_margin_ka = switchboard_fault_rating_ka - total_fault_current_ka

    incident_energy_cal_cm2 = (
        total_fault_current_ka
        * arcing_current_factor
        * clearing_time_s
        * incident_energy_factor
        / (working_distance_m**2)
    )
    incident_energy_margin_cal_cm2 = allowable_incident_energy_cal_cm2 - incident_energy_cal_cm2
    touch_voltage_v = total_fault_current_ka * 1000.0 * earth_grid_resistance_ohm
    touch_voltage_margin_v = touch_voltage_limit_v - touch_voltage_v
    busbar_force_kn = busbar_force_factor * total_fault_current_ka**2
    busbar_force_margin_kn = busbar_force_rating_kn - busbar_force_kn

    overall_pass_score = (
        1.0
        if min(
            fault_rating_margin_ka,
            incident_energy_margin_cal_cm2,
            touch_voltage_margin_v,
            busbar_force_margin_kn,
        )
        >= 0.0
        else 0.0
    )

    return {
        "utility_fault_current_ka": round(utility_fault_current_ka, 3),
        "total_fault_current_ka": round(total_fault_current_ka, 3),
        "fault_rating_margin_ka": round(fault_rating_margin_ka, 3),
        "incident_energy_cal_cm2": round(incident_energy_cal_cm2, 3),
        "incident_energy_margin_cal_cm2": round(incident_energy_margin_cal_cm2, 3),
        "touch_voltage_v": round(touch_voltage_v, 3),
        "touch_voltage_margin_v": round(touch_voltage_margin_v, 3),
        "busbar_force_kn": round(busbar_force_kn, 3),
        "busbar_force_margin_kn": round(busbar_force_margin_kn, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
