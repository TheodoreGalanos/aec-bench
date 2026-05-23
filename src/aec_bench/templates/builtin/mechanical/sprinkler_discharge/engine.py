# ABOUTME: Sprinkler discharge computation engine for fire suppression checks.
# ABOUTME: Calculates discharge from sprinkler K factor and operating pressure.

import math


def _validate_inputs(k_factor_l_min_sqrt_bar: float, pressure_bar: float) -> None:
    """Raise ValueError for invalid input parameters."""
    if k_factor_l_min_sqrt_bar <= 0:
        msg = "k_factor_l_min_sqrt_bar must be > 0"
        raise ValueError(msg)
    if pressure_bar <= 0:
        msg = "pressure_bar must be > 0"
        raise ValueError(msg)


def compute(k_factor_l_min_sqrt_bar: float, pressure_bar: float) -> dict[str, float]:
    """Compute sprinkler discharge from K factor and pressure.

    Returns a dict with keys: discharge_l_min, discharge_l_s, pressure_kpa.
    """
    _validate_inputs(k_factor_l_min_sqrt_bar, pressure_bar)

    discharge_l_min = k_factor_l_min_sqrt_bar * math.sqrt(pressure_bar)
    discharge_l_s = discharge_l_min / 60.0
    pressure_kpa = pressure_bar * 100.0

    return {
        "discharge_l_min": round(discharge_l_min, 2),
        "discharge_l_s": round(discharge_l_s, 2),
        "pressure_kpa": round(pressure_kpa, 2),
    }
