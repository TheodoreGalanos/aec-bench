# ABOUTME: Computes SSC-14 retaining foundation groundwater stability package metrics.
# ABOUTME: Combines earth pressure, hydrostatic load, stability, bearing, and uplift checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    retained_height_m: float,
    soil_unit_weight_kn_m3: float,
    soil_friction_angle_deg: float,
    surcharge_kpa: float,
    water_height_m: float,
    wall_vertical_weight_kn_m: float,
    base_width_m: float,
    resisting_lever_arm_ratio: float,
    base_friction_coefficient: float,
    allowable_bearing_kpa: float,
    uplift_force_kn_m: float,
    minimum_overturning_fs: float,
    minimum_sliding_fs: float,
) -> dict[str, float]:
    """Compute deterministic SSC-14 retaining and groundwater stability metrics."""
    _require_positive(
        retained_height_m=retained_height_m,
        soil_unit_weight_kn_m3=soil_unit_weight_kn_m3,
        base_width_m=base_width_m,
        resisting_lever_arm_ratio=resisting_lever_arm_ratio,
        base_friction_coefficient=base_friction_coefficient,
        allowable_bearing_kpa=allowable_bearing_kpa,
        minimum_overturning_fs=minimum_overturning_fs,
        minimum_sliding_fs=minimum_sliding_fs,
    )
    if not 0.0 < soil_friction_angle_deg < 45.0:
        msg = "soil_friction_angle_deg must be between 0 and 45"
        raise ValueError(msg)

    ka = math.tan(math.radians(45.0 - soil_friction_angle_deg / 2.0)) ** 2
    active_earth_force_kn_m = 0.5 * ka * soil_unit_weight_kn_m3 * retained_height_m**2
    surcharge_force_kn_m = ka * surcharge_kpa * retained_height_m
    hydrostatic_force_kn_m = 0.5 * 9.81 * water_height_m**2
    total_lateral_force_kn_m = active_earth_force_kn_m + surcharge_force_kn_m + hydrostatic_force_kn_m
    overturning_moment_knm_m = (
        active_earth_force_kn_m * retained_height_m / 3.0
        + surcharge_force_kn_m * retained_height_m / 2.0
        + hydrostatic_force_kn_m * water_height_m / 3.0
    )
    resisting_moment_knm_m = wall_vertical_weight_kn_m * base_width_m * resisting_lever_arm_ratio
    overturning_factor_of_safety = resisting_moment_knm_m / overturning_moment_knm_m
    sliding_factor_of_safety = (
        base_friction_coefficient * (wall_vertical_weight_kn_m - uplift_force_kn_m) / total_lateral_force_kn_m
    )
    bearing_pressure_kpa = wall_vertical_weight_kn_m / base_width_m
    bearing_utilization = bearing_pressure_kpa / allowable_bearing_kpa
    uplift_margin_kn_m = 0.9 * wall_vertical_weight_kn_m - uplift_force_kn_m

    pass_checks = [
        overturning_factor_of_safety >= minimum_overturning_fs,
        sliding_factor_of_safety >= minimum_sliding_fs,
        bearing_utilization <= 1.0,
        uplift_margin_kn_m >= 0.0,
    ]

    return {
        "active_earth_force_kn_m": round(active_earth_force_kn_m, 3),
        "surcharge_force_kn_m": round(surcharge_force_kn_m, 3),
        "hydrostatic_force_kn_m": round(hydrostatic_force_kn_m, 3),
        "total_lateral_force_kn_m": round(total_lateral_force_kn_m, 3),
        "overturning_moment_knm_m": round(overturning_moment_knm_m, 3),
        "resisting_moment_knm_m": round(resisting_moment_knm_m, 3),
        "overturning_factor_of_safety": round(overturning_factor_of_safety, 3),
        "sliding_factor_of_safety": round(sliding_factor_of_safety, 3),
        "bearing_pressure_kpa": round(bearing_pressure_kpa, 3),
        "bearing_utilization": round(bearing_utilization, 3),
        "uplift_margin_kn_m": round(uplift_margin_kn_m, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
