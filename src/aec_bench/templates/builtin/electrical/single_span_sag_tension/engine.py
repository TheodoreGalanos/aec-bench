# ABOUTME: Single span sag-tension computation engine for overhead contact wires.
# ABOUTME: Calculates parabolic/catenary sag, wire length, and catenary constant.

import math

# Gravitational acceleration (m/s^2) for converting mass to weight.
_GRAVITY = 9.81


def _validate_inputs(
    span_length_m: float,
    wire_weight_per_m_n: float,
    horizontal_tension_n: float,
    wire_diameter_mm: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if span_length_m <= 0:
        msg = "span_length_m must be > 0"
        raise ValueError(msg)
    if wire_weight_per_m_n <= 0:
        msg = "wire_weight_per_m_n must be > 0"
        raise ValueError(msg)
    if horizontal_tension_n <= 0:
        msg = "horizontal_tension_n must be > 0"
        raise ValueError(msg)
    if wire_diameter_mm <= 0:
        msg = "wire_diameter_mm must be > 0"
        raise ValueError(msg)


def compute(
    span_length_m: float,
    wire_weight_per_m_n: float,
    horizontal_tension_n: float,
    wire_diameter_mm: float,
) -> dict[str, float]:
    """Compute sag, wire length, and catenary constant for a single level span.

    Uses both the parabolic approximation and exact catenary equations.
    The parabolic approximation is accurate when sag < ~5% of span length.

    Parabolic sag: S = w * L^2 / (8 * T)
    Catenary constant: C = T / w
    Exact catenary sag: S_cat = C * (cosh(L / (2 * C)) - 1)
    Wire length (catenary): l = 2 * C * sinh(L / (2 * C))

    Returns a dict with keys: sag_m, sag_catenary_m, wire_length_m, catenary_constant_m.
    """
    _validate_inputs(
        span_length_m,
        wire_weight_per_m_n,
        horizontal_tension_n,
        wire_diameter_mm,
    )

    w = wire_weight_per_m_n
    span = span_length_m
    t_h = horizontal_tension_n

    # Catenary constant: ratio of horizontal tension to weight per unit length
    catenary_constant = t_h / w

    # Parabolic approximation for sag (valid when sag/span < ~0.05)
    sag_parabolic = w * span**2 / (8.0 * t_h)

    # Exact catenary sag: S = C * (cosh(L / (2C)) - 1)
    half_span_over_c = span / (2.0 * catenary_constant)
    sag_catenary = catenary_constant * (math.cosh(half_span_over_c) - 1.0)

    # Exact wire length from catenary: l = 2C * sinh(L / (2C))
    wire_length = 2.0 * catenary_constant * math.sinh(half_span_over_c)

    return {
        "sag_m": round(sag_parabolic, 2),
        "sag_catenary_m": round(sag_catenary, 2),
        "wire_length_m": round(wire_length, 2),
        "catenary_constant_m": round(catenary_constant, 2),
    }
