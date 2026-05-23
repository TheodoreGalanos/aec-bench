# ABOUTME: Gravity base stability computation engine for foundation checks.
# ABOUTME: Calculates overturning factor, eccentricity, and bearing pressure.


def _validate_inputs(
    vertical_load_kn: float,
    overturning_moment_knm: float,
    base_width_m: float,
    base_length_m: float,
    allowable_bearing_kpa: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if vertical_load_kn <= 0:
        msg = "vertical_load_kn must be > 0"
        raise ValueError(msg)
    if overturning_moment_knm < 0:
        msg = "overturning_moment_knm must be >= 0"
        raise ValueError(msg)
    if base_width_m <= 0:
        msg = "base_width_m must be > 0"
        raise ValueError(msg)
    if base_length_m <= 0:
        msg = "base_length_m must be > 0"
        raise ValueError(msg)
    if allowable_bearing_kpa <= 0:
        msg = "allowable_bearing_kpa must be > 0"
        raise ValueError(msg)


def compute(
    vertical_load_kn: float,
    overturning_moment_knm: float,
    base_width_m: float,
    base_length_m: float,
    allowable_bearing_kpa: float,
) -> dict[str, float]:
    """Compute reduced gravity base stability outputs.

    Returns a dict with keys: eccentricity_m, middle_third_limit_m,
    maximum_bearing_kpa, bearing_utilisation_ratio, middle_third_satisfied.
    """
    _validate_inputs(
        vertical_load_kn,
        overturning_moment_knm,
        base_width_m,
        base_length_m,
        allowable_bearing_kpa,
    )

    base_area = base_width_m * base_length_m
    eccentricity = overturning_moment_knm / vertical_load_kn
    middle_third_limit = base_width_m / 6.0
    average_bearing = vertical_load_kn / base_area
    maximum_bearing = average_bearing * (1.0 + 6.0 * eccentricity / base_width_m)
    bearing_utilisation = maximum_bearing / allowable_bearing_kpa
    middle_third_satisfied = 1.0 if eccentricity <= middle_third_limit else 0.0

    return {
        "eccentricity_m": round(eccentricity, 3),
        "middle_third_limit_m": round(middle_third_limit, 3),
        "maximum_bearing_kpa": round(maximum_bearing, 2),
        "bearing_utilisation_ratio": round(bearing_utilisation, 3),
        "middle_third_satisfied": round(middle_third_satisfied, 2),
    }
