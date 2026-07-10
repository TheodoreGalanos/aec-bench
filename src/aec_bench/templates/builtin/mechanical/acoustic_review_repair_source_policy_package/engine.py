# ABOUTME: Computes SSC-12 acoustic review repair and source-policy metrics.
# ABOUTME: Scores source traceability, affected checks, corrected margins, and unresolved conflicts.

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
    updated_calculations: float,
    affected_calculations: float,
    source_referenced_rows: float,
    required_source_rows: float,
    pre_repair_level_dba: float,
    post_repair_level_dba: float,
    noise_criterion_dba: float,
    corrected_vibration_velocity_mm_s: float,
    vibration_criterion_mm_s: float,
    unresolved_conflict_count: float,
    complete_repair_ledger_rows: float,
    required_repair_ledger_rows: float,
) -> dict[str, float]:
    """Compute deterministic acoustic review repair and source-policy checks."""
    _require_positive(
        total_review_comments=total_review_comments,
        affected_calculations=affected_calculations,
        required_source_rows=required_source_rows,
        pre_repair_level_dba=pre_repair_level_dba,
        post_repair_level_dba=post_repair_level_dba,
        noise_criterion_dba=noise_criterion_dba,
        corrected_vibration_velocity_mm_s=corrected_vibration_velocity_mm_s,
        vibration_criterion_mm_s=vibration_criterion_mm_s,
        required_repair_ledger_rows=required_repair_ledger_rows,
    )
    if (
        min(
            closed_review_comments,
            updated_calculations,
            source_referenced_rows,
            unresolved_conflict_count,
            complete_repair_ledger_rows,
        )
        < 0
    ):
        msg = "counts must be >= 0"
        raise ValueError(msg)

    review_comment_closure_fraction = closed_review_comments / total_review_comments
    affected_calculation_update_fraction = updated_calculations / affected_calculations
    source_traceability_fraction = source_referenced_rows / required_source_rows
    mitigation_delta_db = pre_repair_level_dba - post_repair_level_dba
    corrected_noise_margin_db = noise_criterion_dba - post_repair_level_dba
    vibration_margin_mm_s = vibration_criterion_mm_s - corrected_vibration_velocity_mm_s
    repair_ledger_completeness_fraction = complete_repair_ledger_rows / required_repair_ledger_rows

    pass_checks = [
        review_comment_closure_fraction >= 1.0,
        affected_calculation_update_fraction >= 1.0,
        source_traceability_fraction >= 1.0,
        corrected_noise_margin_db >= 0.0,
        vibration_margin_mm_s >= 0.0,
        unresolved_conflict_count == 0.0,
        repair_ledger_completeness_fraction >= 0.9,
    ]

    return {
        "review_comment_closure_fraction": round(review_comment_closure_fraction, 3),
        "affected_calculation_update_fraction": round(affected_calculation_update_fraction, 3),
        "source_traceability_fraction": round(source_traceability_fraction, 3),
        "mitigation_delta_db": round(mitigation_delta_db, 3),
        "corrected_noise_margin_db": round(corrected_noise_margin_db, 3),
        "vibration_margin_mm_s": round(vibration_margin_mm_s, 3),
        "unresolved_conflict_count": round(unresolved_conflict_count, 3),
        "repair_ledger_completeness_fraction": round(repair_ledger_completeness_fraction, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
