# ABOUTME: Rail cant (superelevation) computation engine for curved track sections.
# ABOUTME: Implements ARTC ETS-05-00 / AREMA equilibrium cant E_eq = 11.82 * V^2 / R.

import math
from typing import Literal

# Standard gauge rail-centre-to-centre distance used to derive the cant constant.
# The constant 11.82 = S / (g * SU^2) where S ~ 1500 mm, g = 9.80665, SU = 3.6.
# This is a conventional value used across all standard-gauge networks (ARTC, Network
# Rail, etc.) regardless of minor gauge variations (1432-1438 mm).
_CANT_CONSTANT_STANDARD: float = 11.82
_CANT_CONSTANT_NARROW: float = 8.90

_GAUGE_CONSTANTS: dict[str, float] = {
    "standard": _CANT_CONSTANT_STANDARD,
    "narrow": _CANT_CONSTANT_NARROW,
}

# Maximum actual cant limits by gauge type (mm).
# Standard gauge: 150 mm (ARTC ETS-05-00 typical limit).
# Narrow gauge: 100 mm (QR typical limit for 1067 mm gauge).
_MAX_CANT_MM: dict[str, float] = {
    "standard": 150.0,
    "narrow": 100.0,
}


def _validate_inputs(
    design_speed_km_h: float,
    curve_radius_m: float,
    actual_cant_mm: float,
    max_cant_deficiency_mm: float,
    gauge_type: str,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if design_speed_km_h <= 0:
        msg = "design_speed_km_h must be > 0"
        raise ValueError(msg)
    if curve_radius_m <= 0:
        msg = "curve_radius_m must be > 0"
        raise ValueError(msg)
    if actual_cant_mm < 0:
        msg = "actual_cant_mm must be >= 0"
        raise ValueError(msg)
    if max_cant_deficiency_mm < 0:
        msg = "max_cant_deficiency_mm must be >= 0"
        raise ValueError(msg)
    if gauge_type not in _GAUGE_CONSTANTS:
        msg = f"gauge_type must be one of {list(_GAUGE_CONSTANTS.keys())}, got '{gauge_type}'"
        raise ValueError(msg)
    max_cant = _MAX_CANT_MM[gauge_type]
    if actual_cant_mm > max_cant:
        msg = f"actual_cant_mm must be <= {max_cant} for {gauge_type} gauge"
        raise ValueError(msg)


def _equilibrium_cant(
    design_speed_km_h: float,
    curve_radius_m: float,
    cant_constant: float,
) -> float:
    """Calculate equilibrium cant E_eq in mm.

    E_eq = cant_constant * V^2 / R
    where V is in km/h, R is in metres, and the result is in mm.
    """
    return cant_constant * (design_speed_km_h**2) / curve_radius_m


def _maximum_speed(
    curve_radius_m: float,
    actual_cant_mm: float,
    max_cant_deficiency_mm: float,
    cant_constant: float,
) -> float:
    """Calculate maximum allowable speed on curve in km/h.

    V_max = sqrt(R * (E_a + C_d_max) / cant_constant)
    where E_a is actual cant (mm), C_d_max is maximum cant deficiency (mm),
    R is radius (m), and the result is in km/h.
    """
    return math.sqrt(curve_radius_m * (actual_cant_mm + max_cant_deficiency_mm) / cant_constant)


def compute(
    design_speed_km_h: float,
    curve_radius_m: float,
    actual_cant_mm: float,
    max_cant_deficiency_mm: float,
    gauge_type: Literal["standard", "narrow"] = "standard",
) -> dict[str, float]:
    """Compute rail cant parameters for a curved track section.

    Returns a dict with keys: equilibrium_cant_mm, cant_deficiency_mm,
    maximum_speed_km_h.
    """
    _validate_inputs(
        design_speed_km_h,
        curve_radius_m,
        actual_cant_mm,
        max_cant_deficiency_mm,
        gauge_type,
    )

    cant_constant = _GAUGE_CONSTANTS[gauge_type]

    # Equilibrium cant for the design speed and radius
    e_eq = _equilibrium_cant(design_speed_km_h, curve_radius_m, cant_constant)

    # Cant deficiency: difference between what equilibrium requires and what is applied
    c_d = e_eq - actual_cant_mm

    # Maximum allowable speed given actual cant plus maximum tolerable deficiency
    v_max = _maximum_speed(curve_radius_m, actual_cant_mm, max_cant_deficiency_mm, cant_constant)

    return {
        "equilibrium_cant_mm": round(e_eq, 2),
        "cant_deficiency_mm": round(c_d, 2),
        "maximum_speed_km_h": round(v_max, 2),
    }
