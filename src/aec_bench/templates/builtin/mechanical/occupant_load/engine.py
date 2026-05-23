# ABOUTME: Occupant load computation engine for prescriptive checks.
# ABOUTME: Calculates design occupancy from area and explicit occupant density.

import math


def _validate_inputs(floor_area_m2: float, area_per_occupant_m2: float) -> None:
    """Raise ValueError for invalid input parameters."""
    if floor_area_m2 <= 0:
        msg = "floor_area_m2 must be > 0"
        raise ValueError(msg)
    if area_per_occupant_m2 <= 0:
        msg = "area_per_occupant_m2 must be > 0"
        raise ValueError(msg)


def compute(floor_area_m2: float, area_per_occupant_m2: float) -> dict[str, float]:
    """Compute occupant load from floor area and density criterion.

    Returns a dict with keys: calculated_occupants, design_occupants,
    occupant_density_person_m2.
    """
    _validate_inputs(floor_area_m2, area_per_occupant_m2)

    calculated_occupants = floor_area_m2 / area_per_occupant_m2
    design_occupants = math.ceil(calculated_occupants)
    occupant_density = design_occupants / floor_area_m2

    return {
        "calculated_occupants": round(calculated_occupants, 2),
        "design_occupants": round(float(design_occupants), 2),
        "occupant_density_person_m2": round(occupant_density, 3),
    }
