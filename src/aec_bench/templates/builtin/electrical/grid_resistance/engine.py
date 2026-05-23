# ABOUTME: IEEE 80-2013 substation grounding grid resistance computation engine.
# ABOUTME: Calculates grid resistance and ground potential rise using the simplified Schwarz equation.

import math


def _validate_inputs(
    soil_resistivity_ohm_m: float,
    grid_length_m: float,
    grid_width_m: float,
    total_conductor_length_m: float,
    burial_depth_m: float,
    grid_current_ka: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if soil_resistivity_ohm_m <= 0:
        msg = "soil_resistivity_ohm_m must be > 0"
        raise ValueError(msg)
    if grid_length_m <= 0:
        msg = "grid_length_m must be > 0"
        raise ValueError(msg)
    if grid_width_m <= 0:
        msg = "grid_width_m must be > 0"
        raise ValueError(msg)
    if total_conductor_length_m <= 0:
        msg = "total_conductor_length_m must be > 0"
        raise ValueError(msg)
    if burial_depth_m <= 0:
        msg = "burial_depth_m must be > 0"
        raise ValueError(msg)
    if grid_current_ka <= 0:
        msg = "grid_current_ka must be > 0"
        raise ValueError(msg)


def compute(
    soil_resistivity_ohm_m: float,
    grid_length_m: float,
    grid_width_m: float,
    total_conductor_length_m: float,
    burial_depth_m: float,
    grid_current_ka: float,
) -> dict[str, float]:
    """Compute grounding grid resistance and GPR per IEEE 80-2013 Equation 57.

    Uses the simplified Schwarz equation which combines the resistive
    properties of a buried conductor grid with area and depth effects.

    Returns a dict with keys: grid_area_m2, equivalent_radius_m,
    grid_resistance_ohm, ground_potential_rise_v.
    """
    _validate_inputs(
        soil_resistivity_ohm_m,
        grid_length_m,
        grid_width_m,
        total_conductor_length_m,
        burial_depth_m,
        grid_current_ka,
    )

    # Grid area from rectangular dimensions
    area = grid_length_m * grid_width_m

    # Equivalent circular radius: r = sqrt(A / pi)
    equivalent_radius = math.sqrt(area / math.pi)

    # IEEE 80-2013 Equation 57 (simplified Schwarz):
    # Rg = rho * [1/Lt + 1/sqrt(20*A) * (1 + 1/(1 + h*sqrt(20/A)))]
    # where rho = soil resistivity, Lt = total conductor length,
    # A = grid area, h = burial depth
    conductor_term = 1.0 / total_conductor_length_m
    area_factor = 1.0 / math.sqrt(20.0 * area)
    depth_factor = 1.0 + 1.0 / (1.0 + burial_depth_m * math.sqrt(20.0 / area))
    grid_resistance = soil_resistivity_ohm_m * (conductor_term + area_factor * depth_factor)

    # Ground potential rise: GPR = Ig * Rg
    # Grid current in kA, convert to A for voltage calculation
    grid_current_a = grid_current_ka * 1000.0
    gpr = grid_current_a * grid_resistance

    return {
        "grid_area_m2": round(area, 2),
        "equivalent_radius_m": round(equivalent_radius, 2),
        "grid_resistance_ohm": round(grid_resistance, 2),
        "ground_potential_rise_v": round(gpr, 2),
    }
