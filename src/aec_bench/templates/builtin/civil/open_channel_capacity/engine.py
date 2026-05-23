# ABOUTME: Manning's equation open channel capacity engine for trapezoidal and rectangular channels.
# ABOUTME: Computes flow area, wetted perimeter, hydraulic radius, velocity, capacity, and Froude number.

import math

# Gravitational acceleration in m/s².
_G = 9.81


def _validate_inputs(
    bottom_width_m: float,
    flow_depth_m: float,
    side_slope_z: float,
    mannings_n: float,
    channel_slope_m_per_m: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if bottom_width_m <= 0:
        msg = "bottom_width_m must be > 0"
        raise ValueError(msg)
    if flow_depth_m <= 0:
        msg = "flow_depth_m must be > 0"
        raise ValueError(msg)
    if side_slope_z < 0:
        msg = "side_slope_z must be >= 0"
        raise ValueError(msg)
    if mannings_n <= 0:
        msg = "mannings_n must be > 0"
        raise ValueError(msg)
    if channel_slope_m_per_m <= 0:
        msg = "channel_slope_m_per_m must be > 0"
        raise ValueError(msg)


def _channel_geometry(
    bottom_width_m: float,
    flow_depth_m: float,
    side_slope_z: float,
) -> tuple[float, float, float, float]:
    """Calculate geometric properties of a trapezoidal/rectangular channel.

    For rectangular channels, side_slope_z = 0.
    For trapezoidal channels, side_slope_z is the horizontal run per unit
    vertical rise (z:1, H:V).

    Returns (flow_area, wetted_perimeter, hydraulic_radius, top_width).
    """
    b = bottom_width_m
    y = flow_depth_m
    z = side_slope_z

    # Trapezoidal cross-section area: A = (b + z*y) * y
    # Reduces to A = b*y for rectangular (z = 0)
    flow_area = (b + z * y) * y

    # Wetted perimeter: P = b + 2*y*sqrt(1 + z^2)
    # Reduces to P = b + 2*y for rectangular (z = 0)
    wetted_perimeter = b + 2.0 * y * math.sqrt(1.0 + z**2)

    hydraulic_radius = flow_area / wetted_perimeter

    # Top width: T = b + 2*z*y
    top_width = b + 2.0 * z * y

    return flow_area, wetted_perimeter, hydraulic_radius, top_width


def compute(
    bottom_width_m: float,
    flow_depth_m: float,
    side_slope_z: float,
    mannings_n: float,
    channel_slope_m_per_m: float,
) -> dict[str, float]:
    """Compute open channel flow capacity using Manning's equation.

    Manning's equation (SI units): V = (1/n) * R^(2/3) * S^(1/2)
    Flow capacity: Q = V * A
    Froude number: Fr = V / sqrt(g * D_h) where D_h = A / T (hydraulic depth)

    side_slope_z is the horizontal:vertical ratio. Use 0 for rectangular channels.

    Returns a dict with keys: flow_area_m2, wetted_perimeter_m,
    hydraulic_radius_m, flow_velocity_m_s, flow_capacity_m3_s, froude_number.
    """
    _validate_inputs(
        bottom_width_m,
        flow_depth_m,
        side_slope_z,
        mannings_n,
        channel_slope_m_per_m,
    )

    flow_area, wetted_perimeter, hydraulic_radius, top_width = _channel_geometry(
        bottom_width_m,
        flow_depth_m,
        side_slope_z,
    )

    # Manning's equation: V = (1/n) * R^(2/3) * S^(1/2)
    velocity = (1.0 / mannings_n) * hydraulic_radius ** (2.0 / 3.0) * math.sqrt(channel_slope_m_per_m)

    # Flow capacity: Q = V * A
    capacity = velocity * flow_area

    # Froude number: Fr = V / sqrt(g * D_h)
    # Hydraulic depth D_h = A / T (top width)
    hydraulic_depth = flow_area / top_width
    froude_number = velocity / math.sqrt(_G * hydraulic_depth)

    return {
        "flow_area_m2": round(flow_area, 2),
        "wetted_perimeter_m": round(wetted_perimeter, 2),
        "hydraulic_radius_m": round(hydraulic_radius, 2),
        "flow_velocity_m_s": round(velocity, 2),
        "flow_capacity_m3_s": round(capacity, 2),
        "froude_number": round(froude_number, 2),
    }
