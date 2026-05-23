# ABOUTME: Visibility criterion computation engine for tenability checks.
# ABOUTME: Calculates visibility from extinction coefficient and explicit criterion.


def _validate_inputs(
    extinction_coefficient_m_inv: float,
    visibility_constant: float,
    minimum_visibility_m: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if extinction_coefficient_m_inv <= 0:
        msg = "extinction_coefficient_m_inv must be > 0"
        raise ValueError(msg)
    if visibility_constant <= 0:
        msg = "visibility_constant must be > 0"
        raise ValueError(msg)
    if minimum_visibility_m <= 0:
        msg = "minimum_visibility_m must be > 0"
        raise ValueError(msg)


def compute(
    extinction_coefficient_m_inv: float,
    visibility_constant: float,
    minimum_visibility_m: float,
) -> dict[str, float]:
    """Compute visibility and tenability margin.

    Returns a dict with keys: visibility_m, visibility_margin_m,
    visibility_utilisation_ratio, criterion_satisfied.
    """
    _validate_inputs(
        extinction_coefficient_m_inv,
        visibility_constant,
        minimum_visibility_m,
    )

    visibility = visibility_constant / extinction_coefficient_m_inv
    margin = visibility - minimum_visibility_m
    utilisation = minimum_visibility_m / visibility
    criterion_satisfied = 1.0 if visibility >= minimum_visibility_m else 0.0

    return {
        "visibility_m": round(visibility, 2),
        "visibility_margin_m": round(margin, 2),
        "visibility_utilisation_ratio": round(utilisation, 3),
        "criterion_satisfied": round(criterion_satisfied, 2),
    }
