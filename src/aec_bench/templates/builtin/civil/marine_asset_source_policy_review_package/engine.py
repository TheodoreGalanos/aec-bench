# ABOUTME: Computes SSC-04 marine asset source-policy review metrics.
# ABOUTME: Combines datum, criteria, asset schedule, calculation, comments, authority, and response checks.

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
    datum_items_traced: float,
    required_datum_items: float,
    resolved_criteria_items: float,
    criteria_items: float,
    matching_asset_rows: float,
    asset_schedule_rows: float,
    traced_calculation_rows: float,
    calculation_rows: float,
    resolved_comments: float,
    review_comments: float,
    separated_authority_roles: float,
    required_authority_roles: float,
    unsupported_source_value_count: float,
    response_sections: float,
    required_response_sections: float,
) -> dict[str, float]:
    """Compute deterministic marine asset source-policy review metrics."""
    _require_positive(
        required_datum_items=required_datum_items,
        criteria_items=criteria_items,
        asset_schedule_rows=asset_schedule_rows,
        calculation_rows=calculation_rows,
        review_comments=review_comments,
        required_authority_roles=required_authority_roles,
        required_response_sections=required_response_sections,
    )
    _require_nonnegative(
        datum_items_traced=datum_items_traced,
        resolved_criteria_items=resolved_criteria_items,
        matching_asset_rows=matching_asset_rows,
        traced_calculation_rows=traced_calculation_rows,
        resolved_comments=resolved_comments,
        separated_authority_roles=separated_authority_roles,
        unsupported_source_value_count=unsupported_source_value_count,
        response_sections=response_sections,
    )

    datum_trace_score = datum_items_traced / required_datum_items
    criteria_resolution_fraction = resolved_criteria_items / criteria_items
    asset_schedule_match_fraction = matching_asset_rows / asset_schedule_rows
    calculation_trace_fraction = traced_calculation_rows / calculation_rows
    comment_resolution_fraction = resolved_comments / review_comments
    authority_partition_score = separated_authority_roles / required_authority_roles
    response_completeness_score = response_sections / required_response_sections
    evidence_boundary_score = (
        datum_trace_score
        + criteria_resolution_fraction
        + asset_schedule_match_fraction
        + calculation_trace_fraction
        + comment_resolution_fraction
        + authority_partition_score
        + response_completeness_score
    ) / 7.0

    pass_checks = [
        datum_trace_score >= 1.0,
        criteria_resolution_fraction >= 1.0,
        authority_partition_score >= 1.0,
        unsupported_source_value_count == 0.0,
        response_completeness_score >= 0.9,
    ]

    return {
        "datum_trace_score": round(datum_trace_score, 3),
        "criteria_resolution_fraction": round(criteria_resolution_fraction, 3),
        "asset_schedule_match_fraction": round(asset_schedule_match_fraction, 3),
        "calculation_trace_fraction": round(calculation_trace_fraction, 3),
        "comment_resolution_fraction": round(comment_resolution_fraction, 3),
        "authority_partition_score": round(authority_partition_score, 3),
        "unsupported_source_value_count": round(unsupported_source_value_count, 3),
        "response_completeness_score": round(response_completeness_score, 3),
        "evidence_boundary_score": round(evidence_boundary_score, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
