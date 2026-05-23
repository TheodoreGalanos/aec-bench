# ABOUTME: Computes three-phase overhead line inductance from conductor geometry.
# ABOUTME: Uses GMD/GMR relations for a reduced transposed-line calculation.

import math


def _validate_inputs(
    conductor_gmr_m: float,
    phase_spacing_ab_m: float,
    phase_spacing_bc_m: float,
    phase_spacing_ca_m: float,
    bundle_count: str,
    bundle_spacing_m: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if conductor_gmr_m <= 0:
        msg = "conductor_gmr_m must be > 0"
        raise ValueError(msg)
    for name, value in {
        "phase_spacing_ab_m": phase_spacing_ab_m,
        "phase_spacing_bc_m": phase_spacing_bc_m,
        "phase_spacing_ca_m": phase_spacing_ca_m,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)
    if bundle_count not in {"single", "two", "three", "four"}:
        msg = "bundle_count must be one of: single, two, three, four"
        raise ValueError(msg)
    if bundle_spacing_m <= 0:
        msg = "bundle_spacing_m must be > 0"
        raise ValueError(msg)


def _equivalent_gmr(
    conductor_gmr_m: float,
    bundle_count: str,
    bundle_spacing_m: float,
) -> float:
    if bundle_count == "single":
        return conductor_gmr_m
    if bundle_count == "two":
        return (conductor_gmr_m * bundle_spacing_m) ** 0.5
    if bundle_count == "three":
        return (conductor_gmr_m * bundle_spacing_m**2) ** (1.0 / 3.0)
    return 1.09 * (conductor_gmr_m * bundle_spacing_m**3) ** 0.25


def compute(
    conductor_gmr_m: float,
    phase_spacing_ab_m: float,
    phase_spacing_bc_m: float,
    phase_spacing_ca_m: float,
    bundle_count: str,
    bundle_spacing_m: float,
) -> dict[str, float]:
    """Compute equivalent GMR, GMD, and inductance in mH/km."""
    _validate_inputs(
        conductor_gmr_m,
        phase_spacing_ab_m,
        phase_spacing_bc_m,
        phase_spacing_ca_m,
        bundle_count,
        bundle_spacing_m,
    )

    geometric_mean_distance_m = (phase_spacing_ab_m * phase_spacing_bc_m * phase_spacing_ca_m) ** (1.0 / 3.0)
    equivalent_gmr_m = _equivalent_gmr(conductor_gmr_m, bundle_count, bundle_spacing_m)
    inductance_mh_per_km = 0.2 * math.log(geometric_mean_distance_m / equivalent_gmr_m)

    return {
        "geometric_mean_distance_m": round(geometric_mean_distance_m, 2),
        "equivalent_gmr_mm": round(equivalent_gmr_m * 1000.0, 2),
        "inductance_mh_per_km": round(inductance_mh_per_km, 2),
    }
