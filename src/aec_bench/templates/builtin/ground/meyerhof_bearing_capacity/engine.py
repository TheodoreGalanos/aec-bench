# ABOUTME: Meyerhof (1963) bearing capacity computation engine.
# ABOUTME: Calculates bearing capacity with shape, depth, and inclination factors.

import math
from typing import Literal


# Passive earth pressure coefficient
def _kp(phi_deg: float) -> float:
    """Rankine passive earth pressure coefficient: tan²(45 + phi/2)."""
    return math.tan(math.radians(45.0 + phi_deg / 2.0)) ** 2


# Unit weight of water in kN/m³
_GAMMA_W = 9.81


def _validate_inputs(
    cohesion_kpa: float,
    friction_angle_deg: float,
    unit_weight_kn_m3: float,
    footing_width_m: float,
    footing_length_m: float,
    embedment_depth_m: float,
    footing_shape: str,
    load_inclination_deg: float,
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
    if footing_length_m <= 0:
        msg = "footing_length_m must be > 0"
        raise ValueError(msg)
    if embedment_depth_m < 0:
        msg = "embedment_depth_m must be >= 0"
        raise ValueError(msg)
    if load_inclination_deg < 0:
        msg = "load_inclination_deg must be >= 0"
        raise ValueError(msg)
    if load_inclination_deg > 45:
        msg = "load_inclination_deg must be <= 45"
        raise ValueError(msg)
    if factor_of_safety <= 0:
        msg = "factor_of_safety must be > 0"
        raise ValueError(msg)
    valid_shapes = ("strip", "rectangular", "square", "circular")
    if footing_shape not in valid_shapes:
        msg = f"footing_shape must be one of {list(valid_shapes)}, got '{footing_shape}'"
        raise ValueError(msg)


def _bearing_capacity_factors(phi_deg: float) -> tuple[float, float, float]:
    """Return (Nc, Nq, Ngamma) using Meyerhof's analytical expressions.

    Nq = exp(pi * tan(phi)) * tan²(45 + phi/2)
    Nc = (Nq - 1) * cot(phi)          [Nc = 5.14 when phi = 0]
    Ngamma = (Nq - 1) * tan(1.4 * phi)
    """
    phi_rad = math.radians(phi_deg)

    # Nq
    nq = math.exp(math.pi * math.tan(phi_rad)) * math.tan(math.radians(45.0 + phi_deg / 2.0)) ** 2

    # Nc
    if phi_deg == 0.0:
        nc = 5.14
    else:
        nc = (nq - 1.0) / math.tan(phi_rad)

    # Ngamma (+ 0.0 avoids negative zero for phi=0)
    ngamma = (nq - 1.0) * math.tan(1.4 * phi_rad) + 0.0

    return nc, nq, ngamma


def _shape_factors(phi_deg: float, b_over_l: float) -> tuple[float, float, float]:
    """Return (sc, sq, sgamma) shape factors per Meyerhof (1963).

    sc = 1 + 0.2 * Kp * (B/L)          for any phi
    sq = sgamma = 1 + 0.1 * Kp * (B/L)  for phi > 10
    sq = sgamma = 1                      for phi <= 10
    """
    kp = _kp(phi_deg)
    sc = 1.0 + 0.2 * kp * b_over_l

    if phi_deg > 10.0:
        sq = 1.0 + 0.1 * kp * b_over_l
        sgamma = sq
    else:
        sq = 1.0
        sgamma = 1.0

    return sc, sq, sgamma


def _depth_factors(phi_deg: float, d_over_b: float) -> tuple[float, float, float]:
    """Return (dc, dq, dgamma) depth factors per Meyerhof (1963).

    dc = 1 + 0.2 * sqrt(Kp) * (Df/B)          for any phi
    dq = dgamma = 1 + 0.1 * sqrt(Kp) * (Df/B)  for phi > 10
    dq = dgamma = 1                              for phi <= 10
    """
    kp = _kp(phi_deg)
    sqrt_kp = math.sqrt(kp)
    dc = 1.0 + 0.2 * sqrt_kp * d_over_b

    if phi_deg > 10.0:
        dq = 1.0 + 0.1 * sqrt_kp * d_over_b
        dgamma = dq
    else:
        dq = 1.0
        dgamma = 1.0

    return dc, dq, dgamma


def _inclination_factors(phi_deg: float, theta_deg: float) -> tuple[float, float, float]:
    """Return (ic, iq, igamma) inclination factors per Meyerhof (1963).

    ic = iq = (1 - theta/90)²
    igamma = (1 - theta/phi)²           [igamma = 0 when phi = 0]
    """
    ic = (1.0 - theta_deg / 90.0) ** 2
    iq = ic

    if phi_deg == 0.0 or theta_deg >= phi_deg:
        igamma = 0.0
    else:
        igamma = (1.0 - theta_deg / phi_deg) ** 2

    return ic, iq, igamma


def compute(
    cohesion_kpa: float,
    friction_angle_deg: float,
    unit_weight_kn_m3: float,
    footing_width_m: float,
    footing_length_m: float,
    embedment_depth_m: float,
    footing_shape: Literal["strip", "rectangular", "square", "circular"],
    load_inclination_deg: float = 0.0,
    factor_of_safety: float = 3.0,
) -> dict[str, float]:
    """Compute ultimate and allowable bearing capacity using Meyerhof's 1963 method.

    Returns a dict with keys: nc, nq, ngamma, sc, sq, sgamma, dc, dq, dgamma,
    ic, iq, igamma, ultimate_bearing_capacity_kpa, allowable_bearing_capacity_kpa.
    """
    _validate_inputs(
        cohesion_kpa,
        friction_angle_deg,
        unit_weight_kn_m3,
        footing_width_m,
        footing_length_m,
        embedment_depth_m,
        footing_shape,
        load_inclination_deg,
        factor_of_safety,
    )

    # Bearing capacity factors
    nc, nq, ngamma = _bearing_capacity_factors(friction_angle_deg)

    # Ensure B <= L (B is the shorter dimension)
    b = min(footing_width_m, footing_length_m)
    length_m = max(footing_width_m, footing_length_m)

    # Geometric ratios
    b_over_l = b / length_m
    d_over_b = embedment_depth_m / b

    # Shape, depth, inclination factors
    sc, sq, sgamma = _shape_factors(friction_angle_deg, b_over_l)
    dc, dq, dgamma = _depth_factors(friction_angle_deg, d_over_b)
    ic, iq, igamma = _inclination_factors(friction_angle_deg, load_inclination_deg)

    # Overburden pressure
    q = unit_weight_kn_m3 * embedment_depth_m

    # Meyerhof general bearing capacity equation
    # qu = c * Nc * sc * dc * ic + q * Nq * sq * dq * iq + 0.5 * gamma * B * Ngamma * sgamma * dgamma * igamma
    qu = (
        cohesion_kpa * nc * sc * dc * ic
        + q * nq * sq * dq * iq
        + 0.5 * unit_weight_kn_m3 * b * ngamma * sgamma * dgamma * igamma
    )

    qa = qu / factor_of_safety

    return {
        "nc": round(nc, 2),
        "nq": round(nq, 2),
        "ngamma": round(ngamma, 2),
        "sc": round(sc, 2),
        "sq": round(sq, 2),
        "sgamma": round(sgamma, 2),
        "dc": round(dc, 2),
        "dq": round(dq, 2),
        "dgamma": round(dgamma, 2),
        "ic": round(ic, 2),
        "iq": round(iq, 2),
        "igamma": round(igamma, 2),
        "ultimate_bearing_capacity_kpa": round(qu, 2),
        "allowable_bearing_capacity_kpa": round(qa, 2),
    }
