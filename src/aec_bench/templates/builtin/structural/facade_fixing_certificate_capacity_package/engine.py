# ABOUTME: Computes SSC-15 facade fixing certificate and capacity metrics.
# ABOUTME: Combines wind demand, bracket capacity, anchors, weldability, and tolerance checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    wind_pressure_kpa: float,
    tributary_area_m2: float,
    load_factor: float,
    bracket_capacity_kn: float,
    anchor_shear_capacity_kn: float,
    anchor_shear_demand_kn: float,
    matching_certificate_fields: float,
    required_certificate_fields: float,
    carbon_equivalent: float,
    carbon_equivalent_limit: float,
    adjustment_allowance_mm: float,
    measured_deviation_mm: float,
) -> dict[str, float]:
    _require_positive(
        wind_pressure_kpa=wind_pressure_kpa,
        tributary_area_m2=tributary_area_m2,
        load_factor=load_factor,
        bracket_capacity_kn=bracket_capacity_kn,
        anchor_shear_capacity_kn=anchor_shear_capacity_kn,
        anchor_shear_demand_kn=anchor_shear_demand_kn,
        required_certificate_fields=required_certificate_fields,
        carbon_equivalent_limit=carbon_equivalent_limit,
        adjustment_allowance_mm=adjustment_allowance_mm,
    )

    design_bracket_load_kn = wind_pressure_kpa * tributary_area_m2 * load_factor
    bracket_capacity_margin_kn = bracket_capacity_kn - design_bracket_load_kn
    bracket_utilization = design_bracket_load_kn / bracket_capacity_kn
    anchor_shear_margin_kn = anchor_shear_capacity_kn - anchor_shear_demand_kn
    certificate_field_match_fraction = matching_certificate_fields / required_certificate_fields
    carbon_equivalent_margin = carbon_equivalent_limit - carbon_equivalent
    tolerance_adjustment_margin_mm = adjustment_allowance_mm - measured_deviation_mm

    overall_pass_score = (
        1.0
        if (
            bracket_capacity_margin_kn >= 0.0
            and anchor_shear_margin_kn >= 0.0
            and certificate_field_match_fraction >= 1.0
            and carbon_equivalent_margin >= 0.0
            and tolerance_adjustment_margin_mm >= 0.0
        )
        else 0.0
    )

    return {
        "design_bracket_load_kn": round(design_bracket_load_kn, 3),
        "bracket_capacity_margin_kn": round(bracket_capacity_margin_kn, 3),
        "bracket_utilization": round(bracket_utilization, 3),
        "anchor_shear_margin_kn": round(anchor_shear_margin_kn, 3),
        "certificate_field_match_fraction": round(certificate_field_match_fraction, 3),
        "carbon_equivalent_margin": round(carbon_equivalent_margin, 3),
        "tolerance_adjustment_margin_mm": round(tolerance_adjustment_margin_mm, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
