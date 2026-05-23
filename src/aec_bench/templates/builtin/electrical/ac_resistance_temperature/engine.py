# ABOUTME: AC resistance at operating temperature computation engine per IEC 60287-1-1.
# ABOUTME: Calculates DC resistance at temperature, skin effect factor, and AC resistance.

import math
from typing import Literal

# Temperature coefficient of resistance at 20 deg C (per IEC 60287-1-1).
# Units: 1/°C
_ALPHA_20: dict[str, float] = {
    "copper": 0.00393,
    "aluminium": 0.00403,
}

# Skin effect constant ks for round stranded conductors (IEC 60287-1-1, Table 2).
# For round stranded (non-segmental) conductors, ks = 1.
# For segmental (Milliken) conductors the value is lower, but this template
# covers standard round stranded conductors only.
_KS_FACTOR = 1.0


def _validate_inputs(
    dc_resistance_20c_ohm_per_km: float,
    conductor_material: str,
    operating_temp_c: float,
    frequency_hz: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if dc_resistance_20c_ohm_per_km <= 0:
        msg = "dc_resistance_20c_ohm_per_km must be > 0"
        raise ValueError(msg)
    if conductor_material not in _ALPHA_20:
        valid = list(_ALPHA_20.keys())
        msg = f"conductor_material must be one of {valid}, got '{conductor_material}'"
        raise ValueError(msg)
    if operating_temp_c < -40:
        msg = "operating_temp_c must be >= -40"
        raise ValueError(msg)
    if operating_temp_c > 250:
        msg = "operating_temp_c must be <= 250"
        raise ValueError(msg)
    if frequency_hz <= 0:
        msg = "frequency_hz must be > 0"
        raise ValueError(msg)


def _dc_resistance_at_temp(
    r20_ohm_per_km: float,
    alpha_20: float,
    temp_c: float,
) -> float:
    """Calculate DC resistance at operating temperature per IEC 60287-1-1.

    Formula: R'(theta) = R_20 * [1 + alpha_20 * (theta - 20)]
    """
    return r20_ohm_per_km * (1.0 + alpha_20 * (temp_c - 20.0))


def _skin_effect_factor(
    r_dc_ohm_per_km: float,
    frequency_hz: float,
) -> float:
    """Calculate skin effect factor ys per IEC 60287-1-1.

    The argument xs^2 is computed from the DC resistance (converted to ohm/m),
    the frequency, and the skin-effect constant ks.

    xs^2 = 8 * pi * f * 1e-7 * ks / R'_dc
    where R'_dc is in ohm/m (divide ohm/km by 1000).

    ys = xs^4 / (192 + 0.8 * xs^4)   for xs < 2.8

    This simplified formula is valid for most practical conductor sizes
    at power frequencies (50/60 Hz).
    """
    # Convert resistance from ohm/km to ohm/m
    r_dc_ohm_per_m = r_dc_ohm_per_km / 1000.0

    xs_squared = 8.0 * math.pi * frequency_hz * 1e-7 * _KS_FACTOR / r_dc_ohm_per_m
    xs_fourth = xs_squared * xs_squared

    ys = xs_fourth / (192.0 + 0.8 * xs_fourth)
    return ys


def compute(
    dc_resistance_20c_ohm_per_km: float,
    conductor_material: Literal["copper", "aluminium"],
    operating_temp_c: float,
    frequency_hz: float,
) -> dict[str, float]:
    """Compute AC resistance at operating temperature per IEC 60287-1-1.

    Steps:
    1. Correct DC resistance from 20 deg C to operating temperature.
    2. Calculate skin effect factor ys from the corrected DC resistance.
    3. Calculate AC resistance: R_ac = R_dc(T) * (1 + ys).
       Proximity effect (yp) is neglected for single isolated conductors.

    Returns a dict with keys: dc_resistance_at_temp_ohm_per_km,
    skin_effect_factor, ac_resistance_ohm_per_km.
    """
    _validate_inputs(
        dc_resistance_20c_ohm_per_km,
        conductor_material,
        operating_temp_c,
        frequency_hz,
    )

    alpha_20 = _ALPHA_20[conductor_material]

    # Step 1: DC resistance at operating temperature
    r_dc_t = _dc_resistance_at_temp(
        dc_resistance_20c_ohm_per_km,
        alpha_20,
        operating_temp_c,
    )

    # Step 2: Skin effect factor
    ys = _skin_effect_factor(r_dc_t, frequency_hz)

    # Step 3: AC resistance (proximity effect yp = 0 for single conductors)
    r_ac = r_dc_t * (1.0 + ys)

    return {
        "dc_resistance_at_temp_ohm_per_km": round(r_dc_t, 2),
        "skin_effect_factor": round(ys, 2),
        "ac_resistance_ohm_per_km": round(r_ac, 2),
    }
