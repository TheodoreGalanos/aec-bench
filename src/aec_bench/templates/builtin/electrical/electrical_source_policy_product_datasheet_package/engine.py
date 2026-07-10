# ABOUTME: Computes SSC-05 electrical source-policy and product datasheet metrics.
# ABOUTME: Combines datasheet completeness, traceability, derated ratings, comments, and response checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _require_fraction(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        msg = f"{name} must be between 0 and 1"
        raise ValueError(msg)


def compute(
    provided_datasheet_fields: float,
    required_datasheet_fields: float,
    traced_source_values: float,
    required_source_values: float,
    product_nameplate_current_a: float,
    product_derating_factor: float,
    design_current_a: float,
    cable_allowable_current_a: float,
    max_voltage_drop_percent: float,
    calculated_voltage_drop_percent: float,
    protection_setting_margin_percent: float,
    review_comment_count: float,
    resolved_comment_count: float,
    critical_open_comments: float,
    response_completeness_score: float,
) -> dict[str, float]:
    """Compute source-bound datasheet, rating, source-policy, and review metrics."""
    _require_positive(
        provided_datasheet_fields=provided_datasheet_fields,
        required_datasheet_fields=required_datasheet_fields,
        traced_source_values=traced_source_values,
        required_source_values=required_source_values,
        product_nameplate_current_a=product_nameplate_current_a,
        design_current_a=design_current_a,
        cable_allowable_current_a=cable_allowable_current_a,
        max_voltage_drop_percent=max_voltage_drop_percent,
        review_comment_count=review_comment_count,
    )
    if resolved_comment_count < 0.0 or critical_open_comments < 0.0:
        msg = "comment counts must be >= 0"
        raise ValueError(msg)
    _require_fraction("product_derating_factor", product_derating_factor)
    _require_fraction("response_completeness_score", response_completeness_score)

    datasheet_completeness_fraction = provided_datasheet_fields / required_datasheet_fields
    source_trace_score = traced_source_values / required_source_values
    derated_product_current_a = product_nameplate_current_a * product_derating_factor
    breaker_rating_margin_a = derated_product_current_a - design_current_a
    cable_rating_margin_a = cable_allowable_current_a - design_current_a
    voltage_drop_margin_percent = max_voltage_drop_percent - calculated_voltage_drop_percent
    open_comments = review_comment_count - resolved_comment_count

    overall_pass_score = (
        1.0
        if min(
            datasheet_completeness_fraction - 0.85,
            source_trace_score - 0.8,
            breaker_rating_margin_a,
            cable_rating_margin_a,
            voltage_drop_margin_percent,
            protection_setting_margin_percent,
            response_completeness_score - 0.9,
        )
        >= 0.0
        and critical_open_comments == 0.0
        else 0.0
    )

    return {
        "datasheet_completeness_fraction": round(datasheet_completeness_fraction, 3),
        "source_trace_score": round(source_trace_score, 3),
        "derated_product_current_a": round(derated_product_current_a, 3),
        "breaker_rating_margin_a": round(breaker_rating_margin_a, 3),
        "cable_rating_margin_a": round(cable_rating_margin_a, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "protection_setting_margin_percent": round(protection_setting_margin_percent, 3),
        "open_comments": round(open_comments, 3),
        "critical_open_comments": round(critical_open_comments, 3),
        "response_completeness_score": round(response_completeness_score, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
