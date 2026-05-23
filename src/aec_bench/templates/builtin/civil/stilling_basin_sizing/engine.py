# ABOUTME: USBR stilling basin sizing computation engine.
# ABOUTME: Calculates Froude number, Belanger sequent depth, and basin length/type per USBR hydraulic design methods.

import math

# Gravitational acceleration (m/s^2).
_G = 9.81

# Basin type multipliers (k) keyed by USBR basin type code.
# Fr < 2.5: no basin needed (k = 0)
# 2.5 <= Fr < 4.5: USBR Type I pre-formed basin (k = 4.0)
# 4.5 <= Fr < 9.0: USBR Type II dentated sill basin (k = 4.5)
# Fr >= 9.0: USBR Type III baffle block basin (k = 4.0)
_BASIN_TYPES: list[tuple[float, float, float]] = [
    # (froude_upper_bound, basin_type_code, k_factor)
    (2.5, 0.0, 0.0),
    (4.5, 1.0, 4.0),
    (9.0, 2.0, 4.5),
]
_BASIN_TYPE_HIGH: tuple[float, float] = (3.0, 4.0)


def _select_basin(froude: float) -> tuple[float, float]:
    """Select basin type code and length factor k from Froude number.

    Returns (basin_type_code, k_factor) where basin_type_code is:
    0.0 = no basin, 1.0 = Type I, 2.0 = Type II, 3.0 = Type III.
    """
    for upper_bound, type_code, k_factor in _BASIN_TYPES:
        if froude < upper_bound:
            return type_code, k_factor
    return _BASIN_TYPE_HIGH


def _validate_inputs(
    unit_discharge_m3_s_m: float,
    drop_height_m: float,
    tailwater_depth_m: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if unit_discharge_m3_s_m <= 0:
        msg = "unit_discharge_m3_s_m must be > 0"
        raise ValueError(msg)
    if drop_height_m <= 0:
        msg = "drop_height_m must be > 0"
        raise ValueError(msg)
    if tailwater_depth_m < 0:
        msg = "tailwater_depth_m must be >= 0"
        raise ValueError(msg)


def compute(
    unit_discharge_m3_s_m: float,
    drop_height_m: float,
    tailwater_depth_m: float,
) -> dict[str, float]:
    """Compute USBR stilling basin dimensions from spillway parameters.

    Uses the energy-based supercritical velocity approximation and the Belanger
    conjugate depth equation to determine sequent depth, then selects basin type
    and length based on the entry Froude number.

    Returns a dict with keys: froude_number, sequent_depth_m, basin_length_m,
    basin_type.
    """
    _validate_inputs(unit_discharge_m3_s_m, drop_height_m, tailwater_depth_m)

    # Step 1: Supercritical velocity at basin entry (energy approximation)
    # V1 = sqrt(2 * g * delta_H)
    v1 = math.sqrt(2.0 * _G * drop_height_m)

    # Step 2: Supercritical depth from continuity
    # d1 = q / V1
    d1 = unit_discharge_m3_s_m / v1

    # Step 3: Froude number at basin entry
    # Fr1 = V1 / sqrt(g * d1)
    fr1 = v1 / math.sqrt(_G * d1)

    # Step 4: Sequent (conjugate) depth via Belanger equation
    # d2 = (d1 / 2) * (sqrt(1 + 8 * Fr1^2) - 1)
    d2 = (d1 / 2.0) * (math.sqrt(1.0 + 8.0 * fr1 * fr1) - 1.0)

    # Step 5: Select basin type and compute basin length
    basin_type_code, k_factor = _select_basin(fr1)
    l_basin = k_factor * d2

    return {
        "froude_number": round(fr1, 2),
        "sequent_depth_m": round(d2, 2),
        "basin_length_m": round(l_basin, 2),
        "basin_type": round(basin_type_code, 2),
    }
