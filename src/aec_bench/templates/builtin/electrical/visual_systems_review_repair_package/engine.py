# ABOUTME: Computes SSC-13 visual systems review and repair metrics.
# ABOUTME: Combines comment closure, affected-check repair, and source-conflict checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    closed_review_comments: float,
    total_review_comments: float,
    updated_affected_checks: float,
    required_affected_checks: float,
    revised_minimum_lux: float,
    required_minimum_lux: float,
    cctv_horizontal_pixels: float,
    revised_target_width_m: float,
    required_ppm: float,
    revised_network_load_mbps: float,
    network_capacity_mbps: float,
    revised_poe_load_w: float,
    poe_budget_w: float,
    unresolved_conflict_count: float,
    completed_repair_memo_sections: float,
    required_repair_memo_sections: float,
) -> dict[str, float]:
    _require_positive(
        total_review_comments=total_review_comments,
        required_affected_checks=required_affected_checks,
        required_minimum_lux=required_minimum_lux,
        cctv_horizontal_pixels=cctv_horizontal_pixels,
        revised_target_width_m=revised_target_width_m,
        required_ppm=required_ppm,
        network_capacity_mbps=network_capacity_mbps,
        poe_budget_w=poe_budget_w,
        required_repair_memo_sections=required_repair_memo_sections,
    )

    review_comment_closure_fraction = closed_review_comments / total_review_comments
    affected_check_update_fraction = updated_affected_checks / required_affected_checks
    lighting_minimum_margin_lux = revised_minimum_lux - required_minimum_lux
    revised_cctv_pixels_per_m = cctv_horizontal_pixels / revised_target_width_m
    cctv_ppm_margin = revised_cctv_pixels_per_m - required_ppm
    network_headroom_mbps = network_capacity_mbps - revised_network_load_mbps
    poe_headroom_w = poe_budget_w - revised_poe_load_w
    repair_memo_completeness_fraction = completed_repair_memo_sections / required_repair_memo_sections
    overall_pass_score = (
        1.0
        if (
            review_comment_closure_fraction >= 1.0
            and affected_check_update_fraction >= 1.0
            and lighting_minimum_margin_lux >= 0.0
            and cctv_ppm_margin >= 0.0
            and network_headroom_mbps >= 0.0
            and poe_headroom_w >= 0.0
            and unresolved_conflict_count == 0.0
            and repair_memo_completeness_fraction >= 0.85
        )
        else 0.0
    )

    return {
        "review_comment_closure_fraction": round(review_comment_closure_fraction, 3),
        "affected_check_update_fraction": round(affected_check_update_fraction, 3),
        "lighting_minimum_margin_lux": round(lighting_minimum_margin_lux, 3),
        "revised_cctv_pixels_per_m": round(revised_cctv_pixels_per_m, 3),
        "cctv_ppm_margin": round(cctv_ppm_margin, 3),
        "network_headroom_mbps": round(network_headroom_mbps, 3),
        "poe_headroom_w": round(poe_headroom_w, 3),
        "unresolved_conflict_count": round(unresolved_conflict_count, 3),
        "repair_memo_completeness_fraction": round(repair_memo_completeness_fraction, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
