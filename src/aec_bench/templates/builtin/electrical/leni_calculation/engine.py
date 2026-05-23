# ABOUTME: Computes interior lighting LENI and savings against a reference.
# ABOUTME: Applies control and daylight factors to installed lighting energy.


def _validate_inputs(
    installed_lighting_power_w: float,
    annual_operating_hours: float,
    control_factor: float,
    daylight_factor: float,
    zone_area_m2: float,
    reference_leni_kwh_m2_year: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "installed_lighting_power_w": installed_lighting_power_w,
        "annual_operating_hours": annual_operating_hours,
        "zone_area_m2": zone_area_m2,
        "reference_leni_kwh_m2_year": reference_leni_kwh_m2_year,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)
    for name, value in {
        "control_factor": control_factor,
        "daylight_factor": daylight_factor,
    }.items():
        if not 0 <= value <= 1:
            msg = f"{name} must be between 0 and 1"
            raise ValueError(msg)


def compute(
    installed_lighting_power_w: float,
    annual_operating_hours: float,
    control_factor: float,
    daylight_factor: float,
    zone_area_m2: float,
    reference_leni_kwh_m2_year: float,
) -> dict[str, float]:
    """Compute LENI and reference savings for an interior lighting zone."""
    _validate_inputs(
        installed_lighting_power_w,
        annual_operating_hours,
        control_factor,
        daylight_factor,
        zone_area_m2,
        reference_leni_kwh_m2_year,
    )

    annual_lighting_energy_kwh = (
        installed_lighting_power_w * annual_operating_hours * control_factor * daylight_factor
    ) / 1000.0
    leni_kwh_m2_year = annual_lighting_energy_kwh / zone_area_m2
    reference_saving_pct = (reference_leni_kwh_m2_year - leni_kwh_m2_year) / reference_leni_kwh_m2_year * 100.0

    return {
        "annual_lighting_energy_kwh": round(annual_lighting_energy_kwh, 2),
        "leni_kwh_m2_year": round(leni_kwh_m2_year, 2),
        "reference_saving_pct": round(reference_saving_pct, 2),
    }
