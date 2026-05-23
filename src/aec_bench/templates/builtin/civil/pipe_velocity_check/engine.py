# ABOUTME: Pipe velocity compliance check computation engine.
# ABOUTME: Calculates flow velocity and checks against AS/NZS 3500.1 service-type limits.

import math
from typing import Literal

# Velocity limits per service type from AS/NZS 3500.1.
# Each entry: (min_velocity_m_s, max_velocity_m_s)
_VELOCITY_LIMITS: dict[str, tuple[float, float]] = {
    "water_supply": (0.6, 3.0),
    "sewer_gravity": (0.6, 4.0),
    "stormwater": (0.6, 6.0),
    "fire_services": (0.5, 4.0),
}


def _validate_inputs(
    pipe_diameter_mm: float,
    flow_rate_l_s: float,
    service_type: str,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if pipe_diameter_mm <= 0:
        msg = "pipe_diameter_mm must be > 0"
        raise ValueError(msg)
    if flow_rate_l_s <= 0:
        msg = "flow_rate_l_s must be > 0"
        raise ValueError(msg)
    if service_type not in _VELOCITY_LIMITS:
        msg = f"service_type must be one of {list(_VELOCITY_LIMITS.keys())}, got '{service_type}'"
        raise ValueError(msg)


def compute(
    pipe_diameter_mm: float,
    flow_rate_l_s: float,
    service_type: Literal["water_supply", "sewer_gravity", "stormwater", "fire_services"],
) -> dict[str, float]:
    """Compute pipe flow velocity and check compliance against AS/NZS 3500.1 limits.

    Steps:
      1. Convert pipe diameter from mm to m
      2. Calculate cross-sectional area A = pi * (D/2)^2
      3. Convert flow rate from L/s to m^3/s
      4. Calculate velocity V = Q / A
      5. Look up min and max velocity limits for the service type
      6. Determine compliance (1.0 if within limits, 0.0 if outside)

    Returns a dict with keys: velocity_m_s, compliance.
    """
    _validate_inputs(pipe_diameter_mm, flow_rate_l_s, service_type)

    # Convert diameter from mm to m
    diameter_m = pipe_diameter_mm / 1000.0

    # Cross-sectional area of the pipe
    area_m2 = math.pi * (diameter_m / 2.0) ** 2

    # Convert flow rate from L/s to m^3/s
    flow_rate_m3_s = flow_rate_l_s / 1000.0

    # Flow velocity
    velocity = flow_rate_m3_s / area_m2

    # Look up velocity limits for this service type
    min_vel, max_vel = _VELOCITY_LIMITS[service_type]

    # Compliance: 1.0 if velocity is within [min, max], 0.0 otherwise
    compliant = 1.0 if min_vel <= velocity <= max_vel else 0.0

    return {
        "velocity_m_s": round(velocity, 2),
        "compliance": round(compliant, 2),
    }
