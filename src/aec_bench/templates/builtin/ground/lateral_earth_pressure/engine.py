# ABOUTME: Lateral earth pressure computation engine for retaining walls.
# ABOUTME: Calculates active/passive coefficients and forces using Rankine or Coulomb theory.

import math
from typing import Literal

# Unit weight of water in kN/m3.
_GAMMA_W = 9.81

# Valid pressure theories.
_VALID_THEORIES: list[str] = ["rankine", "coulomb"]


def _rankine_ka_horizontal(phi_rad: float) -> float:
    """Active pressure coefficient for horizontal backfill (Rankine).

    Ka = tan²(45° - φ'/2) = (1 - sinφ') / (1 + sinφ')
    """
    return math.tan(math.pi / 4.0 - phi_rad / 2.0) ** 2


def _rankine_kp_horizontal(phi_rad: float) -> float:
    """Passive pressure coefficient for horizontal backfill (Rankine).

    Kp = tan²(45° + φ'/2) = (1 + sinφ') / (1 - sinφ')
    """
    return math.tan(math.pi / 4.0 + phi_rad / 2.0) ** 2


def _rankine_ka_inclined(phi_rad: float, beta_rad: float) -> float:
    """Active pressure coefficient for inclined backfill (Rankine).

    Ka = cosβ × (cosβ - √(cos²β - cos²φ)) / (cosβ + √(cos²β - cos²φ))
    Requires β < φ for the square root to be real.
    """
    cos_beta = math.cos(beta_rad)
    cos_phi = math.cos(phi_rad)
    discriminant = cos_beta**2 - cos_phi**2
    # When β ≈ φ the discriminant approaches zero
    if discriminant < 0:
        discriminant = 0.0
    sqrt_disc = math.sqrt(discriminant)
    return cos_beta * (cos_beta - sqrt_disc) / (cos_beta + sqrt_disc)


def _rankine_kp_inclined(phi_rad: float, beta_rad: float) -> float:
    """Passive pressure coefficient for inclined backfill (Rankine).

    Kp = cosβ × (cosβ + √(cos²β - cos²φ)) / (cosβ - √(cos²β - cos²φ))
    Requires β < φ for the square root to be real.
    """
    cos_beta = math.cos(beta_rad)
    cos_phi = math.cos(phi_rad)
    discriminant = cos_beta**2 - cos_phi**2
    if discriminant < 0:
        discriminant = 0.0
    sqrt_disc = math.sqrt(discriminant)
    denominator = cos_beta - sqrt_disc
    # Guard against division by zero when β = φ
    if abs(denominator) < 1e-12:
        return 1e6
    return cos_beta * (cos_beta + sqrt_disc) / denominator


def _coulomb_ka(phi_rad: float, delta_rad: float, beta_rad: float) -> float:
    """Active pressure coefficient using Coulomb theory (vertical wall).

    Ka = sin²(α + φ) / [sin²α × sin(α - δ) × (1 + √(sin(φ+δ)×sin(φ-β) / (sin(α-δ)×sin(α+β))))²]

    For a vertical wall, α = 90° (wall face angle from horizontal).
    Simplifies to:
    Ka = cos²φ / [cos δ × (1 + √(sin(φ+δ)×sin(φ-β) / (cosδ × cosβ)))²]
    """
    # For vertical wall: α = π/2
    cos_phi = math.cos(phi_rad)
    cos_delta = math.cos(delta_rad)
    cos_beta = math.cos(beta_rad)

    sin_phi_delta = math.sin(phi_rad + delta_rad)
    sin_phi_beta = math.sin(phi_rad - beta_rad)

    # Guard: φ must be > β for active case
    if sin_phi_beta < 0:
        sin_phi_beta = 0.0

    product = sin_phi_delta * sin_phi_beta
    denominator_inner = cos_delta * cos_beta
    # Guard against division by zero
    if abs(denominator_inner) < 1e-12:
        return 0.0

    sqrt_term = math.sqrt(product / denominator_inner)
    bracket = (1.0 + sqrt_term) ** 2

    return cos_phi**2 / (cos_delta * bracket)


