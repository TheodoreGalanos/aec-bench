# ABOUTME: Horizontal curve element computation engine for simple circular curves.
# ABOUTME: Implements tangent, arc, external, mid-ordinate, and chainage formulas per AGRD Part 3.

import math


def _validate_inputs(
    curve_radius_m: float,
    deflection_angle_deg: float,
    ip_chainage_m: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if curve_radius_m <= 0:
        msg = "curve_radius_m must be > 0"
        raise ValueError(msg)
    if deflection_angle_deg <= 0:
        msg = "deflection_angle_deg must be > 0"
        raise ValueError(msg)
    if deflection_angle_deg >= 180:
        msg = "deflection_angle_deg must be < 180"
        raise ValueError(msg)
    if ip_chainage_m < 0:
        msg = "ip_chainage_m must be >= 0"
        raise ValueError(msg)


def _tangent_length(radius: float, delta_rad: float) -> float:
    """Calculate tangent length T = R * tan(delta/2)."""
    return radius * math.tan(delta_rad / 2.0)


def _arc_length(radius: float, delta_rad: float) -> float:
    """Calculate arc length L = R * delta (delta in radians)."""
    return radius * delta_rad


def _external_distance(radius: float, delta_rad: float) -> float:
    """Calculate external distance E = R * (1/cos(delta/2) - 1)."""
    return radius * (1.0 / math.cos(delta_rad / 2.0) - 1.0)


def _mid_ordinate(radius: float, delta_rad: float) -> float:
    """Calculate mid-ordinate M = R * (1 - cos(delta/2))."""
    return radius * (1.0 - math.cos(delta_rad / 2.0))


def compute(
    curve_radius_m: float,
    deflection_angle_deg: float,
    ip_chainage_m: float,
) -> dict[str, float]:
    """Compute horizontal curve elements for a simple circular curve.

    Returns a dict with keys: tangent_length_m, arc_length_m,
    external_distance_m, mid_ordinate_m, pc_chainage_m, pt_chainage_m.
    """
    _validate_inputs(curve_radius_m, deflection_angle_deg, ip_chainage_m)

    delta_rad = math.radians(deflection_angle_deg)

    tangent = _tangent_length(curve_radius_m, delta_rad)
    arc = _arc_length(curve_radius_m, delta_rad)
    external = _external_distance(curve_radius_m, delta_rad)
    mid_ord = _mid_ordinate(curve_radius_m, delta_rad)

    pc_chainage = ip_chainage_m - tangent
    pt_chainage = pc_chainage + arc

    return {
        "tangent_length_m": round(tangent, 2),
        "arc_length_m": round(arc, 2),
        "external_distance_m": round(external, 2),
        "mid_ordinate_m": round(mid_ord, 2),
        "pc_chainage_m": round(pc_chainage, 2),
        "pt_chainage_m": round(pt_chainage, 2),
    }
