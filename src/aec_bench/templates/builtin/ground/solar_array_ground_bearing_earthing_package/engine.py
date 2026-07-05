# ABOUTME: Computes SSC-07 solar array wind, bearing, and earthing metrics.
# ABOUTME: Combines PV rack load, foundation bearing, uplift, and GPR screening.

from __future__ import annotations

import math


def compute(
    wind_pressure_kpa: float,
    module_area_m2: float,
    drag_coefficient: float,
    module_count: float,
    support_count: float,
    ballast_dead_load_kn: float,
    footing_area_m2: float,
    allowable_bearing_kpa: float,
    soil_resistivity_ohm_m: float,
    grid_length_m: float,
    grid_width_m: float,
    conductor_length_m: float,
    grid_current_ka: float,
    gpr_limit_v: float,
) -> dict[str, float]:
    """Compute PV ground-bearing and earthing source-pack metrics."""
    wind_force_total_kn = wind_pressure_kpa * module_area_m2 * drag_coefficient * module_count
    support_reaction_kn = wind_force_total_kn / support_count
    uplift_force_kn = wind_force_total_kn * 0.55
    uplift_margin_kn = ballast_dead_load_kn - uplift_force_kn
    bearing_pressure_kpa = (ballast_dead_load_kn + 0.25 * wind_force_total_kn) / footing_area_m2
    bearing_utilization = bearing_pressure_kpa / allowable_bearing_kpa
    grid_area_m2 = grid_length_m * grid_width_m
    grid_resistance_ohm = (
        soil_resistivity_ohm_m / (4.0 * math.sqrt(grid_area_m2)) + soil_resistivity_ohm_m / conductor_length_m
    )
    ground_potential_rise_v = grid_resistance_ohm * grid_current_ka * 1000.0
    gpr_margin_v = gpr_limit_v - ground_potential_rise_v
    overall_pass_score = 1.0 if uplift_margin_kn >= 0.0 and bearing_utilization <= 1.0 and gpr_margin_v >= 0.0 else 0.0

    return {
        "wind_force_total_kn": round(wind_force_total_kn, 3),
        "support_reaction_kn": round(support_reaction_kn, 3),
        "uplift_force_kn": round(uplift_force_kn, 3),
        "uplift_margin_kn": round(uplift_margin_kn, 3),
        "bearing_pressure_kpa": round(bearing_pressure_kpa, 3),
        "bearing_utilization": round(bearing_utilization, 3),
        "grid_resistance_ohm": round(grid_resistance_ohm, 3),
        "ground_potential_rise_v": round(ground_potential_rise_v, 3),
        "gpr_margin_v": round(gpr_margin_v, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
