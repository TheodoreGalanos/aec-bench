# ABOUTME: Manning's equation pipe capacity engine for circular pipes.
# ABOUTME: Computes flow area, hydraulic radius, velocity, and capacity.

import math


def _validate_inputs(
    pipe_diameter_m: float,
    mannings_n: float,
    slope_m_per_m: float,
    flow_depth_ratio: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if pipe_diameter_m <= 0:
        msg = "pipe_diameter_m must be > 0"
        raise ValueError(msg)
    if mannings_n <= 0:
        msg = "mannings_n must be > 0"
        raise ValueError(msg)
    if slope_m_per_m <= 0:
        msg = "slope_m_per_m must be > 0"
        raise ValueError(msg)
    if flow_depth_ratio <= 0:
        msg = "flow_depth_ratio must be > 0"
        raise ValueError(msg)
    if flow_depth_ratio > 1.0:
        msg = "flow_depth_ratio must be <= 1.0"
        raise ValueError(msg)


def _circular_pipe_geometry(
    diameter: float,
    depth_ratio: float,
) -> tuple[float, float, float]:
    """Calculate flow area, wetted perimeter, and hydraulic radius for a circular pipe.

    Uses the central angle method:
      theta = 2 * acos(1 - 2 * d/D)
      A = (D^2 / 8) * (theta - sin(theta))
      P = (D / 2) * theta
      R = A / P

    For full pipe (d/D = 1.0), theta = 2*pi, giving the standard
    full-pipe values: A = pi*D^2/4, P = pi*D, R = D/4.

    Returns (flow_area, wetted_perimeter, hydraulic_radius).
    """
    d = diameter

    if depth_ratio >= 1.0:
        # Full pipe: use exact closed-form to avoid floating-point edge cases
        area = math.pi * d**2 / 4.0
        perimeter = math.pi * d
    else:
        # Central angle subtended by the water surface
        theta = 2.0 * math.acos(1.0 - 2.0 * depth_ratio)
        area = (d**2 / 8.0) * (theta - math.sin(theta))
        perimeter = (d / 2.0) * theta

    hydraulic_radius = area / perimeter
    return area, perimeter, hydraulic_radius


def compute(
    pipe_diameter_m: float,
    mannings_n: float,
    slope_m_per_m: float,
    flow_depth_ratio: float = 1.0,
) -> dict[str, float]:
    """Compute flow capacity in a circular pipe using Manning's equation.

    Manning's equation (SI units): Q = (1/n) * A * R^(2/3) * S^(1/2)
    where n = roughness coefficient, A = flow area, R = hydraulic radius,
    S = longitudinal slope.

    Returns a dict with keys: flow_area_m2, hydraulic_radius_m,
    flow_velocity_m_s, flow_capacity_m3_s.
    """
    _validate_inputs(pipe_diameter_m, mannings_n, slope_m_per_m, flow_depth_ratio)

    area, _perimeter, hydraulic_radius = _circular_pipe_geometry(
        pipe_diameter_m,
        flow_depth_ratio,
    )

    # Manning's equation: V = (1/n) * R^(2/3) * S^(1/2)
    velocity = (1.0 / mannings_n) * hydraulic_radius ** (2.0 / 3.0) * math.sqrt(slope_m_per_m)

    # Flow capacity: Q = V * A
    capacity = velocity * area

    return {
        "flow_area_m2": round(area, 2),
        "hydraulic_radius_m": round(hydraulic_radius, 2),
        "flow_velocity_m_s": round(velocity, 2),
        "flow_capacity_m3_s": round(capacity, 2),
    }
