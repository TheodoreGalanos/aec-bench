# ABOUTME: Infinite slope factor of safety computation engine.
# ABOUTME: Calculates FoS for shallow planar slides with optional water table.

import math

# Unit weight of water (kN/m3).
_GAMMA_W = 9.81


def _validate_inputs(
    slope_angle_deg: float,
    friction_angle_deg: float,
    cohesion_kpa: float,
    unit_weight_kn_m3: float,
    failure_depth_m: float,
    water_table_depth_m: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if slope_angle_deg < 5:
        msg = "slope_angle_deg must be >= 5"
        raise ValueError(msg)
    if slope_angle_deg > 89:
        msg = "slope_angle_deg must be <= 89"
        raise ValueError(msg)
    if friction_angle_deg < 0:
        msg = "friction_angle_deg must be >= 0"
        raise ValueError(msg)
    if cohesion_kpa < 0:
        msg = "cohesion_kpa must be >= 0"
        raise ValueError(msg)
    if unit_weight_kn_m3 <= 0:
        msg = "unit_weight_kn_m3 must be > 0"
        raise ValueError(msg)
    if failure_depth_m <= 0:
        msg = "failure_depth_m must be > 0"
        raise ValueError(msg)
    if water_table_depth_m < 0:
        msg = "water_table_depth_m must be >= 0"
        raise ValueError(msg)


def compute(
    slope_angle_deg: float,
    friction_angle_deg: float,
    cohesion_kpa: float,
    unit_weight_kn_m3: float,
    failure_depth_m: float,
    water_table_depth_m: float = 20.0,
) -> dict[str, float]:
    """Compute factor of safety for infinite slope failure.

    Uses the general infinite slope equation with seepage parallel to slope.
    Returns a dict with keys: pore_pressure_kpa, driving_stress_kpa,
    resisting_stress_kpa, factor_of_safety.
    """
    _validate_inputs(
        slope_angle_deg,
        friction_angle_deg,
        cohesion_kpa,
        unit_weight_kn_m3,
        failure_depth_m,
        water_table_depth_m,
    )

    beta_rad = math.radians(slope_angle_deg)
    phi_rad = math.radians(friction_angle_deg)

    z = failure_depth_m
    zw = water_table_depth_m
    gamma = unit_weight_kn_m3

    cos_beta = math.cos(beta_rad)
    sin_beta = math.sin(beta_rad)

    # Pore pressure: acts when water table is above the failure surface
    water_height = max(0.0, z - zw)
    pore_pressure = _GAMMA_W * water_height * cos_beta**2

    # Driving shear stress along the failure plane
    driving = gamma * z * sin_beta * cos_beta

    # Resisting shear stress (Mohr-Coulomb along the failure plane)
    normal_effective = gamma * z * cos_beta**2 - pore_pressure
    resisting = cohesion_kpa + normal_effective * math.tan(phi_rad)

    # Factor of safety
    fos = resisting / driving

    return {
        "pore_pressure_kpa": round(pore_pressure, 2),
        "driving_stress_kpa": round(driving, 2),
        "resisting_stress_kpa": round(resisting, 2),
        "factor_of_safety": round(fos, 2),
    }
