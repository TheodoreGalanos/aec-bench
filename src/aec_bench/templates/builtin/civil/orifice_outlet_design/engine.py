# ABOUTME: Orifice outlet sizing computation engine for detention basins.
# ABOUTME: Calculates required orifice area, diameter, and discharge velocity from Q = Cd * A * sqrt(2gH).

import math

# Gravitational acceleration (m/s2).
_G = 9.81


def _validate_inputs(
    design_flow_m3_s: float,
    head_above_centreline_m: float,
    discharge_coefficient: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if design_flow_m3_s <= 0:
        msg = "design_flow_m3_s must be > 0"
        raise ValueError(msg)
    if head_above_centreline_m <= 0:
        msg = "head_above_centreline_m must be > 0"
        raise ValueError(msg)
    if discharge_coefficient <= 0:
        msg = "discharge_coefficient must be > 0"
        raise ValueError(msg)
    if discharge_coefficient > 1.0:
        msg = "discharge_coefficient must be <= 1.0"
        raise ValueError(msg)


def compute(
    design_flow_m3_s: float,
    head_above_centreline_m: float,
    discharge_coefficient: float = 0.61,
) -> dict[str, float]:
    """Size an orifice outlet for a detention basin.

    Uses the orifice equation Q = Cd * A * sqrt(2 * g * H) rearranged to
    solve for area, diameter, and discharge velocity.

    Returns a dict with keys: required_orifice_area_m2, orifice_diameter_mm,
    discharge_velocity_m_s.
    """
    _validate_inputs(design_flow_m3_s, head_above_centreline_m, discharge_coefficient)

    q = design_flow_m3_s
    h = head_above_centreline_m
    cd = discharge_coefficient

    # Velocity through the orifice: v = sqrt(2 * g * H)
    velocity = math.sqrt(2.0 * _G * h)

    # Required orifice area: A = Q / (Cd * sqrt(2 * g * H))
    area = q / (cd * velocity)

    # Orifice diameter from area: D = sqrt(4 * A / pi), converted to mm
    diameter_m = math.sqrt(4.0 * area / math.pi)
    diameter_mm = diameter_m * 1000.0

    return {
        "required_orifice_area_m2": round(area, 2),
        "orifice_diameter_mm": round(diameter_mm, 2),
        "discharge_velocity_m_s": round(velocity, 2),
    }
