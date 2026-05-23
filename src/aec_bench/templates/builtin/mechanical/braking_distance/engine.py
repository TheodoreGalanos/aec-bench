# ABOUTME: Train braking distance computation engine for rolling stock checks.
# ABOUTME: Calculates net deceleration and stopping distance from brake effort and gradient.

_G = 9.81


def _validate_inputs(
    train_mass_t: float,
    initial_speed_km_h: float,
    brake_effort_kn: float,
    adhesion_coefficient: float,
    track_gradient_pct: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if train_mass_t <= 0:
        msg = "train_mass_t must be > 0"
        raise ValueError(msg)
    if initial_speed_km_h <= 0:
        msg = "initial_speed_km_h must be > 0"
        raise ValueError(msg)
    if brake_effort_kn <= 0:
        msg = "brake_effort_kn must be > 0"
        raise ValueError(msg)
    if adhesion_coefficient <= 0:
        msg = "adhesion_coefficient must be > 0"
        raise ValueError(msg)


def compute(
    train_mass_t: float,
    initial_speed_km_h: float,
    brake_effort_kn: float,
    adhesion_coefficient: float,
    track_gradient_pct: float,
) -> dict[str, float]:
    """Compute stopping distance under constant braking deceleration.

    Returns a dict with keys: adhesion_limited_brake_effort_kn,
    net_deceleration_m_s2, stopping_distance_m, stopping_time_s.
    """
    _validate_inputs(
        train_mass_t,
        initial_speed_km_h,
        brake_effort_kn,
        adhesion_coefficient,
        track_gradient_pct,
    )

    mass_kg = train_mass_t * 1000.0
    speed_m_s = initial_speed_km_h / 3.6
    adhesion_limit_kn = adhesion_coefficient * mass_kg * _G / 1000.0
    effective_brake_kn = min(brake_effort_kn, adhesion_limit_kn)
    brake_deceleration = effective_brake_kn * 1000.0 / mass_kg
    gradient_acceleration = _G * track_gradient_pct / 100.0
    net_deceleration = brake_deceleration - gradient_acceleration
    if net_deceleration <= 0:
        msg = "net_deceleration must be > 0; braking is insufficient for the gradient"
        raise ValueError(msg)

    stopping_distance = speed_m_s**2 / (2.0 * net_deceleration)
    stopping_time = speed_m_s / net_deceleration

    return {
        "adhesion_limited_brake_effort_kn": round(effective_brake_kn, 2),
        "net_deceleration_m_s2": round(net_deceleration, 2),
        "stopping_distance_m": round(stopping_distance, 2),
        "stopping_time_s": round(stopping_time, 2),
    }
