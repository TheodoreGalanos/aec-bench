# ABOUTME: Computes SSC-02 rail standards conflict and operator-review completeness metrics.
# ABOUTME: Scores selection, comments, updates, exceptions, traceability, and response completeness.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _require_nonnegative(**values: float) -> None:
    for name, value in values.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)


def compute(
    candidate_standards_count: float,
    selected_standards_count: float,
    conflicting_comments: float,
    resolved_comments: float,
    affected_calculations: float,
    calculations_updated: float,
    exception_requests: float,
    approved_exceptions: float,
    source_values_traced: float,
    required_source_values: float,
    response_sections: float,
    required_response_sections: float,
    critical_open_comments: float,
) -> dict[str, float]:
    """Compute source-bound rail standards conflict and operator-review metrics."""
    _require_positive(
        candidate_standards_count=candidate_standards_count,
        conflicting_comments=conflicting_comments,
        affected_calculations=affected_calculations,
        exception_requests=exception_requests,
        required_source_values=required_source_values,
        required_response_sections=required_response_sections,
    )
    _require_nonnegative(
        selected_standards_count=selected_standards_count,
        resolved_comments=resolved_comments,
        calculations_updated=calculations_updated,
        approved_exceptions=approved_exceptions,
        source_values_traced=source_values_traced,
        response_sections=response_sections,
        critical_open_comments=critical_open_comments,
    )

    standard_selection_fraction = selected_standards_count / candidate_standards_count
    comment_resolution_fraction = resolved_comments / conflicting_comments
    calculation_update_fraction = calculations_updated / affected_calculations
    exception_resolution_fraction = approved_exceptions / exception_requests
    source_trace_score = source_values_traced / required_source_values
    response_completeness_score = response_sections / required_response_sections
    operator_review_score = (
        standard_selection_fraction
        + comment_resolution_fraction
        + calculation_update_fraction
        + exception_resolution_fraction
        + source_trace_score
        + response_completeness_score
    ) / 6.0
    open_comments = conflicting_comments - resolved_comments
    overall_pass_score = (
        1.0
        if min(
            standard_selection_fraction - 0.8,
            comment_resolution_fraction - 0.9,
            calculation_update_fraction - 0.8,
            exception_resolution_fraction - 0.9,
            source_trace_score - 0.85,
            response_completeness_score - 0.85,
        )
        >= 0.0
        and critical_open_comments == 0.0
        else 0.0
    )

    return {
        "standard_selection_fraction": round(standard_selection_fraction, 3),
        "comment_resolution_fraction": round(comment_resolution_fraction, 3),
        "calculation_update_fraction": round(calculation_update_fraction, 3),
        "exception_resolution_fraction": round(exception_resolution_fraction, 3),
        "source_trace_score": round(source_trace_score, 3),
        "response_completeness_score": round(response_completeness_score, 3),
        "operator_review_score": round(operator_review_score, 3),
        "open_comments": round(open_comments, 3),
        "critical_open_comments": round(critical_open_comments, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
