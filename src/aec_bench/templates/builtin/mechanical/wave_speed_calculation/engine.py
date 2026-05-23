# ABOUTME: Pressure wave speed computation engine for water hammer screening checks.
# ABOUTME: Combines fluid compressibility and pipe-wall flexibility terms.

import math
from typing import Literal

_RESTRAINT_FACTORS: dict[str, float] = {
    "fully_restrained": 1.0,
    "anchored_with_expansion": 0.85,
    "unrestrained": 0.7,
}


def _validate_inputs(
    fluid_bulk_modulus_gpa: float,
    fluid_density_kg_m3: float,
    pipe_elastic_modulus_gpa: float,
    pipe_diameter_mm: float,
    pipe_wall_thickness_mm: float,
    restraint_condition: str,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if fluid_bulk_modulus_gpa <= 0:
        msg = "fluid_bulk_modulus_gpa must be > 0"
        raise ValueError(msg)
    if fluid_density_kg_m3 <= 0:
        msg = "fluid_density_kg_m3 must be > 0"
        raise ValueError(msg)
    if pipe_elastic_modulus_gpa <= 0:
        msg = "pipe_elastic_modulus_gpa must be > 0"
        raise ValueError(msg)
    if pipe_diameter_mm <= 0:
        msg = "pipe_diameter_mm must be > 0"
        raise ValueError(msg)
    if pipe_wall_thickness_mm <= 0:
        msg = "pipe_wall_thickness_mm must be > 0"
        raise ValueError(msg)
    if restraint_condition not in _RESTRAINT_FACTORS:
        msg = f"restraint_condition must be one of {list(_RESTRAINT_FACTORS.keys())}"
        raise ValueError(msg)


def compute(
    fluid_bulk_modulus_gpa: float,
    fluid_density_kg_m3: float,
    pipe_elastic_modulus_gpa: float,
    pipe_diameter_mm: float,
    pipe_wall_thickness_mm: float,
    restraint_condition: Literal["fully_restrained", "anchored_with_expansion", "unrestrained"],
) -> dict[str, float]:
    """Compute pressure wave speed in an elastic pipe.

    Returns a dict with keys: fluid_only_wave_speed_m_s, flexibility_factor,
    wave_speed_m_s, pipe_flexibility_ratio.
    """
    _validate_inputs(
        fluid_bulk_modulus_gpa,
        fluid_density_kg_m3,
        pipe_elastic_modulus_gpa,
        pipe_diameter_mm,
        pipe_wall_thickness_mm,
        restraint_condition,
    )

    bulk_modulus_pa = fluid_bulk_modulus_gpa * 1.0e9
    elastic_modulus_pa = pipe_elastic_modulus_gpa * 1.0e9
    diameter_m = pipe_diameter_mm / 1000.0
    wall_thickness_m = pipe_wall_thickness_mm / 1000.0
    restraint_factor = _RESTRAINT_FACTORS[restraint_condition]

    fluid_only_speed = math.sqrt(bulk_modulus_pa / fluid_density_kg_m3)
    pipe_flexibility_ratio = bulk_modulus_pa * diameter_m / (elastic_modulus_pa * wall_thickness_m * restraint_factor)
    flexibility_factor = math.sqrt(1.0 + pipe_flexibility_ratio)
    wave_speed = fluid_only_speed / flexibility_factor

    return {
        "fluid_only_wave_speed_m_s": round(fluid_only_speed, 2),
        "flexibility_factor": round(flexibility_factor, 2),
        "wave_speed_m_s": round(wave_speed, 2),
        "pipe_flexibility_ratio": round(pipe_flexibility_ratio, 2),
    }
