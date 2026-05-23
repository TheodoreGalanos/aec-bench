# ABOUTME: Computes traffic-signal yellow interval using the metric ITE equation.
# ABOUTME: Applies speed, perception-reaction time, deceleration, and road grade.


def _validate_inputs(
    approach_speed_kmh: float,
    perception_reaction_time_s: float,
    deceleration_rate_m_s2: float,
    road_grade_pct: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if approach_speed_kmh <= 0:
        msg = "approach_speed_kmh must be > 0"
        raise ValueError(msg)
    if perception_reaction_time_s <= 0:
        msg = "perception_reaction_time_s must be > 0"
        raise ValueError(msg)
    if deceleration_rate_m_s2 <= 0:
        msg = "deceleration_rate_m_s2 must be > 0"
        raise ValueError(msg)
    grade_adjusted_denominator = 2.0 * deceleration_rate_m_s2 + 19.62 * (road_grade_pct / 100.0)
    if grade_adjusted_denominator <= 0:
        msg = "road grade and deceleration produce a non-positive denominator"
        raise ValueError(msg)


def compute(
    approach_speed_kmh: float,
    perception_reaction_time_s: float,
    deceleration_rate_m_s2: float,
    road_grade_pct: float,
) -> dict[str, float]:
    """Compute metric ITE yellow change interval."""
    _validate_inputs(
        approach_speed_kmh,
        perception_reaction_time_s,
        deceleration_rate_m_s2,
        road_grade_pct,
    )

    approach_speed_m_s = approach_speed_kmh / 3.6
    grade_adjusted_denominator = 2.0 * deceleration_rate_m_s2 + 19.62 * (road_grade_pct / 100.0)
    yellow_interval_s = perception_reaction_time_s + approach_speed_m_s / grade_adjusted_denominator
    yellow_interval_rounded_s = round(yellow_interval_s, 1)

    return {
        "approach_speed_m_s": round(approach_speed_m_s, 2),
        "grade_adjusted_denominator": round(grade_adjusted_denominator, 2),
        "yellow_interval_s": round(yellow_interval_s, 2),
        "yellow_interval_rounded_s": round(yellow_interval_rounded_s, 2),
    }
