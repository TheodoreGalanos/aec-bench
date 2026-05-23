# ABOUTME: Retaining wall base bearing pressure computation engine.
# ABOUTME: Checks bearing under wall base using Meyerhof effective width.

import math

# Unit weight of water in kN/m3
_GAMMA_W = 9.81


def _validate_inputs(
    base_width_m: float,
    total_vertical_load_kn_per_m: float,
    net_moment_knm_per_m: float,
    soil_cohesion_kpa: float,
    soil_friction_angle_deg: float,
    soil_unit_weight_kn_m3: float,
    embedment_depth_m: float,
    allowable_bearing_capacity_kpa: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if base_width_m <= 0:
        msg = "base_width_m must be > 0"
        raise ValueError(msg)
    if total_vertical_load_kn_per_m <= 0:
        msg = "total_vertical_load_kn_per_m must be > 0"
        raise ValueError(msg)
    if soil_cohesion_kpa < 0:
        msg = "soil_cohesion_kpa must be >= 0"
        raise ValueError(msg)
    if soil_friction_angle_deg < 0:
        msg = "soil_friction_angle_deg must be >= 0"
        raise ValueError(msg)
    if soil_friction_angle_deg > 50:
        msg = "soil_friction_angle_deg must be <= 50"
        raise ValueError(msg)
    if soil_unit_weight_kn_m3 <= 0:
        msg = "soil_unit_weight_kn_m3 must be > 0"
        raise ValueError(msg)
    if embedment_depth_m < 0:
        msg = "embedment_depth_m must be >= 0"
        raise ValueError(msg)
    if allowable_bearing_capacity_kpa <= 0:
        msg = "allowable_bearing_capacity_kpa must be > 0"
        raise ValueError(msg)


def _bearing_capacity_factors(phi_deg: float) -> tuple[float, float, float]:
    """Return (Nc, Nq, Ngamma) using Meyerhof's analytical expressions.

    Nq = exp(pi * tan(phi)) * tan^2(45 + phi/2)
    Nc = (Nq - 1) * cot(phi)          [Nc = 5.14 when phi = 0]
    Ngamma = (Nq - 1) * tan(1.4 * phi)
    """
    phi_rad = math.radians(phi_deg)

    # Nq
    nq = math.exp(math.pi * math.tan(phi_rad)) * math.tan(math.radians(45.0 + phi_deg / 2.0)) ** 2

    # Nc: special case for phi = 0 (cot(0) is undefined)
    if phi_deg == 0.0:
        nc = 5.14
    else:
        nc = (nq - 1.0) / math.tan(phi_rad)

    # Ngamma (+ 0.0 avoids negative zero for phi = 0)
    ngamma = (nq - 1.0) * math.tan(1.4 * phi_rad) + 0.0

    return nc, nq, ngamma


def compute(
    base_width_m: float,
    total_vertical_load_kn_per_m: float,
    net_moment_knm_per_m: float,
    soil_cohesion_kpa: float,
    soil_friction_angle_deg: float,
    soil_unit_weight_kn_m3: float,
    embedment_depth_m: float = 0.5,
    allowable_bearing_capacity_kpa: float = 200.0,
) -> dict[str, float]:
    """Compute bearing pressure check for a retaining wall base.

    Uses Meyerhof's effective width method to account for eccentricity of
    the resultant vertical load on the wall base.

    Steps:
    1. Calculate eccentricity e = B/2 - (M / V)  (distance from base centre)
    2. Calculate effective width B' = B - 2e (Meyerhof)
    3. Calculate maximum bearing pressure q_max = V / B'
    4. Calculate ultimate bearing capacity using Meyerhof factors for strip footing
    5. Calculate factor of safety = q_allowable / q_max

    Returns a dict with keys: eccentricity_m, effective_width_m,
    max_bearing_pressure_kpa, ultimate_bearing_capacity_kpa,
    factor_of_safety.
    """
    _validate_inputs(
        base_width_m,
        total_vertical_load_kn_per_m,
        net_moment_knm_per_m,
        soil_cohesion_kpa,
        soil_friction_angle_deg,
        soil_unit_weight_kn_m3,
        embedment_depth_m,
        allowable_bearing_capacity_kpa,
    )

    b = base_width_m
    v = total_vertical_load_kn_per_m
    m = net_moment_knm_per_m

    # Step 1: Eccentricity of resultant from base centre
    # The moment arm from the toe is M/V; eccentricity from centre is B/2 - M/V
    eccentricity = b / 2.0 - abs(m) / v

    # Step 2: Effective base width using Meyerhof's method
    # If eccentricity is negative (resultant outside middle third), B' is clamped to
    # a small positive value to avoid division by zero — represents an unstable wall
    effective_width = max(b - 2.0 * abs(eccentricity), 0.01)

    # Step 3: Maximum bearing pressure on effective area (strip footing per metre run)
    q_max = v / effective_width

    # Step 4: Ultimate bearing capacity using Meyerhof factors for strip footing
    # Strip footing: shape factors all = 1.0, depth factors applied
    nc, nq, ngamma = _bearing_capacity_factors(soil_friction_angle_deg)

    # Overburden pressure at foundation level
    q_overburden = soil_unit_weight_kn_m3 * embedment_depth_m

    # Depth factors for strip footing (Meyerhof)
    phi_deg = soil_friction_angle_deg
    kp = math.tan(math.radians(45.0 + phi_deg / 2.0)) ** 2
    sqrt_kp = math.sqrt(kp)
    d_over_b = embedment_depth_m / effective_width if effective_width > 0 else 0.0

    dc = 1.0 + 0.2 * sqrt_kp * d_over_b
    if phi_deg > 10.0:
        dq = 1.0 + 0.1 * sqrt_kp * d_over_b
        dgamma = dq
    else:
        dq = 1.0
        dgamma = 1.0

    # Meyerhof equation for strip footing (shape factors = 1, inclination factors = 1)
    # q_ult = c * Nc * dc + q * Nq * dq + 0.5 * gamma * B' * Ngamma * dgamma
    q_ult = (
        soil_cohesion_kpa * nc * dc
        + q_overburden * nq * dq
        + 0.5 * soil_unit_weight_kn_m3 * effective_width * ngamma * dgamma
    )

    # Step 5: Factor of safety against bearing failure
    # FoS = q_allowable / q_max (using the provided allowable capacity)
    fos = allowable_bearing_capacity_kpa / q_max if q_max > 0 else 0.0

    return {
        "eccentricity_m": round(eccentricity, 2),
        "effective_width_m": round(effective_width, 2),
        "max_bearing_pressure_kpa": round(q_max, 2),
        "ultimate_bearing_capacity_kpa": round(q_ult, 2),
        "factor_of_safety": round(fos, 2),
    }
