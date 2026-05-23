# ABOUTME: Computes ice accretion and combined ice-wind loading on a conductor.
# ABOUTME: Uses annular ice area, ice density, wind pressure, and span length.

import math

_GRAVITY_M_S2 = 9.81


def _validate_inputs(
    conductor_diameter_mm: float,
    ice_thickness_mm: float,
    ice_density_kg_m3: float,
    wind_on_ice_pressure_pa: float,
    span_length_m: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "conductor_diameter_mm": conductor_diameter_mm,
        "ice_density_kg_m3": ice_density_kg_m3,
        "span_length_m": span_length_m,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)
    for name, value in {
        "ice_thickness_mm": ice_thickness_mm,
        "wind_on_ice_pressure_pa": wind_on_ice_pressure_pa,
    }.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)


def compute(
    conductor_diameter_mm: float,
    ice_thickness_mm: float,
    ice_density_kg_m3: float,
    wind_on_ice_pressure_pa: float,
    span_length_m: float,
) -> dict[str, float]:
    """Compute ice and wind loading on an iced conductor."""
    _validate_inputs(
        conductor_diameter_mm,
        ice_thickness_mm,
        ice_density_kg_m3,
        wind_on_ice_pressure_pa,
        span_length_m,
    )

    conductor_diameter_m = conductor_diameter_mm / 1000.0
    iced_conductor_diameter_m = (conductor_diameter_mm + 2.0 * ice_thickness_mm) / 1000.0
    ice_area_m2_per_m = math.pi * (iced_conductor_diameter_m**2 - conductor_diameter_m**2) / 4.0
    ice_weight_n_per_m = ice_area_m2_per_m * ice_density_kg_m3 * _GRAVITY_M_S2
    wind_on_ice_load_n_per_m = wind_on_ice_pressure_pa * iced_conductor_diameter_m
    combined_ice_wind_load_n_per_m = math.hypot(ice_weight_n_per_m, wind_on_ice_load_n_per_m)
    span_combined_load_n = combined_ice_wind_load_n_per_m * span_length_m

    return {
        "iced_conductor_diameter_mm": round(iced_conductor_diameter_m * 1000.0, 2),
        "ice_weight_n_per_m": round(ice_weight_n_per_m, 2),
        "total_vertical_load_n_per_m": round(ice_weight_n_per_m, 2),
        "wind_on_ice_load_n_per_m": round(wind_on_ice_load_n_per_m, 2),
        "combined_ice_wind_load_n_per_m": round(combined_ice_wind_load_n_per_m, 2),
        "span_combined_load_n": round(span_combined_load_n, 2),
    }
