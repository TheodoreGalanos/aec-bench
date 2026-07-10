# ABOUTME: Computes SSC-15 product submittal compliance package metrics.
# ABOUTME: Combines duty margins, source evidence completeness, comments, and deviations.

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
    required_flow_l_s: float,
    submitted_flow_l_s: float,
    required_head_m: float,
    submitted_head_m: float,
    bep_flow_l_s: float,
    por_low_percent: float,
    por_high_percent: float,
    motor_nameplate_kw: float,
    motor_service_factor: float,
    required_motor_kw: float,
    max_system_pressure_kpa: float,
    certificate_pressure_rating_kpa: float,
    required_evidence_items: float,
    submitted_evidence_items: float,
    required_certificate_items: float,
    matching_certificate_items: float,
    total_review_comments: float,
    closed_review_comments: float,
    open_critical_comments: float,
    review_period_days: float,
    elapsed_review_days: float,
    approved_deviation_count: float,
    unresolved_deviation_count: float,
) -> dict[str, float]:
    """Compute submittal duty, evidence, review, and disposition metrics."""
    _require_positive(
        required_flow_l_s=required_flow_l_s,
        submitted_flow_l_s=submitted_flow_l_s,
        required_head_m=required_head_m,
        submitted_head_m=submitted_head_m,
        bep_flow_l_s=bep_flow_l_s,
        por_low_percent=por_low_percent,
        por_high_percent=por_high_percent,
        motor_nameplate_kw=motor_nameplate_kw,
        motor_service_factor=motor_service_factor,
        required_motor_kw=required_motor_kw,
        max_system_pressure_kpa=max_system_pressure_kpa,
        certificate_pressure_rating_kpa=certificate_pressure_rating_kpa,
        required_evidence_items=required_evidence_items,
        required_certificate_items=required_certificate_items,
        total_review_comments=total_review_comments,
        review_period_days=review_period_days,
    )
    _require_nonnegative(
        submitted_evidence_items=submitted_evidence_items,
        matching_certificate_items=matching_certificate_items,
        closed_review_comments=closed_review_comments,
        open_critical_comments=open_critical_comments,
        elapsed_review_days=elapsed_review_days,
        approved_deviation_count=approved_deviation_count,
        unresolved_deviation_count=unresolved_deviation_count,
    )
    if por_high_percent <= por_low_percent:
        msg = "por_high_percent must be greater than por_low_percent"
        raise ValueError(msg)

    flow_capacity_margin_l_s = submitted_flow_l_s - required_flow_l_s
    flow_capacity_ratio = submitted_flow_l_s / required_flow_l_s
    head_capacity_margin_m = submitted_head_m - required_head_m
    head_capacity_ratio = submitted_head_m / required_head_m

    bep_flow_percent = required_flow_l_s / bep_flow_l_s * 100.0
    por_min_flow_l_s = bep_flow_l_s * por_low_percent / 100.0
    por_max_flow_l_s = bep_flow_l_s * por_high_percent / 100.0
    por_low_margin_l_s = required_flow_l_s - por_min_flow_l_s
    por_high_margin_l_s = por_max_flow_l_s - required_flow_l_s

    motor_available_kw = motor_nameplate_kw * motor_service_factor
    motor_margin_kw = motor_available_kw - required_motor_kw
    pressure_certificate_margin_kpa = certificate_pressure_rating_kpa - max_system_pressure_kpa

    evidence_completeness_percent = submitted_evidence_items / required_evidence_items * 100.0
    certificate_match_percent = matching_certificate_items / required_certificate_items * 100.0
    review_closeout_percent = closed_review_comments / total_review_comments * 100.0
    review_days_remaining = review_period_days - elapsed_review_days

    overall_pass_score = (
        1.0
        if (
            flow_capacity_margin_l_s >= 0.0
            and head_capacity_margin_m >= 0.0
            and por_low_margin_l_s >= 0.0
            and por_high_margin_l_s >= 0.0
            and motor_margin_kw >= 0.0
            and pressure_certificate_margin_kpa >= 0.0
            and evidence_completeness_percent >= 100.0
            and certificate_match_percent >= 100.0
            and review_closeout_percent >= 100.0
            and review_days_remaining >= 0.0
            and open_critical_comments == 0.0
            and unresolved_deviation_count == 0.0
        )
        else 0.0
    )

    return {
        "flow_capacity_margin_l_s": round(flow_capacity_margin_l_s, 3),
        "flow_capacity_ratio": round(flow_capacity_ratio, 3),
        "head_capacity_margin_m": round(head_capacity_margin_m, 3),
        "head_capacity_ratio": round(head_capacity_ratio, 3),
        "bep_flow_percent": round(bep_flow_percent, 3),
        "por_min_flow_l_s": round(por_min_flow_l_s, 3),
        "por_max_flow_l_s": round(por_max_flow_l_s, 3),
        "por_low_margin_l_s": round(por_low_margin_l_s, 3),
        "por_high_margin_l_s": round(por_high_margin_l_s, 3),
        "motor_available_kw": round(motor_available_kw, 3),
        "motor_margin_kw": round(motor_margin_kw, 3),
        "pressure_certificate_margin_kpa": round(pressure_certificate_margin_kpa, 3),
        "evidence_completeness_percent": round(evidence_completeness_percent, 3),
        "certificate_match_percent": round(certificate_match_percent, 3),
        "review_closeout_percent": round(review_closeout_percent, 3),
        "review_days_remaining": round(review_days_remaining, 3),
        "approved_deviation_count": round(approved_deviation_count, 3),
        "unresolved_deviation_count": round(unresolved_deviation_count, 3),
        "open_critical_comments": round(open_critical_comments, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
