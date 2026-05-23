# ABOUTME: CPT parameter derivation computation engine using Robertson (1990) correlations.
# ABOUTME: Derives corrected cone resistance, soil behavior type index Ic, and strength parameters.

import math

# Unit weight of water in kN/m3.
_GAMMA_W = 9.81

# Atmospheric pressure reference (kPa) for normalization.
_PA = 100.0

# Soil behavior type index boundary between clay-like and sand-like soils.
# Ic > 2.6 is clay-like (undrained), Ic <= 2.6 is sand-like (drained).
_IC_BOUNDARY = 2.6

# Cone bearing factor for undrained shear strength estimation.
# Typical range 10-18; 14 is a widely-used default (Lunne et al., 1997).
_NKT = 14.0


def _validate_inputs(
    qc_mpa: float,
    fs_kpa: float,
    u2_kpa: float,
    depth_m: float,
    total_unit_weight_kn_m3: float,
    water_table_depth_m: float,
    net_area_ratio: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if qc_mpa <= 0:
        msg = "qc_mpa must be > 0"
        raise ValueError(msg)
    if fs_kpa < 0:
        msg = "fs_kpa must be >= 0"
        raise ValueError(msg)
    if depth_m <= 0:
        msg = "depth_m must be > 0"
        raise ValueError(msg)
    if total_unit_weight_kn_m3 <= 0:
        msg = "total_unit_weight_kn_m3 must be > 0"
        raise ValueError(msg)
    if water_table_depth_m < 0:
        msg = "water_table_depth_m must be >= 0"
        raise ValueError(msg)
    if net_area_ratio <= 0 or net_area_ratio > 1.0:
        msg = "net_area_ratio must be > 0 and <= 1.0"
        raise ValueError(msg)


def _compute_stresses(
    depth_m: float,
    total_unit_weight_kn_m3: float,
    water_table_depth_m: float,
) -> tuple[float, float]:
    """Calculate total and effective vertical overburden stresses at test depth.

    Returns (sigma_v0_kpa, sigma_prime_v0_kpa).
    """
    sigma_v0 = total_unit_weight_kn_m3 * depth_m

    # Effective stress accounts for pore water pressure below water table
    if depth_m <= water_table_depth_m:
        # Test is above water table — no pore pressure correction
        sigma_prime_v0 = sigma_v0
    else:
        # Pore pressure = gamma_w * height of water above test depth
        u0 = _GAMMA_W * (depth_m - water_table_depth_m)
        sigma_prime_v0 = sigma_v0 - u0

    return sigma_v0, sigma_prime_v0


def _compute_ic(qt_norm: float, fr_norm: float) -> float:
    """Calculate Robertson (1990) soil behavior type index Ic.

    Ic = sqrt((3.47 - log10(Qt))^2 + (log10(Fr) + 1.22)^2)

    Qt and Fr must be positive for the log terms to be valid.
    """
    # Guard against non-positive values that would break log10
    qt_safe = max(qt_norm, 1.0)
    fr_safe = max(fr_norm, 0.1)

    term1 = (3.47 - math.log10(qt_safe)) ** 2
    term2 = (math.log10(fr_safe) + 1.22) ** 2
    return math.sqrt(term1 + term2)


def _estimate_su(qt_kpa: float, sigma_v0_kpa: float) -> float:
    """Estimate undrained shear strength for clay-like soils (Ic > 2.6).

    Su = (qt - sigma_v0) / Nkt where Nkt = 14 (Lunne et al., 1997).
    """
    q_net = qt_kpa - sigma_v0_kpa
    # Guard against negative net cone resistance
    q_net = max(q_net, 0.0)
    return q_net / _NKT


def _estimate_phi(qt_norm: float) -> float:
    """Estimate effective friction angle for sand-like soils (Ic <= 2.6).

    phi' = 17.6 + 11.0 * log10(Qt) (Robertson & Campanella, 1983).
    Valid for uncemented, unaged, moderately compressible quartz sands.
    """
    qt_safe = max(qt_norm, 1.0)
    return 17.6 + 11.0 * math.log10(qt_safe)


def compute(
    qc_mpa: float,
    fs_kpa: float,
    u2_kpa: float,
    depth_m: float,
    total_unit_weight_kn_m3: float,
    water_table_depth_m: float = 50.0,
    net_area_ratio: float = 0.80,
) -> dict[str, float]:
    """Derive soil parameters from CPT data using Robertson (1990) correlations.

    Returns a dict with keys: qt_mpa, friction_ratio_pct, qt_norm, fr_norm,
    ic, su_kpa, phi_deg.
    """
    _validate_inputs(
        qc_mpa,
        fs_kpa,
        u2_kpa,
        depth_m,
        total_unit_weight_kn_m3,
        water_table_depth_m,
        net_area_ratio,
    )

    # Step 1: Corrected cone resistance (accounts for unequal end area effect)
    # qt = qc + u2 * (1 - a), where a is the net area ratio
    qt_mpa = qc_mpa + (u2_kpa / 1000.0) * (1.0 - net_area_ratio)

    # Convert qt to kPa for strength calculations
    qt_kpa = qt_mpa * 1000.0

    # Step 2: Friction ratio
    # Rf = fs / qt * 100 (%)
    friction_ratio_pct = (fs_kpa / qt_kpa) * 100.0

    # Step 3: Overburden stresses
    sigma_v0, sigma_prime_v0 = _compute_stresses(
        depth_m,
        total_unit_weight_kn_m3,
        water_table_depth_m,
    )

    # Step 4: Normalized CPT parameters (Robertson 1990)
    # Qt = (qt - sigma_v0) / sigma'_v0
    q_net_kpa = qt_kpa - sigma_v0
    qt_norm = q_net_kpa / sigma_prime_v0

    # Fr = fs / (qt - sigma_v0) * 100 (%)
    # Guard against zero or negative net cone resistance
    if q_net_kpa <= 0:
        fr_norm = 100.0
    else:
        fr_norm = (fs_kpa / q_net_kpa) * 100.0

    # Step 5: Soil behavior type index
    ic = _compute_ic(qt_norm, fr_norm)

    # Step 6: Derived strength parameters depend on soil type
    # Ic > 2.6 indicates clay-like behavior (undrained analysis)
    # Ic <= 2.6 indicates sand-like behavior (drained analysis)
    if ic > _IC_BOUNDARY:
        su_kpa = _estimate_su(qt_kpa, sigma_v0)
        phi_deg = 0.0
    else:
        su_kpa = 0.0
        phi_deg = _estimate_phi(qt_norm)

    return {
        "qt_mpa": round(qt_mpa, 2),
        "friction_ratio_pct": round(friction_ratio_pct, 2),
        "qt_norm": round(qt_norm, 2),
        "fr_norm": round(fr_norm, 2),
        "ic": round(ic, 2),
        "su_kpa": round(su_kpa, 2),
        "phi_deg": round(phi_deg, 2),
    }
