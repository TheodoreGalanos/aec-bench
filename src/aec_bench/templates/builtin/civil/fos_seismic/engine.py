# ABOUTME: Pseudo-static seismic slope stability computation engine.
# ABOUTME: Calculates FoS, yield acceleration, and yield ratio for infinite slopes under seismic loading.

import math


def _validate_inputs(
    slope_angle_deg: float,
    slip_depth_m: float,
    cohesion_kpa: float,
    friction_angle_deg: float,
    unit_weight_kn_m3: float,
    pore_pressure_ratio: float,
    kh: float,
    kv: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if slope_angle_deg < 5:
        msg = "slope_angle_deg must be >= 5"
        raise ValueError(msg)
    if slope_angle_deg > 60:
        msg = "slope_angle_deg must be <= 60"
        raise ValueError(msg)
    if slip_depth_m <= 0:
        msg = "slip_depth_m must be > 0"
        raise ValueError(msg)
    if cohesion_kpa < 0:
        msg = "cohesion_kpa must be >= 0"
        raise ValueError(msg)
    if friction_angle_deg < 0:
        msg = "friction_angle_deg must be >= 0"
        raise ValueError(msg)
    if friction_angle_deg > 50:
        msg = "friction_angle_deg must be <= 50"
        raise ValueError(msg)
    if unit_weight_kn_m3 <= 0:
        msg = "unit_weight_kn_m3 must be > 0"
        raise ValueError(msg)
    if pore_pressure_ratio < 0:
        msg = "pore_pressure_ratio must be >= 0"
        raise ValueError(msg)
    if pore_pressure_ratio > 0.6:
        msg = "pore_pressure_ratio must be <= 0.6"
        raise ValueError(msg)
    if kh < 0:
        msg = "kh must be >= 0"
        raise ValueError(msg)
    if kh > 0.5:
        msg = "kh must be <= 0.5"
        raise ValueError(msg)
    if kv < 0:
        msg = "kv must be >= 0"
        raise ValueError(msg)
    if kv > 0.5:
        msg = "kv must be <= 0.5"
        raise ValueError(msg)


def compute(
    slope_angle_deg: float,
    slip_depth_m: float,
    cohesion_kpa: float,
    friction_angle_deg: float,
    unit_weight_kn_m3: float,
    pore_pressure_ratio: float,
    kh: float,
    kv: float = 0.0,
) -> dict[str, float]:
    """Compute pseudo-static seismic factor of safety for an infinite slope.

    Uses the infinite slope equation extended with horizontal (kh) and
    vertical (kv) seismic coefficients.  The vertical coefficient acts
    upward (reduces effective weight) which is the conservative case
    per USACE EM 1110-2-1902 and ICOLD Bulletin 148.

    The driving shear stress on the slip plane is:
        T_d = gamma * z * [(1 - kv) * sin(beta) + kh * cos(beta)] * cos(beta)

    The normal effective stress on the slip plane is:
        sigma_n = gamma * z * [(1 - kv) * cos(beta) - kh * sin(beta)] * cos(beta)

    Pore pressure on the slip plane (via pore pressure ratio ru):
        u = ru * gamma * z * cos^2(beta)

    Resisting shear stress (Mohr-Coulomb):
        T_r = c' + (sigma_n - u) * tan(phi')

    Factor of safety: FoS = T_r / T_d

    Yield acceleration ky is the horizontal seismic coefficient at which
    FoS = 1.0, solved analytically from the equilibrium equation.

    Returns dict with keys: fos, yield_acceleration_ky, yield_ratio.
    """
    _validate_inputs(
        slope_angle_deg,
        slip_depth_m,
        cohesion_kpa,
        friction_angle_deg,
        unit_weight_kn_m3,
        pore_pressure_ratio,
        kh,
        kv,
    )

    beta = math.radians(slope_angle_deg)
    phi = math.radians(friction_angle_deg)
    gamma = unit_weight_kn_m3
    z = slip_depth_m
    ru = pore_pressure_ratio
    cos_b = math.cos(beta)
    sin_b = math.sin(beta)
    tan_phi = math.tan(phi)

    # Driving shear stress on the slip plane
    driving = gamma * z * ((1.0 - kv) * sin_b + kh * cos_b) * cos_b

    # Normal effective stress on the slip plane
    sigma_n = gamma * z * ((1.0 - kv) * cos_b - kh * sin_b) * cos_b

    # Pore water pressure on the slip plane
    u = ru * gamma * z * cos_b**2

    # Resisting shear stress (Mohr-Coulomb)
    resisting = cohesion_kpa + (sigma_n - u) * tan_phi

    # Factor of safety
    fos = resisting / driving

    # Yield acceleration ky: the kh at which FoS = 1.0
    # From T_r = T_d with kh replaced by ky:
    #   c' + [gamma*z*((1-kv)*cos_b - ky*sin_b)*cos_b - u]*tan_phi
    #     = gamma*z*((1-kv)*sin_b + ky*cos_b)*cos_b
    #
    # Rearranging for ky:
    #   numerator = c' + gamma*z*cos_b*[(1-kv)*cos_b - ru*cos_b]*tan_phi
    #               - gamma*z*(1-kv)*sin_b*cos_b
    #   denominator = gamma*z*cos_b*(cos_b + sin_b*tan_phi)
    #   ky = numerator / denominator
    ky_num = (
        cohesion_kpa
        + gamma * z * cos_b * ((1.0 - kv) * cos_b - ru * cos_b) * tan_phi
        - gamma * z * (1.0 - kv) * sin_b * cos_b
    )
    ky_den = gamma * z * cos_b * (cos_b + sin_b * tan_phi)
    ky = ky_num / ky_den

    # Yield ratio: ky / kh (guarded against kh = 0)
    if kh > 0:
        yield_ratio = ky / kh
    else:
        yield_ratio = float("inf")

    return {
        "fos": round(fos, 2),
        "yield_acceleration_ky": round(ky, 2),
        "yield_ratio": round(yield_ratio, 2),
    }
