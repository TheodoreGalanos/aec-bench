# ABOUTME: Pipe velocity computation engine for hydraulic checks.
# ABOUTME: Calculates velocity from flow and diameter and compares explicit limits.

import math


def _validate_inputs(
    flow_rate_l_s: float,
    pipe_internal_diameter_mm: float,
    minimum_velocity_m_s: float,
    maximum_velocity_m_s: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if flow_rate_l_s < 0:
        msg = "flow_rate_l_s must be >= 0"
        raise ValueError(msg)
    if pipe_internal_diameter_mm <= 0:
        msg = "pipe_internal_diameter_mm must be > 0"
        raise ValueError(msg)
    if minimum_velocity_m_s < 0:
        msg = "minimum_velocity_m_s must be >= 0"
        raise ValueError(msg)
    if maximum_velocity_m_s <= minimum_velocity_m_s:
        msg = "maximum_velocity_m_s must be > minimum_velocity_m_s"
        raise ValueError(msg)


def compute(
    flow_rate_l_s: float,
    pipe_internal_diameter_mm: float,
    minimum_velocity_m_s: float,
    maximum_velocity_m_s: float,
) -> dict[str, float]:
    """Compute pipe velocity and explicit limit checks.

    Returns a dict with keys: pipe_area_m2, velocity_m_s, min_margin_m_s,
    max_margin_m_s, velocity_within_range.
    """
    _validate_inputs(
        flow_rate_l_s,
        pipe_internal_diameter_mm,
        minimum_velocity_m_s,
        maximum_velocity_m_s,
    )

    pipe_area = math.pi / 4.0 * (pipe_internal_diameter_mm / 1000.0) ** 2
    velocity = (flow_rate_l_s / 1000.0) / pipe_area
    min_margin = velocity - minimum_velocity_m_s
    max_margin = maximum_velocity_m_s - velocity
    within_range = 1.0 if minimum_velocity_m_s <= velocity <= maximum_velocity_m_s else 0.0

    return {
        "pipe_area_m2": round(pipe_area, 3),
        "velocity_m_s": round(velocity, 2),
        "min_margin_m_s": round(min_margin, 2),
        "max_margin_m_s": round(max_margin, 2),
        "velocity_within_range": round(within_range, 2),
    }
