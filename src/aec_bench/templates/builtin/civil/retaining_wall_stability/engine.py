# ABOUTME: Gravity retaining wall stability engine for sliding, overturning, and bearing checks.
# ABOUTME: Computes FoS values using Rankine active pressure and Terzaghi bearing capacity per AS 4678.

import math

# Unit weight of water in kN/m3.
_GAMMA_W = 9.81


def _validate_inputs(
    wall_height_m: float,
    base_width_m: float,
    wall_thickness_m: float,
    concrete_unit_weight_kn_m3: float,
    backfill_friction_angle_deg: float,
    backfill_unit_weight_kn_m3: float,
    backfill_cohesion_kpa: float,
    surcharge_kpa: float,
    foundation_friction_angle_deg: float,
    foundation_cohesion_kpa: float,
    base_friction_ratio: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if wall_height_m <= 0:
        msg = "wall_height_m must be > 0"
        raise ValueError(msg)
    if wall_height_m > 12.0:
        msg = "wall_height_m must be <= 12"
        raise ValueError(msg)
    if base_width_m <= 0:
        msg = "base_width_m must be > 0"
        raise ValueError(msg)
    if wall_thickness_m <= 0:
        msg = "wall_thickness_m must be > 0"
        raise ValueError(msg)
    if wall_thickness_m > base_width_m:
        msg = "wall_thickness_m must be <= base_width_m"
        raise ValueError(msg)
    if concrete_unit_weight_kn_m3 <= 0:
        msg = "concrete_unit_weight_kn_m3 must be > 0"
        raise ValueError(msg)
    if backfill_friction_angle_deg < 0:
        msg = "backfill_friction_angle_deg must be >= 0"
        raise ValueError(msg)
    if backfill_friction_angle_deg > 50:
        msg = "backfill_friction_angle_deg must be <= 50"
        raise ValueError(msg)
    if backfill_unit_weight_kn_m3 <= 0:
        msg = "backfill_unit_weight_kn_m3 must be > 0"
        raise ValueError(msg)
    if backfill_cohesion_kpa < 0:
        msg = "backfill_cohesion_kpa must be >= 0"
        raise ValueError(msg)
    if surcharge_kpa < 0:
        msg = "surcharge_kpa must be >= 0"
        raise ValueError(msg)
    if foundation_friction_angle_deg < 0:
        msg = "foundation_friction_angle_deg must be >= 0"
        raise ValueError(msg)
    if foundation_friction_angle_deg > 50:
        msg = "foundation_friction_angle_deg must be <= 50"
        raise ValueError(msg)
    if foundation_cohesion_kpa < 0:
        msg = "foundation_cohesion_kpa must be >= 0"
        raise ValueError(msg)
    if base_friction_ratio <= 0:
        msg = "base_friction_ratio must be > 0"
        raise ValueError(msg)
    if base_friction_ratio > 1.0:
        msg = "base_friction_ratio must be <= 1.0"
        raise ValueError(msg)


def _rankine_ka(phi_rad: float) -> float:
    """Active earth pressure coefficient using Rankine theory for horizontal backfill.

    Ka = tan^2(45 - phi/2)
    """
    if phi_rad == 0:
        return 1.0
    return math.tan(math.pi / 4.0 - phi_rad / 2.0) ** 2


def _terzaghi_bearing_factors(phi_rad: float) -> tuple[float, float, float]:
    """Terzaghi bearing capacity factors Nc, Nq, Ngamma for a strip footing.

    Nq = e^(2*(3pi/4 - phi/2)*tan(phi)) / (2 * cos^2(45 + phi/2))
    Nc = (Nq - 1) * cot(phi)       [for phi > 0; Nc = 5.14 for phi = 0]
    Ngamma = 2 * (Nq + 1) * tan(phi)   [Vesic approximation]
    """
    if phi_rad == 0:
        return 5.14, 1.0, 0.0
    nq_exp = math.exp(2.0 * (3.0 * math.pi / 4.0 - phi_rad / 2.0) * math.tan(phi_rad))
    nq = nq_exp / (2.0 * math.cos(math.pi / 4.0 + phi_rad / 2.0) ** 2)
    nc = (nq - 1.0) / math.tan(phi_rad)
    # Vesic (1973) approximation for Ngamma, widely used in practice.
    ngamma = 2.0 * (nq + 1.0) * math.tan(phi_rad)
    return nc, nq, ngamma


def compute(
    wall_height_m: float,
    base_width_m: float,
    wall_thickness_m: float,
    concrete_unit_weight_kn_m3: float,
    backfill_friction_angle_deg: float,
    backfill_unit_weight_kn_m3: float,
    backfill_cohesion_kpa: float = 0.0,
    surcharge_kpa: float = 0.0,
    foundation_friction_angle_deg: float = 30.0,
    foundation_cohesion_kpa: float = 0.0,
    base_friction_ratio: float = 0.67,
) -> dict[str, float]:
    """Compute stability factors of safety for a gravity retaining wall.

    Analyses a rectangular gravity wall against three failure modes:
    1. Sliding along the base
    2. Overturning about the toe
    3. Bearing capacity failure of the foundation

    The wall is rectangular with height H, base width B, and stem thickness t.
    The stem is placed at the front (toe side) of the base, so backfill soil
    sits on the heel portion (B - t) of the base behind the stem.

    Uses Rankine active earth pressure for horizontal backfill and Terzaghi
    bearing capacity theory for the foundation check.

    Returns a dict with keys: ka, fos_sliding, fos_overturning, fos_bearing,
    eccentricity_m, max_base_pressure_kpa.
    """
    _validate_inputs(
        wall_height_m,
        base_width_m,
        wall_thickness_m,
        concrete_unit_weight_kn_m3,
        backfill_friction_angle_deg,
        backfill_unit_weight_kn_m3,
        backfill_cohesion_kpa,
        surcharge_kpa,
        foundation_friction_angle_deg,
        foundation_cohesion_kpa,
        base_friction_ratio,
    )

    phi_backfill_rad = math.radians(backfill_friction_angle_deg)
    phi_foundation_rad = math.radians(foundation_friction_angle_deg)

    h = wall_height_m
    b = base_width_m
    t = wall_thickness_m
    gamma_c = concrete_unit_weight_kn_m3
    gamma_s = backfill_unit_weight_kn_m3
    c_backfill = backfill_cohesion_kpa
    q = surcharge_kpa
    c_found = foundation_cohesion_kpa

    # --- Active earth pressure ---
    ka = _rankine_ka(phi_backfill_rad)
    sqrt_ka = math.sqrt(ka)

    # Lateral active earth pressure resultant (kN/m):
    # Triangular soil pressure: Pa_soil = 0.5 * Ka * gamma_s * H^2
    # Uniform surcharge pressure: Pa_surcharge = Ka * q * H
    # Cohesion reduction: Pa_cohesion = -2 * c * sqrt(Ka) * H
    pa_soil = 0.5 * ka * gamma_s * h**2
    pa_surcharge = ka * q * h
    pa_cohesion = -2.0 * c_backfill * sqrt_ka * h

    # Total horizontal active force.
    h_active = pa_soil + pa_surcharge + pa_cohesion
    if h_active < 0:
        h_active = 0.0

    # --- Vertical forces ---
    # Wall self-weight (rectangular concrete section).
    w_wall = gamma_c * h * t

    # Weight of backfill soil on the heel (behind the stem, on the base).
    heel_width = b - t
    w_soil = gamma_s * h * heel_width if heel_width > 0 else 0.0

    # Surcharge weight on the heel.
    w_surcharge = q * heel_width if heel_width > 0 else 0.0

    # Total vertical force.
    v_total = w_wall + w_soil + w_surcharge

    # --- Moments about the toe (front edge of base) ---
    # Convention: stabilising moments are positive, overturning moments are positive
    # and computed separately.

    # Wall weight acts at the centroid of the stem.
    # Stem is at the front (toe side) of the base, centroid at t/2 from the toe.
    arm_wall = t / 2.0
    m_wall = w_wall * arm_wall

    # Backfill soil on heel acts at centroid of the heel area.
    # Heel extends from the back of the stem to the back of the base.
    # Centroid of heel soil: from toe = t + heel_width/2 = t + (b-t)/2 = (b+t)/2
    arm_soil = (b + t) / 2.0 if heel_width > 0 else 0.0
    m_soil = w_soil * arm_soil

    # Surcharge on heel acts at same arm as soil on heel.
    m_surcharge_v = w_surcharge * arm_soil

    # Total stabilising moment about toe.
    m_stabilising = m_wall + m_soil + m_surcharge_v

    # Overturning moments from horizontal active forces about the toe.
    # Triangular soil pressure: resultant acts at H/3 from base.
    arm_pa_soil = h / 3.0
    # Uniform surcharge pressure: resultant acts at H/2 from base.
    arm_pa_surcharge = h / 2.0
    # Cohesion (uniform reduction): resultant acts at H/2 from base.
    arm_pa_cohesion = h / 2.0

    m_overturning = pa_soil * arm_pa_soil + pa_surcharge * arm_pa_surcharge + pa_cohesion * arm_pa_cohesion
    if m_overturning < 0:
        m_overturning = 0.0

    # --- Factor of Safety: Sliding ---
    # Resisting force = V * tan(delta) + c_b * B
    # delta = base_friction_ratio * phi_foundation (interface friction)
    # c_b = base_friction_ratio * c_foundation (base adhesion)
    delta = base_friction_ratio * phi_foundation_rad
    c_base = base_friction_ratio * c_found
    sliding_resistance = v_total * math.tan(delta) + c_base * b

    if h_active > 0:
        fos_sliding = sliding_resistance / h_active
    else:
        # No driving force; wall is unconditionally stable against sliding.
        fos_sliding = 99.99

    # --- Factor of Safety: Overturning ---
    if m_overturning > 0:
        fos_overturning = m_stabilising / m_overturning
    else:
        fos_overturning = 99.99

    # --- Eccentricity and base pressure ---
    # Net moment about the toe.
    m_net = m_stabilising - m_overturning

    # Distance from toe to the resultant vertical force.
    x_resultant = m_net / v_total

    # Eccentricity from the centre of the base.
    eccentricity = b / 2.0 - x_resultant

    # Maximum base pressure using trapezoidal distribution.
    # q_max = V/B * (1 + 6|e|/B) for |e| within the middle third.
    # The absolute value of eccentricity is used because the maximum pressure
    # occurs at whichever edge the resultant is closest to (toe or heel).
    # If |e| > B/6, the resultant is outside the middle third and
    # part of the base lifts off: q_max = 2V / (3 * distance_to_edge).
    abs_e = abs(eccentricity)
    if abs_e <= b / 6.0:
        max_base_pressure = (v_total / b) * (1.0 + 6.0 * abs_e / b)
    else:
        # Resultant outside middle third; only part of base in compression.
        # Distance from the edge where compression is maximum to the resultant.
        dist_to_near_edge = b / 2.0 - abs_e
        if dist_to_near_edge > 0:
            max_base_pressure = 2.0 * v_total / (3.0 * dist_to_near_edge)
        else:
            max_base_pressure = 99999.0

    # --- Factor of Safety: Bearing Capacity ---
    # Ultimate bearing capacity using Terzaghi for a strip footing at surface.
    # q_ult = c * Nc + q_overburden * Nq + 0.5 * gamma * B' * Ngamma
    # For a surface footing: q_overburden = 0, so the Nq term is zero.
    # Use effective width B' = B - 2e for eccentric loading.
    nc, nq, ngamma = _terzaghi_bearing_factors(phi_foundation_rad)
    b_effective = b - 2.0 * abs(eccentricity)
    if b_effective <= 0:
        b_effective = 0.01

    q_ultimate = c_found * nc + 0.5 * gamma_s * b_effective * ngamma

    if max_base_pressure > 0:
        fos_bearing = q_ultimate / max_base_pressure
    else:
        fos_bearing = 99.99

    return {
        "ka": round(ka, 2),
        "fos_sliding": round(fos_sliding, 2),
        "fos_overturning": round(fos_overturning, 2),
        "fos_bearing": round(fos_bearing, 2),
        "eccentricity_m": round(eccentricity, 2),
        "max_base_pressure_kpa": round(max_base_pressure, 2),
    }
