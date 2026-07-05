# ABOUTME: Computes SSC-03 SWMM/HEC report source-policy metrics.
# ABOUTME: Combines model/report object matching, hash completeness, peak deltas, continuity, and negative cases.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    model_subcatchment_count: float,
    report_subcatchment_count: float,
    model_node_count: float,
    report_node_count: float,
    model_link_count: float,
    report_link_count: float,
    storage_unit_count: float,
    outlet_row_count: float,
    required_hash_count: float,
    present_hash_count: float,
    manual_peak_flow_m3_s: float,
    model_peak_flow_m3_s: float,
    allowed_peak_delta_m3_s: float,
    continuity_error_percent: float,
    maximum_continuity_error_percent: float,
    expected_negative_cases: float,
    captured_negative_cases: float,
    unresolved_source_conflicts: float,
) -> dict[str, float]:
    """Compute deterministic SSC-03 report and source-policy metrics."""
    _require_positive(
        model_subcatchment_count=model_subcatchment_count,
        report_subcatchment_count=report_subcatchment_count,
        model_node_count=model_node_count,
        report_node_count=report_node_count,
        model_link_count=model_link_count,
        report_link_count=report_link_count,
        required_hash_count=required_hash_count,
        present_hash_count=present_hash_count,
        manual_peak_flow_m3_s=manual_peak_flow_m3_s,
        model_peak_flow_m3_s=model_peak_flow_m3_s,
        allowed_peak_delta_m3_s=allowed_peak_delta_m3_s,
        maximum_continuity_error_percent=maximum_continuity_error_percent,
        expected_negative_cases=expected_negative_cases,
        captured_negative_cases=captured_negative_cases,
    )
    if unresolved_source_conflicts < 0:
        msg = "unresolved_source_conflicts must be >= 0"
        raise ValueError(msg)

    matched_objects = (
        min(model_subcatchment_count, report_subcatchment_count)
        + min(model_node_count, report_node_count)
        + min(model_link_count, report_link_count)
    )
    model_objects = model_subcatchment_count + model_node_count + model_link_count
    object_match_percent = matched_objects / model_objects * 100.0
    hash_completeness_percent = present_hash_count / required_hash_count * 100.0
    peak_delta_m3_s = abs(manual_peak_flow_m3_s - model_peak_flow_m3_s)
    peak_delta_margin_m3_s = allowed_peak_delta_m3_s - peak_delta_m3_s
    continuity_margin_percent = maximum_continuity_error_percent - continuity_error_percent
    negative_case_capture_percent = captured_negative_cases / expected_negative_cases * 100.0

    pass_checks = [
        object_match_percent >= 100.0,
        hash_completeness_percent >= 100.0,
        peak_delta_margin_m3_s >= 0.0,
        continuity_margin_percent >= 0.0,
        negative_case_capture_percent >= 100.0,
        unresolved_source_conflicts == 0.0,
    ]

    return {
        "object_match_percent": round(object_match_percent, 3),
        "hash_completeness_percent": round(hash_completeness_percent, 3),
        "peak_delta_m3_s": round(peak_delta_m3_s, 3),
        "peak_delta_margin_m3_s": round(peak_delta_margin_m3_s, 3),
        "continuity_error_percent": round(continuity_error_percent, 3),
        "continuity_margin_percent": round(continuity_margin_percent, 3),
        "storage_unit_count": round(storage_unit_count, 3),
        "outlet_row_count": round(outlet_row_count, 3),
        "negative_case_capture_percent": round(negative_case_capture_percent, 3),
        "unresolved_source_conflicts": round(unresolved_source_conflicts, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
