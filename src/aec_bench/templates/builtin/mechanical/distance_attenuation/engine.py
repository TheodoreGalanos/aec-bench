# ABOUTME: Point-source distance attenuation computation engine for acoustic checks.
# ABOUTME: Calculates sound pressure level at a target distance using inverse-square spreading.

import math


def _validate_inputs(
    reference_spl_db: float,
    reference_distance_m: float,
    target_distance_m: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if reference_spl_db < 0:
        msg = "reference_spl_db must be >= 0"
        raise ValueError(msg)
    if reference_distance_m <= 0:
        msg = "reference_distance_m must be > 0"
        raise ValueError(msg)
    if target_distance_m <= 0:
        msg = "target_distance_m must be > 0"
        raise ValueError(msg)


def compute(
    reference_spl_db: float,
    reference_distance_m: float,
    target_distance_m: float,
) -> dict[str, float]:
    """Compute target SPL from geometric spreading of a point source.

    Returns a dict with keys: distance_ratio, attenuation_db, target_spl_db.
    """
    _validate_inputs(reference_spl_db, reference_distance_m, target_distance_m)

    distance_ratio = target_distance_m / reference_distance_m
    attenuation = 20.0 * math.log10(distance_ratio)
    target_spl = reference_spl_db - attenuation

    return {
        "distance_ratio": round(distance_ratio, 2),
        "attenuation_db": round(attenuation, 2),
        "target_spl_db": round(target_spl, 2),
    }
