# ABOUTME: Surface overflow rate computation engine for clarifiers.
# ABOUTME: Calculates hydraulic loading and numeric design-criterion margins.


def _validate_inputs(
    flow_rate_m3_d: float,
    clarifier_surface_area_m2: float,
    maximum_sor_m3_m2_d: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if flow_rate_m3_d <= 0:
        msg = "flow_rate_m3_d must be > 0"
        raise ValueError(msg)
    if clarifier_surface_area_m2 <= 0:
        msg = "clarifier_surface_area_m2 must be > 0"
        raise ValueError(msg)
    if maximum_sor_m3_m2_d <= 0:
        msg = "maximum_sor_m3_m2_d must be > 0"
        raise ValueError(msg)


def compute(
    flow_rate_m3_d: float,
    clarifier_surface_area_m2: float,
    maximum_sor_m3_m2_d: float,
) -> dict[str, float]:
    """Compute surface overflow rate and criterion margin.

    Returns a dict with keys: surface_overflow_rate_m3_m2_d,
    utilisation_ratio, compliance_margin_m3_m2_d, criterion_satisfied.
    """
    _validate_inputs(flow_rate_m3_d, clarifier_surface_area_m2, maximum_sor_m3_m2_d)

    sor = flow_rate_m3_d / clarifier_surface_area_m2
    utilisation_ratio = sor / maximum_sor_m3_m2_d
    compliance_margin = maximum_sor_m3_m2_d - sor
    criterion_satisfied = 1.0 if sor <= maximum_sor_m3_m2_d else 0.0

    return {
        "surface_overflow_rate_m3_m2_d": round(sor, 2),
        "utilisation_ratio": round(utilisation_ratio, 2),
        "compliance_margin_m3_m2_d": round(compliance_margin, 2),
        "criterion_satisfied": round(criterion_satisfied, 2),
    }
