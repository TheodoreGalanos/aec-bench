# ABOUTME: Pump affinity law computation engine for variable-speed pump checks.
# ABOUTME: Calculates flow, head, and power at a new rotational speed.


def _validate_inputs(
    original_speed_rpm: float,
    new_speed_rpm: float,
    original_flow_l_s: float,
    original_head_m: float,
    original_power_kw: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if original_speed_rpm <= 0:
        msg = "original_speed_rpm must be > 0"
        raise ValueError(msg)
    if new_speed_rpm <= 0:
        msg = "new_speed_rpm must be > 0"
        raise ValueError(msg)
    if original_flow_l_s <= 0:
        msg = "original_flow_l_s must be > 0"
        raise ValueError(msg)
    if original_head_m <= 0:
        msg = "original_head_m must be > 0"
        raise ValueError(msg)
    if original_power_kw <= 0:
        msg = "original_power_kw must be > 0"
        raise ValueError(msg)


def compute(
    original_speed_rpm: float,
    new_speed_rpm: float,
    original_flow_l_s: float,
    original_head_m: float,
    original_power_kw: float,
) -> dict[str, float]:
    """Compute pump performance at a changed speed using affinity laws.

    Returns a dict with keys: speed_ratio, new_flow_l_s, new_head_m, new_power_kw.
    """
    _validate_inputs(
        original_speed_rpm,
        new_speed_rpm,
        original_flow_l_s,
        original_head_m,
        original_power_kw,
    )

    speed_ratio = new_speed_rpm / original_speed_rpm
    new_flow = original_flow_l_s * speed_ratio
    new_head = original_head_m * speed_ratio**2
    new_power = original_power_kw * speed_ratio**3

    return {
        "speed_ratio": round(speed_ratio, 2),
        "new_flow_l_s": round(new_flow, 2),
        "new_head_m": round(new_head, 2),
        "new_power_kw": round(new_power, 2),
    }
