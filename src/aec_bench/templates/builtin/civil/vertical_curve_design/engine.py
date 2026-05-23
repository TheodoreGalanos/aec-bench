# ABOUTME: Railway vertical curve design computation engine for grade transitions.
# ABOUTME: Implements ARTC ETS-05-00 / AREMA vertical curve radius and length from speed and vertical acceleration.


def _validate_inputs(
    initial_grade_pct: float,
    final_grade_pct: float,
    design_speed_km_h: float,
    max_vertical_acceleration_m_s2: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if not -5.0 <= initial_grade_pct <= 5.0:
        msg = "initial_grade_pct must be between -5.0 and 5.0"
        raise ValueError(msg)
    if not -5.0 <= final_grade_pct <= 5.0:
        msg = "final_grade_pct must be between -5.0 and 5.0"
        raise ValueError(msg)
    if design_speed_km_h <= 0:
        msg = "design_speed_km_h must be > 0"
        raise ValueError(msg)
    if max_vertical_acceleration_m_s2 <= 0:
        msg = "max_vertical_acceleration_m_s2 must be > 0"
        raise ValueError(msg)


def compute(
    initial_grade_pct: float,
    final_grade_pct: float,
    design_speed_km_h: float,
    max_vertical_acceleration_m_s2: float,
) -> dict[str, float]:
    """Compute vertical curve parameters for a railway grade transition.

    The algebraic grade difference A = |g1 - g2| quantifies the total grade
    change at the transition point.  The minimum vertical curve radius limits
    vertical acceleration experienced by passengers and rolling stock:

        R_v = V^2 / (3.6^2 * a_v)

    where V is in km/h and a_v is the acceptable vertical acceleration in m/s^2.
    The minimum curve length is the arc subtended by the grade change:

        L_v = (A / 100) * R_v

    Returns a dict with keys: algebraic_grade_difference_pct,
    min_vertical_curve_radius_m, min_vertical_curve_length_m.
    """
    _validate_inputs(
        initial_grade_pct,
        final_grade_pct,
        design_speed_km_h,
        max_vertical_acceleration_m_s2,
    )

    # Algebraic grade difference (absolute value of grade change)
    a_pct = abs(initial_grade_pct - final_grade_pct)

    # Minimum vertical curve radius from speed and vertical acceleration limit.
    # V in km/h is converted to m/s by dividing by 3.6; squaring gives 3.6^2 = 12.96.
    r_v = (design_speed_km_h**2) / (12.96 * max_vertical_acceleration_m_s2)

    # Minimum vertical curve length: grade change (in radians) times radius.
    # A/100 converts percent grade difference to radians (small angle approximation).
    l_v = (a_pct / 100.0) * r_v

    return {
        "algebraic_grade_difference_pct": round(a_pct, 2),
        "min_vertical_curve_radius_m": round(r_v, 2),
        "min_vertical_curve_length_m": round(l_v, 2),
    }
