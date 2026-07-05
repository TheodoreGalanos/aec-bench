# ABOUTME: Computes SSC-11 buried pipeline groundwater and uplift package metrics.
# ABOUTME: Combines buoyancy, soil cover, exit gradient, pressure class, and pass checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    pipe_outer_diameter_m: float,
    pipe_wall_thickness_m: float,
    pipe_unit_weight_kn_m3: float,
    water_unit_weight_kn_m3: float,
    soil_unit_weight_kn_m3: float,
    soil_cover_m: float,
    trench_width_m: float,
    bedding_resistance_kn_m: float,
    groundwater_head_difference_m: float,
    seepage_path_length_m: float,
    critical_exit_gradient: float,
    required_uplift_factor_of_safety: float,
    required_exit_gradient_factor_of_safety: float,
    operating_pressure_kpa: float,
    pipe_pressure_class_kpa: float,
) -> dict[str, float]:
    """Compute deterministic SSC-11 buried pipeline uplift metrics."""
    _require_positive(
        pipe_outer_diameter_m=pipe_outer_diameter_m,
        pipe_wall_thickness_m=pipe_wall_thickness_m,
        pipe_unit_weight_kn_m3=pipe_unit_weight_kn_m3,
        water_unit_weight_kn_m3=water_unit_weight_kn_m3,
        soil_unit_weight_kn_m3=soil_unit_weight_kn_m3,
        soil_cover_m=soil_cover_m,
        trench_width_m=trench_width_m,
        seepage_path_length_m=seepage_path_length_m,
        critical_exit_gradient=critical_exit_gradient,
        required_uplift_factor_of_safety=required_uplift_factor_of_safety,
        required_exit_gradient_factor_of_safety=required_exit_gradient_factor_of_safety,
        operating_pressure_kpa=operating_pressure_kpa,
        pipe_pressure_class_kpa=pipe_pressure_class_kpa,
    )

    pipe_inner_diameter_m = pipe_outer_diameter_m - 2.0 * pipe_wall_thickness_m
    outer_area_m2 = math.pi / 4.0 * pipe_outer_diameter_m**2
    inner_area_m2 = math.pi / 4.0 * pipe_inner_diameter_m**2
    annulus_area_m2 = outer_area_m2 - inner_area_m2
    buoyant_uplift_kn_m = water_unit_weight_kn_m3 * outer_area_m2
    pipe_self_weight_kn_m = pipe_unit_weight_kn_m3 * annulus_area_m2
    contents_weight_kn_m = water_unit_weight_kn_m3 * inner_area_m2
    soil_overburden_kn_m = soil_unit_weight_kn_m3 * soil_cover_m * trench_width_m
    downward_resistance_kn_m = pipe_self_weight_kn_m + contents_weight_kn_m + soil_overburden_kn_m
    downward_resistance_kn_m += bedding_resistance_kn_m
    uplift_factor_of_safety = downward_resistance_kn_m / buoyant_uplift_kn_m
    exit_gradient = groundwater_head_difference_m / seepage_path_length_m
    exit_gradient_factor_of_safety = critical_exit_gradient / exit_gradient
    pressure_class_margin_kpa = pipe_pressure_class_kpa - operating_pressure_kpa

    pass_checks = [
        uplift_factor_of_safety >= required_uplift_factor_of_safety,
        exit_gradient_factor_of_safety >= required_exit_gradient_factor_of_safety,
        pressure_class_margin_kpa >= 0.0,
    ]

    return {
        "buoyant_uplift_kn_m": round(buoyant_uplift_kn_m, 3),
        "pipe_self_weight_kn_m": round(pipe_self_weight_kn_m, 3),
        "contents_weight_kn_m": round(contents_weight_kn_m, 3),
        "soil_overburden_kn_m": round(soil_overburden_kn_m, 3),
        "downward_resistance_kn_m": round(downward_resistance_kn_m, 3),
        "uplift_factor_of_safety": round(uplift_factor_of_safety, 3),
        "exit_gradient": round(exit_gradient, 3),
        "exit_gradient_factor_of_safety": round(exit_gradient_factor_of_safety, 3),
        "pressure_class_margin_kpa": round(pressure_class_margin_kpa, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
