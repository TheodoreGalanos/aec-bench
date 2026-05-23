# ABOUTME: Exit gradient and piping safety computation engine for dam foundations.
# ABOUTME: Calculates exit gradient, critical gradient, and factor of safety per USACE EM 1110-2-1901.

from typing import Literal

# Unit weight of water in kN/m3.
_GAMMA_W = 9.81

# Typical specific gravity of soil solids by soil type.
# Values from USACE EM 1110-1-1905 and standard geotechnical references.
_GS_TABLE: dict[str, float] = {
    "clean_sand": 2.65,
    "silty_sand": 2.66,
    "sandy_silt": 2.67,
    "clayey_silt": 2.70,
    "silty_clay": 2.72,
}

# Typical void ratio ranges by soil type (mid-range default).
# Used when void ratio is hidden and must be inferred from soil type.
_VOID_RATIO_TABLE: dict[str, float] = {
    "clean_sand": 0.65,
    "silty_sand": 0.55,
    "sandy_silt": 0.50,
    "clayey_silt": 0.45,
    "silty_clay": 0.40,
}


def _validate_inputs(
    head_difference_m: float,
    seepage_path_length_m: float,
    specific_gravity: float,
    void_ratio: float,
    foundation_soil_type: str,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if head_difference_m <= 0:
        msg = "head_difference_m must be > 0"
        raise ValueError(msg)
    if seepage_path_length_m <= 0:
        msg = "seepage_path_length_m must be > 0"
        raise ValueError(msg)
    if specific_gravity <= 1.0:
        msg = "specific_gravity must be > 1.0 (solid particles are denser than water)"
        raise ValueError(msg)
    if void_ratio <= 0:
        msg = "void_ratio must be > 0"
        raise ValueError(msg)
    if foundation_soil_type not in _GS_TABLE:
        msg = f"foundation_soil_type must be one of {list(_GS_TABLE.keys())}, got '{foundation_soil_type}'"
        raise ValueError(msg)


def _exit_gradient(head_difference_m: float, seepage_path_length_m: float) -> float:
    """Compute the exit gradient at the downstream toe.

    i_exit = delta_h / L_seepage
    where delta_h is the head difference across the structure and
    L_seepage is the total seepage path length through the foundation.
    """
    return head_difference_m / seepage_path_length_m


def _critical_gradient(specific_gravity: float, void_ratio: float) -> float:
    """Compute the critical hydraulic gradient for piping initiation.

    i_cr = (G_s - 1) / (1 + e)
    where G_s is the specific gravity of soil solids and e is the void ratio.
    At this gradient the upward seepage force equals the buoyant weight of the soil.
    """
    return (specific_gravity - 1.0) / (1.0 + void_ratio)


def _saturated_unit_weight(specific_gravity: float, void_ratio: float) -> float:
    """Compute the saturated unit weight of the soil.

    gamma_sat = (G_s + e) / (1 + e) * gamma_w
    """
    return (specific_gravity + void_ratio) / (1.0 + void_ratio) * _GAMMA_W


def _buoyant_unit_weight(specific_gravity: float, void_ratio: float) -> float:
    """Compute the buoyant (submerged) unit weight of the soil.

    gamma_b = gamma_sat - gamma_w = (G_s - 1) / (1 + e) * gamma_w
    """
    return (specific_gravity - 1.0) / (1.0 + void_ratio) * _GAMMA_W


def compute(
    head_difference_m: float,
    seepage_path_length_m: float,
    specific_gravity: float,
    void_ratio: float,
    foundation_soil_type: Literal["clean_sand", "silty_sand", "sandy_silt", "clayey_silt", "silty_clay"],
) -> dict[str, float]:
    """Compute exit gradient, critical gradient, and factor of safety against piping.

    Uses the direct gradient approach per USACE EM 1110-2-1901:
    - Exit gradient: i_exit = delta_h / L_seepage
    - Critical gradient: i_cr = (G_s - 1) / (1 + e)
    - Factor of safety: FoS = i_cr / i_exit

    Returns a dict with keys: exit_gradient, critical_gradient, factor_of_safety,
    saturated_unit_weight_kn_m3, buoyant_unit_weight_kn_m3.
    """
    _validate_inputs(
        head_difference_m,
        seepage_path_length_m,
        specific_gravity,
        void_ratio,
        foundation_soil_type,
    )

    i_exit = _exit_gradient(head_difference_m, seepage_path_length_m)
    i_cr = _critical_gradient(specific_gravity, void_ratio)
    fos = i_cr / i_exit

    gamma_sat = _saturated_unit_weight(specific_gravity, void_ratio)
    gamma_b = _buoyant_unit_weight(specific_gravity, void_ratio)

    return {
        "exit_gradient": round(i_exit, 2),
        "critical_gradient": round(i_cr, 2),
        "factor_of_safety": round(fos, 2),
        "saturated_unit_weight_kn_m3": round(gamma_sat, 2),
        "buoyant_unit_weight_kn_m3": round(gamma_b, 2),
    }
