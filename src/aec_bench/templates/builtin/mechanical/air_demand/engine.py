# ABOUTME: Compressed air demand computation engine for plant services.
# ABOUTME: Sums connected tool demand and applies explicit diversity factors.


def _validate_inputs(
    tool_1_flow_l_s: float,
    tool_1_quantity: float,
    tool_2_flow_l_s: float,
    tool_2_quantity: float,
    tool_3_flow_l_s: float,
    tool_3_quantity: float,
    simultaneity_factor: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "tool_1_flow_l_s": tool_1_flow_l_s,
        "tool_1_quantity": tool_1_quantity,
        "tool_2_flow_l_s": tool_2_flow_l_s,
        "tool_2_quantity": tool_2_quantity,
        "tool_3_flow_l_s": tool_3_flow_l_s,
        "tool_3_quantity": tool_3_quantity,
    }.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)
    if not 0 < simultaneity_factor <= 1:
        msg = "simultaneity_factor must be > 0 and <= 1"
        raise ValueError(msg)


def compute(
    tool_1_flow_l_s: float,
    tool_1_quantity: float,
    tool_2_flow_l_s: float,
    tool_2_quantity: float,
    tool_3_flow_l_s: float,
    tool_3_quantity: float,
    simultaneity_factor: float,
) -> dict[str, float]:
    """Compute connected and simultaneous compressed air demand.

    Returns a dict with keys: connected_demand_l_s, simultaneous_demand_l_s,
    connected_demand_m3_min, simultaneous_demand_m3_min.
    """
    _validate_inputs(
        tool_1_flow_l_s,
        tool_1_quantity,
        tool_2_flow_l_s,
        tool_2_quantity,
        tool_3_flow_l_s,
        tool_3_quantity,
        simultaneity_factor,
    )

    connected = (
        tool_1_flow_l_s * tool_1_quantity + tool_2_flow_l_s * tool_2_quantity + tool_3_flow_l_s * tool_3_quantity
    )
    simultaneous = connected * simultaneity_factor

    return {
        "connected_demand_l_s": round(connected, 2),
        "simultaneous_demand_l_s": round(simultaneous, 2),
        "connected_demand_m3_min": round(connected * 0.06, 2),
        "simultaneous_demand_m3_min": round(simultaneous * 0.06, 2),
    }
