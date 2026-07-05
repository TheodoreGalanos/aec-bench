# ABOUTME: Computes SSC-18 chemical dosing flowmeter and control metrics.
# ABOUTME: Combines dose mass, solution feed, 4-20 mA flowmeter signal, alarm, and pump current.

from __future__ import annotations

from math import sqrt


def compute(
    plant_flow_m3_d: float,
    dose_mg_l: float,
    active_fraction: float,
    solution_density_kg_l: float,
    pump_operating_hours_d: float,
    selected_pump_capacity_l_h: float,
    flowmeter_lower_l_h: float,
    flowmeter_upper_l_h: float,
    high_alarm_flow_l_h: float,
    pump_power_kw: float,
    supply_voltage_v: float,
    motor_power_factor: float,
) -> dict[str, float]:
    """Compute deterministic dosing flowmeter and control checks."""
    if active_fraction <= 0 or solution_density_kg_l <= 0 or pump_operating_hours_d <= 0:
        msg = "active_fraction, solution_density_kg_l, and pump_operating_hours_d must be > 0"
        raise ValueError(msg)
    span_l_h = flowmeter_upper_l_h - flowmeter_lower_l_h
    if span_l_h <= 0:
        msg = "flowmeter_upper_l_h must be greater than flowmeter_lower_l_h"
        raise ValueError(msg)

    active_dose_kg_d = plant_flow_m3_d * 1000.0 * dose_mg_l / 1_000_000.0
    solution_volume_l_d = active_dose_kg_d / active_fraction / solution_density_kg_l
    dosing_pump_flow_l_h = solution_volume_l_d / pump_operating_hours_d
    pump_capacity_margin_l_h = selected_pump_capacity_l_h - dosing_pump_flow_l_h

    def signal(flow_l_h: float) -> float:
        return 4.0 + 16.0 * ((flow_l_h - flowmeter_lower_l_h) / span_l_h)

    flowmeter_signal_ma = signal(dosing_pump_flow_l_h)
    high_alarm_current_ma = signal(high_alarm_flow_l_h)
    alarm_headroom_ma = high_alarm_current_ma - flowmeter_signal_ma
    pump_current_a = pump_power_kw * 1000.0 / (sqrt(3.0) * supply_voltage_v * motor_power_factor)
    overall_pass_score = 1.0 if pump_capacity_margin_l_h >= 0.0 and alarm_headroom_ma >= 0.0 else 0.0

    return {
        "active_dose_kg_d": round(active_dose_kg_d, 3),
        "solution_volume_l_d": round(solution_volume_l_d, 3),
        "dosing_pump_flow_l_h": round(dosing_pump_flow_l_h, 3),
        "pump_capacity_margin_l_h": round(pump_capacity_margin_l_h, 3),
        "flowmeter_signal_ma": round(flowmeter_signal_ma, 3),
        "high_alarm_current_ma": round(high_alarm_current_ma, 3),
        "alarm_headroom_ma": round(alarm_headroom_ma, 3),
        "pump_current_a": round(pump_current_a, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
