# ABOUTME: HDS-5 culvert capacity computation engine for circular culverts.
# ABOUTME: Computes headwater under inlet and outlet control to determine controlling condition.

import math
from typing import Literal

# Composite culvert configuration combining material and inlet geometry.
# Each config maps to (K, M, c, Y, slope_sign, ke, mannings_n) where:
#   K, M = unsubmerged inlet control regression coefficients (Form 1)
#   c, Y = submerged inlet control regression coefficients
#   slope_sign = slope correction factor (-0.5 for most, +0.7 for mitered)
#   ke = entrance loss coefficient for outlet control
#   mannings_n = Manning's roughness coefficient
_CONFIG_TABLE: dict[str, tuple[float, float, float, float, float, float, float]] = {
    "concrete_square_edge_headwall": (0.0098, 2.0, 0.0398, 0.67, -0.5, 0.5, 0.013),
    "concrete_groove_end_headwall": (0.0078, 2.0, 0.0292, 0.74, -0.5, 0.2, 0.013),
    "concrete_groove_end_projecting": (0.0045, 2.0, 0.0317, 0.69, -0.5, 0.2, 0.013),
    "cmp_headwall": (0.0078, 2.0, 0.0379, 0.69, -0.5, 0.5, 0.024),
    "cmp_mitered": (0.0210, 1.33, 0.0463, 0.75, 0.7, 0.7, 0.024),
    "cmp_projecting": (0.0340, 1.50, 0.0553, 0.54, -0.5, 0.9, 0.024),
}

# Gravitational acceleration in m/s^2.
_G = 9.81

# Ku constant for Manning's friction loss in SI units.
# Friction loss: Hf = (Ku * n^2 * L) / R^(4/3) * V^2/(2g)
# Ku = 19.63 converts the US customary HDS-5 formula to SI.
_KU_SI = 19.63


