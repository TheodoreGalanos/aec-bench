# ABOUTME: Stopping sight distance computation engine for graded road segments.
# ABOUTME: Implements d_r + d_b per AGRD Part 3 Section 5 with speed-dependent friction lookup.


# AGRD Table 5.5 — longitudinal friction coefficient vs design speed.
# Keys are design speed in km/h; values are the corresponding friction coefficient f.
_FRICTION_TABLE: dict[int, float] = {
    40: 0.52,
    50: 0.48,
    60: 0.45,
    70: 0.43,
    80: 0.40,
    90: 0.38,
    100: 0.36,
    110: 0.34,
    120: 0.32,
    130: 0.29,
}


def _lookup_friction(design_speed_km_h: float) -> float:
    """Look up longitudinal friction coefficient from AGRD Table 5.5.

    Performs linear interpolation between tabulated speed values.
    Clamps to table bounds (40-130 km/h).
    """
    speeds = sorted(_FRICTION_TABLE.keys())
    speed = max(speeds[0], min(speeds[-1], design_speed_km_h))

    # Exact match
    if speed in _FRICTION_TABLE:
        return _FRICTION_TABLE[int(speed)]

    # Find surrounding entries for interpolation
    lower_speed = max(s for s in speeds if s <= speed)
    upper_speed = min(s for s in speeds if s >= speed)

    f_lower = _FRICTION_TABLE[lower_speed]
    f_upper = _FRICTION_TABLE[upper_speed]

    # Linear interpolation
    fraction = (speed - lower_speed) / (upper_speed - lower_speed)
    return f_lower + fraction * (f_upper - f_lower)


def _validate_inputs(
    design_speed_km_h: float,
    grade_pct: float,
    reaction_time_s: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if design_speed_km_h <= 0:
        msg = "design_speed_km_h must be > 0"
        raise ValueError(msg)
    if grade_pct < -10.0 or grade_pct > 10.0:
        msg = "grade_pct must be between -10 and 10"
        raise ValueError(msg)
    if reaction_time_s <= 0:
        msg = "reaction_time_s must be > 0"
        raise ValueError(msg)
    # Check that braking denominator is positive (friction must exceed grade effect)
    f = _lookup_friction(design_speed_km_h)
    g = grade_pct / 100.0
    if (f + g) <= 0:
        msg = f"Braking infeasible: friction f={f:.3f} cannot overcome downhill grade g={g:.3f} (f + g must be > 0)"
        raise ValueError(msg)


def _reaction_distance(design_speed_km_h: float, reaction_time_s: float) -> float:
    """Calculate reaction distance d_r in metres.

    d_r = V * t_r / 3.6
    where V is in km/h and t_r is in seconds.
    """
    return design_speed_km_h * reaction_time_s / 3.6


def _braking_distance(
    design_speed_km_h: float,
    friction_coeff: float,
    grade_pct: float,
) -> float:
    """Calculate braking distance d_b in metres.

    d_b = V^2 / (254 * (f + g))
    where V is in km/h, f is the longitudinal friction coefficient,
    and g is the grade as a decimal (positive = uphill, so +g aids braking).
    Sign convention: grade_pct positive means uphill travel.
    When braking uphill, the grade assists braking → (f + g).
    When braking downhill, grade_pct is negative → (f + g) becomes (f - |g|).
    """
    g = grade_pct / 100.0
    return (design_speed_km_h**2) / (254.0 * (friction_coeff + g))


def compute(
    design_speed_km_h: float,
    grade_pct: float,
    reaction_time_s: float,
) -> dict[str, float]:
    """Compute stopping sight distance on a graded road segment.

    Returns a dict with keys: reaction_distance_m, braking_distance_m,
    stopping_sight_distance_m.
    """
    _validate_inputs(design_speed_km_h, grade_pct, reaction_time_s)

    f = _lookup_friction(design_speed_km_h)

    d_r = _reaction_distance(design_speed_km_h, reaction_time_s)
    d_b = _braking_distance(design_speed_km_h, f, grade_pct)
    ssd = d_r + d_b

    return {
        "reaction_distance_m": round(d_r, 2),
        "braking_distance_m": round(d_b, 2),
        "stopping_sight_distance_m": round(ssd, 2),
    }
