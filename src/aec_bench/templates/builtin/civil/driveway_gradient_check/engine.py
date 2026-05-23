# ABOUTME: Driveway gradient computation engine per AS/NZS 2890.1:2004.
# ABOUTME: Calculates driveway gradient and checks compliance against location-based maximums.

from typing import Literal

# Maximum allowable gradients (%) by driveway location type.
# Sources: AS/NZS 2890.1:2004 and typical Australian council DCPs.
#   - transition_zone: first 6m from street boundary, max 12.5% (1:8)
#   - internal_residential: residential driveway beyond transition, max 25% (1:4)
#   - internal_commercial: commercial driveway beyond transition, max 20% (1:5)
#   - near_garage: approach to garage or parking area, max 16.7% (1:6)
#   - pedestrian_shared: shared pedestrian/vehicle access, max 12.5% (1:8)
_MAX_GRADIENT_PCT: dict[str, float] = {
    "transition_zone": 12.5,
    "internal_residential": 25.0,
    "internal_commercial": 20.0,
    "near_garage": 16.67,
    "pedestrian_shared": 12.5,
}


def _validate_inputs(
    start_level_m: float,
    end_level_m: float,
    horizontal_length_m: float,
    location_type: str,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if horizontal_length_m <= 0:
        msg = "horizontal_length_m must be > 0"
        raise ValueError(msg)
    if location_type not in _MAX_GRADIENT_PCT:
        msg = f"location_type must be one of {list(_MAX_GRADIENT_PCT.keys())}, got '{location_type}'"
        raise ValueError(msg)


def compute(
    start_level_m: float,
    end_level_m: float,
    horizontal_length_m: float,
    location_type: Literal[
        "transition_zone",
        "internal_residential",
        "internal_commercial",
        "near_garage",
        "pedestrian_shared",
    ],
) -> dict[str, float]:
    """Compute driveway gradient and check compliance with AS/NZS 2890.1:2004.

    Gradient formula: G = abs(end_level - start_level) / horizontal_length * 100 (%)

    Compliance: 1.0 if gradient <= max allowable for the location type, else 0.0.

    Returns a dict with keys: gradient_pct, max_allowable_gradient_pct, compliance.
    """
    _validate_inputs(start_level_m, end_level_m, horizontal_length_m, location_type)

    # Gradient as a percentage
    gradient_pct = abs(end_level_m - start_level_m) / horizontal_length_m * 100.0

    # Maximum allowable gradient for this location type
    max_allowable_pct = _MAX_GRADIENT_PCT[location_type]

    # Compliance check
    compliant = 1.0 if gradient_pct <= max_allowable_pct else 0.0

    return {
        "gradient_pct": round(gradient_pct, 2),
        "max_allowable_gradient_pct": round(max_allowable_pct, 2),
        "compliance": round(compliant, 2),
    }
