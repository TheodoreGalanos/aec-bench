# ABOUTME: Computes SSC-18 instrumentation source-policy extension metrics.
# ABOUTME: Combines traceability, cross-domain update, gap documentation, verification, and authority partition checks.

from __future__ import annotations


def compute(
    source_items_traced: float,
    source_items_total: float,
    linked_tables_updated: float,
    linked_tables_total: float,
    documented_gap_count: float,
    expected_gap_count: float,
    verification_cases_passed: float,
    verification_cases_total: float,
    process_margin: float,
    electrical_margin: float,
    authority_partitions_signed: float,
    authority_partitions_total: float,
    unresolved_conflict_count: float,
    extension_memo_completeness_fraction: float,
) -> dict[str, float]:
    """Compute deterministic instrumentation source-policy extension checks."""
    denominators = [
        source_items_total,
        linked_tables_total,
        expected_gap_count,
        verification_cases_total,
        authority_partitions_total,
    ]
    if any(value <= 0 for value in denominators):
        msg = "all total/count denominator values must be > 0"
        raise ValueError(msg)

    source_traceability_fraction = source_items_traced / source_items_total
    linked_table_update_fraction = linked_tables_updated / linked_tables_total
    gap_documentation_fraction = documented_gap_count / expected_gap_count
    verification_case_pass_fraction = verification_cases_passed / verification_cases_total
    min_cross_domain_margin = min(process_margin, electrical_margin)
    authority_partition_fraction = authority_partitions_signed / authority_partitions_total
    overall_pass_score = (
        1.0
        if source_traceability_fraction >= 1.0
        and linked_table_update_fraction >= 1.0
        and gap_documentation_fraction >= 1.0
        and verification_case_pass_fraction >= 1.0
        and min_cross_domain_margin >= 0.0
        and authority_partition_fraction >= 1.0
        and unresolved_conflict_count == 0.0
        else 0.0
    )

    return {
        "source_traceability_fraction": round(source_traceability_fraction, 3),
        "linked_table_update_fraction": round(linked_table_update_fraction, 3),
        "gap_documentation_fraction": round(gap_documentation_fraction, 3),
        "verification_case_pass_fraction": round(verification_case_pass_fraction, 3),
        "min_cross_domain_margin": round(min_cross_domain_margin, 3),
        "authority_partition_fraction": round(authority_partition_fraction, 3),
        "unresolved_conflict_count": round(unresolved_conflict_count, 3),
        "extension_memo_completeness_fraction": round(extension_memo_completeness_fraction, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
