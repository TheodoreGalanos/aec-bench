# ABOUTME: Computes SSC-09 facade submittal and source-policy review metrics.
# ABOUTME: Combines traceability, calculator, material, comment, exception, and response checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _require_nonnegative(**values: float) -> None:
    """Raise ValueError when any supplied value is negative."""
    for name, value in values.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)


def compute(
    source_items_traced: float,
    required_source_items: float,
    calculator_rows_checked: float,
    required_calculator_rows: float,
    matching_material_items: float,
    material_schedule_items: float,
    passing_utilization_rows: float,
    utilization_rows: float,
    resolved_comments: float,
    review_comments: float,
    approved_boundary_exceptions: float,
    boundary_exceptions: float,
    unapproved_substitution_count: float,
    response_sections: float,
    required_response_sections: float,
) -> dict[str, float]:
    """Compute deterministic facade source-policy review metrics."""
    _require_positive(
        required_source_items=required_source_items,
        required_calculator_rows=required_calculator_rows,
        material_schedule_items=material_schedule_items,
        utilization_rows=utilization_rows,
        review_comments=review_comments,
        boundary_exceptions=boundary_exceptions,
        required_response_sections=required_response_sections,
    )
    _require_nonnegative(
        source_items_traced=source_items_traced,
        calculator_rows_checked=calculator_rows_checked,
        matching_material_items=matching_material_items,
        passing_utilization_rows=passing_utilization_rows,
        resolved_comments=resolved_comments,
        approved_boundary_exceptions=approved_boundary_exceptions,
        unapproved_substitution_count=unapproved_substitution_count,
        response_sections=response_sections,
    )

    source_trace_score = source_items_traced / required_source_items
    calculator_check_fraction = calculator_rows_checked / required_calculator_rows
    material_match_fraction = matching_material_items / material_schedule_items
    utilization_pass_fraction = passing_utilization_rows / utilization_rows
    comment_resolution_fraction = resolved_comments / review_comments
    boundary_exception_resolution_fraction = approved_boundary_exceptions / boundary_exceptions
    response_completeness_score = response_sections / required_response_sections
    evidence_boundary_score = (
        source_trace_score
        + calculator_check_fraction
        + material_match_fraction
        + utilization_pass_fraction
        + comment_resolution_fraction
        + boundary_exception_resolution_fraction
        + response_completeness_score
    ) / 7.0

    pass_checks = [
        calculator_check_fraction >= 1.0,
        utilization_pass_fraction >= 1.0,
        boundary_exception_resolution_fraction >= 1.0,
        unapproved_substitution_count == 0.0,
    ]

    return {
        "source_trace_score": round(source_trace_score, 3),
        "calculator_check_fraction": round(calculator_check_fraction, 3),
        "material_match_fraction": round(material_match_fraction, 3),
        "utilization_pass_fraction": round(utilization_pass_fraction, 3),
        "comment_resolution_fraction": round(comment_resolution_fraction, 3),
        "boundary_exception_resolution_fraction": round(boundary_exception_resolution_fraction, 3),
        "unapproved_substitution_count": round(unapproved_substitution_count, 3),
        "response_completeness_score": round(response_completeness_score, 3),
        "evidence_boundary_score": round(evidence_boundary_score, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
