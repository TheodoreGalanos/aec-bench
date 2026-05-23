# ABOUTME: Computes capacitor kVAr needed to correct load power factor.
# ABOUTME: Uses the standard P x (tan phi_initial - tan phi_target) relation.

import math


def _validate_inputs(
    real_power_kw: float,
    initial_power_factor: float,
    target_power_factor: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if real_power_kw <= 0:
        msg = "real_power_kw must be > 0"
        raise ValueError(msg)
    if not 0 < initial_power_factor < 1:
        msg = "initial_power_factor must be between 0 and 1"
        raise ValueError(msg)
    if not 0 < target_power_factor < 1:
        msg = "target_power_factor must be between 0 and 1"
        raise ValueError(msg)
    if target_power_factor <= initial_power_factor:
        msg = "target_power_factor must be greater than initial_power_factor"
        raise ValueError(msg)


def compute(
    real_power_kw: float,
    initial_power_factor: float,
    target_power_factor: float,
) -> dict[str, float]:
    """Compute capacitor kVAr and apparent-power reduction."""
    _validate_inputs(real_power_kw, initial_power_factor, target_power_factor)

    initial_angle_rad = math.acos(initial_power_factor)
    target_angle_rad = math.acos(target_power_factor)
    initial_apparent_power_kva = real_power_kw / initial_power_factor
    corrected_apparent_power_kva = real_power_kw / target_power_factor
    required_reactive_power_kvar = real_power_kw * (math.tan(initial_angle_rad) - math.tan(target_angle_rad))
    current_reduction_pct = (
        (initial_apparent_power_kva - corrected_apparent_power_kva) / initial_apparent_power_kva * 100.0
    )

    return {
        "initial_apparent_power_kva": round(initial_apparent_power_kva, 2),
        "corrected_apparent_power_kva": round(corrected_apparent_power_kva, 2),
        "required_reactive_power_kvar": round(required_reactive_power_kvar, 2),
        "current_reduction_pct": round(current_reduction_pct, 2),
    }
