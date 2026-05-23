# ABOUTME: Infinite slope factor of safety engine for embankment dams under steady-state seepage.
# ABOUTME: Computes FoS, driving stress, and resisting stress using pore pressure ratio (ru).

import math

# Unit weight of water (kN/m3).
_GAMMA_W = 9.81


def _validate_inputs(
    slope_angle_deg: float,
    failure_depth_m: float,
    cohesion_kpa: float,
    friction_angle_deg: float,
    saturated_unit_weight_kn_m3: float,
    pore_pressure_ratio: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if slope_angle_deg < 5.0:
        msg = "slope_angle_deg must be >= 5"
        raise ValueError(msg)
    if slope_angle_deg > 60.0:
        msg = "slope_angle_deg must be <= 60"
        raise ValueError(msg)
    if failure_depth_m <= 0.0:
        msg = "failure_depth_m must be > 0"
        raise ValueError(msg)
    if cohesion_kpa < 0.0:
        msg = "cohesion_kpa must be >= 0"
        raise ValueError(msg)
    if friction_angle_deg < 0.0:
        msg = "friction_angle_deg must be >= 0"
        raise ValueError(msg)
    if friction_angle_deg > 50.0:
        msg = "friction_angle_deg must be <= 50"
        raise ValueError(msg)
    if saturated_unit_weight_kn_m3 <= _GAMMA_W:
        msg = "saturated_unit_weight_kn_m3 must be > gamma_w (9.81)"
        raise ValueError(msg)
    if pore_pressure_ratio < 0.0:
        msg = "pore_pressure_ratio must be >= 0"
        raise ValueError(msg)
    if pore_pressure_ratio > 0.65:
        msg = "pore_pressure_ratio must be <= 0.65"
        raise ValueError(msg)


def _pore_pressure_kpa(
    pore_pressure_ratio: float,
    saturated_unit_weight_kn_m3: float,
    failure_depth_m: float,
) -> float:
    """Compute pore water pressure at the failure surface.

    u = ru * gamma_sat * z
    """
    return pore_pressure_ratio * saturated_unit_weight_kn_m3 * failure_depth_m


def _driving_stress_kpa(
    saturated_unit_weight_kn_m3: float,
    failure_depth_m: float,
    beta_rad: float,
) -> float:
    """Compute the driving shear stress along the failure plane.

    tau_d = gamma_sat * z * sin(beta) * cos(beta)
    """
    return saturated_unit_weight_kn_m3 * failure_depth_m * math.sin(beta_rad) * math.cos(beta_rad)


def _resisting_stress_kpa(
    cohesion_kpa: float,
    saturated_unit_weight_kn_m3: float,
    failure_depth_m: float,
    beta_rad: float,
    phi_rad: float,
    pore_pressure_kpa: float,
) -> float:
    """Compute the resisting shear stress along the failure plane.

    sigma'_n = gamma_sat * z * cos^2(beta) - u
    tau_r = c' + sigma'_n * tan(phi')
    """
    normal_total = saturated_unit_weight_kn_m3 * failure_depth_m * math.cos(beta_rad) ** 2
    normal_effective = normal_total - pore_pressure_kpa
    return cohesion_kpa + normal_effective * math.tan(phi_rad)


def compute(
    slope_angle_deg: float,
    failure_depth_m: float,
    cohesion_kpa: float,
    friction_angle_deg: float,
    saturated_unit_weight_kn_m3: float,
    pore_pressure_ratio: float,
) -> dict[str, float]:
    """Compute factor of safety for an infinite slope under steady-state seepage.

    Uses the infinite slope equation with the pore pressure ratio (ru) to
    represent steady-state seepage conditions in an embankment dam slope.

    Returns a dict with keys: fos, driving_stress_kpa, resisting_stress_kpa.
    """
    _validate_inputs(
        slope_angle_deg,
        failure_depth_m,
        cohesion_kpa,
        friction_angle_deg,
        saturated_unit_weight_kn_m3,
        pore_pressure_ratio,
    )

    beta_rad = math.radians(slope_angle_deg)
    phi_rad = math.radians(friction_angle_deg)

    u = _pore_pressure_kpa(
        pore_pressure_ratio,
        saturated_unit_weight_kn_m3,
        failure_depth_m,
    )

    driving = _driving_stress_kpa(
        saturated_unit_weight_kn_m3,
        failure_depth_m,
        beta_rad,
    )

    resisting = _resisting_stress_kpa(
        cohesion_kpa,
        saturated_unit_weight_kn_m3,
        failure_depth_m,
        beta_rad,
        phi_rad,
        u,
    )

    fos = resisting / driving

    return {
        "fos": round(fos, 2),
        "driving_stress_kpa": round(driving, 2),
        "resisting_stress_kpa": round(resisting, 2),
    }
