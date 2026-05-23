# ABOUTME: Computes signal overlap distance with gradient and adhesion effects.
# ABOUTME: Uses approach speed, reaction time, braking rate, and danger point distance.

_GRAVITY_M_S2 = 9.81


def _validate_inputs(
    maximum_approach_speed_kmh: float,
    emergency_braking_rate_m_s2: float,
    track_gradient_pct: float,
    reaction_time_s: float,
    danger_point_distance_m: float,
    low_adhesion_factor: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "maximum_approach_speed_kmh": maximum_approach_speed_kmh,
        "emergency_braking_rate_m_s2": emergency_braking_rate_m_s2,
        "reaction_time_s": reaction_time_s,
        "danger_point_distance_m": danger_point_distance_m,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)
    if not 0 < low_adhesion_factor <= 1:
        msg = "low_adhesion_factor must be > 0 and <= 1"
        raise ValueError(msg)
    effective_rate = emergency_braking_rate_m_s2 * low_adhesion_factor + (_GRAVITY_M_S2 * track_gradient_pct / 100.0)
    if effective_rate <= 0:
        msg = "gradient-adjusted braking rate must be > 0"
        raise ValueError(msg)


def compute(
    maximum_approach_speed_kmh: float,
    emergency_braking_rate_m_s2: float,
    track_gradient_pct: float,
    reaction_time_s: float,
    danger_point_distance_m: float,
    low_adhesion_factor: float,
) -> dict[str, float]:
    """Compute full-speed and timed signal overlap distances."""
    _validate_inputs(
        maximum_approach_speed_kmh,
        emergency_braking_rate_m_s2,
        track_gradient_pct,
        reaction_time_s,
        danger_point_distance_m,
        low_adhesion_factor,
    )

    approach_speed_m_s = maximum_approach_speed_kmh / 3.6
    gradient_adjusted_braking_rate_m_s2 = emergency_braking_rate_m_s2 * low_adhesion_factor + (
        _GRAVITY_M_S2 * track_gradient_pct / 100.0
    )
    reaction_distance_m = approach_speed_m_s * reaction_time_s
    timed_overlap_option_m = approach_speed_m_s**2 / (2.0 * gradient_adjusted_braking_rate_m_s2)
    full_speed_overlap_m = reaction_distance_m + timed_overlap_option_m
    danger_point_clearance_m = danger_point_distance_m - full_speed_overlap_m

    return {
        "approach_speed_m_s": round(approach_speed_m_s, 2),
        "gradient_adjusted_braking_rate_m_s2": round(gradient_adjusted_braking_rate_m_s2, 2),
        "reaction_distance_m": round(reaction_distance_m, 2),
        "full_speed_overlap_m": round(full_speed_overlap_m, 2),
        "timed_overlap_option_m": round(timed_overlap_option_m, 2),
        "danger_point_clearance_m": round(danger_point_clearance_m, 2),
    }
