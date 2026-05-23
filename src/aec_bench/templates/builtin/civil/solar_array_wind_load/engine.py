# ABOUTME: Wind load computation engine for ground-mounted solar PV arrays.
# ABOUTME: Combines AS/NZS 1170.2 dynamic pressure with SEAOC PV2-2017 net pressure coefficients.

import math

# GCrn lookup table from SEAOC PV2-2017 for exposed (end-row) panels.
# Keys are tilt angles in degrees; values are (GCrn_uplift, GCrn_downforce).
# Uplift values are negative (suction on top surface), stored as magnitudes here
# and applied as negative in the computation.
_GCRN_TABLE_EXPOSED: dict[float, tuple[float, float]] = {
    5.0: (0.8, 0.3),
    10.0: (1.0, 0.5),
    15.0: (1.2, 0.7),
    20.0: (1.4, 0.9),
    25.0: (1.5, 1.0),
    30.0: (1.6, 1.1),
    35.0: (1.7, 1.1),
    45.0: (1.8, 1.2),
}

# Interior panels have reduced coefficients due to sheltering from adjacent rows.
# Reduction factor applied to the exposed-panel GCrn values.
_INTERIOR_REDUCTION_FACTOR = 0.6

# Drag coefficient for tilted flat panels (SEAOC PV2 / general aerodynamics).
_C_DRAG = 1.3


def _interpolate_gcrn(
    tilt_deg: float,
    table: dict[float, tuple[float, float]],
) -> tuple[float, float]:
    """Linearly interpolate GCrn values for a given tilt angle.

    Returns (GCrn_uplift_magnitude, GCrn_downforce) by interpolating between
    the two nearest tilt entries in the lookup table.
    """
    sorted_tilts = sorted(table.keys())

    # Clamp to table bounds.
    if tilt_deg <= sorted_tilts[0]:
        return table[sorted_tilts[0]]
    if tilt_deg >= sorted_tilts[-1]:
        return table[sorted_tilts[-1]]

    # Find bounding entries.
    for i in range(len(sorted_tilts) - 1):
        t_lo = sorted_tilts[i]
        t_hi = sorted_tilts[i + 1]
        if t_lo <= tilt_deg <= t_hi:
            frac = (tilt_deg - t_lo) / (t_hi - t_lo)
            uplift_lo, down_lo = table[t_lo]
            uplift_hi, down_hi = table[t_hi]
            uplift = uplift_lo + frac * (uplift_hi - uplift_lo)
            down = down_lo + frac * (down_hi - down_lo)
            return (uplift, down)

    # Fallback (should not be reached).
    return table[sorted_tilts[-1]]


