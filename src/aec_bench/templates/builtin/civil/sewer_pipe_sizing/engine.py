# ABOUTME: Gravity sewer pipe sizing engine using Manning's equation.
# ABOUTME: Selects smallest standard diameter for design flow, computes velocity and depth ratio.

import math

# Standard gravity sewer pipe diameters (mm) per WSAA WSA 02 / AS 4130.
_STANDARD_DIAMETERS_MM: list[int] = [
    150,
    225,
    300,
    375,
    450,
    525,
    600,
    675,
    750,
    900,
    1050,
    1200,
]


def _validate_inputs(
    design_flow_l_s: float,
    upstream_invert_m: float,
    downstream_invert_m: float,
    pipe_length_m: float,
    mannings_n: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if design_flow_l_s <= 0:
        msg = "design_flow_l_s must be > 0"
        raise ValueError(msg)
    if pipe_length_m <= 0:
        msg = "pipe_length_m must be > 0"
        raise ValueError(msg)
    if mannings_n <= 0:
        msg = "mannings_n must be > 0"
        raise ValueError(msg)


def _compute_slope(
    upstream_invert_m: float,
    downstream_invert_m: float,
    pipe_length_m: float,
) -> float:
    """Compute pipe slope as a positive fraction (m/m).

    Uses the absolute difference between inverts so that the result is always
    positive regardless of which invert is higher.
    """
    return abs(upstream_invert_m - downstream_invert_m) / pipe_length_m


def _full_pipe_capacity_m3_s(
    diameter_m: float,
    mannings_n: float,
    slope: float,
) -> float:
    """Compute full-pipe capacity (m^3/s) using Manning's equation.

    Q_full = (1/n) * (pi * D^2 / 4) * (D / 4)^(2/3) * S^(1/2)
    """
    area = math.pi * diameter_m**2 / 4.0
    hydraulic_radius = diameter_m / 4.0
    return (1.0 / mannings_n) * area * hydraulic_radius ** (2.0 / 3.0) * math.sqrt(slope)


def compute(
    design_flow_l_s: float,
    upstream_invert_m: float,
    downstream_invert_m: float,
    pipe_length_m: float,
    mannings_n: float,
) -> dict[str, float]:
    """Size a gravity sewer pipe for a given design flow.

    Procedure:
      1. Compute pipe slope from invert levels and length (clamped positive).
      2. Iterate standard diameters, compute full-pipe capacity via Manning's.
      3. Select smallest diameter where Q_full >= design flow.
      4. Compute full-pipe velocity and flow depth ratio (Q/Q_full proxy).

    Returns a dict with keys: selected_diameter_mm, pipe_slope_pct,
    full_pipe_velocity_m_s, flow_depth_ratio.
    """
    _validate_inputs(
        design_flow_l_s,
        upstream_invert_m,
        downstream_invert_m,
        pipe_length_m,
        mannings_n,
    )

    # Slope as a fraction (m/m), guaranteed positive via abs()
    slope = _compute_slope(upstream_invert_m, downstream_invert_m, pipe_length_m)

    # Guard against zero slope (flat pipe cannot convey flow by gravity)
    if slope == 0.0:
        msg = "pipe slope is zero; upstream and downstream inverts are equal"
        raise ValueError(msg)

    # Convert design flow from L/s to m^3/s for comparison
    design_flow_m3_s = design_flow_l_s / 1000.0

    # Select smallest standard diameter whose full-pipe capacity >= design flow
    selected_diameter_mm: int | None = None
    q_full: float = 0.0

    for diameter_mm in _STANDARD_DIAMETERS_MM:
        diameter_m = diameter_mm / 1000.0
        q_full = _full_pipe_capacity_m3_s(diameter_m, mannings_n, slope)
        if q_full >= design_flow_m3_s:
            selected_diameter_mm = diameter_mm
            break

    # If no standard diameter is large enough, select the largest available
    if selected_diameter_mm is None:
        selected_diameter_mm = _STANDARD_DIAMETERS_MM[-1]
        diameter_m = selected_diameter_mm / 1000.0
        q_full = _full_pipe_capacity_m3_s(diameter_m, mannings_n, slope)

    # Full-pipe velocity: V = Q_full / A
    diameter_m = selected_diameter_mm / 1000.0
    area = math.pi * diameter_m**2 / 4.0
    velocity = q_full / area

    # Flow depth ratio approximation: d/D ~ Q_design / Q_full
    flow_depth_ratio = design_flow_m3_s / q_full

    # Slope as a percentage
    slope_pct = slope * 100.0

    return {
        "selected_diameter_mm": round(float(selected_diameter_mm), 2),
        "pipe_slope_pct": round(slope_pct, 2),
        "full_pipe_velocity_m_s": round(velocity, 2),
        "flow_depth_ratio": round(flow_depth_ratio, 2),
    }
