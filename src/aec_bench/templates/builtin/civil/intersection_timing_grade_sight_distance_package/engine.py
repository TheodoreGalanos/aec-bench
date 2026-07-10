# ABOUTME: Computes SSC-01 intersection timing, grade, and sight-distance metrics.
# ABOUTME: Combines stopping distance, yellow/all-red timing, and pedestrian clearance checks.

from __future__ import annotations

_G = 9.81


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    approach_speed_kmh: float,
    approach_grade_pct: float,
    reaction_time_s: float,
    braking_friction_coefficient: float,
    available_sight_distance_m: float,
    yellow_reaction_time_s: float,
    yellow_deceleration_m_s2: float,
    intersection_width_m: float,
    design_vehicle_length_m: float,
    all_red_speed_kmh: float,
    pedestrian_startup_time_s: float,
    crossing_width_m: float,
    pedestrian_walk_speed_m_s: float,
    pedestrian_clearance_available_s: float,
) -> dict[str, float]:
    """Compute deterministic SSC-01 intersection timing and sight-distance metrics."""
    _require_positive(
        approach_speed_kmh=approach_speed_kmh,
        reaction_time_s=reaction_time_s,
        braking_friction_coefficient=braking_friction_coefficient,
        available_sight_distance_m=available_sight_distance_m,
        yellow_reaction_time_s=yellow_reaction_time_s,
        yellow_deceleration_m_s2=yellow_deceleration_m_s2,
        intersection_width_m=intersection_width_m,
        design_vehicle_length_m=design_vehicle_length_m,
        all_red_speed_kmh=all_red_speed_kmh,
        pedestrian_walk_speed_m_s=pedestrian_walk_speed_m_s,
        pedestrian_clearance_available_s=pedestrian_clearance_available_s,
    )
    speed_m_s = approach_speed_kmh / 3.6
    grade_fraction = approach_grade_pct / 100.0
    braking_denominator = 2.0 * _G * (braking_friction_coefficient + grade_fraction)
    if braking_denominator <= 0:
        msg = "braking denominator must be positive"
        raise ValueError(msg)

    grade_adjusted_braking_distance_m = speed_m_s**2 / braking_denominator
    stopping_distance_m = speed_m_s * reaction_time_s + grade_adjusted_braking_distance_m
    sight_distance_margin_m = available_sight_distance_m - stopping_distance_m
    yellow_interval_s = yellow_reaction_time_s + speed_m_s / (
        2.0 * yellow_deceleration_m_s2 + 2.0 * _G * grade_fraction
    )
    all_red_interval_s = (intersection_width_m + design_vehicle_length_m) / (all_red_speed_kmh / 3.6)
    ped_clearance_required_s = pedestrian_startup_time_s + crossing_width_m / pedestrian_walk_speed_m_s
    ped_clearance_margin_s = pedestrian_clearance_available_s - ped_clearance_required_s

    pass_checks = [
        sight_distance_margin_m >= 0.0,
        yellow_interval_s > 0.0,
        all_red_interval_s > 0.0,
        ped_clearance_margin_s >= 0.0,
    ]

    return {
        "stopping_distance_m": round(stopping_distance_m, 3),
        "sight_distance_margin_m": round(sight_distance_margin_m, 3),
        "yellow_interval_s": round(yellow_interval_s, 3),
        "all_red_interval_s": round(all_red_interval_s, 3),
        "ped_clearance_required_s": round(ped_clearance_required_s, 3),
        "ped_clearance_margin_s": round(ped_clearance_margin_s, 3),
        "grade_adjusted_braking_distance_m": round(grade_adjusted_braking_distance_m, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
