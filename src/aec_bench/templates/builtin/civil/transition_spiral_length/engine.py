# ABOUTME: Transition spiral length computation engine for rail track geometry.
# ABOUTME: Implements ARTC ETS-05-00 / AREMA cant runoff, cant deficiency rate, and twist criteria.


def _validate_inputs(
    actual_cant_mm: float,
    cant_deficiency_mm: float,
    max_speed_km_h: float,
    rate_of_change_cant_mm_s: float,
    rate_of_change_cd_mm_s: float,
    min_twist_ratio: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if actual_cant_mm < 0:
        msg = "actual_cant_mm must be >= 0"
        raise ValueError(msg)
    if cant_deficiency_mm < 0:
        msg = "cant_deficiency_mm must be >= 0"
        raise ValueError(msg)
    if max_speed_km_h <= 0:
        msg = "max_speed_km_h must be > 0"
        raise ValueError(msg)
    if rate_of_change_cant_mm_s <= 0:
        msg = "rate_of_change_cant_mm_s must be > 0"
        raise ValueError(msg)
    if rate_of_change_cd_mm_s <= 0:
        msg = "rate_of_change_cd_mm_s must be > 0"
        raise ValueError(msg)
    if min_twist_ratio <= 0:
        msg = "min_twist_ratio must be > 0"
        raise ValueError(msg)


def _spiral_length_cant_runoff(
    actual_cant_mm: float,
    max_speed_km_h: float,
    rate_of_change_cant_mm_s: float,
) -> float:
    """Calculate spiral length from cant runoff criterion in metres.

    L_cant = (E_a * V_max) / (3.6 * D_cant)
    where E_a is actual cant (mm), V_max is speed (km/h),
    D_cant is the maximum rate of change of cant (mm/s).
    The 3.6 converts km/h to m/s.
    """
    return (actual_cant_mm * max_speed_km_h) / (3.6 * rate_of_change_cant_mm_s)


def _spiral_length_cant_deficiency_rate(
    cant_deficiency_mm: float,
    max_speed_km_h: float,
    rate_of_change_cd_mm_s: float,
) -> float:
    """Calculate spiral length from rate of change of cant deficiency in metres.

    L_cd = (C_d * V_max) / (3.6 * D_cd)
    where C_d is cant deficiency (mm), V_max is speed (km/h),
    D_cd is the maximum rate of change of cant deficiency (mm/s).
    """
    return (cant_deficiency_mm * max_speed_km_h) / (3.6 * rate_of_change_cd_mm_s)


def _spiral_length_twist(
    actual_cant_mm: float,
    min_twist_ratio: float,
) -> float:
    """Calculate spiral length from twist rate criterion in metres.

    L_twist = E_a * twist_ratio / 1000
    where twist_ratio is the minimum twist ratio (e.g. 400 means 1 mm cant per 400 mm length).
    Dividing by 1000 converts the result from mm to metres.
    """
    return actual_cant_mm * min_twist_ratio / 1000.0


def compute(
    actual_cant_mm: float,
    cant_deficiency_mm: float,
    max_speed_km_h: float,
    rate_of_change_cant_mm_s: float,
    rate_of_change_cd_mm_s: float,
    min_twist_ratio: float,
) -> dict[str, float]:
    """Compute minimum transition spiral lengths for a rail curve transition.

    Returns a dict with keys: spiral_length_cant_m, spiral_length_cd_m,
    spiral_length_twist_m, governing_spiral_length_m.
    """
    _validate_inputs(
        actual_cant_mm,
        cant_deficiency_mm,
        max_speed_km_h,
        rate_of_change_cant_mm_s,
        rate_of_change_cd_mm_s,
        min_twist_ratio,
    )

    l_cant = _spiral_length_cant_runoff(actual_cant_mm, max_speed_km_h, rate_of_change_cant_mm_s)
    l_cd = _spiral_length_cant_deficiency_rate(cant_deficiency_mm, max_speed_km_h, rate_of_change_cd_mm_s)
    l_twist = _spiral_length_twist(actual_cant_mm, min_twist_ratio)

    governing = max(l_cant, l_cd, l_twist)

    return {
        "spiral_length_cant_m": round(l_cant, 2),
        "spiral_length_cd_m": round(l_cd, 2),
        "spiral_length_twist_m": round(l_twist, 2),
        "governing_spiral_length_m": round(governing, 2),
    }
