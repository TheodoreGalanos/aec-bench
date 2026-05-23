# ABOUTME: T-squared fire growth computation engine for design fire checks.
# ABOUTME: Calculates unclipped and peak-limited heat release rate from alpha and time.

import math


def _validate_inputs(
    growth_coefficient_kw_s2: float,
    time_from_ignition_s: float,
    peak_hrr_kw: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if growth_coefficient_kw_s2 <= 0:
        msg = "growth_coefficient_kw_s2 must be > 0"
        raise ValueError(msg)
    if time_from_ignition_s < 0:
        msg = "time_from_ignition_s must be >= 0"
        raise ValueError(msg)
    if peak_hrr_kw <= 0:
        msg = "peak_hrr_kw must be > 0"
        raise ValueError(msg)


def compute(
    growth_coefficient_kw_s2: float,
    time_from_ignition_s: float,
    peak_hrr_kw: float,
) -> dict[str, float]:
    """Compute t-squared design fire heat release rate.

    Returns a dict with keys: unclipped_hrr_kw, hrr_at_time_kw,
    time_to_peak_s, peak_limited.
    """
    _validate_inputs(growth_coefficient_kw_s2, time_from_ignition_s, peak_hrr_kw)

    unclipped_hrr = growth_coefficient_kw_s2 * time_from_ignition_s**2
    hrr_at_time = min(unclipped_hrr, peak_hrr_kw)
    time_to_peak = math.sqrt(peak_hrr_kw / growth_coefficient_kw_s2)
    peak_limited = 1.0 if unclipped_hrr >= peak_hrr_kw else 0.0

    return {
        "unclipped_hrr_kw": round(unclipped_hrr, 2),
        "hrr_at_time_kw": round(hrr_at_time, 2),
        "time_to_peak_s": round(time_to_peak, 2),
        "peak_limited": round(peak_limited, 2),
    }
