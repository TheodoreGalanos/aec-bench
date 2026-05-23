# ABOUTME: Uplift pressure computation engine for concrete gravity dam foundations.
# ABOUTME: Calculates bilinear uplift distribution and total uplift force per USACE EM 1110-2-2200.


# Unit weight of water in kN/m3.
_GAMMA_W = 9.81


def _validate_inputs(
    headwater_depth_m: float,
    tailwater_depth_m: float,
    base_width_m: float,
    drain_distance_m: float,
    drain_efficiency_pct: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if headwater_depth_m <= 0:
        msg = "headwater_depth_m must be > 0"
        raise ValueError(msg)
    if tailwater_depth_m < 0:
        msg = "tailwater_depth_m must be >= 0"
        raise ValueError(msg)
    if tailwater_depth_m >= headwater_depth_m:
        msg = "tailwater_depth_m must be < headwater_depth_m"
        raise ValueError(msg)
    if base_width_m <= 0:
        msg = "base_width_m must be > 0"
        raise ValueError(msg)
    if drain_distance_m <= 0:
        msg = "drain_distance_m must be > 0"
        raise ValueError(msg)
    if drain_distance_m >= base_width_m:
        msg = "drain_distance_m must be < base_width_m"
        raise ValueError(msg)
    if drain_efficiency_pct < 0 or drain_efficiency_pct > 100:
        msg = "drain_efficiency_pct must be between 0 and 100 inclusive"
        raise ValueError(msg)


def _upstream_pressure(headwater_depth_m: float) -> float:
    """Compute uplift pressure at the upstream face.

    P_upstream = gamma_w * H_u (kPa)
    Full hydrostatic pressure from the headwater pool.
    """
    return _GAMMA_W * headwater_depth_m


def _drain_pressure(
    headwater_depth_m: float,
    tailwater_depth_m: float,
    drain_efficiency_pct: float,
) -> float:
    """Compute uplift pressure at the drain line.

    P_drain = gamma_w * (H_d + (1 - eta) * (H_u - H_d))
    where eta = drain_efficiency_pct / 100.
    Drain efficiency of 1.0 means full relief to tailwater level;
    efficiency of 0.0 means no drain effect (linear interpolation).
    """
    eta = drain_efficiency_pct / 100.0
    return _GAMMA_W * (tailwater_depth_m + (1.0 - eta) * (headwater_depth_m - tailwater_depth_m))


def _downstream_pressure(tailwater_depth_m: float) -> float:
    """Compute uplift pressure at the downstream face.

    P_downstream = gamma_w * H_d (kPa)
    Full hydrostatic pressure from the tailwater pool.
    """
    return _GAMMA_W * tailwater_depth_m


def _total_uplift_force(
    p_upstream: float,
    p_drain: float,
    p_downstream: float,
    drain_distance_m: float,
    base_width_m: float,
) -> float:
    """Compute total uplift force per unit length of dam using trapezoidal integration.

    U = 0.5 * (P_upstream + P_drain) * d_drain
      + 0.5 * (P_drain + P_downstream) * (B - d_drain)
    Result in kN/m (pressures in kPa, distances in m).
    """
    upstream_segment = 0.5 * (p_upstream + p_drain) * drain_distance_m
    downstream_segment = 0.5 * (p_drain + p_downstream) * (base_width_m - drain_distance_m)
    return upstream_segment + downstream_segment


def compute(
    headwater_depth_m: float,
    tailwater_depth_m: float,
    base_width_m: float,
    drain_distance_m: float,
    drain_efficiency_pct: float,
) -> dict[str, float]:
    """Compute uplift pressure distribution and total uplift force on a gravity dam foundation.

    Uses the simplified bilinear distribution per USACE EM 1110-2-2200:
    - Upstream face: full headwater pressure P_upstream = gamma_w * H_u
    - Drain line: reduced pressure P_drain = gamma_w * (H_d + (1 - eta) * (H_u - H_d))
    - Downstream face: full tailwater pressure P_downstream = gamma_w * H_d
    - Total uplift force: trapezoidal integration across the base

    Returns a dict with keys: upstream_pressure_kpa, drain_pressure_kpa,
    downstream_pressure_kpa, total_uplift_force_kn_m.
    """
    _validate_inputs(
        headwater_depth_m,
        tailwater_depth_m,
        base_width_m,
        drain_distance_m,
        drain_efficiency_pct,
    )

    p_upstream = _upstream_pressure(headwater_depth_m)
    p_drain = _drain_pressure(headwater_depth_m, tailwater_depth_m, drain_efficiency_pct)
    p_downstream = _downstream_pressure(tailwater_depth_m)

    total_uplift = _total_uplift_force(
        p_upstream,
        p_drain,
        p_downstream,
        drain_distance_m,
        base_width_m,
    )

    return {
        "upstream_pressure_kpa": round(p_upstream, 2),
        "drain_pressure_kpa": round(p_drain, 2),
        "downstream_pressure_kpa": round(p_downstream, 2),
        "total_uplift_force_kn_m": round(total_uplift, 2),
    }
