# ABOUTME: Hydraulic grade line check engine for a single stormwater pipe reach.
# ABOUTME: Computes HGL at the upstream pit and checks clearance against surcharge limits.

import math

# Standard pipe diameters in mm (Australian DN sizes for stormwater)
_VALID_DIAMETERS_MM = {
    "225",
    "300",
    "375",
    "450",
    "525",
    "600",
    "750",
    "900",
    "1050",
    "1200",
}


def _validate_inputs(
    design_flow_m3_per_s: float,
    pipe_diameter_mm: str,
    pipe_length_m: float,
    mannings_n: float,
    pit_loss_coefficient: float,
    tailwater_level_m: float,
    surface_level_m: float,
    minimum_clearance_mm: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if design_flow_m3_per_s <= 0:
        msg = "design_flow_m3_per_s must be > 0"
        raise ValueError(msg)
    if pipe_diameter_mm not in _VALID_DIAMETERS_MM:
        msg = f"pipe_diameter_mm must be one of {sorted(_VALID_DIAMETERS_MM)}, got '{pipe_diameter_mm}'"
        raise ValueError(msg)
    if pipe_length_m <= 0:
        msg = "pipe_length_m must be > 0"
        raise ValueError(msg)
    if mannings_n <= 0:
        msg = "mannings_n must be > 0"
        raise ValueError(msg)
    if pit_loss_coefficient < 0:
        msg = "pit_loss_coefficient must be >= 0"
        raise ValueError(msg)
    if minimum_clearance_mm < 0:
        msg = "minimum_clearance_mm must be >= 0"
        raise ValueError(msg)


def compute(
    design_flow_m3_per_s: float,
    pipe_diameter_mm: str,
    pipe_length_m: float,
    mannings_n: float,
    pit_loss_coefficient: float,
    tailwater_level_m: float,
    surface_level_m: float,
    minimum_clearance_mm: float = 150.0,
) -> dict[str, float]:
    """Compute hydraulic grade line at the upstream pit for a single pipe reach.

    Procedure for full-pipe flow (pressure/surcharge check):
    1. Convert diameter to metres, calculate pipe cross-sectional area A and
       hydraulic radius R = D/4 for a circular pipe flowing full.
    2. Flow velocity: V = Q / A
    3. Friction slope (Manning's): S_f = (V * n / R^(2/3))^2
    4. Friction loss: h_f = S_f * L
    5. Pit/junction loss: h_pit = K * V^2 / (2g)
    6. HGL at upstream pit: HGL_up = HGL_down + h_f + h_pit
    7. Clearance: clearance = surface_level - HGL_up (converted to mm)
    8. Surcharge ratio: HGL_up / surface_level (> 1.0 means surcharging)
    9. Pass/fail: pass if clearance >= minimum_clearance

    Returns dict with keys: flow_velocity_m_per_s, friction_loss_m, pit_loss_m,
    hgl_upstream_m, clearance_mm, surcharge_ratio, pass_fail.
    """
    _validate_inputs(
        design_flow_m3_per_s,
        pipe_diameter_mm,
        pipe_length_m,
        mannings_n,
        pit_loss_coefficient,
        tailwater_level_m,
        surface_level_m,
        minimum_clearance_mm,
    )

    # Convert diameter from mm to m
    diameter_m = float(pipe_diameter_mm) / 1000.0

    # Full-pipe cross-sectional area
    area_m2 = math.pi * diameter_m**2 / 4.0

    # Hydraulic radius for circular pipe flowing full: R = D/4
    hydraulic_radius_m = diameter_m / 4.0

    # Flow velocity
    velocity = design_flow_m3_per_s / area_m2

    # Friction slope via Manning's equation: S_f = (V * n / R^(2/3))^2
    friction_slope = (velocity * mannings_n / hydraulic_radius_m ** (2.0 / 3.0)) ** 2

    # Friction head loss over the pipe length
    friction_loss = friction_slope * pipe_length_m

    # Pit/junction loss: h_pit = K * V^2 / (2g)
    g = 9.81
    pit_loss = pit_loss_coefficient * velocity**2 / (2.0 * g)

    # HGL at upstream pit
    hgl_upstream = tailwater_level_m + friction_loss + pit_loss

    # Clearance in mm (positive means HGL below surface)
    clearance_mm_val = (surface_level_m - hgl_upstream) * 1000.0

    # Surcharge ratio: HGL / surface level
    surcharge_ratio = hgl_upstream / surface_level_m

    # Pass/fail assessment: pass (1.0) if clearance >= minimum_clearance
    pass_fail = 1.0 if clearance_mm_val >= minimum_clearance_mm else 0.0

    return {
        "flow_velocity_m_per_s": round(velocity, 2),
        "friction_loss_m": round(friction_loss, 2),
        "pit_loss_m": round(pit_loss, 2),
        "hgl_upstream_m": round(hgl_upstream, 2),
        "clearance_mm": round(clearance_mm_val, 2),
        "surcharge_ratio": round(surcharge_ratio, 2),
        "pass_fail": round(pass_fail, 2),
    }
