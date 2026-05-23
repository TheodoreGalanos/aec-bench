# ABOUTME: Computes pedestrian clearance interval from crosswalk length and walking speed.
# ABOUTME: Uses a deterministic flashing-clearance time relation for signal timing.

import math


def _validate_inputs(crosswalk_length_m: float, walking_speed_m_s: float) -> None:
    """Raise ValueError for invalid input parameters."""
    if crosswalk_length_m <= 0:
        msg = "crosswalk_length_m must be > 0"
        raise ValueError(msg)
    if walking_speed_m_s <= 0:
        msg = "walking_speed_m_s must be > 0"
        raise ValueError(msg)


def compute(crosswalk_length_m: float, walking_speed_m_s: float) -> dict[str, float]:
    """Compute pedestrian clearance interval and whole-second rounded value."""
    _validate_inputs(crosswalk_length_m, walking_speed_m_s)

    pedestrian_clearance_time_s = crosswalk_length_m / walking_speed_m_s
    pedestrian_clearance_rounded_s = math.ceil(pedestrian_clearance_time_s)

    return {
        "pedestrian_clearance_time_s": round(pedestrian_clearance_time_s, 2),
        "pedestrian_clearance_rounded_s": round(float(pedestrian_clearance_rounded_s), 2),
    }