def _validate_inputs(
    design_wind_speed_m_per_s: float,
    tilt_angle_deg: float,
    array_height_m: float,
    module_width_m: float,
    module_length_m: float,
    num_modules_wide: int,
    row_position: str,
    air_density_kg_per_m3: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if design_wind_speed_m_per_s <= 0:
        msg = "design_wind_speed_m_per_s must be > 0"
        raise ValueError(msg)
    if design_wind_speed_m_per_s > 100:
        msg = "design_wind_speed_m_per_s must be <= 100"
        raise ValueError(msg)
    if tilt_angle_deg < 5:
        msg = "tilt_angle_deg must be >= 5"
        raise ValueError(msg)
    if tilt_angle_deg > 45:
        msg = "tilt_angle_deg must be <= 45"
        raise ValueError(msg)
    if array_height_m <= 0:
        msg = "array_height_m must be > 0"
        raise ValueError(msg)
    if array_height_m > 5:
        msg = "array_height_m must be <= 5"
        raise ValueError(msg)
    if module_width_m <= 0:
        msg = "module_width_m must be > 0"
        raise ValueError(msg)
    if module_length_m <= 0:
        msg = "module_length_m must be > 0"
        raise ValueError(msg)
    if num_modules_wide < 1:
        msg = "num_modules_wide must be >= 1"
        raise ValueError(msg)
    if row_position not in ("exposed", "interior"):
        msg = f"row_position must be 'exposed' or 'interior', got '{row_position}'"
        raise ValueError(msg)
    if air_density_kg_per_m3 <= 0:
        msg = "air_density_kg_per_m3 must be > 0"
        raise ValueError(msg)


def compute(
    design_wind_speed_m_per_s: float,
    tilt_angle_deg: float,
    array_height_m: float,
    module_width_m: float,
    module_length_m: float,
    num_modules_wide: int,
    row_position: str = "exposed",
    air_density_kg_per_m3: float = 1.2,
) -> dict[str, float]:
    """Compute wind loads on a ground-mounted solar PV array.

    Combines AS/NZS 1170.2 dynamic pressure (q = 0.5 * rho * V^2) with
    SEAOC PV2-2017 net pressure coefficients (GCrn) for ground-mounted arrays.

    The design wind speed input is the site design wind speed V_des,theta after
    all AS/NZS 1170.2 multipliers (terrain, topography, shielding, direction)
    have been applied.

    Returns a dict with keys:
        dynamic_pressure_kpa    - base velocity pressure (kPa)
        uplift_pressure_kpa     - net uplift (suction) pressure on array (kPa)
        downforce_pressure_kpa  - net downward pressure on array (kPa)
        uplift_force_per_module_kn - uplift force on a single module (kN)
        drag_force_per_m_kn     - horizontal drag force per metre of array width (kN/m)
    """
    _validate_inputs(
        design_wind_speed_m_per_s,
        tilt_angle_deg,
        array_height_m,
        module_width_m,
        module_length_m,
        num_modules_wide,
        row_position,
        air_density_kg_per_m3,
    )

    # Step 1: Dynamic (velocity) pressure per AS/NZS 1170.2.
    # q = 0.5 * rho * V_des^2 (Pa), convert to kPa.
    q_pa = 0.5 * air_density_kg_per_m3 * design_wind_speed_m_per_s**2
    dynamic_pressure_kpa = q_pa / 1000.0

    # Step 2: Interpolate GCrn net pressure coefficients from SEAOC PV2 table.
    gcrn_uplift_mag, gcrn_downforce = _interpolate_gcrn(tilt_angle_deg, _GCRN_TABLE_EXPOSED)

    # Apply interior reduction factor for sheltered rows.
    if row_position == "interior":
        gcrn_uplift_mag *= _INTERIOR_REDUCTION_FACTOR
        gcrn_downforce *= _INTERIOR_REDUCTION_FACTOR

    # Step 3: Net pressures on the array surface.
    # Uplift is suction (acts away from top surface), reported as positive magnitude.
    uplift_pressure_kpa = dynamic_pressure_kpa * gcrn_uplift_mag
    downforce_pressure_kpa = dynamic_pressure_kpa * gcrn_downforce

    # Step 4: Uplift force per module.
    # Module area = width * length.
    module_area_m2 = module_width_m * module_length_m
    uplift_force_per_module_kn = uplift_pressure_kpa * module_area_m2

    # Step 5: Drag force per metre of array width.
    # Projected area per metre of array width = array_depth * sin(tilt) per metre.
    # Array depth along the slope = num_modules_wide * module_width_m.
    tilt_rad = math.radians(tilt_angle_deg)
    array_depth_m = num_modules_wide * module_width_m
    projected_height_m = array_depth_m * math.sin(tilt_rad)

    # Drag force per unit length along the array row:
    # F_drag = q * C_drag * A_projected (per metre of row length).
    drag_force_per_m_kn = dynamic_pressure_kpa * _C_DRAG * projected_height_m

    return {
        "dynamic_pressure_kpa": round(dynamic_pressure_kpa, 2),
        "uplift_pressure_kpa": round(uplift_pressure_kpa, 2),
        "downforce_pressure_kpa": round(downforce_pressure_kpa, 2),
        "uplift_force_per_module_kn": round(uplift_force_per_module_kn, 2),
        "drag_force_per_m_kn": round(drag_force_per_m_kn, 2),
    }
