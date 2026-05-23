# ABOUTME: Computes PoE switch power requirement and headroom margin.
# ABOUTME: Uses device count, per-device draw, switch budget, and headroom allowance.


def _validate_inputs(
    device_count: float,
    power_draw_per_device_w: float,
    switch_poe_budget_w: float,
    required_headroom_pct: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if device_count <= 0:
        msg = "device_count must be > 0"
        raise ValueError(msg)
    if power_draw_per_device_w <= 0:
        msg = "power_draw_per_device_w must be > 0"
        raise ValueError(msg)
    if switch_poe_budget_w <= 0:
        msg = "switch_poe_budget_w must be > 0"
        raise ValueError(msg)
    if required_headroom_pct < 0:
        msg = "required_headroom_pct must be >= 0"
        raise ValueError(msg)


def compute(
    device_count: float,
    power_draw_per_device_w: float,
    switch_poe_budget_w: float,
    required_headroom_pct: float,
) -> dict[str, float]:
    """Compute total PoE demand, utilization, and headroom margin."""
    _validate_inputs(
        device_count,
        power_draw_per_device_w,
        switch_poe_budget_w,
        required_headroom_pct,
    )

    total_power_requirement_w = device_count * power_draw_per_device_w
    utilization_pct = total_power_requirement_w / switch_poe_budget_w * 100.0
    available_headroom_w = switch_poe_budget_w - total_power_requirement_w
    required_headroom_w = total_power_requirement_w * required_headroom_pct / 100.0
    headroom_margin_w = available_headroom_w - required_headroom_w

    return {
        "total_power_requirement_w": round(total_power_requirement_w, 2),
        "utilization_pct": round(utilization_pct, 2),
        "available_headroom_w": round(available_headroom_w, 2),
        "required_headroom_w": round(required_headroom_w, 2),
        "headroom_margin_w": round(headroom_margin_w, 2),
    }
