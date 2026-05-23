# ABOUTME: Terzaghi (1943) bearing capacity computation engine.
# ABOUTME: Calculates bearing capacity for strip, square, and circular footings.

import math
from typing import Literal

# Terzaghi bearing capacity factor lookup table.
# Each row: (phi_deg, Nc, Nq, Ngamma)
_FACTOR_TABLE: list[tuple[float, float, float, float]] = [
    (0, 5.7, 1.0, 0.0),
    (5, 7.3, 1.6, 0.5),
    (10, 9.6, 2.7, 1.2),
    (15, 12.9, 4.4, 2.5),
    (20, 17.7, 7.4, 5.0),
    (25, 25.1, 12.7, 9.7),
    (30, 37.2, 22.5, 19.7),
    (34, 52.6, 36.5, 36.0),
    (35, 57.8, 41.4, 42.4),
    (40, 95.7, 81.3, 100.4),
    (45, 172.3, 173.3, 297.5),
    (48, 258.3, 287.9, 780.1),
    (50, 347.5, 415.1, 1153.2),
]

# Sorted phi values for binary search.
_PHI_VALUES = [row[0] for row in _FACTOR_TABLE]

# Unit weight of water in kN/m3.
_GAMMA_W = 9.81

# Valid footing shapes and their (sc, sg_coeff) factors.
# sc multiplies Nc term; sg_coeff replaces the 0.5 in the Ngamma term.
_SHAPE_FACTORS: dict[str, tuple[float, float]] = {
    "strip": (1.0, 0.5),
    "square": (1.3, 0.4),
    "circular": (1.3, 0.3),
}


def _interpolate_factor(phi_deg: float, column_index: int) -> float:
    """Linearly interpolate a bearing capacity factor from the lookup table.

    column_index: 1=Nc, 2=Nq, 3=Ngamma
    """
    # Clamp to [0, 50]
    phi_deg = max(0.0, min(50.0, phi_deg))

    # Find bracketing rows
    for i in range(len(_FACTOR_TABLE) - 1):
        phi_lo = _FACTOR_TABLE[i][0]
        phi_hi = _FACTOR_TABLE[i + 1][0]
        if phi_lo <= phi_deg <= phi_hi:
            val_lo = _FACTOR_TABLE[i][column_index]
            val_hi = _FACTOR_TABLE[i + 1][column_index]
            if phi_hi == phi_lo:
                return val_lo
            fraction = (phi_deg - phi_lo) / (phi_hi - phi_lo)
            return val_lo + fraction * (val_hi - val_lo)

    # Exact match at last row
    return _FACTOR_TABLE[-1][column_index]


def _bearing_capacity_factors(phi_deg: float) -> tuple[float, float, float]:
    """Return (Nc, Nq, Ngamma) for a given friction angle using table interpolation.

    Nc and Nq use the analytical Terzaghi formulae with special cases for phi=0.
    Ngamma uses linear interpolation from the lookup table (no closed-form exists).
    """
    phi_rad = math.radians(phi_deg)

    # Nq
    if phi_deg == 0.0:
        nq = 1.0
    else:
        exponent = 2.0 * (3.0 * math.pi / 4.0 - phi_rad / 2.0) * math.tan(phi_rad)
        denominator = 2.0 * math.cos(math.radians(45.0) + phi_rad / 2.0) ** 2
        nq = math.exp(exponent) / denominator

    # Nc
    if phi_deg == 0.0:
        nc = 5.7
    else:
        nc = (1.0 / math.tan(phi_rad)) * (nq - 1.0)

    # Ngamma from lookup table with linear interpolation
    ngamma = _interpolate_factor(phi_deg, 3)

    return nc, nq, ngamma


