# ABOUTME: Computes SSC-19 fire review response and evidence-boundary metrics.
# ABOUTME: Combines source traceability, comments, check updates, gaps, authority roles, and conflicts.

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
    review_comments: float,
    resolved_comments: float,
    affected_checks: float,
    updated_checks: float,
    unresolved_gaps: float,
    allowed_gaps: float,
    authority_roles: float,
    separated_authority_roles: float,
    evidence_conflicts: float,
    resolved_conflicts: float,
    critical_open_comments: float,
    response_sections: float,
    required_response_sections: float,
) -> dict[str, float]:
    """Compute deterministic fire review response and boundary metrics."""
    _require_positive(
        required_source_items=required_source_items,
        review_comments=review_comments,
        affected_checks=affected_checks,
        allowed_gaps=allowed_gaps,
        authority_roles=authority_roles,
        evidence_conflicts=evidence_conflicts,
        response_sections=response_sections,
        required_response_sections=required_response_sections,
    )
    _require_nonnegative(
        source_items_traced=source_items_traced,
        resolved_comments=resolved_comments,
        updated_checks=updated_checks,
        unresolved_gaps=unresolved_gaps,
        separated_authority_roles=separated_authority_roles,
        resolved_conflicts=resolved_conflicts,
        critical_open_comments=critical_open_comments,
    )

    source_trace_score = source_items_traced / required_source_items
    comment_resolution_fraction = resolved_comments / review_comments
    affected_check_update_fraction = updated_checks / affected_checks
    allowed_gap_margin = allowed_gaps - unresolved_gaps
    authority_role_separation_score = separated_authority_roles / authority_roles
    conflict_resolution_fraction = resolved_conflicts / evidence_conflicts
    response_completeness_score = response_sections / required_response_sections
    review_boundary_score = (
        source_trace_score
        + comment_resolution_fraction
        + affected_check_update_fraction
        + authority_role_separation_score
        + conflict_resolution_fraction
        + response_completeness_score
    ) / 6.0

    pass_checks = [
        allowed_gap_margin >= 0.0,
        affected_check_update_fraction >= 1.0,
        authority_role_separation_score >= 1.0,
        critical_open_comments == 0.0,
    ]

    return {
        "source_trace_score": round(source_trace_score, 3),
        "comment_resolution_fraction": round(comment_resolution_fraction, 3),
        "affected_check_update_fraction": round(affected_check_update_fraction, 3),
        "unresolved_gap_count": round(unresolved_gaps, 3),
        "allowed_gap_margin": round(allowed_gap_margin, 3),
        "authority_role_separation_score": round(authority_role_separation_score, 3),
        "conflict_resolution_fraction": round(conflict_resolution_fraction, 3),
        "response_completeness_score": round(response_completeness_score, 3),
        "review_boundary_score": round(review_boundary_score, 3),
        "critical_open_comments": round(critical_open_comments, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
