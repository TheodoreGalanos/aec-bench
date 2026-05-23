# ABOUTME: Computes average lift interval from round-trip time and lift count.
# ABOUTME: Reports service interval and arrivals per five-minute period.


def _validate_inputs(round_trip_time_s: float, lift_count: float) -> None:
    """Raise ValueError for invalid input parameters."""
    if round_trip_time_s <= 0:
        msg = "round_trip_time_s must be > 0"
        raise ValueError(msg)
    if lift_count <= 0:
        msg = "lift_count must be > 0"
        raise ValueError(msg)


def compute(round_trip_time_s: float, lift_count: float) -> dict[str, float]:
    """Compute average interval between lift arrivals."""
    _validate_inputs(round_trip_time_s, lift_count)

    interval_s = round_trip_time_s / lift_count
    arrivals_per_5min = 300.0 / interval_s

    return {
        "interval_s": round(interval_s, 2),
        "arrivals_per_5min": round(arrivals_per_5min, 2),
    }
