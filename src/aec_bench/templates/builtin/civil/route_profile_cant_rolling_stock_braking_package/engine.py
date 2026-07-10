# ABOUTME: Computes SSC-02 route profile, cant, transition, and rolling-stock braking metrics.
# ABOUTME: Combines equilibrium cant, cant deficiency, vertical-curve length, and Davis braking checks.

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
    curve_radius_m: float,
    speed_kmh: float,
    gauge_m: float,
    applied_cant_mm: float,
    max_cant_deficiency_mm: float,
    transition_length_m: float,
    cant_gradient_limit_mm_per_m: float,
    vertical_curve_radius_m: float,
    grade_change_percent: float,
    braking_rate_m_s2: float,
    reaction_time_s: float,
    grade_percent: float,
    davis_a_n_per_t: float,
    davis_b_n_per_t_kmh: float,
    davis_c_n_per_t_kmh2: float,
    train_mass_t: float,
) -> dict[str, float]:
    """Compute source-bound route profile, cant, and braking metrics."""
    _require_positive(
        curve_radius_m=curve_radius_m,
        speed_kmh=speed_kmh,
        gauge_m=gauge_m,
        max_cant_deficiency_mm=max_cant_deficiency_mm,
        transition_length_m=transition_length_m,
        cant_gradient_limit_mm_per_m=cant_gradient_limit_mm_per_m,
        vertical_curve_radius_m=vertical_curve_radius_m,
        braking_rate_m_s2=braking_rate_m_s2,
        reaction_time_s=reaction_time_s,
        train_mass_t=train_mass_t,
    )
    _require_nonnegative(
        applied_cant_mm=applied_cant_mm,
        grade_change_percent=grade_change_percent,
        grade_percent=grade_percent,
        davis_a_n_per_t=davis_a_n_per_t,
        davis_b_n_per_t_kmh=davis_b_n_per_t_kmh,
        davis_c_n_per_t_kmh2=davis_c_n_per_t_kmh2,
    )

    speed_m_s = speed_kmh / 3.6
    equilibrium_cant_mm = gauge_m * 1000.0 * speed_m_s**2 / (9.81 * curve_radius_m)
    cant_deficiency_mm = equilibrium_cant_mm - applied_cant_mm
    cant_deficiency_margin_mm = max_cant_deficiency_mm - cant_deficiency_mm
    cant_gradient_mm_per_m = applied_cant_mm / transition_length_m
    cant_gradient_margin_mm_per_m = cant_gradient_limit_mm_per_m - cant_gradient_mm_per_m
    vertical_curve_length_m = vertical_curve_radius_m * grade_change_percent / 100.0
    effective_braking_deceleration_m_s2 = braking_rate_m_s2 - 9.81 * grade_percent / 100.0
    if effective_braking_deceleration_m_s2 <= 0.0:
        msg = "effective braking deceleration must be > 0"
        raise ValueError(msg)

    braking_distance_m = speed_m_s**2 / (2.0 * effective_braking_deceleration_m_s2) + speed_m_s * reaction_time_s
    davis_resistance_n_per_t = davis_a_n_per_t + davis_b_n_per_t_kmh * speed_kmh + davis_c_n_per_t_kmh2 * speed_kmh**2
    resistance_force_kn = davis_resistance_n_per_t * train_mass_t / 1000.0
    overall_pass_score = (
        1.0
        if min(cant_deficiency_margin_mm, cant_gradient_margin_mm_per_m, effective_braking_deceleration_m_s2) >= 0.0
        else 0.0
    )

    return {
        "speed_m_s": round(speed_m_s, 3),
        "equilibrium_cant_mm": round(equilibrium_cant_mm, 3),
        "cant_deficiency_mm": round(cant_deficiency_mm, 3),
        "cant_deficiency_margin_mm": round(cant_deficiency_margin_mm, 3),
        "cant_gradient_mm_per_m": round(cant_gradient_mm_per_m, 3),
        "cant_gradient_margin_mm_per_m": round(cant_gradient_margin_mm_per_m, 3),
        "vertical_curve_length_m": round(vertical_curve_length_m, 3),
        "effective_braking_deceleration_m_s2": round(effective_braking_deceleration_m_s2, 3),
        "braking_distance_m": round(braking_distance_m, 3),
        "davis_resistance_n_per_t": round(davis_resistance_n_per_t, 3),
        "resistance_force_kn": round(resistance_force_kn, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
