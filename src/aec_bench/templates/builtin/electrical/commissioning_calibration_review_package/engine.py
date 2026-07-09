# ABOUTME: Computes SSC-18 commissioning and calibration review metrics.
# ABOUTME: Combines 4-20 mA calibration error, loop-test pass fraction, and valve headroom.

from __future__ import annotations


def compute(
    test_process_value_m3_h: float,
    lower_range_value_m3_h: float,
    upper_range_value_m3_h: float,
    as_found_signal_ma: float,
    calibration_tolerance_ma: float,
    loop_points_passed: float,
    loop_points_total: float,
    failed_point_count: float,
    process_acceptance_margin: float,
    required_valve_cv: float,
    selected_valve_cv: float,
) -> dict[str, float]:
    """Compute deterministic commissioning and calibration checks."""
    span = upper_range_value_m3_h - lower_range_value_m3_h
    if span <= 0:
        msg = "upper_range_value_m3_h must be greater than lower_range_value_m3_h"
        raise ValueError(msg)
    if loop_points_total <= 0:
        msg = "loop_points_total must be > 0"
        raise ValueError(msg)

    ideal_signal_ma = 4.0 + 16.0 * ((test_process_value_m3_h - lower_range_value_m3_h) / span)
    calibration_error_ma = as_found_signal_ma - ideal_signal_ma
    calibration_error_pct_span = abs(calibration_error_ma) / 16.0 * 100.0
    calibration_margin_ma = calibration_tolerance_ma - abs(calibration_error_ma)
    loop_check_pass_fraction = loop_points_passed / loop_points_total
    valve_cv_headroom = selected_valve_cv - required_valve_cv
    commissioning_completeness_fraction = 1.0 if loop_check_pass_fraction >= 1.0 and failed_point_count == 0 else 0.0
    overall_pass_score = (
        1.0
        if calibration_margin_ma >= 0.0
        and failed_point_count == 0.0
        and process_acceptance_margin >= 0.0
        and valve_cv_headroom >= 0.0
        else 0.0
    )

    return {
        "ideal_signal_ma": round(ideal_signal_ma, 3),
        "calibration_error_ma": round(calibration_error_ma, 3),
        "calibration_error_pct_span": round(calibration_error_pct_span, 3),
        "calibration_margin_ma": round(calibration_margin_ma, 3),
        "loop_check_pass_fraction": round(loop_check_pass_fraction, 3),
        "failed_point_count": round(failed_point_count, 3),
        "process_acceptance_margin": round(process_acceptance_margin, 3),
        "valve_cv_headroom": round(valve_cv_headroom, 3),
        "commissioning_completeness_fraction": round(commissioning_completeness_fraction, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
