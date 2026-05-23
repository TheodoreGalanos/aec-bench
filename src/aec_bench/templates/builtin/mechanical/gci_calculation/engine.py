# ABOUTME: Grid convergence index computation engine.
# ABOUTME: Calculates observed order, extrapolated value, and fine-grid GCI.

import math

_SAFETY_FACTOR = 1.25


def _validate_inputs(
    coarse_grid_value: float,
    medium_grid_value: float,
    fine_grid_value: float,
    refinement_ratio: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if refinement_ratio <= 1:
        msg = "refinement_ratio must be > 1"
        raise ValueError(msg)
    coarse_medium = coarse_grid_value - medium_grid_value
    medium_fine = medium_grid_value - fine_grid_value
    if coarse_medium == 0:
        msg = "coarse_grid_value and medium_grid_value must differ"
        raise ValueError(msg)
    if medium_fine == 0:
        msg = "medium_grid_value and fine_grid_value must differ"
        raise ValueError(msg)
    if coarse_medium / medium_fine <= 0:
        msg = "grid values must show monotonic convergence"
        raise ValueError(msg)
    if fine_grid_value == 0:
        msg = "fine_grid_value must be non-zero"
        raise ValueError(msg)


def compute(
    coarse_grid_value: float,
    medium_grid_value: float,
    fine_grid_value: float,
    refinement_ratio: float,
) -> dict[str, float]:
    """Compute observed order, Richardson extrapolation, and fine-grid GCI.

    Returns a dict with keys: observed_order, extrapolated_value,
    approximate_relative_error_pct, gci_fine_pct, asymptotic_range_ratio.
    """
    _validate_inputs(
        coarse_grid_value,
        medium_grid_value,
        fine_grid_value,
        refinement_ratio,
    )

    coarse_medium = coarse_grid_value - medium_grid_value
    medium_fine = medium_grid_value - fine_grid_value
    observed_order = math.log(abs(coarse_medium / medium_fine)) / math.log(refinement_ratio)
    refinement_term = refinement_ratio**observed_order - 1.0
    extrapolated_value = fine_grid_value + (fine_grid_value - medium_grid_value) / refinement_term
    approximate_relative_error = abs((fine_grid_value - medium_grid_value) / fine_grid_value) * 100.0
    gci_fine = _SAFETY_FACTOR * approximate_relative_error / refinement_term
    gci_medium = (
        _SAFETY_FACTOR * abs((medium_grid_value - coarse_grid_value) / medium_grid_value) * 100.0 / refinement_term
    )
    asymptotic_range_ratio = gci_medium / (refinement_ratio**observed_order * gci_fine)

    return {
        "observed_order": round(observed_order, 3),
        "extrapolated_value": round(extrapolated_value, 3),
        "approximate_relative_error_pct": round(approximate_relative_error, 3),
        "gci_fine_pct": round(gci_fine, 3),
        "asymptotic_range_ratio": round(asymptotic_range_ratio, 3),
    }
