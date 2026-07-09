# ABOUTME: Computes SSC-07 ground improvement acceptance and foundation recheck metrics.
# ABOUTME: Keeps post-improvement SPT, bearing, settlement, and certificate checks source-bound.

from __future__ import annotations


def compute(
    pre_improvement_n1_60: float,
    post_improvement_n1_60: float,
    target_n1_60: float,
    applied_bearing_pressure_kpa: float,
    bearing_factor_per_blow_kpa: float,
    footing_width_m: float,
    elastic_modulus_kpa: float,
    poisson_ratio: float,
    primary_settlement_mm: float,
    allowable_settlement_mm: float,
    required_certificate_items: float,
    matching_certificate_items: float,
) -> dict[str, float]:
    """Compute ground-improvement acceptance source-pack metrics."""
    improvement_ratio = post_improvement_n1_60 / pre_improvement_n1_60
    post_improvement_n_margin = post_improvement_n1_60 - target_n1_60
    allowable_bearing_capacity_kpa = bearing_factor_per_blow_kpa * post_improvement_n1_60
    bearing_utilization = applied_bearing_pressure_kpa / allowable_bearing_capacity_kpa
    bearing_margin_kpa = allowable_bearing_capacity_kpa - applied_bearing_pressure_kpa
    immediate_settlement_mm = (
        applied_bearing_pressure_kpa * footing_width_m * (1.0 - poisson_ratio**2) / elastic_modulus_kpa * 1000.0
    )
    total_settlement_mm = immediate_settlement_mm + primary_settlement_mm
    settlement_margin_mm = allowable_settlement_mm - total_settlement_mm
    certificate_match_percent = matching_certificate_items / required_certificate_items * 100.0
    overall_pass_score = (
        1.0
        if (
            post_improvement_n_margin >= 0.0
            and bearing_margin_kpa >= 0.0
            and settlement_margin_mm >= 0.0
            and certificate_match_percent >= 100.0
        )
        else 0.0
    )

    return {
        "improvement_ratio": round(improvement_ratio, 3),
        "post_improvement_n_margin": round(post_improvement_n_margin, 3),
        "allowable_bearing_capacity_kpa": round(allowable_bearing_capacity_kpa, 3),
        "bearing_utilization": round(bearing_utilization, 3),
        "bearing_margin_kpa": round(bearing_margin_kpa, 3),
        "immediate_settlement_mm": round(immediate_settlement_mm, 3),
        "primary_settlement_mm": round(primary_settlement_mm, 3),
        "total_settlement_mm": round(total_settlement_mm, 3),
        "settlement_margin_mm": round(settlement_margin_mm, 3),
        "certificate_match_percent": round(certificate_match_percent, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
