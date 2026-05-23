# ABOUTME: Hydraulic retention time computation engine for treatment units.
# ABOUTME: Calculates HRT from tank volume and flow rate in days and hours.


def _validate_inputs(reactor_volume_m3: float, flow_rate_m3_d: float) -> None:
    """Raise ValueError for invalid input parameters."""
    if reactor_volume_m3 <= 0:
        msg = "reactor_volume_m3 must be > 0"
        raise ValueError(msg)
    if flow_rate_m3_d <= 0:
        msg = "flow_rate_m3_d must be > 0"
        raise ValueError(msg)


def compute(reactor_volume_m3: float, flow_rate_m3_d: float) -> dict[str, float]:
    """Compute hydraulic retention time from reactor volume and flow.

    Returns a dict with keys: hrt_days, hrt_hours, flow_rate_m3_h.
    """
    _validate_inputs(reactor_volume_m3, flow_rate_m3_d)

    hrt_days = reactor_volume_m3 / flow_rate_m3_d
    hrt_hours = hrt_days * 24.0
    flow_rate_m3_h = flow_rate_m3_d / 24.0

    return {
        "hrt_days": round(hrt_days, 2),
        "hrt_hours": round(hrt_hours, 2),
        "flow_rate_m3_h": round(flow_rate_m3_h, 2),
    }
