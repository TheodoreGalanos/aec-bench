# ABOUTME: Spillway weir discharge capacity computation engine.
# ABOUTME: Calculates discharge with pier and abutment contraction corrections.

from typing import Literal

# Pier contraction coefficients (Kp) by pier nose shape.
# USBR Design Standard No. 14, USACE EM 1110-2-1603.
_PIER_KP_TABLE: dict[str, float] = {
    "square": 0.02,
    "round": 0.01,
    "pointed": 0.00,
}

# Abutment contraction coefficients (Ka) by abutment shape.
# USBR/USACE standard values.
_ABUTMENT_KA_TABLE: dict[str, float] = {
    "square": 0.20,
    "rounded": 0.10,
    "streamlined": 0.00,
}

# Gravitational acceleration (m/s^2).
_G = 9.81


def _validate_inputs(
    crest_length_m: float,
    design_head_m: float,
    discharge_coefficient: float,
    number_of_piers: int,
    pier_shape: str,
    abutment_shape: str,
    approach_channel_width_m: float,
    approach_depth_m: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if crest_length_m <= 0:
        msg = "crest_length_m must be > 0"
        raise ValueError(msg)
    if design_head_m <= 0:
        msg = "design_head_m must be > 0"
        raise ValueError(msg)
    if discharge_coefficient <= 0:
        msg = "discharge_coefficient must be > 0"
        raise ValueError(msg)
    if number_of_piers < 0:
        msg = "number_of_piers must be >= 0"
        raise ValueError(msg)
    if pier_shape not in _PIER_KP_TABLE:
        msg = f"pier_shape must be one of {list(_PIER_KP_TABLE.keys())}, got '{pier_shape}'"
        raise ValueError(msg)
    if abutment_shape not in _ABUTMENT_KA_TABLE:
        msg = f"abutment_shape must be one of {list(_ABUTMENT_KA_TABLE.keys())}, got '{abutment_shape}'"
        raise ValueError(msg)
    if approach_channel_width_m <= 0:
        msg = "approach_channel_width_m must be > 0"
        raise ValueError(msg)
    if approach_depth_m <= 0:
        msg = "approach_depth_m must be > 0"
        raise ValueError(msg)


def _effective_crest_length(
    crest_length_m: float,
    number_of_piers: int,
    pier_shape: str,
    abutment_shape: str,
    head_m: float,
) -> float:
    """Compute the effective crest length corrected for pier and abutment contractions.

    L_eff = L - 2 * (N * Kp + Ka) * H
    where N = number of piers, Kp = pier contraction coeff, Ka = abutment contraction coeff.
    """
    kp = _PIER_KP_TABLE[pier_shape]
    ka = _ABUTMENT_KA_TABLE[abutment_shape]

    contraction = 2.0 * (number_of_piers * kp + ka) * head_m
    l_eff = crest_length_m - contraction

    # Effective length cannot be negative or zero
    if l_eff <= 0:
        msg = "Effective crest length is non-positive after pier/abutment corrections"
        raise ValueError(msg)

    return l_eff


def _approach_velocity_head(
    discharge_m3_s: float,
    approach_channel_width_m: float,
    approach_depth_m: float,
) -> float:
    """Compute approach velocity head Va^2 / (2g).

    Va = Q / (B * h_approach)
    Velocity head = Va^2 / (2 * g)
    """
    va = discharge_m3_s / (approach_channel_width_m * approach_depth_m)
    return (va**2) / (2.0 * _G)


def compute(
    crest_length_m: float,
    design_head_m: float,
    discharge_coefficient: float,
    number_of_piers: int = 0,
    pier_shape: Literal["square", "round", "pointed"] = "round",
    abutment_shape: Literal["square", "rounded", "streamlined"] = "rounded",
    approach_channel_width_m: float = 50.0,
    approach_depth_m: float = 5.0,
) -> dict[str, float]:
    """Compute spillway weir discharge capacity using Q = C * L_eff * H_e^1.5.

    Applies pier/abutment contraction corrections to effective crest length and
    approach velocity head correction to total energy head. Initial Q is computed
    without velocity head, then velocity head is calculated from Q and added to H
    for the corrected discharge.

    Returns a dict with keys: effective_crest_length_m, approach_velocity_head_m,
    total_energy_head_m, discharge_m3_s, unit_discharge_m3_s_per_m.
    """
    _validate_inputs(
        crest_length_m,
        design_head_m,
        discharge_coefficient,
        number_of_piers,
        pier_shape,
        abutment_shape,
        approach_channel_width_m,
        approach_depth_m,
    )

    c = discharge_coefficient

    # Step 1: Effective crest length with pier/abutment corrections
    l_eff = _effective_crest_length(
        crest_length_m,
        number_of_piers,
        pier_shape,
        abutment_shape,
        design_head_m,
    )

    # Step 2: Initial discharge estimate without approach velocity correction
    q_initial = c * l_eff * design_head_m**1.5

    # Step 3: Approach velocity head from initial discharge
    va_head = _approach_velocity_head(
        q_initial,
        approach_channel_width_m,
        approach_depth_m,
    )

    # Step 4: Total energy head = design head + approach velocity head
    h_e = design_head_m + va_head

    # Step 5: Corrected discharge using total energy head
    q_corrected = c * l_eff * h_e**1.5

    # Step 6: Unit discharge per metre of effective crest length
    q_unit = q_corrected / l_eff

    return {
        "effective_crest_length_m": round(l_eff, 2),
        "approach_velocity_head_m": round(va_head, 2),
        "total_energy_head_m": round(h_e, 2),
        "discharge_m3_s": round(q_corrected, 2),
        "unit_discharge_m3_s_per_m": round(q_unit, 2),
    }
