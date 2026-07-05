# ABOUTME: Computes SSC-02 signal approach speed, sighting, stopping-distance, and overlap metrics.
# ABOUTME: Checks source-owned photo offset, overlap margin, warning distance, and sighting margins.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _require_nonnegative(**values: float) -> None:
    for name, value in values.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)


def compute(
    approach_speed_kmh: float,
    reaction_time_s: float,
    braking_rate_m_s2: float,
    grade_percent: float,
    available_sighting_distance_m: float,
    required_sighting_time_s: float,
    provided_overlap_m: float,
    danger_point_distance_m: float,
    photo_chainage_m: float,
    signal_chainage_m: float,
    max_photo_offset_m: float,
    warning_time_s: float,
) -> dict[str, float]:
    """Compute source-bound signal sighting, stopping, and overlap metrics."""
    _require_positive(
        approach_speed_kmh=approach_speed_kmh,
        reaction_time_s=reaction_time_s,
        braking_rate_m_s2=braking_rate_m_s2,
        available_sighting_distance_m=available_sighting_distance_m,
        required_sighting_time_s=required_sighting_time_s,
        provided_overlap_m=provided_overlap_m,
        max_photo_offset_m=max_photo_offset_m,
        warning_time_s=warning_time_s,
    )
    _require_nonnegative(grade_percent=grade_percent, danger_point_distance_m=danger_point_distance_m)

    approach_speed_m_s = approach_speed_kmh / 3.6
    effective_braking_deceleration_m_s2 = braking_rate_m_s2 - 9.81 * grade_percent / 100.0
    if effective_braking_deceleration_m_s2 <= 0.0:
        msg = "effective braking deceleration must be > 0"
        raise ValueError(msg)

    stopping_distance_m = (
        approach_speed_m_s**2 / (2.0 * effective_braking_deceleration_m_s2) + approach_speed_m_s * reaction_time_s
    )
    sighting_time_s = available_sighting_distance_m / approach_speed_m_s
    sighting_time_margin_s = sighting_time_s - required_sighting_time_s
    stopping_distance_margin_m = available_sighting_distance_m - stopping_distance_m
    overlap_margin_m = provided_overlap_m - danger_point_distance_m
    photo_offset_m = abs(photo_chainage_m - signal_chainage_m)
    photo_offset_margin_m = max_photo_offset_m - photo_offset_m
    warning_distance_m = approach_speed_m_s * warning_time_s
    overall_pass_score = (
        1.0
        if min(sighting_time_margin_s, stopping_distance_margin_m, overlap_margin_m, photo_offset_margin_m) >= 0.0
        else 0.0
    )

    return {
        "approach_speed_m_s": round(approach_speed_m_s, 3),
        "effective_braking_deceleration_m_s2": round(effective_braking_deceleration_m_s2, 3),
        "stopping_distance_m": round(stopping_distance_m, 3),
        "sighting_time_s": round(sighting_time_s, 3),
        "sighting_time_margin_s": round(sighting_time_margin_s, 3),
        "stopping_distance_margin_m": round(stopping_distance_margin_m, 3),
        "overlap_margin_m": round(overlap_margin_m, 3),
        "photo_offset_m": round(photo_offset_m, 3),
        "photo_offset_margin_m": round(photo_offset_margin_m, 3),
        "warning_distance_m": round(warning_distance_m, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