def _validate_inputs(
    cohesion_kpa: float,
    friction_angle_deg: float,
    unit_weight_kn_m3: float,
    footing_width_m: float,
    embedment_depth_m: float,
    footing_shape: str,
    factor_of_safety: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if cohesion_kpa < 0:
        msg = "cohesion_kpa must be >= 0"
        raise ValueError(msg)
    if friction_angle_deg < 0:
        msg = "friction_angle_deg must be >= 0"
        raise ValueError(msg)
    if friction_angle_deg > 50:
        msg = "friction_angle_deg must be <= 50"
        raise ValueError(msg)
    if unit_weight_kn_m3 <= 0:
        msg = "unit_weight_kn_m3 must be > 0"
        raise ValueError(msg)
    if footing_width_m <= 0:
        msg = "footing_width_m must be > 0"
        raise ValueError(msg)
    if embedment_depth_m < 0:
        msg = "embedment_depth_m must be >= 0"
        raise ValueError(msg)
    if factor_of_safety <= 0:
        msg = "factor_of_safety must be > 0"
        raise ValueError(msg)
    if footing_shape not in _SHAPE_FACTORS:
        msg = f"footing_shape must be one of {list(_SHAPE_FACTORS.keys())}, got '{footing_shape}'"
        raise ValueError(msg)


def _water_table_correction(
    gamma: float,
    embedment_depth_m: float,
    footing_width_m: float,
    water_table_depth_m: float,
) -> tuple[float, float]:
    """Calculate overburden pressure (q) and effective unit weight (gamma_eff).

    Returns (q_kpa, gamma_eff_kn_m3) corrected for water table position.
    Three cases based on water table depth relative to foundation level.
    """
    dw = water_table_depth_m
    df = embedment_depth_m
    b = footing_width_m

    if dw <= df:
        # Case 1: Water at or above foundation level
        # Overburden uses full weight above water table, buoyant weight below
        q = gamma * dw + (gamma - _GAMMA_W) * (df - dw)
        # Soil below foundation is fully submerged
        gamma_eff = gamma - _GAMMA_W
    elif dw < df + b:
        # Case 2: Water between foundation level and Df+B
        # Overburden is fully above water table
        q = gamma * df
        # Interpolated effective unit weight
        gamma_eff = (gamma - _GAMMA_W) + ((dw - df) / b) * _GAMMA_W
    else:
        # Case 3: Water below failure zone — no correction
        q = gamma * df
        gamma_eff = gamma

    return q, gamma_eff


def compute(
    cohesion_kpa: float,
    friction_angle_deg: float,
    unit_weight_kn_m3: float,
    footing_width_m: float,
    embedment_depth_m: float,
    footing_shape: Literal["strip", "square", "circular"],
    water_table_depth_m: float = 100.0,
    factor_of_safety: float = 3.0,
) -> dict[str, float]:
    """Compute ultimate and allowable bearing capacity using Terzaghi's 1943 equation.

    Returns a dict with keys: nc, nq, ngamma, ultimate_bearing_capacity_kpa,
    allowable_bearing_capacity_kpa.
    """
    _validate_inputs(
        cohesion_kpa,
        friction_angle_deg,
        unit_weight_kn_m3,
        footing_width_m,
        embedment_depth_m,
        footing_shape,
        factor_of_safety,
    )

    nc, nq, ngamma = _bearing_capacity_factors(friction_angle_deg)
    sc, sg = _SHAPE_FACTORS[footing_shape]

    q, gamma_eff = _water_table_correction(
        unit_weight_kn_m3,
        embedment_depth_m,
        footing_width_m,
        water_table_depth_m,
    )

    # Terzaghi bearing capacity equation
    # qu = c' * Nc * sc + q * Nq + gamma_eff * B * sg * Ngamma
    qu = cohesion_kpa * nc * sc + q * nq + gamma_eff * footing_width_m * sg * ngamma
    qa = qu / factor_of_safety

    return {
        "nc": round(nc, 2),
        "nq": round(nq, 2),
        "ngamma": round(ngamma, 2),
        "ultimate_bearing_capacity_kpa": round(qu, 2),
        "allowable_bearing_capacity_kpa": round(qa, 2),
    }
