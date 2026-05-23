# ABOUTME: Elastic immediate settlement computation engine.
# ABOUTME: Calculates settlement of shallow foundations using Boussinesq elastic theory.

from typing import Literal

# Influence factors for flexible foundations at the centre.
# For rectangular footings: I_f depends on L/B ratio.
# Source: Bowles (1996), Table 5-6 — flexible centre values.
_INFLUENCE_FACTORS: list[tuple[float, float]] = [
    (1.0, 1.12),  # square
    (1.5, 1.36),
    (2.0, 1.53),
    (3.0, 1.78),
    (5.0, 2.10),
    (10.0, 2.54),
    (100.0, 3.40),  # effectively strip
]

_LB_VALUES = [row[0] for row in _INFLUENCE_FACTORS]

# Rigid foundation correction: rigid I_f = 0.8 * flexible centre I_f
_RIGID_CORRECTION = 0.8

# Circular footing influence factor (flexible centre)
_CIRCULAR_IF = 1.0


def _interpolate_influence_factor(l_over_b: float) -> float:
    """Linearly interpolate the influence factor for a given L/B ratio."""
    l_over_b = max(1.0, min(100.0, l_over_b))

    for i in range(len(_INFLUENCE_FACTORS) - 1):
        lb_lo = _INFLUENCE_FACTORS[i][0]
        lb_hi = _INFLUENCE_FACTORS[i + 1][0]
        if lb_lo <= l_over_b <= lb_hi:
            if_lo = _INFLUENCE_FACTORS[i][1]
            if_hi = _INFLUENCE_FACTORS[i + 1][1]
            fraction = (l_over_b - lb_lo) / (lb_hi - lb_lo)
            return if_lo + fraction * (if_hi - if_lo)

    return _INFLUENCE_FACTORS[-1][1]


def _validate_inputs(
    applied_pressure_kpa: float,
    footing_width_m: float,
    footing_length_m: float,
    elastic_modulus_mpa: float,
    poisson_ratio: float,
    footing_shape: str,
    foundation_rigidity: str,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if applied_pressure_kpa <= 0:
        msg = "applied_pressure_kpa must be > 0"
        raise ValueError(msg)
    if footing_width_m <= 0:
        msg = "footing_width_m must be > 0"
        raise ValueError(msg)
    if footing_length_m <= 0:
        msg = "footing_length_m must be > 0"
        raise ValueError(msg)
    if elastic_modulus_mpa <= 0:
        msg = "elastic_modulus_mpa must be > 0"
        raise ValueError(msg)
    if poisson_ratio < 0 or poisson_ratio >= 0.5:
        msg = "poisson_ratio must be >= 0 and < 0.5"
        raise ValueError(msg)
    valid_shapes = ("square", "rectangular", "circular")
    if footing_shape not in valid_shapes:
        msg = f"footing_shape must be one of {list(valid_shapes)}, got '{footing_shape}'"
        raise ValueError(msg)
    valid_rigidity = ("flexible", "rigid")
    if foundation_rigidity not in valid_rigidity:
        msg = f"foundation_rigidity must be one of {list(valid_rigidity)}, got '{foundation_rigidity}'"
        raise ValueError(msg)


def compute(
    applied_pressure_kpa: float,
    footing_width_m: float,
    footing_length_m: float,
    elastic_modulus_mpa: float,
    poisson_ratio: float,
    footing_shape: Literal["square", "rectangular", "circular"],
    foundation_rigidity: Literal["flexible", "rigid"] = "flexible",
) -> dict[str, float]:
    """Compute elastic immediate settlement using Boussinesq theory.

    Si = q * B * (1 - nu^2) / E * I_f

    where I_f is the influence factor for the footing shape and rigidity.
    For rigid foundations, I_f is multiplied by 0.8.

    Returns a dict with keys: influence_factor, settlement_mm.
    """
    _validate_inputs(
        applied_pressure_kpa,
        footing_width_m,
        footing_length_m,
        elastic_modulus_mpa,
        poisson_ratio,
        footing_shape,
        foundation_rigidity,
    )

    # Determine influence factor based on shape
    b = min(footing_width_m, footing_length_m)
    length_m = max(footing_width_m, footing_length_m)

    if footing_shape == "circular":
        i_f = _CIRCULAR_IF
    else:
        l_over_b = length_m / b
        i_f = _interpolate_influence_factor(l_over_b)

    # Apply rigid correction
    if foundation_rigidity == "rigid":
        i_f *= _RIGID_CORRECTION

    # Elastic settlement formula
    # Si = q * B * (1 - nu^2) / E * I_f
    # Convert E from MPa to kPa for consistent units
    e_kpa = elastic_modulus_mpa * 1000.0
    settlement_m = (applied_pressure_kpa * b * (1.0 - poisson_ratio**2) / e_kpa) * i_f
    settlement_mm = settlement_m * 1000.0

    return {
        "influence_factor": round(i_f, 2),
        "settlement_mm": round(settlement_mm, 2),
    }