def _validate_inputs(
    culvert_diameter_m: float,
    culvert_length_m: float,
    culvert_slope_m_per_m: float,
    design_flow_m3_s: float,
    culvert_configuration: str,
    tailwater_depth_m: float,
    invert_elevation_m: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if culvert_diameter_m <= 0:
        msg = "culvert_diameter_m must be > 0"
        raise ValueError(msg)
    if culvert_length_m <= 0:
        msg = "culvert_length_m must be > 0"
        raise ValueError(msg)
    if culvert_slope_m_per_m < 0:
        msg = "culvert_slope_m_per_m must be >= 0"
        raise ValueError(msg)
    if design_flow_m3_s <= 0:
        msg = "design_flow_m3_s must be > 0"
        raise ValueError(msg)
    if culvert_configuration not in _CONFIG_TABLE:
        msg = f"culvert_configuration must be one of {list(_CONFIG_TABLE.keys())}, got '{culvert_configuration}'"
        raise ValueError(msg)
    if tailwater_depth_m < 0:
        msg = "tailwater_depth_m must be >= 0"
        raise ValueError(msg)
    if invert_elevation_m < 0:
        msg = "invert_elevation_m must be >= 0"
        raise ValueError(msg)


def _critical_depth_circular(diameter: float, flow: float) -> float:
    """Compute critical depth in a circular pipe using bisection.

    Solves Q^2 * T / (g * A^3) = 1 for depth y, where:
      theta = 2 * acos(1 - 2*y/D)
      A = (D^2/8) * (theta - sin(theta))
      T = D * sin(theta/2)

    Returns critical depth dc (m), capped at diameter D.
    """
    d = diameter

    if flow <= 0:
        return 0.0

    y_lo = 0.001 * d
    y_hi = 0.999 * d

    def _froude_residual(y: float) -> float:
        ratio = y / d
        theta = 2.0 * math.acos(1.0 - 2.0 * ratio)
        area = (d**2 / 8.0) * (theta - math.sin(theta))
        top_width = d * math.sin(theta / 2.0)
        if area <= 0 or top_width <= 0:
            return -1.0
        return (flow**2 * top_width) / (_G * area**3) - 1.0

    # Check if flow exceeds full-pipe critical capacity
    res_hi = _froude_residual(y_hi)
    if res_hi > 0:
        return d

    res_lo = _froude_residual(y_lo)
    if res_lo < 0:
        return y_lo

    # Bisection: 100 iterations gives ~1e-30 precision on D
    for _ in range(100):
        y_mid = (y_lo + y_hi) / 2.0
        res_mid = _froude_residual(y_mid)
        if abs(res_mid) < 1e-8:
            return y_mid
        if res_mid > 0:
            y_lo = y_mid
        else:
            y_hi = y_mid

    return (y_lo + y_hi) / 2.0


def _specific_head_at_critical_depth(diameter: float, flow: float) -> float:
    """Compute Hc/D, the specific head at critical depth divided by diameter.

    Hc = dc + Vc^2/(2g), where dc is critical depth and Vc is velocity at dc.
    """
    dc = _critical_depth_circular(diameter, flow)
    if dc <= 0 or diameter <= 0:
        return 0.0

    # Compute flow area at critical depth
    ratio = min(dc / diameter, 0.999)
    theta = 2.0 * math.acos(1.0 - 2.0 * ratio)
    area_c = (diameter**2 / 8.0) * (theta - math.sin(theta))

    if area_c <= 0:
        return dc / diameter

    vc = flow / area_c
    hc = dc + vc**2 / (2.0 * _G)
    return hc / diameter


def _inlet_control_headwater(
    diameter: float,
    flow: float,
    slope: float,
    configuration: str,
) -> float:
    """Compute headwater depth (m) above inlet invert under inlet control.

    Uses HDS-5 methodology:
    - Unsubmerged (Q/(A*D^0.5) <= 3.5): Form 1 equation
    - Submerged (Q/(A*D^0.5) >= 4.0): submerged equation
    - Transition (3.5 to 4.0): linear interpolation
    """
    area = math.pi * diameter**2 / 4.0
    intensity = flow / (area * math.sqrt(diameter))

    k, m, c, y_coeff, slope_sign, _ke, _n = _CONFIG_TABLE[configuration]

    hc_over_d = _specific_head_at_critical_depth(diameter, flow)

    # Unsubmerged: HW/D = Hc/D + K*(Q/(A*D^0.5))^M + slope_sign*S
    hw_unsub = (hc_over_d + k * intensity**m + slope_sign * slope) * diameter

    # Submerged: HW/D = c*(Q/(A*D^0.5))^2 + Y + slope_sign*S
    hw_sub = (c * intensity**2 + y_coeff + slope_sign * slope) * diameter

    if intensity <= 3.5:
        return hw_unsub
    elif intensity >= 4.0:
        return hw_sub
    else:
        # Linear interpolation in the transition zone
        frac = (intensity - 3.5) / 0.5
        return hw_unsub + frac * (hw_sub - hw_unsub)


def _outlet_control_headwater(
    diameter: float,
    length: float,
    slope: float,
    flow: float,
    configuration: str,
    tailwater_depth: float,
) -> float:
    """Compute headwater depth (m) above inlet invert under outlet control.

    Uses HDS-5 energy balance: HW = H + ho - L*S
    where H = entrance loss + friction loss + exit loss.
    Assumes full-flow conditions through the barrel.
    """
    _k, _m, _c, _y, _ss, ke, n = _CONFIG_TABLE[configuration]

    area = math.pi * diameter**2 / 4.0
    velocity = flow / area
    velocity_head = velocity**2 / (2.0 * _G)

    # Entrance loss: He = ke * V^2/(2g)
    he = ke * velocity_head

    # Friction loss: Hf = (Ku * n^2 * L) / R^(4/3) * V^2/(2g)
    # For full circular pipe: R = D/4
    hydraulic_radius = diameter / 4.0
    hf = (_KU_SI * n**2 * length / hydraulic_radius ** (4.0 / 3.0)) * velocity_head

    # Exit loss: Ho = 1.0 * V^2/(2g)
    ho_loss = velocity_head

    # Total head loss through barrel
    h_total = he + hf + ho_loss

    # Outlet depth ho: greater of tailwater depth or (dc + D)/2
    dc = _critical_depth_circular(diameter, flow)
    ho = max(tailwater_depth, (dc + diameter) / 2.0)

    # Headwater above inlet invert: HW = H + ho - L*S
    hw = h_total + ho - length * slope

    return hw


def compute(
    culvert_diameter_m: float,
    culvert_length_m: float,
    culvert_slope_m_per_m: float,
    design_flow_m3_s: float,
    culvert_configuration: Literal[
        "concrete_square_edge_headwall",
        "concrete_groove_end_headwall",
        "concrete_groove_end_projecting",
        "cmp_headwall",
        "cmp_mitered",
        "cmp_projecting",
    ],
    tailwater_depth_m: float,
    invert_elevation_m: float = 100.0,
) -> dict[str, float]:
    """Compute culvert headwater under inlet and outlet control per HDS-5.

    Determines the controlling condition (whichever gives higher headwater)
    and reports the headwater elevation.

    Returns a dict with keys: inlet_control_hw_m, outlet_control_hw_m,
    controlling_condition, headwater_elevation_m.
    """
    _validate_inputs(
        culvert_diameter_m,
        culvert_length_m,
        culvert_slope_m_per_m,
        design_flow_m3_s,
        culvert_configuration,
        tailwater_depth_m,
        invert_elevation_m,
    )

    hw_inlet = _inlet_control_headwater(
        culvert_diameter_m,
        design_flow_m3_s,
        culvert_slope_m_per_m,
        culvert_configuration,
    )

    hw_outlet = _outlet_control_headwater(
        culvert_diameter_m,
        culvert_length_m,
        culvert_slope_m_per_m,
        design_flow_m3_s,
        culvert_configuration,
        tailwater_depth_m,
    )

    # Controlling condition: whichever produces higher headwater
    # Encode as 1.0 for inlet control, 2.0 for outlet control
    if hw_inlet >= hw_outlet:
        controlling = 1.0
        hw_controlling = hw_inlet
    else:
        controlling = 2.0
        hw_controlling = hw_outlet

    headwater_elevation = invert_elevation_m + hw_controlling

    return {
        "inlet_control_hw_m": round(hw_inlet, 2),
        "outlet_control_hw_m": round(hw_outlet, 2),
        "controlling_condition": round(controlling, 2),
        "headwater_elevation_m": round(headwater_elevation, 2),
    }
