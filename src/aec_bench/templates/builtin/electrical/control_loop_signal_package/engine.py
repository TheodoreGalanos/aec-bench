# ABOUTME: Computes SSC-18 control-loop signal metrics from task-owned source-pack values.
# ABOUTME: Combines valve Cv sizing, 4-20 mA scaling, and alarm/trip headroom checks.

from __future__ import annotations

from math import sqrt


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _signal_current_ma(
    *,
    process_value: float,
    lower_range_value: float,
    upper_range_value: float,
) -> float:
    """Return linear 4-20 mA current for a ranged process value."""
    span = upper_range_value - lower_range_value
    if span <= 0:
        msg = "upper_range_value must be greater than lower_range_value"
        raise ValueError(msg)
    return 4.0 + 16.0 * ((process_value - lower_range_value) / span)


def compute(
    flow_rate_m3_h: float,
    upstream_pressure_bar: float,
    downstream_pressure_bar: float,
    fluid_specific_gravity: float,
    fluid_vapor_pressure_bar: float,
    fluid_critical_pressure_bar: float,
    fl_recovery_factor: float,
    selected_valve_cv: float,
    process_value_m3_h: float,
    lower_range_value_m3_h: float,
    upper_range_value_m3_h: float,
    high_alarm_flow_m3_h: float,
    high_high_trip_flow_m3_h: float,
) -> dict[str, float]:
    """Compute valve, signal, and alarm metrics for the SSC-18 source pack."""
    _require_positive(
        flow_rate_m3_h=flow_rate_m3_h,
        upstream_pressure_bar=upstream_pressure_bar,
        downstream_pressure_bar=downstream_pressure_bar,
        fluid_specific_gravity=fluid_specific_gravity,
        fluid_critical_pressure_bar=fluid_critical_pressure_bar,
        fl_recovery_factor=fl_recovery_factor,
        selected_valve_cv=selected_valve_cv,
        upper_range_value_m3_h=upper_range_value_m3_h,
    )
    if upstream_pressure_bar <= downstream_pressure_bar:
        msg = "upstream_pressure_bar must be greater than downstream_pressure_bar"
        raise ValueError(msg)
    if fluid_vapor_pressure_bar < 0:
        msg = "fluid_vapor_pressure_bar must be >= 0"
        raise ValueError(msg)

    pressure_drop_bar = upstream_pressure_bar - downstream_pressure_bar
    liquid_critical_pressure_ratio = 0.96 - 0.28 * sqrt(fluid_vapor_pressure_bar / fluid_critical_pressure_bar)
    choked_pressure_drop_bar = fl_recovery_factor**2 * (
        upstream_pressure_bar - liquid_critical_pressure_ratio * fluid_vapor_pressure_bar
    )
    effective_pressure_drop_bar = min(pressure_drop_bar, choked_pressure_drop_bar)
    cv_required = 1.156 * flow_rate_m3_h * sqrt(fluid_specific_gravity / effective_pressure_drop_bar)
    selected_cv_headroom = selected_valve_cv - cv_required
    valve_travel_pct = cv_required / selected_valve_cv * 100.0

    range_span = upper_range_value_m3_h - lower_range_value_m3_h
    if range_span <= 0:
        msg = "upper_range_value_m3_h must be greater than lower_range_value_m3_h"
        raise ValueError(msg)
    span_pct = (process_value_m3_h - lower_range_value_m3_h) / range_span * 100.0
    current_signal_ma = _signal_current_ma(
        process_value=process_value_m3_h,
        lower_range_value=lower_range_value_m3_h,
        upper_range_value=upper_range_value_m3_h,
    )
    reconstructed_process_value = lower_range_value_m3_h + (current_signal_ma - 4.0) / 16.0 * range_span
    high_alarm_current_ma = _signal_current_ma(
        process_value=high_alarm_flow_m3_h,
        lower_range_value=lower_range_value_m3_h,
        upper_range_value=upper_range_value_m3_h,
    )
    high_high_trip_current_ma = _signal_current_ma(
        process_value=high_high_trip_flow_m3_h,
        lower_range_value=lower_range_value_m3_h,
        upper_range_value=upper_range_value_m3_h,
    )
    alarm_current_headroom_ma = high_alarm_current_ma - current_signal_ma
    trip_flow_headroom_m3_h = high_high_trip_flow_m3_h - process_value_m3_h
    overall_pass_score = (
        1.0
        if selected_cv_headroom >= 0.0 and alarm_current_headroom_ma >= 0.0 and trip_flow_headroom_m3_h >= 0.0
        else 0.0
    )

    return {
        "pressure_drop_bar": round(pressure_drop_bar, 3),
        "choked_pressure_drop_bar": round(choked_pressure_drop_bar, 3),
        "cv_required": round(cv_required, 3),
        "selected_cv_headroom": round(selected_cv_headroom, 3),
        "valve_travel_pct": round(valve_travel_pct, 3),
        "span_pct": round(span_pct, 3),
        "current_signal_ma": round(current_signal_ma, 3),
        "reconstructed_process_value": round(reconstructed_process_value, 3),
        "high_alarm_current_ma": round(high_alarm_current_ma, 3),
        "high_high_trip_current_ma": round(high_high_trip_current_ma, 3),
        "alarm_current_headroom_ma": round(alarm_current_headroom_ma, 3),
        "trip_flow_headroom_m3_h": round(trip_flow_headroom_m3_h, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
