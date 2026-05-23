# ABOUTME: Water pipe pressure-loss computation engine.
# ABOUTME: Calculates Hazen-Williams friction loss, fitting loss, and total loss.

import math

_G = 9.81
_HAZEN_WILLIAMS_COEFFICIENT = 10.67


def _validate_inputs(
    flow_rate_l_s: float,
    pipe_internal_diameter_mm: float,
    pipe_length_m: float,
    hazen_williams_c: float,
    total_fitting_k: float,
    fluid_density_kg_m3: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if flow_rate_l_s <= 0:
        msg = "flow_rate_l_s must be > 0"
        raise ValueError(msg)
    if pipe_internal_diameter_mm <= 0:
        msg = "pipe_internal_diameter_mm must be > 0"
        raise ValueError(msg)
    if pipe_length_m <= 0:
        msg = "pipe_length_m must be > 0"
        raise ValueError(msg)
    if hazen_williams_c <= 0:
        msg = "hazen_williams_c must be > 0"
        raise ValueError(msg)
    if total_fitting_k < 0:
        msg = "total_fitting_k must be >= 0"
        raise ValueError(msg)
    if fluid_density_kg_m3 <= 0:
        msg = "fluid_density_kg_m3 must be > 0"
        raise ValueError(msg)


def compute(
    flow_rate_l_s: float,
    pipe_internal_diameter_mm: float,
    pipe_length_m: float,
    hazen_williams_c: float,
    total_fitting_k: float,
    fluid_density_kg_m3: float,
) -> dict[str, float]:
    """Compute water pipe pressure loss using Hazen-Williams and K losses.

    Returns a dict with keys: velocity_m_s, friction_loss_kpa,
    fitting_loss_kpa, total_pressure_loss_kpa.
    """
    _validate_inputs(
        flow_rate_l_s,
        pipe_internal_diameter_mm,
        pipe_length_m,
        hazen_williams_c,
        total_fitting_k,
        fluid_density_kg_m3,
    )

    flow_rate_m3_s = flow_rate_l_s / 1000.0
    diameter_m = pipe_internal_diameter_mm / 1000.0
    pipe_area_m2 = math.pi * diameter_m**2 / 4.0
    velocity_m_s = flow_rate_m3_s / pipe_area_m2
    friction_head_m = (
        _HAZEN_WILLIAMS_COEFFICIENT
        * pipe_length_m
        * flow_rate_m3_s**1.852
        / (hazen_williams_c**1.852 * diameter_m**4.871)
    )
    fitting_head_m = total_fitting_k * velocity_m_s**2 / (2.0 * _G)
    friction_loss_kpa = fluid_density_kg_m3 * _G * friction_head_m / 1000.0
    fitting_loss_kpa = fluid_density_kg_m3 * _G * fitting_head_m / 1000.0

    return {
        "velocity_m_s": round(velocity_m_s, 2),
        "friction_loss_kpa": round(friction_loss_kpa, 2),
        "fitting_loss_kpa": round(fitting_loss_kpa, 2),
        "total_pressure_loss_kpa": round(friction_loss_kpa + fitting_loss_kpa, 2),
    }
