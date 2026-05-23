# ABOUTME: Thermal movement computation engine for structural and facade components.
# ABOUTME: Calculates expansion and contraction from member length, temperature change, and CTE.


def _validate_inputs(
    member_length_mm: float,
    temperature_range_c: float,
    coefficient_thermal_expansion_microstrain_c: float,
    joint_safety_factor: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if member_length_mm <= 0:
        msg = "member_length_mm must be > 0"
        raise ValueError(msg)
    if temperature_range_c <= 0:
        msg = "temperature_range_c must be > 0"
        raise ValueError(msg)
    if coefficient_thermal_expansion_microstrain_c <= 0:
        msg = "coefficient_thermal_expansion_microstrain_c must be > 0"
        raise ValueError(msg)
    if joint_safety_factor < 1.0:
        msg = "joint_safety_factor must be >= 1.0"
        raise ValueError(msg)


def compute(
    member_length_mm: float,
    temperature_range_c: float,
    coefficient_thermal_expansion_microstrain_c: float,
    joint_safety_factor: float,
) -> dict[str, float]:
    """Compute thermal movement and recommended joint allowance.

    Returns a dict with keys: thermal_movement_mm, expansion_movement_mm,
    contraction_movement_mm, accommodation_required_mm.
    """
    _validate_inputs(
        member_length_mm,
        temperature_range_c,
        coefficient_thermal_expansion_microstrain_c,
        joint_safety_factor,
    )

    alpha = coefficient_thermal_expansion_microstrain_c * 1.0e-6
    movement = alpha * member_length_mm * temperature_range_c
    expansion = movement / 2.0
    contraction = movement / 2.0
    accommodation = movement * joint_safety_factor

    return {
        "thermal_movement_mm": round(movement, 2),
        "expansion_movement_mm": round(expansion, 2),
        "contraction_movement_mm": round(contraction, 2),
        "accommodation_required_mm": round(accommodation, 2),
    }
