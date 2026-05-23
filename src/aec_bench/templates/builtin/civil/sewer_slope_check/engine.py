# ABOUTME: Sewer slope adequacy computation engine using Manning's equation.
# ABOUTME: Calculates full-pipe velocity, flow capacity, and self-cleansing compliance.

import math

# WSAA WSA 02 velocity limits for gravity sewers.
_MIN_VELOCITY_M_S = 0.6
_MAX_VELOCITY_M_S = 4.0


def _validate_inputs(
    pipe_diameter_mm: float,
    pipe_slope_pct: float,
    mannings_n: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if pipe_diameter_mm <= 0:
        msg = "pipe_diameter_mm must be > 0"
        raise ValueError(msg)
    if pipe_slope_pct <= 0:
        msg = "pipe_slope_pct must be > 0"
        raise ValueError(msg)
    if mannings_n <= 0:
        msg = "mannings_n must be > 0"
        raise ValueError(msg)


def compute(
    pipe_diameter_mm: float,
    pipe_slope_pct: float,
    mannings_n: float,
) -> dict[str, float]:
    """Compute full-pipe velocity and capacity, then check self-cleansing compliance.

    Uses Manning's equation for a full circular pipe:
      - Hydraulic radius: R_h = D / 4
      - Velocity: V = (1/n) * R_h^(2/3) * S^(1/2)
      - Capacity: Q = V * A = V * pi * (D/2)^2

    Self-cleansing compliance per WSAA WSA 02:
      - Minimum velocity: 0.6 m/s
      - Maximum velocity: 4.0 m/s (scour limit)
      - compliance = 1.0 if 0.6 <= V <= 4.0, else 0.0

    Returns a dict with keys: full_pipe_velocity_m_s, full_pipe_capacity_l_s,
    compliance.
    """
    _validate_inputs(pipe_diameter_mm, pipe_slope_pct, mannings_n)

    # Convert diameter from mm to m
    diameter_m = pipe_diameter_mm / 1000.0

    # Convert slope from percentage to fraction (m/m)
    slope_fraction = pipe_slope_pct / 100.0

    # Full-pipe hydraulic radius: R_h = D / 4
    hydraulic_radius = diameter_m / 4.0

    # Manning's equation: V = (1/n) * R_h^(2/3) * S^(1/2)
    velocity = (1.0 / mannings_n) * hydraulic_radius ** (2.0 / 3.0) * math.sqrt(slope_fraction)

    # Full-pipe cross-sectional area: A = pi * (D/2)^2
    area_m2 = math.pi * (diameter_m / 2.0) ** 2

    # Flow capacity: Q = V * A (m^3/s), then convert to L/s
    capacity_m3_s = velocity * area_m2
    capacity_l_s = capacity_m3_s * 1000.0

    # Self-cleansing compliance per WSAA WSA 02
    compliant = 1.0 if _MIN_VELOCITY_M_S <= velocity <= _MAX_VELOCITY_M_S else 0.0

    return {
        "full_pipe_velocity_m_s": round(velocity, 2),
        "full_pipe_capacity_l_s": round(capacity_l_s, 2),
        "compliance": round(compliant, 2),
    }
