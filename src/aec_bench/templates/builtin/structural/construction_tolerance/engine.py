# ABOUTME: Construction tolerance computation engine for structural fit-up checks.
# ABOUTME: Calculates total allowance, RSS tolerance, and required slot length.

import math


def _validate_inputs(*values: float) -> None:
    """Raise ValueError for invalid input parameters."""
    for value in values:
        if value < 0:
            msg = "tolerance components and component length must be >= 0"
            raise ValueError(msg)


def compute(
    fabrication_tolerance_mm: float,
    erection_tolerance_mm: float,
    survey_tolerance_mm: float,
    movement_allowance_mm: float,
    clearance_mm: float,
    component_length_mm: float,
) -> dict[str, float]:
    """Compute construction tolerance allowance and required slot length.

    Returns a dict with keys: total_allowance_mm, rss_tolerance_mm,
    required_slot_length_mm, clearance_included_mm.
    """
    _validate_inputs(
        fabrication_tolerance_mm,
        erection_tolerance_mm,
        survey_tolerance_mm,
        movement_allowance_mm,
        clearance_mm,
        component_length_mm,
    )

    total_allowance = (
        fabrication_tolerance_mm + erection_tolerance_mm + survey_tolerance_mm + movement_allowance_mm + clearance_mm
    )
    rss_tolerance = math.sqrt(
        fabrication_tolerance_mm**2 + erection_tolerance_mm**2 + survey_tolerance_mm**2 + movement_allowance_mm**2
    )
    required_slot_length = component_length_mm + 2.0 * total_allowance

    return {
        "total_allowance_mm": round(total_allowance, 2),
        "rss_tolerance_mm": round(rss_tolerance, 2),
        "required_slot_length_mm": round(required_slot_length, 2),
        "clearance_included_mm": round(clearance_mm, 2),
    }
