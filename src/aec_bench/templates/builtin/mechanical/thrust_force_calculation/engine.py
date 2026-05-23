# ABOUTME: Thrust force computation engine for pressurised pipe bends.
# ABOUTME: Calculates bend thrust from pressure, diameter, and deflection angle.

import math


def _validate_inputs(
    internal_pressure_kpa: float,
    pipe_internal_diameter_mm: float,
    bend_angle_deg: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if internal_pressure_kpa < 0:
        msg = "internal_pressure_kpa must be >= 0"
        raise ValueError(msg)
    if pipe_internal_diameter_mm <= 0:
        msg = "pipe_internal_diameter_mm must be > 0"
        raise ValueError(msg)
    if not 0 <= bend_angle_deg <= 180:
        msg = "bend_angle_deg must be between 0 and 180"
        raise ValueError(msg)


def compute(
    internal_pressure_kpa: float,
    pipe_internal_diameter_mm: float,
    bend_angle_deg: float,
) -> dict[str, float]:
    """Compute pipe bend thrust force.

    Returns a dict with keys: pipe_area_m2, pressure_force_kn,
    bend_thrust_force_kn.
    """
    _validate_inputs(internal_pressure_kpa, pipe_internal_diameter_mm, bend_angle_deg)

    pipe_area = math.pi / 4.0 * (pipe_internal_diameter_mm / 1000.0) ** 2
    pressure_force = internal_pressure_kpa * pipe_area
    bend_thrust = 2.0 * pressure_force * math.sin(math.radians(bend_angle_deg) / 2.0)

    return {
        "pipe_area_m2": round(pipe_area, 3),
        "pressure_force_kn": round(pressure_force, 2),
        "bend_thrust_force_kn": round(bend_thrust, 2),
    }
