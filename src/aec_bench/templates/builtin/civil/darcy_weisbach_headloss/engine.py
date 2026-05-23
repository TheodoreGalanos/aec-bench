# ABOUTME: Darcy-Weisbach friction head loss computation engine for pipe flow.
# ABOUTME: Uses Swamee-Jain explicit approximation for the Darcy friction factor.

import math

# Gravitational acceleration in m/s^2.
_G = 9.81


def _validate_inputs(
    flow_rate_m3_s: float,
    pipe_diameter_m: float,
    pipe_length_m: float,
    roughness_height_mm: float,
    kinematic_viscosity_m2_s: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if flow_rate_m3_s <= 0:
        msg = "flow_rate_m3_s must be > 0"
        raise ValueError(msg)
    if pipe_diameter_m <= 0:
        msg = "pipe_diameter_m must be > 0"
        raise ValueError(msg)
    if pipe_length_m <= 0:
        msg = "pipe_length_m must be > 0"
        raise ValueError(msg)
    if roughness_height_mm < 0:
        msg = "roughness_height_mm must be >= 0"
        raise ValueError(msg)
    if kinematic_viscosity_m2_s <= 0:
        msg = "kinematic_viscosity_m2_s must be > 0"
        raise ValueError(msg)


def _flow_velocity(flow_rate_m3_s: float, pipe_diameter_m: float) -> float:
    """Calculate mean flow velocity from volumetric flow rate and pipe diameter.

    V = Q / (pi * D^2 / 4)
    """
    area = math.pi * pipe_diameter_m**2 / 4.0
    return flow_rate_m3_s / area


def _reynolds_number(velocity: float, diameter: float, viscosity: float) -> float:
    """Calculate Reynolds number for pipe flow.

    Re = V * D / nu
    """
    return velocity * diameter / viscosity


def _swamee_jain_friction_factor(roughness_m: float, diameter_m: float, reynolds: float) -> float:
    """Calculate Darcy friction factor using the Swamee-Jain explicit approximation.

    f = 0.25 / [log10(epsilon/(3.7*D) + 5.74/Re^0.9)]^2

    Valid for 5000 <= Re <= 10^8 and 10^-6 <= epsilon/D <= 10^-2.
    For laminar flow (Re < 2300) uses the exact f = 64/Re.
    Transitional flow (2300 <= Re < 4000) uses Swamee-Jain as a practical approximation.
    """
    if reynolds < 2300.0:
        # Laminar flow: exact Darcy friction factor
        return 64.0 / reynolds

    # Turbulent / transitional flow: Swamee-Jain approximation
    relative_roughness = roughness_m / diameter_m
    log_term = math.log10(relative_roughness / 3.7 + 5.74 / reynolds**0.9)
    return 0.25 / log_term**2


def compute(
    flow_rate_m3_s: float,
    pipe_diameter_m: float,
    pipe_length_m: float,
    roughness_height_mm: float,
    kinematic_viscosity_m2_s: float = 1.004e-6,
) -> dict[str, float]:
    """Compute friction head loss using the Darcy-Weisbach equation.

    Steps:
      1. Calculate mean flow velocity V = Q / A
      2. Calculate Reynolds number Re = V * D / nu
      3. Determine Darcy friction factor f via Swamee-Jain (turbulent)
         or f = 64/Re (laminar)
      4. Calculate head loss hf = f * (L/D) * (V^2 / (2*g))

    Returns a dict with keys: flow_velocity_m_s, reynolds_number,
    friction_factor, head_loss_m.
    """
    _validate_inputs(
        flow_rate_m3_s,
        pipe_diameter_m,
        pipe_length_m,
        roughness_height_mm,
        kinematic_viscosity_m2_s,
    )

    velocity = _flow_velocity(flow_rate_m3_s, pipe_diameter_m)
    reynolds = _reynolds_number(velocity, pipe_diameter_m, kinematic_viscosity_m2_s)

    # Convert roughness from mm to m for the friction factor calculation
    roughness_m = roughness_height_mm / 1000.0

    friction_factor = _swamee_jain_friction_factor(roughness_m, pipe_diameter_m, reynolds)

    # Darcy-Weisbach head loss: hf = f * (L/D) * (V^2 / (2*g))
    head_loss = friction_factor * (pipe_length_m / pipe_diameter_m) * (velocity**2 / (2.0 * _G))

    return {
        "flow_velocity_m_s": round(velocity, 2),
        "reynolds_number": round(reynolds, 2),
        "friction_factor": round(friction_factor, 2),
        "head_loss_m": round(head_loss, 2),
    }
