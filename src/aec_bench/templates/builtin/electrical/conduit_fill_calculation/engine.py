# ABOUTME: Computes conduit fill percentage from conduit and cable diameters.
# ABOUTME: Uses circular cross-sectional areas and explicit maximum fill percentage.

import math


def _validate_inputs(
    conduit_internal_diameter_mm: float,
    cable_count: float,
    cable_outer_diameter_mm: float,
    maximum_fill_pct: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "conduit_internal_diameter_mm": conduit_internal_diameter_mm,
        "cable_count": cable_count,
        "cable_outer_diameter_mm": cable_outer_diameter_mm,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)
    if maximum_fill_pct <= 0 or maximum_fill_pct > 100:
        msg = "maximum_fill_pct must be > 0 and <= 100"
        raise ValueError(msg)


def compute(
    conduit_internal_diameter_mm: float,
    cable_count: float,
    cable_outer_diameter_mm: float,
    maximum_fill_pct: float,
) -> dict[str, float]:
    """Compute cable area, conduit area, fill percentage, and margin."""
    _validate_inputs(
        conduit_internal_diameter_mm,
        cable_count,
        cable_outer_diameter_mm,
        maximum_fill_pct,
    )

    total_cable_area_mm2 = cable_count * math.pi * cable_outer_diameter_mm**2 / 4.0
    conduit_area_mm2 = math.pi * conduit_internal_diameter_mm**2 / 4.0
    fill_percentage = total_cable_area_mm2 / conduit_area_mm2 * 100.0
    fill_margin_pct = maximum_fill_pct - fill_percentage

    return {
        "total_cable_area_mm2": round(total_cable_area_mm2, 2),
        "conduit_area_mm2": round(conduit_area_mm2, 2),
        "fill_percentage": round(fill_percentage, 2),
        "fill_margin_pct": round(fill_margin_pct, 2),
    }
