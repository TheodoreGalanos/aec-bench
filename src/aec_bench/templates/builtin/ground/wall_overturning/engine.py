# ABOUTME: Retaining wall overturning stability computation engine.
# ABOUTME: Calculates active earth pressure and factor of safety against overturning about the toe.

import math

# Unit weight of water (kN/m3).
_GAMMA_W = 9.81


def _validate_inputs(
    wall_height_m: float,
    base_width_m: float,
    stem_thickness_m: float,
    base_thickness_m: float,
    backfill_friction_angle_deg: float,
    backfill_unit_weight_kn_m3: float,
    concrete_unit_weight_kn_m3: float,
    surcharge_kpa: float,
    water_table_depth_m: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if wall_height_m <= 0:
        msg = "wall_height_m must be > 0"
        raise ValueError(msg)
    if base_width_m <= 0:
        msg = "base_width_m must be > 0"
        raise ValueError(msg)
    if stem_thickness_m <= 0:
        msg = "stem_thickness_m must be > 0"
        raise ValueError(msg)
    if base_thickness_m <= 0:
        msg = "base_thickness_m must be > 0"
        raise ValueError(msg)
    if stem_thickness_m >= base_width_m:
        msg = "stem_thickness_m must be < base_width_m"
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
    if concrete_unit_weight_kn_m3 <= 0:
        msg = "concrete_unit_weight_kn_m3 must be > 0"
        raise ValueError(msg)
    if surcharge_kpa < 0:
        msg = "surcharge_kpa must be >= 0"
        raise ValueError(msg)
    if water_table_depth_m < 0:
        msg = "water_table_depth_m must be >= 0"
        raise ValueError(msg)


def compute(
    wall_height_m: float,
    base_width_m: float,
    stem_thickness_m: float,
    base_thickness_m: float,
    backfill_friction_angle_deg: float,
    backfill_unit_weight_kn_m3: float,
    concrete_unit_weight_kn_m3: float,
    surcharge_kpa: float = 0.0,
    water_table_depth_m: float = 20.0,
) -> dict[str, float]:
    """Compute overturning stability for a cantilever retaining wall using Rankine theory.

    The wall has an L-shaped cross section: a vertical stem on a horizontal base slab.
    The stem sits at the heel (back) side of the base. Backfill rests on the heel slab
    behind the stem, extending from the stem face to the back edge of the base.

    Returns a dict with keys: ka, active_force_kn_m, overturning_moment_knm_m,
    resisting_moment_knm_m, factor_of_safety_overturning.
    """
    _validate_inputs(
        wall_height_m,
        base_width_m,
        stem_thickness_m,
        base_thickness_m,
        backfill_friction_angle_deg,
        backfill_unit_weight_kn_m3,
        concrete_unit_weight_kn_m3,
        surcharge_kpa,
        water_table_depth_m,
    )

    phi_rad = math.radians(backfill_friction_angle_deg)
    gamma_s = backfill_unit_weight_kn_m3
    gamma_c = concrete_unit_weight_kn_m3

    # Total height from base bottom to top of wall
    total_h = wall_height_m + base_thickness_m

    # Rankine active earth pressure coefficient
    # Ka = (1 - sin(phi)) / (1 + sin(phi))
    sin_phi = math.sin(phi_rad)
    ka = (1.0 - sin_phi) / (1.0 + sin_phi)

    # --- Overturning forces and moments (about toe) ---

    # Active earth pressure force on the full height (triangular distribution)
    # Pa = 0.5 * Ka * gamma * H^2
    pa = 0.5 * ka * gamma_s * total_h**2

    # Active force acts at H/3 from the base
    arm_pa = total_h / 3.0
    overturning_moment = pa * arm_pa

    # Surcharge produces a uniform lateral pressure: q_h = Ka * q
    # This acts over the full height with resultant at H/2
    if surcharge_kpa > 0:
        pa_surcharge = ka * surcharge_kpa * total_h
        arm_surcharge = total_h / 2.0
        overturning_moment += pa_surcharge * arm_surcharge
        pa += pa_surcharge

    # Water pressure contribution when water table is within the wall height
    if water_table_depth_m < total_h:
        hw = total_h - water_table_depth_m
        # Hydrostatic force from water pressure (triangular)
        pa_water = 0.5 * _GAMMA_W * hw**2
        arm_water = hw / 3.0
        overturning_moment += pa_water * arm_water
        pa += pa_water

    # --- Resisting forces and moments (about toe) ---

    # Cantilever L-wall layout (left=toe, right=heel):
    #   |--toe--|--stem--|-------heel-------|
    # Standard proportion: toe is ~1/3 of the base width. The heel carries
    # the backfill soil whose weight provides the resisting moment.
    toe_length = base_width_m / 3.0
    heel_length = base_width_m - toe_length - stem_thickness_m

    resisting_moment = 0.0

    # Component 1: Base slab weight
    w_base = gamma_c * base_width_m * base_thickness_m
    arm_base = base_width_m / 2.0
    resisting_moment += w_base * arm_base

    # Component 2: Stem weight (sits on base, front face at toe_length from toe)
    stem_h = wall_height_m  # stem height above the base slab
    w_stem = gamma_c * stem_thickness_m * stem_h
    arm_stem = toe_length + stem_thickness_m / 2.0
    resisting_moment += w_stem * arm_stem

    # Component 3: Backfill soil on the heel (behind the stem, above the base)
    w_soil = gamma_s * heel_length * stem_h
    arm_soil = toe_length + stem_thickness_m + heel_length / 2.0
    resisting_moment += w_soil * arm_soil

    # Component 4: Surcharge weight on the heel (vertical load, resists overturning)
    if surcharge_kpa > 0:
        w_surcharge = surcharge_kpa * heel_length
        arm_surcharge_v = toe_length + stem_thickness_m + heel_length / 2.0
        resisting_moment += w_surcharge * arm_surcharge_v

    # Factor of safety against overturning
    fos = resisting_moment / overturning_moment

    return {
        "ka": round(ka, 2),
        "active_force_kn_m": round(pa, 2),
        "overturning_moment_knm_m": round(overturning_moment, 2),
        "resisting_moment_knm_m": round(resisting_moment, 2),
        "factor_of_safety_overturning": round(fos, 2),
    }
