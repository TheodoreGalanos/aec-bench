# ABOUTME: Computes all-red clearance interval from crossing distance and speed.
# ABOUTME: Applies a one-decimal rounded interval capped at six seconds.


def _validate_inputs(
    intersection_width_m: float,
    vehicle_length_m: float,
    vehicle_speed_m_s: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "intersection_width_m": intersection_width_m,
        "vehicle_length_m": vehicle_length_m,
        "vehicle_speed_m_s": vehicle_speed_m_s,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    intersection_width_m: float,
    vehicle_length_m: float,
    vehicle_speed_m_s: float,
) -> dict[str, float]:
    """Compute all-red clearance time for a vehicle to clear an intersection."""
    _validate_inputs(intersection_width_m, vehicle_length_m, vehicle_speed_m_s)

    clearance_distance_m = intersection_width_m + vehicle_length_m
    raw_all_red_interval_s = clearance_distance_m / vehicle_speed_m_s
    all_red_interval_s = min(round(raw_all_red_interval_s, 1), 6.0)

    return {
        "clearance_distance_m": round(clearance_distance_m, 2),
        "raw_all_red_interval_s": round(raw_all_red_interval_s, 2),
        "all_red_interval_s": round(all_red_interval_s, 2),
    }
