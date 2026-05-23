# ABOUTME: Hazen-Williams friction head loss computation engine for pressurised pipe flow.
# ABOUTME: Computes head loss, hydraulic gradient, and flow velocity from pipe geometry and C-factor.

import math


def _validate_inputs(
    flow_rate_l_s: float,
    pipe_diameter_mm: float,
    pipe_length_m: float,
    c_factor: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if flow_rate_l_s <= 0:
        msg = "flow_rate_l_s must be > 0"
        raise ValueError(msg)
    if pipe_diameter_mm <= 0:
        msg = "pipe_diameter_mm must be > 0"
        raise ValueError(msg)
    if pipe_length_m <= 0:
        msg = "pipe_length_m must be > 0"
        raise ValueError(msg)
    if c_factor <= 0:
        msg = "c_factor must be > 0"
        raise ValueError(msg)


def compute(
    flow_rate_l_s: float,
    pipe_diameter_mm: float,
    pipe_length_m: float,
    c_factor: float,
) -> dict[str, float]:
    """Compute friction head loss using the Hazen-Williams equation.

    Uses the SI form of the Hazen-Williams formula:
      hf = (10.67 * L * Q^1.852) / (C^1.852 * D^4.87)

    where Q is in m^3/s and D is in metres.

    Also computes:
      - Hydraulic gradient S = hf / L
      - Flow velocity V = Q / A  where A = pi * D^2 / 4

    Returns a dict with keys: head_loss_m, hydraulic_gradient, flow_velocity_m_s.
    """
    _validate_inputs(flow_rate_l_s, pipe_diameter_mm, pipe_length_m, c_factor)

    # Convert input units to SI for the formula
    flow_rate_m3_s = flow_rate_l_s / 1000.0
    pipe_diameter_m = pipe_diameter_mm / 1000.0

    # Hazen-Williams head loss: hf = 10.67 * L * Q^1.852 / (C^1.852 * D^4.87)
    head_loss = 10.67 * pipe_length_m * flow_rate_m3_s**1.852 / (c_factor**1.852 * pipe_diameter_m**4.87)

    # Hydraulic gradient: S = hf / L
    hydraulic_gradient = head_loss / pipe_length_m

    # Flow velocity: V = Q / A
    area = math.pi * pipe_diameter_m**2 / 4.0
    flow_velocity = flow_rate_m3_s / area

    return {
        "head_loss_m": round(head_loss, 2),
        # Hydraulic gradient is typically O(0.001) for practical pipe designs,
        # so 4 decimal places are needed to preserve meaningful precision.
        "hydraulic_gradient": round(hydraulic_gradient, 4),
        "flow_velocity_m_s": round(flow_velocity, 2),
    }
