# ABOUTME: Computes SSC-08 building operations review and scenario repair metrics.
# ABOUTME: Combines source trace, occupancy updates, system checks, comments, authority, and repair closure.

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
    occupancy_rows_updated: float,
    required_occupancy_rows: float,
    affected_system_checks_complete: float,
    required_system_checks: float,
    resolved_comments: float,
    review_comments: float,
    open_critical_comment_count: float,
    partitioned_authority_roles: float,
    required_authority_roles: float,
    repair_actions_closed: float,
    required_repair_actions: float,
    unsupported_value_count: float,
) -> dict[str, float]:
    """Compute deterministic operations review and scenario repair metrics."""
    _require_positive(
        required_source_items=required_source_items,
        required_occupancy_rows=required_occupancy_rows,
        required_system_checks=required_system_checks,
        review_comments=review_comments,
        required_authority_roles=required_authority_roles,
        required_repair_actions=required_repair_actions,
    )
    _require_nonnegative(
        source_items_traced=source_items_traced,
        occupancy_rows_updated=occupancy_rows_updated,
        affected_system_checks_complete=affected_system_checks_complete,
        resolved_comments=resolved_comments,
        open_critical_comment_count=open_critical_comment_count,
        partitioned_authority_roles=partitioned_authority_roles,
        repair_actions_closed=repair_actions_closed,
        unsupported_value_count=unsupported_value_count,
    )

    source_trace_score = source_items_traced / required_source_items
    occupancy_update_fraction = occupancy_rows_updated / required_occupancy_rows
    affected_system_check_fraction = affected_system_checks_complete / required_system_checks
    comment_resolution_fraction = resolved_comments / review_comments
    authority_partition_score = partitioned_authority_roles / required_authority_roles
    repair_action_closure_fraction = repair_actions_closed / required_repair_actions
    evidence_boundary_score = (
        source_trace_score
        + occupancy_update_fraction
        + affected_system_check_fraction
        + comment_resolution_fraction
        + authority_partition_score
        + repair_action_closure_fraction
    ) / 6.0

    pass_checks = [
        source_trace_score >= 1.0,
        occupancy_update_fraction >= 1.0,
        affected_system_check_fraction >= 0.9,
        comment_resolution_fraction >= 0.9,
        open_critical_comment_count == 0.0,
        authority_partition_score >= 1.0,
        unsupported_value_count == 0.0,
    ]

    return {
        "source_trace_score": round(source_trace_score, 3),
        "occupancy_update_fraction": round(occupancy_update_fraction, 3),
        "affected_system_check_fraction": round(affected_system_check_fraction, 3),
        "comment_resolution_fraction": round(comment_resolution_fraction, 3),
        "open_critical_comment_count": round(open_critical_comment_count, 3),
        "authority_partition_score": round(authority_partition_score, 3),
        "repair_action_closure_fraction": round(repair_action_closure_fraction, 3),
        "unsupported_value_count": round(unsupported_value_count, 3),
        "evidence_boundary_score": round(evidence_boundary_score, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
