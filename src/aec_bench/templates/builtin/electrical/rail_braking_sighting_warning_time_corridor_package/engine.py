# ABOUTME: Computes SSC-02 rail braking, sighting, warning-time, and overlap metrics.
# ABOUTME: Combines Davis resistance, gradient braking, signal sighting, and strike-in distance.

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
    train_speed_kmh: float,
    grade_percent: float,
    reaction_time_s: float,
    braking_rate_m_s2: float,
    davis_a_n_per_t: float,
    davis_b_n_per_t_kmh: float,
    davis_c_n_per_t_kmh2: float,
    train_mass_t: float,
    sighting_distance_m: float,
    required_sighting_time_s: float,
    overlap_distance_m: float,
    warning_time_s: float,
    minimum_warning_time_s: float,
) -> dict[str, float]:
    """Compute source-bound rail braking, sighting, warning-time, and overlap metrics."""
    _require_positive(
        train_speed_kmh=train_speed_kmh,
        reaction_time_s=reaction_time_s,
        braking_rate_m_s2=braking_rate_m_s2,
        train_mass_t=train_mass_t,
        sighting_distance_m=sighting_distance_m,
        required_sighting_time_s=required_sighting_time_s,
        overlap_distance_m=overlap_distance_m,
        warning_time_s=warning_time_s,
        minimum_warning_time_s=minimum_warning_time_s,
    )
    _require_nonnegative(
        grade_percent=grade_percent,
        davis_a_n_per_t=davis_a_n_per_t,
        davis_b_n_per_t_kmh=davis_b_n_per_t_kmh,
        davis_c_n_per_t_kmh2=davis_c_n_per_t_kmh2,
    )

    speed_m_s = train_speed_kmh / 3.6
    davis_resistance_n_per_t = (
        davis_a_n_per_t + davis_b_n_per_t_kmh * train_speed_kmh + davis_c_n_per_t_kmh2 * train_speed_kmh**2
    )
    resistance_force_kn = davis_resistance_n_per_t * train_mass_t / 1000.0
    effective_braking_deceleration_m_s2 = braking_rate_m_s2 - 9.81 * grade_percent / 100.0
    if effective_braking_deceleration_m_s2 <= 0:
        msg = "effective braking deceleration must be > 0"
        raise ValueError(msg)

    braking_distance_m = speed_m_s**2 / (2.0 * effective_braking_deceleration_m_s2) + speed_m_s * reaction_time_s
    sighting_time_s = sighting_distance_m / speed_m_s
    sighting_margin_s = sighting_time_s - required_sighting_time_s
    warning_strike_in_distance_m = speed_m_s * warning_time_s
    warning_margin_s = warning_time_s - minimum_warning_time_s
    overlap_margin_m = warning_strike_in_distance_m - braking_distance_m - overlap_distance_m
    overall_pass_score = 1.0 if min(sighting_margin_s, warning_margin_s, overlap_margin_m) >= 0.0 else 0.0

    return {
        "speed_m_s": round(speed_m_s, 3),
        "davis_resistance_n_per_t": round(davis_resistance_n_per_t, 3),
        "resistance_force_kn": round(resistance_force_kn, 3),
        "effective_braking_deceleration_m_s2": round(effective_braking_deceleration_m_s2, 3),
        "braking_distance_m": round(braking_distance_m, 3),
        "sighting_time_s": round(sighting_time_s, 3),
        "sighting_margin_s": round(sighting_margin_s, 3),
        "warning_strike_in_distance_m": round(warning_strike_in_distance_m, 3),
        "warning_margin_s": round(warning_margin_s, 3),
        "overlap_margin_m": round(overlap_margin_m, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
