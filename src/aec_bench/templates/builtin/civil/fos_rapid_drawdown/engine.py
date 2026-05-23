# ABOUTME: Rapid drawdown slope stability computation engine for dam embankments.
# ABOUTME: Calculates pre- and post-drawdown FoS with the simplified infinite slope method.

import math

# Unit weight of water in kN/m3.
_GAMMA_W = 9.81


def _validate_inputs(
    slope_angle_deg: float,
    slip_depth_m: float,
    cohesion_kpa: float,
    friction_angle_deg: float,
    saturated_unit_weight_kn_m3: float,
    initial_reservoir_level_m: float,
    final_reservoir_level_m: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if slope_angle_deg <= 0 or slope_angle_deg >= 90:
        msg = "slope_angle_deg must be between 0 and 90 exclusive"
        raise ValueError(msg)
    if slip_depth_m <= 0:
        msg = "slip_depth_m must be > 0"
        raise ValueError(msg)
    if cohesion_kpa < 0:
        msg = "cohesion_kpa must be >= 0"
        raise ValueError(msg)
    if friction_angle_deg <= 0 or friction_angle_deg >= 90:
        msg = "friction_angle_deg must be between 0 and 90 exclusive"
        raise ValueError(msg)
    if saturated_unit_weight_kn_m3 <= _GAMMA_W:
        msg = "saturated_unit_weight_kn_m3 must be > gamma_w (9.81 kN/m3)"
        raise ValueError(msg)
    if initial_reservoir_level_m <= 0:
        msg = "initial_reservoir_level_m must be > 0"
        raise ValueError(msg)
    if final_reservoir_level_m < 0:
        msg = "final_reservoir_level_m must be >= 0"
        raise ValueError(msg)
    if final_reservoir_level_m >= initial_reservoir_level_m:
        msg = "final_reservoir_level_m must be < initial_reservoir_level_m"
        raise ValueError(msg)


def _buoyant_unit_weight(saturated_unit_weight: float) -> float:
    """Compute the buoyant (submerged) unit weight.

    gamma_sub = gamma_sat - gamma_w
    """
    return saturated_unit_weight - _GAMMA_W


def _fos_before_drawdown(
    beta_rad: float,
    slip_depth_m: float,
    cohesion_kpa: float,
    phi_rad: float,
    gamma_sub: float,
) -> float:
    """Compute factor of safety for the submerged slope before drawdown.

    Before drawdown the slope face is submerged, so both the normal stress
    and the driving shear stress use the buoyant unit weight:
      sigma_n = gamma_sub * z * cos^2(beta)
      tau      = gamma_sub * z * sin(beta) * cos(beta)
      FoS = (c' + sigma_n * tan(phi')) / tau
    """
    cos_b = math.cos(beta_rad)
    sin_b = math.sin(beta_rad)

    sigma_n = gamma_sub * slip_depth_m * cos_b * cos_b
    tau = gamma_sub * slip_depth_m * sin_b * cos_b

    return (cohesion_kpa + sigma_n * math.tan(phi_rad)) / tau


def _fos_after_drawdown(
    beta_rad: float,
    slip_depth_m: float,
    cohesion_kpa: float,
    phi_rad: float,
    gamma_sat: float,
    gamma_sub: float,
) -> float:
    """Compute factor of safety after rapid drawdown (undrained pore pressures).

    After rapid drawdown the external water is removed but internal pore
    pressures have not dissipated:
      sigma_n  = gamma_sat * z * cos^2(beta)   (total normal stress)
      u        = gamma_w * z * cos^2(beta)      (undrained pore pressure)
      sigma_n' = sigma_n - u = gamma_sub * z * cos^2(beta)
      tau      = gamma_sat * z * sin(beta) * cos(beta)  (full saturated weight drives shear)
      FoS = (c' + sigma_n' * tan(phi')) / tau
    """
    cos_b = math.cos(beta_rad)
    sin_b = math.sin(beta_rad)

    sigma_n_eff = gamma_sub * slip_depth_m * cos_b * cos_b
    tau = gamma_sat * slip_depth_m * sin_b * cos_b

    return (cohesion_kpa + sigma_n_eff * math.tan(phi_rad)) / tau


def _pore_pressure_after_drawdown(
    beta_rad: float,
    slip_depth_m: float,
) -> float:
    """Compute the undrained pore pressure at the slip surface after drawdown.

    u = gamma_w * z * cos^2(beta)
    Pore pressures remain at pre-drawdown hydrostatic levels because the
    low-permeability embankment material cannot drain fast enough.
    """
    cos_b = math.cos(beta_rad)
    return _GAMMA_W * slip_depth_m * cos_b * cos_b


def compute(
    slope_angle_deg: float,
    slip_depth_m: float,
    cohesion_kpa: float,
    friction_angle_deg: float,
    saturated_unit_weight_kn_m3: float,
    initial_reservoir_level_m: float,
    final_reservoir_level_m: float,
) -> dict[str, float]:
    """Compute factor of safety before and after rapid drawdown for an infinite slope.

    Uses the simplified infinite slope rapid drawdown method per
    USACE EM 1110-2-1902 Chapter 13:
    - Before drawdown: slope submerged, buoyant unit weight drives both
      normal and shear stresses.
    - After drawdown: external water removed, pore pressures undrained,
      full saturated weight drives shear while effective stress uses buoyant weight.

    Returns a dict with keys: fos_before_drawdown, fos_after_drawdown,
    drawdown_ratio, pore_pressure_kpa.
    """
    _validate_inputs(
        slope_angle_deg,
        slip_depth_m,
        cohesion_kpa,
        friction_angle_deg,
        saturated_unit_weight_kn_m3,
        initial_reservoir_level_m,
        final_reservoir_level_m,
    )

    beta_rad = math.radians(slope_angle_deg)
    phi_rad = math.radians(friction_angle_deg)
    gamma_sub = _buoyant_unit_weight(saturated_unit_weight_kn_m3)

    fos_before = _fos_before_drawdown(
        beta_rad,
        slip_depth_m,
        cohesion_kpa,
        phi_rad,
        gamma_sub,
    )
    fos_after = _fos_after_drawdown(
        beta_rad,
        slip_depth_m,
        cohesion_kpa,
        phi_rad,
        saturated_unit_weight_kn_m3,
        gamma_sub,
    )
    drawdown_ratio = (initial_reservoir_level_m - final_reservoir_level_m) / initial_reservoir_level_m
    pore_pressure = _pore_pressure_after_drawdown(beta_rad, slip_depth_m)

    return {
        "fos_before_drawdown": round(fos_before, 2),
        "fos_after_drawdown": round(fos_after, 2),
        "drawdown_ratio": round(drawdown_ratio, 2),
        "pore_pressure_kpa": round(pore_pressure, 2),
    }
