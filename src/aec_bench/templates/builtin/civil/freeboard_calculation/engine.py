# ABOUTME: Freeboard calculation computation engine for coastal and flood structures.
# ABOUTME: Calculates total freeboard allowance and minimum crest/floor level per NZS 4404 / MfE Guidance.


def _validate_inputs(
    design_water_level_m: float,
    wave_allowance_m: float,
    slr_allowance_m: float,
    construction_tolerance_m: float,
    safety_margin_m: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if design_water_level_m < 0:
        msg = "design_water_level_m must be >= 0"
        raise ValueError(msg)
    if wave_allowance_m < 0:
        msg = "wave_allowance_m must be >= 0"
        raise ValueError(msg)
    if slr_allowance_m < 0:
        msg = "slr_allowance_m must be >= 0"
        raise ValueError(msg)
    if construction_tolerance_m < 0:
        msg = "construction_tolerance_m must be >= 0"
        raise ValueError(msg)
    if safety_margin_m < 0:
        msg = "safety_margin_m must be >= 0"
        raise ValueError(msg)


def compute(
    design_water_level_m: float,
    wave_allowance_m: float,
    slr_allowance_m: float,
    construction_tolerance_m: float,
    safety_margin_m: float,
) -> dict[str, float]:
    """Compute total freeboard and minimum crest level for coastal/flood structures.

    Component-based freeboard approach (NZS 4404:2010 / MfE Guidance 2024):
        total_freeboard = wave_allowance + slr_allowance
                          + construction_tolerance + safety_margin

    Minimum crest or floor level:
        min_crest_level = design_water_level + total_freeboard

    Parameters:
        design_water_level_m: Design still-water level including tidal and
            storm surge components (m above datum).
        wave_allowance_m: Allowance for wave overtopping effects (m),
            depends on wave height and structure type (typical 0.3-1.0 m).
        slr_allowance_m: Climate change sea level rise allowance (m),
            depends on planning horizon (typical 0.1-1.0 m).
        construction_tolerance_m: Allowance for construction tolerances (m),
            typical 0.05-0.15 m.
        safety_margin_m: Safety margin based on consequence category (m),
            typical 0.15-0.50 m.

    Returns a dict with keys: total_freeboard_m, minimum_crest_level_m.
    """
    _validate_inputs(
        design_water_level_m,
        wave_allowance_m,
        slr_allowance_m,
        construction_tolerance_m,
        safety_margin_m,
    )

    # Total freeboard is the sum of all component allowances
    total_freeboard = wave_allowance_m + slr_allowance_m + construction_tolerance_m + safety_margin_m

    # Minimum crest/floor level is design water level plus total freeboard
    minimum_crest_level = design_water_level_m + total_freeboard

    return {
        "total_freeboard_m": round(total_freeboard, 2),
        "minimum_crest_level_m": round(minimum_crest_level, 2),
    }
