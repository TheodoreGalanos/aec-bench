# ABOUTME: HEC-22 roadway gutter spread computation engine for triangular cross-sections.
# ABOUTME: Calculates spread width and curb flow depth from Manning's equation for pavement gutters.

import math

# Manning's formula constant for SI units (m, s).
# HEC-22 Equation 4-2: Q = (K_u / n) * Sx^(5/3) * S_L^(1/2) * T^(8/3)
_K_U = 0.376


def _validate_inputs(
    gutter_flow_m3_s: float,
    cross_slope_pct: float,
    longitudinal_slope_pct: float,
    mannings_n: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if gutter_flow_m3_s <= 0:
        msg = "gutter_flow_m3_s must be > 0"
        raise ValueError(msg)
    if cross_slope_pct <= 0:
        msg = "cross_slope_pct must be > 0"
        raise ValueError(msg)
    if longitudinal_slope_pct <= 0:
        msg = "longitudinal_slope_pct must be > 0"
        raise ValueError(msg)
    if mannings_n <= 0:
        msg = "mannings_n must be > 0"
        raise ValueError(msg)


def compute(
    gutter_flow_m3_s: float,
    cross_slope_pct: float,
    longitudinal_slope_pct: float,
    mannings_n: float,
) -> dict[str, float]:
    """Compute roadway gutter spread width and curb depth per HEC-22.

    Uses Manning's equation for a triangular gutter cross-section:
        Q = (K_u / n) * Sx^(5/3) * S_L^(1/2) * T^(8/3)

    Solved for spread T:
        T = (Q * n / (K_u * Sx^(5/3) * S_L^(1/2)))^(3/8)

    Flow depth at curb:
        d = T * Sx

    Slopes are provided in percent and converted to m/m internally.

    Returns a dict with keys: spread_width_m, curb_depth_m.
    """
    _validate_inputs(
        gutter_flow_m3_s,
        cross_slope_pct,
        longitudinal_slope_pct,
        mannings_n,
    )

    # Convert slopes from percentage to dimensionless (m/m)
    sx = cross_slope_pct / 100.0
    sl = longitudinal_slope_pct / 100.0

    # Solve for spread width T
    # T = (Q * n / (K_u * Sx^(5/3) * S_L^(1/2)))^(3/8)
    numerator = gutter_flow_m3_s * mannings_n
    denominator = _K_U * sx ** (5.0 / 3.0) * math.sqrt(sl)
    spread_width_m = (numerator / denominator) ** (3.0 / 8.0)

    # Flow depth at curb face
    curb_depth_m = spread_width_m * sx

    return {
        "spread_width_m": round(spread_width_m, 2),
        "curb_depth_m": round(curb_depth_m, 2),
    }
