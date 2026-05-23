# ABOUTME: Solids loading rate computation engine for secondary clarifiers.
# ABOUTME: Converts flow and MLSS concentration into area-normalised solids loading.


def _validate_inputs(
    total_flow_m3_d: float,
    mlss_concentration_mg_l: float,
    clarifier_surface_area_m2: float,
    maximum_slr_kg_m2_h: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if total_flow_m3_d <= 0:
        msg = "total_flow_m3_d must be > 0"
        raise ValueError(msg)
    if mlss_concentration_mg_l <= 0:
        msg = "mlss_concentration_mg_l must be > 0"
        raise ValueError(msg)
    if clarifier_surface_area_m2 <= 0:
        msg = "clarifier_surface_area_m2 must be > 0"
        raise ValueError(msg)
    if maximum_slr_kg_m2_h <= 0:
        msg = "maximum_slr_kg_m2_h must be > 0"
        raise ValueError(msg)


def compute(
    total_flow_m3_d: float,
    mlss_concentration_mg_l: float,
    clarifier_surface_area_m2: float,
    maximum_slr_kg_m2_h: float,
) -> dict[str, float]:
    """Compute secondary clarifier solids loading rate.

    Returns a dict with keys: solids_mass_flow_kg_d, solids_loading_rate_kg_m2_h,
    utilisation_ratio, compliance_margin_kg_m2_h, criterion_satisfied.
    """
    _validate_inputs(
        total_flow_m3_d,
        mlss_concentration_mg_l,
        clarifier_surface_area_m2,
        maximum_slr_kg_m2_h,
    )

    solids_mass_flow = total_flow_m3_d * mlss_concentration_mg_l / 1000.0
    slr = solids_mass_flow / clarifier_surface_area_m2 / 24.0
    utilisation_ratio = slr / maximum_slr_kg_m2_h
    compliance_margin = maximum_slr_kg_m2_h - slr
    criterion_satisfied = 1.0 if slr <= maximum_slr_kg_m2_h else 0.0

    return {
        "solids_mass_flow_kg_d": round(solids_mass_flow, 2),
        "solids_loading_rate_kg_m2_h": round(slr, 2),
        "utilisation_ratio": round(utilisation_ratio, 2),
        "compliance_margin_kg_m2_h": round(compliance_margin, 2),
        "criterion_satisfied": round(criterion_satisfied, 2),
    }
