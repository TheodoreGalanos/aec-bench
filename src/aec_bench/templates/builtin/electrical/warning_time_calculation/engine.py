# ABOUTME: Computes level crossing warning time and strike-in distance.
# ABOUTME: Converts train speed and component times into a detection distance.


def _validate_inputs(
    maximum_train_speed_kmh: float,
    minimum_warning_time_s: float,
    road_user_clearance_time_s: float,
    barrier_lowering_time_s: float,
    system_delay_s: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if maximum_train_speed_kmh <= 0:
        msg = "maximum_train_speed_kmh must be > 0"
        raise ValueError(msg)
    for name, value in {
        "minimum_warning_time_s": minimum_warning_time_s,
        "road_user_clearance_time_s": road_user_clearance_time_s,
        "barrier_lowering_time_s": barrier_lowering_time_s,
        "system_delay_s": system_delay_s,
    }.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)


def compute(
    maximum_train_speed_kmh: float,
    minimum_warning_time_s: float,
    road_user_clearance_time_s: float,
    barrier_lowering_time_s: float,
    system_delay_s: float,
) -> dict[str, float]:
    """Compute crossing warning time and strike-in distance."""
    _validate_inputs(
        maximum_train_speed_kmh,
        minimum_warning_time_s,
        road_user_clearance_time_s,
        barrier_lowering_time_s,
        system_delay_s,
    )

    maximum_train_speed_m_s = maximum_train_speed_kmh / 3.6
    total_warning_time_s = (
        minimum_warning_time_s + road_user_clearance_time_s + barrier_lowering_time_s + system_delay_s
    )
    strike_in_distance_m = maximum_train_speed_m_s * total_warning_time_s
    minimum_warning_margin_s = total_warning_time_s - minimum_warning_time_s

    return {
        "maximum_train_speed_m_s": round(maximum_train_speed_m_s, 2),
        "total_warning_time_s": round(total_warning_time_s, 2),
        "strike_in_distance_m": round(strike_in_distance_m, 2),
        "minimum_warning_margin_s": round(minimum_warning_margin_s, 2),
    }
