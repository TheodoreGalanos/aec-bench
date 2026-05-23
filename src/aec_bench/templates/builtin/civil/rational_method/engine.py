# ABOUTME: Rational method peak runoff computation engine.
# ABOUTME: Calculates peak discharge Q = C * I * A / 360 per ARR and HEC-22 standards.


def _validate_inputs(
    runoff_coefficient: float,
    rainfall_intensity_mm_hr: float,
    catchment_area_ha: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if runoff_coefficient < 0.0:
        msg = "runoff_coefficient must be >= 0"
        raise ValueError(msg)
    if runoff_coefficient > 1.0:
        msg = "runoff_coefficient must be <= 1.0"
        raise ValueError(msg)
    if rainfall_intensity_mm_hr <= 0:
        msg = "rainfall_intensity_mm_hr must be > 0"
        raise ValueError(msg)
    if catchment_area_ha <= 0:
        msg = "catchment_area_ha must be > 0"
        raise ValueError(msg)
    if catchment_area_ha > 80:
        msg = "catchment_area_ha must be <= 80 (rational method limit)"
        raise ValueError(msg)


def compute(
    runoff_coefficient: float,
    rainfall_intensity_mm_hr: float,
    catchment_area_ha: float,
) -> dict[str, float]:
    """Compute peak runoff using the rational method Q = C * I * A / 360.

    SI convention: Q in m³/s when I is in mm/hr and A is in hectares.
    The divisor 360 is the unit conversion factor (1 ha = 10 000 m²,
    1 hr = 3 600 s, so 10 000 / 3 600 ≈ 2.778, and 1000 / 2.778 ≈ 360).

    Returns a dict with keys: peak_runoff_m3_s, peak_runoff_l_s.
    """
    _validate_inputs(runoff_coefficient, rainfall_intensity_mm_hr, catchment_area_ha)

    # Rational method equation (SI units)
    peak_runoff_m3_s = runoff_coefficient * rainfall_intensity_mm_hr * catchment_area_ha / 360.0

    # Convert to litres per second (1 m³/s = 1000 L/s)
    peak_runoff_l_s = peak_runoff_m3_s * 1000.0

    return {
        "peak_runoff_m3_s": round(peak_runoff_m3_s, 2),
        "peak_runoff_l_s": round(peak_runoff_l_s, 2),
    }
