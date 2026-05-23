# ABOUTME: Rankine lateral earth pressure engine with water table effects for retaining walls.
# ABOUTME: Computes Ka, Kp, active/passive forces, overturning moment, and water thrust per AS 4678.

import math

# Unit weight of water in kN/m3.
_GAMMA_W = 9.81


def _validate_inputs(
    wall_height_m: float,
    friction_angle_deg: float,
    cohesion_kpa: float,
    unit_weight_kn_m3: float,
    surcharge_kpa: float,
    water_table_depth_m: float,
    backfill_slope_deg: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if wall_height_m <= 0:
        msg = "wall_height_m must be > 0"
        raise ValueError(msg)
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
    if surcharge_kpa < 0:
        msg = "surcharge_kpa must be >= 0"
        raise ValueError(msg)
    if water_table_depth_m < 0:
        msg = "water_table_depth_m must be >= 0"
        raise ValueError(msg)
    if backfill_slope_deg < 0:
        msg = "backfill_slope_deg must be >= 0"
        raise ValueError(msg)
    if backfill_slope_deg >= friction_angle_deg and friction_angle_deg > 0:
        msg = "backfill_slope_deg must be < friction_angle_deg for Rankine theory"
        raise ValueError(msg)


def _rankine_ka(phi_rad: float, beta_rad: float) -> float:
    """Active pressure coefficient using Rankine theory.

    Horizontal backfill: Ka = tan^2(45 - phi/2)
    Inclined backfill:   Ka = cos(beta) * (cos(beta) - sqrt(cos^2(beta) - cos^2(phi)))
                                        / (cos(beta) + sqrt(cos^2(beta) - cos^2(phi)))
    """
    if phi_rad == 0:
        return 1.0
    if beta_rad == 0:
        return math.tan(math.pi / 4.0 - phi_rad / 2.0) ** 2
    cos_beta = math.cos(beta_rad)
    cos_phi = math.cos(phi_rad)
    discriminant = cos_beta**2 - cos_phi**2
    if discriminant < 0:
        discriminant = 0.0
    sqrt_disc = math.sqrt(discriminant)
    return cos_beta * (cos_beta - sqrt_disc) / (cos_beta + sqrt_disc)


def _rankine_kp(phi_rad: float, beta_rad: float) -> float:
    """Passive pressure coefficient using Rankine theory.

    Horizontal backfill: Kp = tan^2(45 + phi/2)
    Inclined backfill:   Kp = cos(beta) * (cos(beta) + sqrt(cos^2(beta) - cos^2(phi)))
                                        / (cos(beta) - sqrt(cos^2(beta) - cos^2(phi)))
    """
    if phi_rad == 0:
        return 1.0
    if beta_rad == 0:
        return math.tan(math.pi / 4.0 + phi_rad / 2.0) ** 2
    cos_beta = math.cos(beta_rad)
    cos_phi = math.cos(phi_rad)
    discriminant = cos_beta**2 - cos_phi**2
    if discriminant < 0:
        discriminant = 0.0
    sqrt_disc = math.sqrt(discriminant)
    denominator = cos_beta - sqrt_disc
    if abs(denominator) < 1e-12:
        return 1e6
    return cos_beta * (cos_beta + sqrt_disc) / denominator


def _effective_unit_weight(unit_weight_kn_m3: float) -> float:
    """Submerged (buoyant) unit weight below the water table.

    gamma' = gamma_sat - gamma_w
    """
    return unit_weight_kn_m3 - _GAMMA_W


def compute(
    wall_height_m: float,
    friction_angle_deg: float,
    cohesion_kpa: float,
    unit_weight_kn_m3: float,
    surcharge_kpa: float = 0.0,
    water_table_depth_m: float = 12.0,
    backfill_slope_deg: float = 0.0,
) -> dict[str, float]:
    """Compute Rankine lateral earth pressures and forces on a retaining wall.

    Handles two-layer pressure distribution when water table is present:
    - Above water table: total unit weight used for effective stress
    - Below water table: effective (buoyant) unit weight + hydrostatic pressure

    When water_table_depth_m >= wall_height_m, there is no water table effect.

    Returns a dict with keys: ka, kp, active_force_kn_per_m,
    passive_force_kn_per_m, active_moment_knm_per_m, water_force_kn_per_m.
    """
    # Clamp water table depth: values >= wall height mean no water table present.
    water_table_depth_m = min(water_table_depth_m, wall_height_m)

    _validate_inputs(
        wall_height_m,
        friction_angle_deg,
        cohesion_kpa,
        unit_weight_kn_m3,
        surcharge_kpa,
        water_table_depth_m,
        backfill_slope_deg,
    )

    phi_rad = math.radians(friction_angle_deg)
    beta_rad = math.radians(backfill_slope_deg)

    ka = _rankine_ka(phi_rad, beta_rad)
    kp = _rankine_kp(phi_rad, beta_rad)

    sqrt_ka = math.sqrt(ka)
    sqrt_kp = math.sqrt(kp)

    h = wall_height_m
    gamma = unit_weight_kn_m3
    c = cohesion_kpa
    q = surcharge_kpa
    d_w = water_table_depth_m  # depth from top to water table

    # Height of submerged zone below the water table.
    h_sub = h - d_w
    gamma_eff = _effective_unit_weight(gamma) if h_sub > 0 else 0.0

    # --- Active earth pressure force ---
    # Zone 1: above water table (depth 0 to d_w), total unit weight
    # Effective vertical stress at water table level:
    #   sigma_v_wt = gamma * d_w + q
    # Active pressure at water table:
    #   sigma_a_wt = Ka * (gamma * d_w + q) - 2c * sqrt(Ka)

    # Zone 2: below water table (depth d_w to h), effective unit weight
    # Additional effective vertical stress below water table:
    #   delta_sigma_v = gamma' * h_sub
    # Active pressure at base:
    #   sigma_a_base = Ka * (gamma * d_w + gamma' * h_sub + q) - 2c * sqrt(Ka)

    # Force components (per unit wall length):
    # 1. Surcharge: uniform Ka*q over full height
    f_surcharge = ka * q * h

    # 2. Cohesion: uniform -2c*sqrt(Ka) over full height
    f_cohesion = -2.0 * c * sqrt_ka * h

    # 3. Soil weight above water table: triangular from 0 to Ka*gamma*d_w
    f_soil_above = 0.5 * ka * gamma * d_w**2 if d_w > 0 else 0.0

    # 4. Soil weight pressure carried through below water table:
    #    Rectangular component: Ka*gamma*d_w acts over h_sub
    f_soil_carryover = ka * gamma * d_w * h_sub if h_sub > 0 else 0.0

    # 5. Effective soil weight below water table: triangular from 0 to Ka*gamma'*h_sub
    f_soil_below = 0.5 * ka * gamma_eff * h_sub**2 if h_sub > 0 else 0.0

    total_active_force = f_surcharge + f_cohesion + f_soil_above + f_soil_carryover + f_soil_below
    # Clamp to zero if cohesion dominates.
    if total_active_force < 0:
        total_active_force = 0.0

    # --- Passive earth pressure force ---
    # Passive pressure at base: Kp * (gamma*d_w + gamma'*h_sub + q) + 2c*sqrt(Kp)
    # Decompose similarly:
    fp_surcharge = kp * q * h
    fp_cohesion = 2.0 * c * sqrt_kp * h
    fp_soil_above = 0.5 * kp * gamma * d_w**2 if d_w > 0 else 0.0
    fp_soil_carryover = kp * gamma * d_w * h_sub if h_sub > 0 else 0.0
    fp_soil_below = 0.5 * kp * gamma_eff * h_sub**2 if h_sub > 0 else 0.0

    total_passive_force = fp_surcharge + fp_cohesion + fp_soil_above + fp_soil_carryover + fp_soil_below

    # --- Water pressure force ---
    # Hydrostatic pressure: triangular from 0 at water table to gamma_w * h_sub at base.
    # This acts independently of Ka (Pascal's law).
    water_force = 0.5 * _GAMMA_W * h_sub**2 if h_sub > 0 else 0.0

    # --- Active moment about the base (overturning moment) ---
    # Each force component has a lever arm measured from the base of the wall.
    # Lever arms:
    #   Surcharge (uniform):       h/2
    #   Cohesion (uniform):        h/2
    #   Soil above WT (triangle):  zero at top, peak at d_w => centroid at 2*d_w/3 from top
    #   Carryover (rect below WT): centroid at h_sub/2
    #   Soil below WT (triangle):  zero at WT, peak at base => centroid at h_sub/3
    #   Water (triangle):          centroid at h_sub/3

    arm_surcharge = h / 2.0
    arm_cohesion = h / 2.0
    arm_soil_above = (h - 2.0 * d_w / 3.0) if d_w > 0 else 0.0
    arm_carryover = h_sub / 2.0 if h_sub > 0 else 0.0
    arm_soil_below = h_sub / 3.0 if h_sub > 0 else 0.0
    arm_water = h_sub / 3.0 if h_sub > 0 else 0.0

    # Use clamped active component forces for moment (consistent with clamped total).
    if total_active_force == 0.0:
        active_moment = 0.0
    else:
        active_moment = (
            f_surcharge * arm_surcharge
            + f_cohesion * arm_cohesion
            + f_soil_above * arm_soil_above
            + f_soil_carryover * arm_carryover
            + f_soil_below * arm_soil_below
        )
        # If cohesion reduced the moment below zero, clamp.
        if active_moment < 0:
            active_moment = 0.0

    # Add water force moment (always present when water table exists).
    water_moment = water_force * arm_water
    # Total overturning moment includes both effective earth pressure and water.
    total_active_moment = active_moment + water_moment

    return {
        "ka": round(ka, 2),
        "kp": round(kp, 2),
        "active_force_kn_per_m": round(total_active_force, 2),
        "passive_force_kn_per_m": round(total_passive_force, 2),
        "active_moment_knm_per_m": round(total_active_moment, 2),
        "water_force_kn_per_m": round(water_force, 2),
    }