def _coulomb_kp(phi_rad: float, delta_rad: float, beta_rad: float) -> float:
    """Passive pressure coefficient using Coulomb theory (vertical wall).

    For a vertical wall (α = 90°):
    Kp = cos²φ / [cos δ × (1 - √(sin(φ-δ)×sin(φ+β) / (cosδ × cosβ)))²]
    """
    cos_phi = math.cos(phi_rad)
    cos_delta = math.cos(delta_rad)
    cos_beta = math.cos(beta_rad)

    sin_phi_minus_delta = math.sin(phi_rad - delta_rad)
    sin_phi_plus_beta = math.sin(phi_rad + beta_rad)

    # Guard: both sine terms should be non-negative for typical cases
    if sin_phi_minus_delta < 0:
        sin_phi_minus_delta = 0.0
    if sin_phi_plus_beta < 0:
        sin_phi_plus_beta = 0.0

    product = sin_phi_minus_delta * sin_phi_plus_beta
    denominator_inner = cos_delta * cos_beta
    if abs(denominator_inner) < 1e-12:
        return 1e6

    sqrt_term = math.sqrt(product / denominator_inner)
    bracket = (1.0 - sqrt_term) ** 2

    if abs(bracket) < 1e-12 or abs(cos_delta) < 1e-12:
        return 1e6

    return cos_phi**2 / (cos_delta * bracket)


