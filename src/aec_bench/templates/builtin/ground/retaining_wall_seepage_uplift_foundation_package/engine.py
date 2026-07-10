# ABOUTME: Computes SSC-07 retaining wall seepage, uplift, and foundation metrics.
# ABOUTME: Keeps lateral pressure, stability, bearing, and seepage values source-bound.

from __future__ import annotations

import math


def compute(
    retained_height_m: float,
    soil_unit_weight_kn_m3: float,
    friction_angle_deg: float,
    surcharge_kpa: float,
    base_width_m: float,
    wall_weight_kn_m: float,
    base_friction_coefficient: float,
    passive_resistance_kn_m: float,
    allowable_bearing_kpa: float,
    head_difference_m: float,
    seepage_path_m: float,
    critical_gradient: float,
) -> dict[str, float]:
    """Compute retaining-wall source-pack metrics."""
    active_pressure_coefficient = math.tan(math.radians(45.0 - friction_angle_deg / 2.0)) ** 2
    active_thrust_kn_m = (
        0.5 * active_pressure_coefficient * soil_unit_weight_kn_m3 * retained_height_m**2
        + active_pressure_coefficient * surcharge_kpa * retained_height_m
    )
    sliding_resistance_kn_m = wall_weight_kn_m * base_friction_coefficient + passive_resistance_kn_m
    sliding_fs = sliding_resistance_kn_m / active_thrust_kn_m
    overturning_moment_kn_m_m = active_thrust_kn_m * retained_height_m / 3.0
    resisting_moment_kn_m_m = wall_weight_kn_m * base_width_m / 2.0
    overturning_fs = resisting_moment_kn_m_m / overturning_moment_kn_m_m
    max_bearing_pressure_kpa = wall_weight_kn_m / base_width_m + 6.0 * overturning_moment_kn_m_m / base_width_m**2
    bearing_margin_kpa = allowable_bearing_kpa - max_bearing_pressure_kpa
    exit_gradient = head_difference_m / seepage_path_m
    exit_gradient_fs = critical_gradient / exit_gradient
    uplift_pressure_kpa = 9.81 * head_difference_m
    uplift_margin_kpa = wall_weight_kn_m / base_width_m - uplift_pressure_kpa
    overall_pass_score = (
        1.0
        if (
            sliding_fs >= 1.5
            and overturning_fs >= 2.0
            and bearing_margin_kpa >= 0.0
            and exit_gradient_fs >= 3.0
            and uplift_margin_kpa >= 0.0
        )
        else 0.0
    )

    return {
        "active_pressure_coefficient": round(active_pressure_coefficient, 3),
        "active_thrust_kn_m": round(active_thrust_kn_m, 3),
        "sliding_fs": round(sliding_fs, 3),
        "overturning_fs": round(overturning_fs, 3),
        "max_bearing_pressure_kpa": round(max_bearing_pressure_kpa, 3),
        "bearing_margin_kpa": round(bearing_margin_kpa, 3),
        "exit_gradient": round(exit_gradient, 3),
        "exit_gradient_fs": round(exit_gradient_fs, 3),
        "uplift_pressure_kpa": round(uplift_pressure_kpa, 3),
        "uplift_margin_kpa": round(uplift_margin_kpa, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
