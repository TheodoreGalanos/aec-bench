# ABOUTME: Computes height-adjusted wind load on an overhead conductor span.
# ABOUTME: Uses terrain exponent, wind pressure, diameter, drag, and span length.

_TERRAIN_EXPONENTS = {
    "open": 0.16,
    "suburban": 0.22,
    "urban": 0.30,
}


def _validate_inputs(
    wind_pressure_pa: float,
    conductor_diameter_mm: float,
    span_length_m: float,
    drag_coefficient: float,
    terrain_category: str,
    height_above_ground_m: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "wind_pressure_pa": wind_pressure_pa,
        "conductor_diameter_mm": conductor_diameter_mm,
        "span_length_m": span_length_m,
        "drag_coefficient": drag_coefficient,
        "height_above_ground_m": height_above_ground_m,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)
    if terrain_category not in _TERRAIN_EXPONENTS:
        msg = f"terrain_category must be one of {sorted(_TERRAIN_EXPONENTS)}"
        raise ValueError(msg)


def compute(
    wind_pressure_pa: float,
    conductor_diameter_mm: float,
    span_length_m: float,
    drag_coefficient: float,
    terrain_category: str,
    height_above_ground_m: float,
) -> dict[str, float]:
    """Compute height-adjusted conductor wind load."""
    _validate_inputs(
        wind_pressure_pa,
        conductor_diameter_mm,
        span_length_m,
        drag_coefficient,
        terrain_category,
        height_above_ground_m,
    )

    terrain_exponent = _TERRAIN_EXPONENTS[terrain_category]
    height_factor = (height_above_ground_m / 10.0) ** terrain_exponent
    height_adjusted_wind_pressure_pa = wind_pressure_pa * height_factor
    conductor_diameter_m = conductor_diameter_mm / 1000.0
    wind_load_per_unit_length_n_m = height_adjusted_wind_pressure_pa * conductor_diameter_m * drag_coefficient
    transverse_wind_load_n = wind_load_per_unit_length_n_m * span_length_m

    return {
        "height_adjusted_wind_pressure_pa": round(height_adjusted_wind_pressure_pa, 2),
        "wind_load_per_unit_length_n_m": round(wind_load_per_unit_length_n_m, 2),
        "transverse_wind_load_n": round(transverse_wind_load_n, 2),
    }