def _validate_inputs(
    friction_angle_deg: float,
    cohesion_kpa: float,
    unit_weight_kn_m3: float,
    wall_height_m: float,
    backfill_slope_deg: float,
    wall_friction_angle_deg: float,
    surcharge_kpa: float,
    theory: str,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if friction_angle_deg < 0:
        msg = "friction_angle_deg must be >= 0"
        raise ValueError(msg)
    if friction_angle_deg > 50:
        msg = "friction_angle_deg must be <= 50"
        raise ValueError(msg)
    if cohesion_kpa < 0:
        msg = "cohesion_kpa must be >= 0"
        raise ValueError(msg)
    if unit_weight_kn_m3 <= 0:
        msg = "unit_weight_kn_m3 must be > 0"
        raise ValueError(msg)
    if wall_height_m <= 0:
        msg = "wall_height_m must be > 0"
        raise ValueError(msg)
    if backfill_slope_deg < 0:
        msg = "backfill_slope_deg must be >= 0"
        raise ValueError(msg)
    if wall_friction_angle_deg < 0:
        msg = "wall_friction_angle_deg must be >= 0"
        raise ValueError(msg)
    if surcharge_kpa < 0:
        msg = "surcharge_kpa must be >= 0"
        raise ValueError(msg)
    if theory not in _VALID_THEORIES:
        msg = f"theory must be one of {_VALID_THEORIES}, got '{theory}'"
        raise ValueError(msg)
    if theory == "coulomb" and friction_angle_deg == 0:
        msg = "Coulomb theory requires friction_angle_deg > 0"
        raise ValueError(msg)


def compute(
    friction_angle_deg: float,
    cohesion_kpa: float,
    unit_weight_kn_m3: float,
    wall_height_m: float,
    backfill_slope_deg: float = 0.0,
    wall_friction_angle_deg: float = 0.0,
    surcharge_kpa: float = 0.0,
    theory: Literal["rankine", "coulomb"] = "rankine",
) -> dict[str, float]:
    """Compute lateral earth pressure coefficients and forces for a retaining wall.

    Supports both Rankine and Coulomb theories. Includes cohesion effects on
    active/passive pressure and surcharge loading.

    Returns a dict with keys: ka, kp, active_pressure_at_base_kpa,
    passive_pressure_at_base_kpa, total_active_force_kn_m,
    total_passive_force_kn_m, active_force_application_point_m.
    """
    _validate_inputs(
        friction_angle_deg,
        cohesion_kpa,
        unit_weight_kn_m3,
        wall_height_m,
        backfill_slope_deg,
        wall_friction_angle_deg,
        surcharge_kpa,
        theory,
    )

    phi_rad = math.radians(friction_angle_deg)
    beta_rad = math.radians(backfill_slope_deg)
    # Wall friction cannot exceed soil friction angle (engineering convention)
    effective_delta = min(wall_friction_angle_deg, friction_angle_deg)
    delta_rad = math.radians(effective_delta)
    gamma = unit_weight_kn_m3
    h = wall_height_m
    c = cohesion_kpa
    q = surcharge_kpa

    # Compute pressure coefficients based on selected theory
    if theory == "rankine":
        # Special case: φ = 0 (undrained, purely cohesive soil)
        if friction_angle_deg == 0:
            ka = 1.0
            kp = 1.0
        elif backfill_slope_deg == 0:
            ka = _rankine_ka_horizontal(phi_rad)
            kp = _rankine_kp_horizontal(phi_rad)
        else:
            ka = _rankine_ka_inclined(phi_rad, beta_rad)
            kp = _rankine_kp_inclined(phi_rad, beta_rad)
    else:
        # Coulomb theory (includes wall friction and backfill slope)
        ka = _coulomb_ka(phi_rad, delta_rad, beta_rad)
        kp = _coulomb_kp(phi_rad, delta_rad, beta_rad)

    # Active pressure at base of wall: σ_a = Ka × γ × H + Ka × q - 2c√Ka
    # The cohesion term reduces active pressure (tension in upper zone)
    sqrt_ka = math.sqrt(ka)
    active_pressure_at_base = ka * gamma * h + ka * q - 2.0 * c * sqrt_ka

    # Passive pressure at base: σ_p = Kp × γ × H + Kp × q + 2c√Kp
    # Cohesion increases passive resistance
    sqrt_kp = math.sqrt(kp)
    passive_pressure_at_base = kp * gamma * h + kp * q + 2.0 * c * sqrt_kp

    # Total active force per unit length of wall (kN/m)
    # Pa = 0.5 × Ka × γ × H² + Ka × q × H - 2c√Ka × H
    total_active_force = 0.5 * ka * gamma * h**2 + ka * q * h - 2.0 * c * sqrt_ka * h

    # If active force is negative (cohesion dominates), clamp to zero
    if total_active_force < 0:
        total_active_force = 0.0

    # Total passive force per unit length of wall (kN/m)
    # Pp = 0.5 × Kp × γ × H² + Kp × q × H + 2c√Kp × H
    total_passive_force = 0.5 * kp * gamma * h**2 + kp * q * h + 2.0 * c * sqrt_kp * h

    # Point of application of active force above the base
    # For triangular distribution: H/3 from base
    # For combined triangular (soil) + rectangular (surcharge + cohesion), use moments
    # Component forces and their lever arms from base:
    #   Soil wedge: F1 = 0.5 × Ka × γ × H², arm = H/3
    #   Surcharge:  F2 = Ka × q × H,         arm = H/2
    #   Cohesion:   F3 = -2c√Ka × H,         arm = H/2 (uniform reduction)
    f_soil = 0.5 * ka * gamma * h**2
    f_surcharge = ka * q * h
    f_cohesion = -2.0 * c * sqrt_ka * h

    if total_active_force > 1e-6:
        # Weighted average of application points
        moment = f_soil * (h / 3.0) + f_surcharge * (h / 2.0) + f_cohesion * (h / 2.0)
        application_point = moment / total_active_force
        # Clamp to reasonable range [0, H]
        application_point = max(0.0, min(h, application_point))
    else:
        # Default to H/3 when force is negligible
        application_point = h / 3.0

    return {
        "ka": round(ka, 2),
        "kp": round(kp, 2),
        "active_pressure_at_base_kpa": round(active_pressure_at_base, 2),
        "passive_pressure_at_base_kpa": round(passive_pressure_at_base, 2),
        "total_active_force_kn_m": round(total_active_force, 2),
        "total_passive_force_kn_m": round(total_passive_force, 2),
        "active_force_application_point_m": round(application_point, 2),
    }
