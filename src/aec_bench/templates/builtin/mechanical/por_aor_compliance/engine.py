# ABOUTME: POR/AOR compliance computation engine for pump operating ranges.
# ABOUTME: Compares operating flow ratio with explicit preferred and allowable ranges.


def _validate_inputs(
    operating_flow_l_s: float,
    best_efficiency_flow_l_s: float,
    por_min_ratio: float,
    por_max_ratio: float,
    aor_min_ratio: float,
    aor_max_ratio: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if operating_flow_l_s < 0:
        msg = "operating_flow_l_s must be >= 0"
        raise ValueError(msg)
    if best_efficiency_flow_l_s <= 0:
        msg = "best_efficiency_flow_l_s must be > 0"
        raise ValueError(msg)
    if not 0 <= aor_min_ratio <= por_min_ratio <= por_max_ratio <= aor_max_ratio:
        msg = "range ratios must satisfy aor_min <= por_min <= por_max <= aor_max"
        raise ValueError(msg)


def compute(
    operating_flow_l_s: float,
    best_efficiency_flow_l_s: float,
    por_min_ratio: float,
    por_max_ratio: float,
    aor_min_ratio: float,
    aor_max_ratio: float,
) -> dict[str, float]:
    """Compute pump preferred and allowable operating range compliance.

    Returns a dict with keys: flow_ratio, por_margin_low, por_margin_high,
    within_por, within_aor.
    """
    _validate_inputs(
        operating_flow_l_s,
        best_efficiency_flow_l_s,
        por_min_ratio,
        por_max_ratio,
        aor_min_ratio,
        aor_max_ratio,
    )

    flow_ratio = operating_flow_l_s / best_efficiency_flow_l_s
    por_margin_low = flow_ratio - por_min_ratio
    por_margin_high = por_max_ratio - flow_ratio
    within_por = 1.0 if por_min_ratio <= flow_ratio <= por_max_ratio else 0.0
    within_aor = 1.0 if aor_min_ratio <= flow_ratio <= aor_max_ratio else 0.0

    return {
        "flow_ratio": round(flow_ratio, 3),
        "por_margin_low": round(por_margin_low, 3),
        "por_margin_high": round(por_margin_high, 3),
        "within_por": round(within_por, 2),
        "within_aor": round(within_aor, 2),
    }
