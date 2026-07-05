# ABOUTME: Computes SSC-10 instrumented process control and valve metrics.
# ABOUTME: Combines Cv, authority, 4-20 mA scaling, fail-close timing, and basin HRT checks.

from __future__ import annotations

import math


def compute(
    design_flow_l_s: float,
    specific_gravity: float,
    upstream_pressure_kpa: float,
    downstream_pressure_kpa: float,
    selected_valve_cv: float,
    total_control_zone_drop_kpa: float,
    process_lrv: float,
    process_urv: float,
    setpoint_value: float,
    measured_signal_ma: float,
    required_fail_close_s: float,
    actual_fail_close_s: float,
    basin_volume_m3: float,
) -> dict[str, float]:
    """Compute source-bound SSC-10 control valve and instrumentation metrics."""
    flow_gpm = design_flow_l_s * 15.8503
    delta_psi = (upstream_pressure_kpa - downstream_pressure_kpa) * 0.145038
    required_cv = flow_gpm / math.sqrt(delta_psi / specific_gravity)
    cv_margin = selected_valve_cv - required_cv
    valve_authority_ratio = (upstream_pressure_kpa - downstream_pressure_kpa) / total_control_zone_drop_kpa
    command_signal_ma = 4.0 + 16.0 * ((setpoint_value - process_lrv) / (process_urv - process_lrv))
    signal_error_ma = abs(measured_signal_ma - command_signal_ma)
    fail_close_margin_s = required_fail_close_s - actual_fail_close_s
    basin_hrt_hr = basin_volume_m3 / (design_flow_l_s * 86.4) * 24.0
    overall_pass_score = (
        1.0
        if min(cv_margin, valve_authority_ratio, 0.2 - signal_error_ma, fail_close_margin_s, basin_hrt_hr) >= 0.0
        else 0.0
    )

    return {
        "required_cv": round(required_cv, 3),
        "cv_margin": round(cv_margin, 3),
        "valve_authority_ratio": round(valve_authority_ratio, 3),
        "command_signal_ma": round(command_signal_ma, 3),
        "signal_error_ma": round(signal_error_ma, 3),
        "fail_close_margin_s": round(fail_close_margin_s, 3),
        "basin_hrt_hr": round(basin_hrt_hr, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
