# ABOUTME: Concrete target mean strength computation engine for mix design checks.
# ABOUTME: Applies explicit reliability and minimum-margin inputs to concrete strength.


def _validate_inputs(
    specified_strength_mpa: float,
    standard_deviation_mpa: float,
    k_factor: float,
    minimum_margin_mpa: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if specified_strength_mpa <= 0:
        msg = "specified_strength_mpa must be > 0"
        raise ValueError(msg)
    if standard_deviation_mpa < 0:
        msg = "standard_deviation_mpa must be >= 0"
        raise ValueError(msg)
    if k_factor < 0:
        msg = "k_factor must be >= 0"
        raise ValueError(msg)
    if minimum_margin_mpa < 0:
        msg = "minimum_margin_mpa must be >= 0"
        raise ValueError(msg)


def compute(
    specified_strength_mpa: float,
    standard_deviation_mpa: float,
    k_factor: float,
    minimum_margin_mpa: float,
) -> dict[str, float]:
    """Compute target mean concrete strength using an explicit margin rule.

    Returns a dict with keys: statistical_margin_mpa, governing_margin_mpa,
    target_mean_strength_mpa, margin_above_specified_mpa.
    """
    _validate_inputs(
        specified_strength_mpa,
        standard_deviation_mpa,
        k_factor,
        minimum_margin_mpa,
    )

    statistical_margin = k_factor * standard_deviation_mpa
    governing_margin = max(statistical_margin, minimum_margin_mpa)
    target_strength = specified_strength_mpa + governing_margin

    return {
        "statistical_margin_mpa": round(statistical_margin, 2),
        "governing_margin_mpa": round(governing_margin, 2),
        "target_mean_strength_mpa": round(target_strength, 2),
        "margin_above_specified_mpa": round(governing_margin, 2),
    }
