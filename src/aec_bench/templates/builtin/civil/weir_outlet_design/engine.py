# ABOUTME: Sharp-crested rectangular weir sizing engine for detention basin spillways.
# ABOUTME: Uses the Francis formula Q = Cw(L - 0.1nH)H^1.5 to solve for weir length.

import math

# Francis weir coefficient for sharp-crested rectangular weir (SI units).
# Incorporates Cd ≈ 0.62 and √(2g) into a single constant: Cd × √(2g) ≈ 1.84.
_FRANCIS_COEFFICIENT_SUPPRESSED = 1.84


def _validate_inputs(
    design_flow_m3_s: float,
    head_over_weir_m: float,
    discharge_coefficient: float,
    number_of_contractions: int,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if design_flow_m3_s <= 0:
        msg = "design_flow_m3_s must be > 0"
        raise ValueError(msg)
    if head_over_weir_m <= 0:
        msg = "head_over_weir_m must be > 0"
        raise ValueError(msg)
    if discharge_coefficient <= 0:
        msg = "discharge_coefficient must be > 0"
        raise ValueError(msg)
    if discharge_coefficient > 1.0:
        msg = "discharge_coefficient must be <= 1.0"
        raise ValueError(msg)
    if number_of_contractions not in (0, 1, 2):
        msg = "number_of_contractions must be 0, 1, or 2"
        raise ValueError(msg)


def _effective_weir_coefficient(discharge_coefficient: float) -> float:
    """Derive the weir coefficient from Cd using Cw = Cd × √(2g).

    The Francis formula lumps Cd and √(2g) into a single coefficient.
    For Cd = 0.62, Cw ≈ 1.84 × (Cd / 0.62), scaling linearly.
    More precisely: Cw = Cd × √(2 × 9.81).
    """
    g = 9.81
    return discharge_coefficient * math.sqrt(2.0 * g)


def compute(
    design_flow_m3_s: float,
    head_over_weir_m: float,
    discharge_coefficient: float = 0.62,
    number_of_contractions: int = 0,
) -> dict[str, float]:
    """Size a sharp-crested rectangular weir for detention basin overflow.

    Uses the Francis formula: Q = Cw × (L - 0.1 × n × H) × H^(3/2)
    where Cw = Cd × √(2g).

    Rearranged for weir length: L = Q / (Cw × H^(3/2)) + 0.1 × n × H

    Returns a dict with keys: required_weir_length_m, unit_discharge_m3_s_per_m.
    """
    _validate_inputs(
        design_flow_m3_s,
        head_over_weir_m,
        discharge_coefficient,
        number_of_contractions,
    )

    q = design_flow_m3_s
    h = head_over_weir_m
    n = number_of_contractions

    # Weir coefficient from discharge coefficient: Cw = Cd × √(2g)
    cw = _effective_weir_coefficient(discharge_coefficient)

    # Head term: H^(3/2)
    h_term = h**1.5

    # Solve for effective crest length: L_eff = Q / (Cw × H^(3/2))
    l_eff = q / (cw * h_term)

    # Account for end contractions: L = L_eff + 0.1 × n × H
    weir_length = l_eff + 0.1 * n * h

    # Unit discharge: q_unit = Q / L
    unit_discharge = q / weir_length

    return {
        "required_weir_length_m": round(weir_length, 2),
        "unit_discharge_m3_s_per_m": round(unit_discharge, 2),
    }
