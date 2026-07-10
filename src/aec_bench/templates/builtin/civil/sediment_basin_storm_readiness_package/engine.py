# ABOUTME: Computes SSC-16 sediment basin and storm readiness metrics.
# ABOUTME: Combines runoff volume, basin storage, weir capacity, drawdown, TSS, and inspection checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    catchment_area_ha: float,
    storm_depth_mm: float,
    runoff_coefficient: float,
    sediment_allowance_m3: float,
    provided_basin_volume_m3: float,
    weir_coefficient: float,
    weir_length_m: float,
    weir_head_m: float,
    peak_inflow_m3_s: float,
    provided_freeboard_m: float,
    required_freeboard_m: float,
    outlet_drawdown_flow_m3_s: float,
    maximum_drawdown_time_h: float,
    tss_event_mean_concentration_mg_l: float,
    inspection_due_window_h: float,
    hours_since_storm_end: float,
) -> dict[str, float]:
    """Compute deterministic sediment basin storm readiness checks."""
    _require_positive(
        catchment_area_ha=catchment_area_ha,
        storm_depth_mm=storm_depth_mm,
        runoff_coefficient=runoff_coefficient,
        sediment_allowance_m3=sediment_allowance_m3,
        provided_basin_volume_m3=provided_basin_volume_m3,
        weir_coefficient=weir_coefficient,
        weir_length_m=weir_length_m,
        weir_head_m=weir_head_m,
        peak_inflow_m3_s=peak_inflow_m3_s,
        provided_freeboard_m=provided_freeboard_m,
        required_freeboard_m=required_freeboard_m,
        outlet_drawdown_flow_m3_s=outlet_drawdown_flow_m3_s,
        maximum_drawdown_time_h=maximum_drawdown_time_h,
        tss_event_mean_concentration_mg_l=tss_event_mean_concentration_mg_l,
        inspection_due_window_h=inspection_due_window_h,
    )
    if hours_since_storm_end < 0:
        msg = "hours_since_storm_end must be >= 0"
        raise ValueError(msg)

    runoff_volume_m3 = catchment_area_ha * 10_000.0 * (storm_depth_mm / 1000.0) * runoff_coefficient
    required_basin_volume_m3 = runoff_volume_m3 + sediment_allowance_m3
    basin_headroom_m3 = provided_basin_volume_m3 - required_basin_volume_m3
    weir_capacity_m3_s = weir_coefficient * weir_length_m * weir_head_m**1.5
    weir_capacity_margin_m3_s = weir_capacity_m3_s - peak_inflow_m3_s
    freeboard_margin_m = provided_freeboard_m - required_freeboard_m
    drawdown_time_h = required_basin_volume_m3 / (outlet_drawdown_flow_m3_s * 3600.0)
    drawdown_margin_h = maximum_drawdown_time_h - drawdown_time_h
    tss_load_kg = runoff_volume_m3 * tss_event_mean_concentration_mg_l / 1000.0
    inspection_window_margin_h = inspection_due_window_h - hours_since_storm_end

    pass_checks = [
        basin_headroom_m3 >= 0.0,
        weir_capacity_margin_m3_s >= 0.0,
        freeboard_margin_m >= 0.0,
        drawdown_margin_h >= 0.0,
        inspection_window_margin_h >= 0.0,
    ]

    return {
        "runoff_volume_m3": round(runoff_volume_m3, 3),
        "required_basin_volume_m3": round(required_basin_volume_m3, 3),
        "basin_headroom_m3": round(basin_headroom_m3, 3),
        "weir_capacity_m3_s": round(weir_capacity_m3_s, 3),
        "weir_capacity_margin_m3_s": round(weir_capacity_margin_m3_s, 3),
        "freeboard_margin_m": round(freeboard_margin_m, 3),
        "drawdown_time_h": round(drawdown_time_h, 3),
        "drawdown_margin_h": round(drawdown_margin_h, 3),
        "tss_load_kg": round(tss_load_kg, 3),
        "inspection_window_margin_h": round(inspection_window_margin_h, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
