# ABOUTME: Computes SSC-04 wave runup, freeboard, and asset protection metrics.
# ABOUTME: Combines wave transform, breaking, runup, freeboard, and armor checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    offshore_wave_height_m: float,
    wave_period_s: float,
    shoaling_coefficient: float,
    nearshore_depth_m: float,
    breaker_index: float,
    runup_coefficient: float,
    slope_factor: float,
    stillwater_level_m: float,
    asset_platform_level_m: float,
    required_freeboard_m: float,
    selected_armor_mass_t: float,
    required_armor_mass_t: float,
) -> dict[str, float]:
    """Compute deterministic wave protection metrics for the SSC-04 source pack."""
    _require_positive(
        offshore_wave_height_m=offshore_wave_height_m,
        wave_period_s=wave_period_s,
        shoaling_coefficient=shoaling_coefficient,
        nearshore_depth_m=nearshore_depth_m,
        breaker_index=breaker_index,
        runup_coefficient=runup_coefficient,
        slope_factor=slope_factor,
        selected_armor_mass_t=selected_armor_mass_t,
        required_armor_mass_t=required_armor_mass_t,
    )

    deepwater_wavelength_m = 9.81 * wave_period_s**2 / (2.0 * math.pi)
    nearshore_wave_height_m = offshore_wave_height_m * shoaling_coefficient
    breaking_height_limit_m = breaker_index * nearshore_depth_m
    breaking_margin_m = breaking_height_limit_m - nearshore_wave_height_m
    runup_2_percent_m = runup_coefficient * nearshore_wave_height_m * slope_factor
    total_water_level_m = stillwater_level_m + runup_2_percent_m
    freeboard_margin_m = asset_platform_level_m - (total_water_level_m + required_freeboard_m)
    armor_stability_margin_t = selected_armor_mass_t - required_armor_mass_t

    pass_checks = [
        breaking_margin_m >= 0.0,
        freeboard_margin_m >= 0.0,
        armor_stability_margin_t >= 0.0,
    ]

    return {
        "deepwater_wavelength_m": round(deepwater_wavelength_m, 3),
        "shoaling_coefficient": round(shoaling_coefficient, 3),
        "nearshore_wave_height_m": round(nearshore_wave_height_m, 3),
        "breaking_height_limit_m": round(breaking_height_limit_m, 3),
        "breaking_margin_m": round(breaking_margin_m, 3),
        "runup_2_percent_m": round(runup_2_percent_m, 3),
        "total_water_level_m": round(total_water_level_m, 3),
        "freeboard_margin_m": round(freeboard_margin_m, 3),
        "armor_stability_margin_t": round(armor_stability_margin_t, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
