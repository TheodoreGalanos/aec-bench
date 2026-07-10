# ABOUTME: Computes SSC-19 structural fire and tenability metrics.
# ABOUTME: Combines HRR, fire energy, steel temperature, visibility, egress, and NAC checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    fire_growth_alpha_kw_s2: float,
    time_to_check_s: float,
    max_hrr_kw: float,
    fire_duration_min: float,
    structural_load_ratio: float,
    steel_temperature_c: float,
    visibility_constant: float,
    smoke_extinction_coefficient_m1: float,
    required_visibility_m: float,
    available_egress_width_m: float,
    occupant_load: float,
    egress_width_factor_m_per_10_persons: float,
    nac_current_a: float,
    nac_capacity_a: float,
) -> dict[str, float]:
    """Compute deterministic structural fire and tenability metrics."""
    _require_positive(
        fire_growth_alpha_kw_s2=fire_growth_alpha_kw_s2,
        time_to_check_s=time_to_check_s,
        max_hrr_kw=max_hrr_kw,
        fire_duration_min=fire_duration_min,
        structural_load_ratio=structural_load_ratio,
        visibility_constant=visibility_constant,
        smoke_extinction_coefficient_m1=smoke_extinction_coefficient_m1,
        required_visibility_m=required_visibility_m,
        available_egress_width_m=available_egress_width_m,
        occupant_load=occupant_load,
        egress_width_factor_m_per_10_persons=egress_width_factor_m_per_10_persons,
        nac_current_a=nac_current_a,
        nac_capacity_a=nac_capacity_a,
    )
    if structural_load_ratio >= 1.0:
        msg = "structural_load_ratio must be < 1"
        raise ValueError(msg)

    design_hrr_kw = min(fire_growth_alpha_kw_s2 * time_to_check_s**2.0, max_hrr_kw)
    fire_energy_mj = design_hrr_kw * fire_duration_min * 60.0 / 1000.0
    steel_critical_temp_c = 39.19 * math.log(1.0 / structural_load_ratio - 1.0) + 482.0
    steel_temperature_margin_c = steel_critical_temp_c - steel_temperature_c
    visibility_distance_m = visibility_constant / smoke_extinction_coefficient_m1
    visibility_margin_m = visibility_distance_m - required_visibility_m
    required_egress_width_m = occupant_load * egress_width_factor_m_per_10_persons / 10.0
    egress_width_margin_m = available_egress_width_m - required_egress_width_m
    nac_current_margin_a = nac_capacity_a - nac_current_a

    pass_checks = [
        steel_temperature_margin_c >= 0.0,
        visibility_margin_m >= 0.0,
        egress_width_margin_m >= 0.0,
        nac_current_margin_a >= 0.0,
    ]

    return {
        "design_hrr_kw": round(design_hrr_kw, 3),
        "fire_energy_mj": round(fire_energy_mj, 3),
        "steel_critical_temp_c": round(steel_critical_temp_c, 3),
        "steel_temperature_margin_c": round(steel_temperature_margin_c, 3),
        "visibility_distance_m": round(visibility_distance_m, 3),
        "visibility_margin_m": round(visibility_margin_m, 3),
        "required_egress_width_m": round(required_egress_width_m, 3),
        "egress_width_margin_m": round(egress_width_margin_m, 3),
        "nac_current_margin_a": round(nac_current_margin_a, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
