# ABOUTME: Computes SSC-06 equipment datasheet and commissioning review metrics.
# ABOUTME: Combines capacity margins, POR/AOR position, NPSH, motor service, and review evidence checks.

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
    scheduled_flow_l_s: float,
    datasheet_max_flow_l_s: float,
    scheduled_head_m: float,
    datasheet_max_head_m: float,
    bep_flow_l_s: float,
    por_lower_pct: float,
    por_upper_pct: float,
    npsh_available_m: float,
    npsh_required_m: float,
    shaft_power_kw: float,
    selected_motor_kw: float,
    motor_service_factor: float,
    provided_evidence_count: float,
    required_evidence_count: float,
    open_commissioning_items: float,
    critical_review_comments_open: float,
) -> dict[str, float]:
    """Compute source-bound equipment review and commissioning metrics."""
    _require_positive(
        scheduled_flow_l_s=scheduled_flow_l_s,
        datasheet_max_flow_l_s=datasheet_max_flow_l_s,
        scheduled_head_m=scheduled_head_m,
        datasheet_max_head_m=datasheet_max_head_m,
        bep_flow_l_s=bep_flow_l_s,
        por_lower_pct=por_lower_pct,
        por_upper_pct=por_upper_pct,
        npsh_available_m=npsh_available_m,
        npsh_required_m=npsh_required_m,
        shaft_power_kw=shaft_power_kw,
        selected_motor_kw=selected_motor_kw,
        motor_service_factor=motor_service_factor,
        required_evidence_count=required_evidence_count,
    )
    _require_nonnegative(
        provided_evidence_count=provided_evidence_count,
        open_commissioning_items=open_commissioning_items,
        critical_review_comments_open=critical_review_comments_open,
    )
    if por_upper_pct <= por_lower_pct:
        msg = "por_upper_pct must be greater than por_lower_pct"
        raise ValueError(msg)
    if motor_service_factor < 1.0:
        msg = "motor_service_factor must be >= 1"
        raise ValueError(msg)

    flow_capacity_margin_pct = (datasheet_max_flow_l_s - scheduled_flow_l_s) / scheduled_flow_l_s * 100.0
    head_capacity_margin_pct = (datasheet_max_head_m - scheduled_head_m) / scheduled_head_m * 100.0
    por_position_pct = scheduled_flow_l_s / bep_flow_l_s * 100.0
    por_margin_pct = min(por_position_pct - por_lower_pct, por_upper_pct - por_position_pct)
    npsh_margin_m = npsh_available_m - npsh_required_m
    motor_service_margin_kw = selected_motor_kw - shaft_power_kw * motor_service_factor
    evidence_completeness_score = provided_evidence_count / required_evidence_count
    overall_pass_score = (
        1.0
        if min(
            flow_capacity_margin_pct,
            head_capacity_margin_pct,
            por_margin_pct,
            npsh_margin_m,
            motor_service_margin_kw,
            evidence_completeness_score - 0.8,
            -critical_review_comments_open,
        )
        >= 0.0
        else 0.0
    )

    return {
        "flow_capacity_margin_pct": round(flow_capacity_margin_pct, 3),
        "head_capacity_margin_pct": round(head_capacity_margin_pct, 3),
        "por_position_pct": round(por_position_pct, 3),
        "por_margin_pct": round(por_margin_pct, 3),
        "npsh_margin_m": round(npsh_margin_m, 3),
        "motor_service_margin_kw": round(motor_service_margin_kw, 3),
        "evidence_completeness_score": round(evidence_completeness_score, 3),
        "open_commissioning_items": round(open_commissioning_items, 3),
        "critical_review_comments_open": round(critical_review_comments_open, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
