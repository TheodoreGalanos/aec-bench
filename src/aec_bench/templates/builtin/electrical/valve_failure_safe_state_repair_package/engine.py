# ABOUTME: Computes SSC-18 valve failure safe-state repair metrics.
# ABOUTME: Combines failed-signal threshold, safe Cv, bypass flow, runtime, and repair ledger checks.

from __future__ import annotations


def compute(
    failed_signal_ma: float,
    fail_threshold_ma: float,
    fail_closed_cv: float,
    required_safe_cv: float,
    bypass_cv: float,
    required_bypass_cv: float,
    safe_flow_m3_h: float,
    minimum_safe_flow_m3_h: float,
    tank_volume_m3: float,
    drawdown_flow_m3_h: float,
    required_safe_duration_h: float,
    source_items_resolved: float,
    source_items_total: float,
    unresolved_conflict_count: float,
) -> dict[str, float]:
    """Compute deterministic valve failure and safe-state repair checks."""
    if drawdown_flow_m3_h <= 0 or source_items_total <= 0:
        msg = "drawdown_flow_m3_h and source_items_total must be > 0"
        raise ValueError(msg)

    failed_signal_margin_ma = fail_threshold_ma - failed_signal_ma
    fail_closed_cv_margin = fail_closed_cv - required_safe_cv
    bypass_cv_margin = bypass_cv - required_bypass_cv
    safe_flow_margin_m3_h = safe_flow_m3_h - minimum_safe_flow_m3_h
    safe_runtime_h = tank_volume_m3 / drawdown_flow_m3_h
    safe_runtime_margin_h = safe_runtime_h - required_safe_duration_h
    source_resolution_fraction = source_items_resolved / source_items_total
    overall_pass_score = (
        1.0
        if failed_signal_margin_ma >= 0.0
        and fail_closed_cv_margin >= 0.0
        and bypass_cv_margin >= 0.0
        and safe_flow_margin_m3_h >= 0.0
        and safe_runtime_margin_h >= 0.0
        and source_resolution_fraction >= 1.0
        and unresolved_conflict_count == 0.0
        else 0.0
    )

    return {
        "failed_signal_margin_ma": round(failed_signal_margin_ma, 3),
        "fail_closed_cv_margin": round(fail_closed_cv_margin, 3),
        "bypass_cv_margin": round(bypass_cv_margin, 3),
        "safe_flow_margin_m3_h": round(safe_flow_margin_m3_h, 3),
        "safe_runtime_h": round(safe_runtime_h, 3),
        "safe_runtime_margin_h": round(safe_runtime_margin_h, 3),
        "source_resolution_fraction": round(source_resolution_fraction, 3),
        "unresolved_conflict_count": round(unresolved_conflict_count, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
