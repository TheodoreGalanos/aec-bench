# ABOUTME: Computes SSC-15 steel certificate structural, fire, and carbon metrics.
# ABOUTME: Combines weldability, capacity, fire temperature, and source evidence checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _fraction(numerator: float, denominator: float) -> float:
    _require_positive(denominator=denominator)
    return numerator / denominator


def compute(
    carbon_percent: float,
    manganese_percent: float,
    chromium_percent: float,
    molybdenum_percent: float,
    vanadium_percent: float,
    nickel_percent: float,
    copper_percent: float,
    carbon_equivalent_limit: float,
    certificate_capacity_kn: float,
    design_load_kn: float,
    fire_load_ratio: float,
    required_fire_temperature_c: float,
    matching_certificate_fields: float,
    required_certificate_fields: float,
    completed_memo_sections: float,
    required_memo_sections: float,
) -> dict[str, float]:
    _require_positive(
        carbon_equivalent_limit=carbon_equivalent_limit,
        certificate_capacity_kn=certificate_capacity_kn,
        design_load_kn=design_load_kn,
        fire_load_ratio=fire_load_ratio,
        required_fire_temperature_c=required_fire_temperature_c,
        required_certificate_fields=required_certificate_fields,
        required_memo_sections=required_memo_sections,
    )

    carbon_equivalent = (
        carbon_percent
        + manganese_percent / 6.0
        + (chromium_percent + molybdenum_percent + vanadium_percent) / 5.0
        + (nickel_percent + copper_percent) / 15.0
    )
    carbon_equivalent_margin = carbon_equivalent_limit - carbon_equivalent
    structural_capacity_margin_kn = certificate_capacity_kn - design_load_kn
    structural_utilization = design_load_kn / certificate_capacity_kn
    critical_steel_temperature_c = 905.0 - 690.0 * fire_load_ratio
    fire_temperature_margin_c = critical_steel_temperature_c - required_fire_temperature_c
    certificate_field_match_fraction = _fraction(matching_certificate_fields, required_certificate_fields)
    material_memo_completeness_fraction = _fraction(completed_memo_sections, required_memo_sections)

    overall_pass_score = (
        1.0
        if (
            carbon_equivalent_margin >= 0.0
            and structural_capacity_margin_kn >= 0.0
            and fire_temperature_margin_c >= 0.0
            and certificate_field_match_fraction >= 1.0
            and material_memo_completeness_fraction >= 1.0
        )
        else 0.0
    )

    return {
        "carbon_equivalent": round(carbon_equivalent, 3),
        "carbon_equivalent_margin": round(carbon_equivalent_margin, 3),
        "structural_capacity_margin_kn": round(structural_capacity_margin_kn, 3),
        "structural_utilization": round(structural_utilization, 3),
        "critical_steel_temperature_c": round(critical_steel_temperature_c, 3),
        "fire_temperature_margin_c": round(fire_temperature_margin_c, 3),
        "certificate_field_match_fraction": round(certificate_field_match_fraction, 3),
        "material_memo_completeness_fraction": round(material_memo_completeness_fraction, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
