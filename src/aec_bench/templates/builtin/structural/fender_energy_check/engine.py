# ABOUTME: Fender energy capacity computation engine for marine structural checks.
# ABOUTME: Applies correction factors and compares fender capacity with design energy.


def _validate_inputs(
    design_berthing_energy_knm: float,
    fender_rated_energy_knm: float,
    temperature_factor: float,
    velocity_factor: float,
    angular_factor: float,
    manufacturing_tolerance_factor: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if design_berthing_energy_knm <= 0:
        msg = "design_berthing_energy_knm must be > 0"
        raise ValueError(msg)
    if fender_rated_energy_knm <= 0:
        msg = "fender_rated_energy_knm must be > 0"
        raise ValueError(msg)
    for name, value in {
        "temperature_factor": temperature_factor,
        "velocity_factor": velocity_factor,
        "angular_factor": angular_factor,
        "manufacturing_tolerance_factor": manufacturing_tolerance_factor,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    design_berthing_energy_knm: float,
    fender_rated_energy_knm: float,
    temperature_factor: float,
    velocity_factor: float,
    angular_factor: float,
    manufacturing_tolerance_factor: float,
) -> dict[str, float]:
    """Compute corrected fender capacity and utilisation.

    Returns a dict with keys: correction_factor, corrected_capacity_knm,
    energy_utilisation_ratio, capacity_margin_knm.
    """
    _validate_inputs(
        design_berthing_energy_knm,
        fender_rated_energy_knm,
        temperature_factor,
        velocity_factor,
        angular_factor,
        manufacturing_tolerance_factor,
    )

    correction_factor = temperature_factor * velocity_factor * angular_factor * manufacturing_tolerance_factor
    corrected_capacity = fender_rated_energy_knm * correction_factor
    utilisation = design_berthing_energy_knm / corrected_capacity
    margin = corrected_capacity - design_berthing_energy_knm

    return {
        "correction_factor": round(correction_factor, 2),
        "corrected_capacity_knm": round(corrected_capacity, 2),
        "energy_utilisation_ratio": round(utilisation, 2),
        "capacity_margin_knm": round(margin, 2),
    }
