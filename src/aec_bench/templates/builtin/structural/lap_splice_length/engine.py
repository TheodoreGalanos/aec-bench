# ABOUTME: Lap splice length computation engine for reinforcement detailing.
# ABOUTME: Applies explicit splice factors and rounds required lap length.

import math


def _validate_inputs(
    development_length_mm: float,
    splice_class_factor: float,
    bar_location_factor: float,
    coating_factor: float,
    provided_lap_length_mm: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "development_length_mm": development_length_mm,
        "splice_class_factor": splice_class_factor,
        "bar_location_factor": bar_location_factor,
        "coating_factor": coating_factor,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)
    if provided_lap_length_mm < 0:
        msg = "provided_lap_length_mm must be >= 0"
        raise ValueError(msg)


def compute(
    development_length_mm: float,
    splice_class_factor: float,
    bar_location_factor: float,
    coating_factor: float,
    provided_lap_length_mm: float,
) -> dict[str, float]:
    """Compute required lap splice length from explicit factors.

    Returns a dict with keys: calculated_lap_length_mm, rounded_lap_length_mm,
    provided_margin_mm, provided_lap_satisfies.
    """
    _validate_inputs(
        development_length_mm,
        splice_class_factor,
        bar_location_factor,
        coating_factor,
        provided_lap_length_mm,
    )

    calculated_lap = development_length_mm * splice_class_factor * bar_location_factor * coating_factor
    rounded_lap = math.ceil(calculated_lap / 10.0) * 10.0
    provided_margin = provided_lap_length_mm - rounded_lap
    provided_satisfies = 1.0 if provided_lap_length_mm >= rounded_lap else 0.0

    return {
        "calculated_lap_length_mm": round(calculated_lap, 2),
        "rounded_lap_length_mm": round(rounded_lap, 2),
        "provided_margin_mm": round(provided_margin, 2),
        "provided_lap_satisfies": round(provided_satisfies, 2),
    }
