# ABOUTME: Computes SSC-16 staging review response and negative-case metrics.
# ABOUTME: Scores comment closure, affected updates, source matching, margins, conflicts, and repair completeness.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    closed_review_comments: float,
    total_review_comments: float,
    updated_affected_checks: float,
    total_affected_checks: float,
    matching_stage_sources: float,
    referenced_stage_sources: float,
    revised_basin_capacity_m3: float,
    required_basin_capacity_m3: float,
    scheduled_traffic_device_count: float,
    inventoried_traffic_device_count: float,
    available_temp_power_w: float,
    revised_temp_load_w: float,
    allowed_tolerance_mm: float,
    observed_tolerance_mm: float,
    unresolved_conflict_count: float,
    completed_repair_fields: float,
    required_repair_fields: float,
) -> dict[str, float]:
    """Compute deterministic staging review response checks."""
    _require_positive(
        total_review_comments=total_review_comments,
        total_affected_checks=total_affected_checks,
        referenced_stage_sources=referenced_stage_sources,
        revised_basin_capacity_m3=revised_basin_capacity_m3,
        required_basin_capacity_m3=required_basin_capacity_m3,
        scheduled_traffic_device_count=scheduled_traffic_device_count,
        inventoried_traffic_device_count=inventoried_traffic_device_count,
        available_temp_power_w=available_temp_power_w,
        revised_temp_load_w=revised_temp_load_w,
        allowed_tolerance_mm=allowed_tolerance_mm,
        required_repair_fields=required_repair_fields,
    )
    if (
        min(
            closed_review_comments,
            updated_affected_checks,
            matching_stage_sources,
            observed_tolerance_mm,
            unresolved_conflict_count,
            completed_repair_fields,
        )
        < 0
    ):
        msg = "count and tolerance values must be >= 0"
        raise ValueError(msg)

    review_comment_closure_fraction = closed_review_comments / total_review_comments
    affected_check_update_fraction = updated_affected_checks / total_affected_checks
    stage_source_match_fraction = matching_stage_sources / referenced_stage_sources
    sediment_basin_margin_m3 = revised_basin_capacity_m3 - required_basin_capacity_m3
    traffic_device_delta_count = abs(scheduled_traffic_device_count - inventoried_traffic_device_count)
    power_headroom_w = available_temp_power_w - revised_temp_load_w
    tolerance_margin_mm = allowed_tolerance_mm - observed_tolerance_mm
    repair_ledger_completeness_fraction = completed_repair_fields / required_repair_fields

    pass_checks = [
        review_comment_closure_fraction >= 1.0,
        affected_check_update_fraction >= 1.0,
        stage_source_match_fraction >= 1.0,
        sediment_basin_margin_m3 >= 0.0,
        traffic_device_delta_count == 0.0,
        power_headroom_w >= 0.0,
        tolerance_margin_mm >= 0.0,
        unresolved_conflict_count == 0.0,
        repair_ledger_completeness_fraction >= 0.9,
    ]

    return {
        "review_comment_closure_fraction": round(review_comment_closure_fraction, 3),
        "affected_check_update_fraction": round(affected_check_update_fraction, 3),
        "stage_source_match_fraction": round(stage_source_match_fraction, 3),
        "sediment_basin_margin_m3": round(sediment_basin_margin_m3, 3),
        "traffic_device_delta_count": round(traffic_device_delta_count, 3),
        "power_headroom_w": round(power_headroom_w, 3),
        "tolerance_margin_mm": round(tolerance_margin_mm, 3),
        "unresolved_conflict_count": round(unresolved_conflict_count, 3),
        "repair_ledger_completeness_fraction": round(repair_ledger_completeness_fraction, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
