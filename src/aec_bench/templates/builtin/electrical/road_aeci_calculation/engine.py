# ABOUTME: Computes road lighting annual energy and AECI.
# ABOUTME: Combines full-output hours with dimmed operation over lit area.


def _validate_inputs(
    system_power_w: float,
    full_output_hours_per_year: float,
    dimmed_hours_per_year: float,
    dimming_level_pct: float,
    illuminated_area_m2: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if system_power_w <= 0:
        msg = "system_power_w must be > 0"
        raise ValueError(msg)
    if illuminated_area_m2 <= 0:
        msg = "illuminated_area_m2 must be > 0"
        raise ValueError(msg)
    for name, value in {
        "full_output_hours_per_year": full_output_hours_per_year,
        "dimmed_hours_per_year": dimmed_hours_per_year,
    }.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)
    if not 0 <= dimming_level_pct <= 100:
        msg = "dimming_level_pct must be between 0 and 100"
        raise ValueError(msg)


def compute(
    system_power_w: float,
    full_output_hours_per_year: float,
    dimmed_hours_per_year: float,
    dimming_level_pct: float,
    illuminated_area_m2: float,
) -> dict[str, float]:
    """Compute road lighting annual energy and Annual Energy Consumption Index."""
    _validate_inputs(
        system_power_w,
        full_output_hours_per_year,
        dimmed_hours_per_year,
        dimming_level_pct,
        illuminated_area_m2,
    )

    dimming_fraction = dimming_level_pct / 100.0
    annual_energy_kwh = (
        system_power_w * full_output_hours_per_year + system_power_w * dimming_fraction * dimmed_hours_per_year
    ) / 1000.0
    aeci_kwh_per_m2_year = annual_energy_kwh / illuminated_area_m2

    return {
        "annual_energy_kwh": round(annual_energy_kwh, 2),
        "aeci_kwh_per_m2_year": round(aeci_kwh_per_m2_year, 2),
    }
