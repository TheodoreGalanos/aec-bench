# ABOUTME: Computes SSC-10 treatment review response and permit-basis metrics.
# ABOUTME: Combines SRT, permit margins, process capacity, comment closure, and source completeness.

from __future__ import annotations


def compute(
    base_required_srt_d: float,
    temperature_c: float,
    theta_factor: float,
    actual_srt_d: float,
    permit_bod_mg_l: float,
    predicted_bod_mg_l: float,
    permit_ammonia_mg_l: float,
    predicted_ammonia_mg_l: float,
    oxygen_required_kg_d: float,
    oxygen_capacity_kg_d: float,
    chemical_required_kg_d: float,
    chemical_capacity_kg_d: float,
    sludge_predicted_kg_d: float,
    sludge_handling_capacity_kg_d: float,
    total_review_comments: float,
    closed_review_comments: float,
    critical_comments_open: float,
    source_references_found: float,
    source_references_required: float,
) -> dict[str, float]:
    """Compute source-bound SSC-10 permit and review response metrics."""
    required_srt_d = base_required_srt_d * theta_factor ** (20.0 - temperature_c)
    srt_margin_d = actual_srt_d - required_srt_d
    bod_permit_margin_mg_l = permit_bod_mg_l - predicted_bod_mg_l
    ammonia_permit_margin_mg_l = permit_ammonia_mg_l - predicted_ammonia_mg_l
    oxygen_capacity_margin_kg_d = oxygen_capacity_kg_d - oxygen_required_kg_d
    chemical_capacity_margin_kg_d = chemical_capacity_kg_d - chemical_required_kg_d
    sludge_capacity_margin_kg_d = sludge_handling_capacity_kg_d - sludge_predicted_kg_d
    comments_resolved_fraction = closed_review_comments / total_review_comments
    source_completeness_fraction = source_references_found / source_references_required
    critical_closed_score = 1.0 if critical_comments_open == 0.0 else 0.0
    response_completeness_score = (
        comments_resolved_fraction + source_completeness_fraction + critical_closed_score
    ) / 3.0
    overall_pass_score = (
        1.0
        if min(
            srt_margin_d,
            bod_permit_margin_mg_l,
            ammonia_permit_margin_mg_l,
            oxygen_capacity_margin_kg_d,
            chemical_capacity_margin_kg_d,
            sludge_capacity_margin_kg_d,
            critical_closed_score,
        )
        >= 0.0
        else 0.0
    )

    return {
        "required_srt_d": round(required_srt_d, 3),
        "srt_margin_d": round(srt_margin_d, 3),
        "bod_permit_margin_mg_l": round(bod_permit_margin_mg_l, 3),
        "ammonia_permit_margin_mg_l": round(ammonia_permit_margin_mg_l, 3),
        "oxygen_capacity_margin_kg_d": round(oxygen_capacity_margin_kg_d, 3),
        "chemical_capacity_margin_kg_d": round(chemical_capacity_margin_kg_d, 3),
        "sludge_capacity_margin_kg_d": round(sludge_capacity_margin_kg_d, 3),
        "comments_resolved_fraction": round(comments_resolved_fraction, 3),
        "source_completeness_fraction": round(source_completeness_fraction, 3),
        "response_completeness_score": round(response_completeness_score, 3),
        "critical_comments_open": round(critical_comments_open, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
