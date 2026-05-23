# ABOUTME: SCS/NRCS curve number runoff depth computation engine.
# ABOUTME: Calculates runoff depth Q from rainfall and curve number per NRCS TR-55.


def _validate_inputs(
    rainfall_depth_mm: float,
    curve_number: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if rainfall_depth_mm < 0:
        msg = "rainfall_depth_mm must be >= 0"
        raise ValueError(msg)
    if curve_number < 1:
        msg = "curve_number must be >= 1"
        raise ValueError(msg)
    if curve_number > 100:
        msg = "curve_number must be <= 100"
        raise ValueError(msg)


def compute(
    rainfall_depth_mm: float,
    curve_number: float,
) -> dict[str, float]:
    """Compute runoff depth using the SCS/NRCS curve number method.

    Formulas (metric, all lengths in mm):
        S  = (25400 / CN) - 254         potential maximum retention
        Ia = 0.2 * S                     initial abstraction
        Q  = (P - Ia)^2 / (P - Ia + S)  when P > Ia, else Q = 0

    Returns a dict with keys: potential_max_retention_mm,
    initial_abstraction_mm, runoff_depth_mm.
    """
    _validate_inputs(rainfall_depth_mm, curve_number)

    # Potential maximum retention (mm)
    s_mm = (25400.0 / curve_number) - 254.0

    # Initial abstraction (mm) — standard Ia = 0.2 * S
    ia_mm = 0.2 * s_mm

    # Runoff depth (mm) — only when rainfall exceeds initial abstraction
    if rainfall_depth_mm > ia_mm:
        numerator = (rainfall_depth_mm - ia_mm) ** 2
        denominator = (rainfall_depth_mm - ia_mm) + s_mm
        q_mm = numerator / denominator
    else:
        q_mm = 0.0

    return {
        "potential_max_retention_mm": round(s_mm, 2),
        "initial_abstraction_mm": round(ia_mm, 2),
        "runoff_depth_mm": round(q_mm, 2),
    }
