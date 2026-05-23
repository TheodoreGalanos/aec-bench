# ABOUTME: Outfall submergence analysis engine using a sinusoidal tide model.
# ABOUTME: Calculates outfall submergence time under present and future sea levels.

import math

# Semi-diurnal tidal period in hours (M2 constituent)
_DEFAULT_TIDAL_PERIOD_HOURS = 12.42


def _submergence_fraction(
    invert_level_m: float,
    mean_sea_level_m: float,
    tidal_amplitude_m: float,
) -> float:
    """Calculate the fraction of a tidal cycle during which water level exceeds the invert.

    For a sinusoidal tide h(t) = MSL + A * sin(theta), the outfall is submerged
    when h(t) > z_inv, i.e. sin(theta) > (z_inv - MSL) / A.

    Let x = (z_inv - MSL) / A.  For |x| <= 1 the closed-form fraction of time
    submerged is:  f = 0.5 - (1/pi) * arcsin(x).

    Boundary cases:
      x >= 1  =>  never submerged  =>  0.0
      x <= -1 =>  always submerged =>  1.0
    """
    if tidal_amplitude_m == 0:
        # No tidal variation: submerged iff MSL > invert
        return 1.0 if mean_sea_level_m > invert_level_m else 0.0

    x = (invert_level_m - mean_sea_level_m) / tidal_amplitude_m

    if x >= 1.0:
        return 0.0
    if x <= -1.0:
        return 1.0

    return 0.5 - (1.0 / math.pi) * math.asin(x)


def _validate_inputs(
    outfall_invert_level_m: float,
    mean_sea_level_m: float,
    tidal_amplitude_m: float,
    sea_level_rise_m: float,
    tidal_period_hours: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if tidal_amplitude_m < 0:
        msg = "tidal_amplitude_m must be >= 0"
        raise ValueError(msg)
    if sea_level_rise_m < 0:
        msg = "sea_level_rise_m must be >= 0"
        raise ValueError(msg)
    if tidal_period_hours <= 0:
        msg = "tidal_period_hours must be > 0"
        raise ValueError(msg)


def compute(
    outfall_invert_level_m: float,
    mean_sea_level_m: float,
    tidal_amplitude_m: float,
    sea_level_rise_m: float,
    tidal_period_hours: float = _DEFAULT_TIDAL_PERIOD_HOURS,
) -> dict[str, float]:
    """Compute outfall submergence under present and future sea level conditions.

    Procedure:
    1. Model the tide as h(t) = MSL + A * sin(2*pi*t / T).
    2. Calculate the fraction of a tidal cycle during which the water level
       exceeds the outfall invert level (present-day MSL).
    3. Repeat for future MSL = MSL + sea_level_rise_m.
    4. Convert fractions to percentages and hours per day.

    Returns a dict with keys:
        present_submergence_percent  — % of time submerged under present MSL
        future_submergence_percent   — % of time submerged under future MSL
        present_hours_submerged_per_day — hours/day submerged (present)
        future_hours_submerged_per_day  — hours/day submerged (future)
        submergence_increase_percent — absolute increase in submergence (%)
    """
    _validate_inputs(
        outfall_invert_level_m,
        mean_sea_level_m,
        tidal_amplitude_m,
        sea_level_rise_m,
        tidal_period_hours,
    )

    # Present-day submergence
    frac_present = _submergence_fraction(
        outfall_invert_level_m,
        mean_sea_level_m,
        tidal_amplitude_m,
    )

    # Future submergence (MSL shifted by SLR)
    future_msl = mean_sea_level_m + sea_level_rise_m
    frac_future = _submergence_fraction(
        outfall_invert_level_m,
        future_msl,
        tidal_amplitude_m,
    )

    present_pct = frac_present * 100.0
    future_pct = frac_future * 100.0
    increase_pct = future_pct - present_pct

    return {
        "present_submergence_percent": round(present_pct, 2),
        "future_submergence_percent": round(future_pct, 2),
        "present_hours_submerged_per_day": round(frac_present * 24.0, 2),
        "future_hours_submerged_per_day": round(frac_future * 24.0, 2),
        "submergence_increase_percent": round(increase_pct, 2),
    }
