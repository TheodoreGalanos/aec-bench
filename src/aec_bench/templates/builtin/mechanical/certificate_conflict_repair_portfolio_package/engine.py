# ABOUTME: Computes SSC-15 certificate conflict and repair portfolio metrics.
# ABOUTME: Combines source authority, affected-calculation updates, substitution, and memo checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    selected_source_is_current: float,
    selected_source_has_authority: float,
    affected_calculation_count: float,
    updated_calculation_count: float,
    governing_certificate_capacity_kn: float,
    conflicting_datasheet_capacity_kn: float,
    replacement_capacity_kn: float,
    required_capacity_kn: float,
    total_conflict_items: float,
    closed_conflict_items: float,
    unresolved_conflict_count: float,
    expired_source_count: float,
    completed_repair_memo_sections: float,
    required_repair_memo_sections: float,
) -> dict[str, float]:
    _require_positive(
        affected_calculation_count=affected_calculation_count,
        governing_certificate_capacity_kn=governing_certificate_capacity_kn,
        conflicting_datasheet_capacity_kn=conflicting_datasheet_capacity_kn,
        replacement_capacity_kn=replacement_capacity_kn,
        required_capacity_kn=required_capacity_kn,
        total_conflict_items=total_conflict_items,
        required_repair_memo_sections=required_repair_memo_sections,
    )

    source_authority_score = min(selected_source_is_current, selected_source_has_authority)
    affected_calculation_update_fraction = updated_calculation_count / affected_calculation_count
    certificate_capacity_delta_kn = governing_certificate_capacity_kn - conflicting_datasheet_capacity_kn
    replacement_capacity_margin_kn = replacement_capacity_kn - required_capacity_kn
    source_conflict_closure_fraction = closed_conflict_items / total_conflict_items
    repair_memo_completeness_fraction = completed_repair_memo_sections / required_repair_memo_sections

    overall_pass_score = (
        1.0
        if (
            source_authority_score >= 1.0
            and affected_calculation_update_fraction >= 1.0
            and certificate_capacity_delta_kn > 0.0
            and replacement_capacity_margin_kn >= 0.0
            and source_conflict_closure_fraction >= 1.0
            and unresolved_conflict_count == 0.0
            and expired_source_count == 0.0
            and repair_memo_completeness_fraction >= 0.9
        )
        else 0.0
    )

    return {
        "source_authority_score": round(source_authority_score, 3),
        "affected_calculation_update_fraction": round(affected_calculation_update_fraction, 3),
        "certificate_capacity_delta_kn": round(certificate_capacity_delta_kn, 3),
        "replacement_capacity_margin_kn": round(replacement_capacity_margin_kn, 3),
        "source_conflict_closure_fraction": round(source_conflict_closure_fraction, 3),
        "unresolved_conflict_count": round(unresolved_conflict_count, 3),
        "expired_source_count": round(expired_source_count, 3),
        "repair_memo_completeness_fraction": round(repair_memo_completeness_fraction, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
