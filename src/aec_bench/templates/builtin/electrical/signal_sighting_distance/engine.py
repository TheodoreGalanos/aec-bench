# ABOUTME: Computes signal sighting distance from speed, reaction time, braking, and grade.
# ABOUTME: Uses a reduced kinematic stopping-distance calculation.


def _validate_inputs(
    maximum_line_speed_kmh: float,
    service_braking_rate_m_s2: float,
    driver_reaction_time_s: float,
    track_gradient_pct: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if maximum_line_speed_kmh <= 0:
        msg = "maximum_line_speed_kmh must be > 0"
        raise ValueError(msg)
    if service_braking_rate_m_s2 <= 0:
        msg = "service_braking_rate_m_s2 must be > 0"
        raise ValueError(msg)
    if driver_reaction_time_s < 0:
        msg = "driver_reaction_time_s must be >= 0"
        raise ValueError(msg)
    grade_adjusted = service_braking_rate_m_s2 + 9.81 * track_gradient_pct / 100.0
    if grade_adjusted <= 0:
        msg = "track grade and braking rate produce non-positive braking"
        raise ValueError(msg)


def compute(
    maximum_line_speed_kmh: float,
    service_braking_rate_m_s2: float,
    driver_reaction_time_s: float,
    track_gradient_pct: float,
) -> dict[str, float]:
    """Compute reaction, braking, and total signal sighting distance."""
    _validate_inputs(
        maximum_line_speed_kmh,
        service_braking_rate_m_s2,
        driver_reaction_time_s,
        track_gradient_pct,
    )

    line_speed_m_s = maximum_line_speed_kmh / 3.6
    reaction_distance_m = line_speed_m_s * driver_reaction_time_s
    grade_adjusted_braking_rate_m_s2 = service_braking_rate_m_s2 + 9.81 * track_gradient_pct / 100.0
    braking_distance_m = line_speed_m_s**2 / (2.0 * grade_adjusted_braking_rate_m_s2)
    required_sighting_distance_m = reaction_distance_m + braking_distance_m

    return {
        "line_speed_m_s": round(line_speed_m_s, 2),
        "reaction_distance_m": round(reaction_distance_m, 2),
        "grade_adjusted_braking_rate_m_s2": round(grade_adjusted_braking_rate_m_s2, 2),
        "braking_distance_m": round(braking_distance_m, 2),
        "required_sighting_distance_m": round(required_sighting_distance_m, 2),
    }
