# ABOUTME: Egress width computation engine for life-safety checks.
# ABOUTME: Calculates required egress width and provided margin from explicit rates.


def _validate_inputs(
    occupant_load: float,
    width_per_occupant_mm: float,
    provided_width_mm: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if occupant_load <= 0:
        msg = "occupant_load must be > 0"
        raise ValueError(msg)
    if width_per_occupant_mm <= 0:
        msg = "width_per_occupant_mm must be > 0"
        raise ValueError(msg)
    if provided_width_mm < 0:
        msg = "provided_width_mm must be >= 0"
        raise ValueError(msg)


def compute(
    occupant_load: float,
    width_per_occupant_mm: float,
    provided_width_mm: float,
) -> dict[str, float]:
    """Compute required egress width and adequacy margin.

    Returns a dict with keys: required_width_mm, provided_margin_mm,
    utilisation_ratio, width_satisfies.
    """
    _validate_inputs(occupant_load, width_per_occupant_mm, provided_width_mm)

    required_width = occupant_load * width_per_occupant_mm
    provided_margin = provided_width_mm - required_width
    if provided_width_mm > 0:
        utilisation_ratio = required_width / provided_width_mm
    else:
        utilisation_ratio = float("inf")
    width_satisfies = 1.0 if provided_width_mm >= required_width else 0.0

    return {
        "required_width_mm": round(required_width, 2),
        "provided_margin_mm": round(provided_margin, 2),
        "utilisation_ratio": round(utilisation_ratio, 3),
        "width_satisfies": round(width_satisfies, 2),
    }
