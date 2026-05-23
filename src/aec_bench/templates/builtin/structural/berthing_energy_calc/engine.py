# ABOUTME: Berthing energy computation engine for marine structural checks.
# ABOUTME: Calculates characteristic and design berthing energy from vessel coefficients.


def _validate_inputs(
    vessel_displacement_t: float,
    approach_velocity_m_s: float,
    added_mass_coefficient: float,
    eccentricity_coefficient: float,
    berth_configuration_coefficient: float,
    softness_coefficient: float,
    safety_factor: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if vessel_displacement_t <= 0:
        msg = "vessel_displacement_t must be > 0"
        raise ValueError(msg)
    if approach_velocity_m_s <= 0:
        msg = "approach_velocity_m_s must be > 0"
        raise ValueError(msg)
    for name, value in {
        "added_mass_coefficient": added_mass_coefficient,
        "eccentricity_coefficient": eccentricity_coefficient,
        "berth_configuration_coefficient": berth_configuration_coefficient,
        "softness_coefficient": softness_coefficient,
        "safety_factor": safety_factor,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    vessel_displacement_t: float,
    approach_velocity_m_s: float,
    added_mass_coefficient: float,
    eccentricity_coefficient: float,
    berth_configuration_coefficient: float,
    softness_coefficient: float,
    safety_factor: float,
) -> dict[str, float]:
    """Compute characteristic and design berthing energy.

    Returns a dict with keys: kinetic_energy_knm, characteristic_energy_knm,
    design_energy_knm, coefficient_product.
    """
    _validate_inputs(
        vessel_displacement_t,
        approach_velocity_m_s,
        added_mass_coefficient,
        eccentricity_coefficient,
        berth_configuration_coefficient,
        softness_coefficient,
        safety_factor,
    )

    vessel_mass_kg = vessel_displacement_t * 1000.0
    kinetic_energy_knm = 0.5 * vessel_mass_kg * approach_velocity_m_s**2 / 1000.0
    coefficient_product = (
        added_mass_coefficient * eccentricity_coefficient * berth_configuration_coefficient * softness_coefficient
    )
    characteristic_energy = kinetic_energy_knm * coefficient_product
    design_energy = characteristic_energy * safety_factor

    return {
        "kinetic_energy_knm": round(kinetic_energy_knm, 2),
        "characteristic_energy_knm": round(characteristic_energy, 2),
        "design_energy_knm": round(design_energy, 2),
        "coefficient_product": round(coefficient_product, 2),
    }
