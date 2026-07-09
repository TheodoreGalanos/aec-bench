# ABOUTME: Computes SSC-18 fire pump pressure signal and alarm metrics.
# ABOUTME: Combines 4-20 mA pressure scaling, alarm margins, NAC load, and battery capacity.

from __future__ import annotations


def compute(
    residual_pressure_kpa: float,
    pressure_lower_kpa: float,
    pressure_upper_kpa: float,
    low_alarm_pressure_kpa: float,
    pump_start_pressure_kpa: float,
    nac_device_count: float,
    nac_device_current_a: float,
    nac_panel_capacity_a: float,
    control_load_w: float,
    standby_duration_h: float,
    alarm_duration_h: float,
    battery_capacity_kwh: float,
    dc_voltage_v: float,
    charger_efficiency: float,
) -> dict[str, float]:
    """Compute deterministic fire pump pressure signal and alarm checks."""
    span_kpa = pressure_upper_kpa - pressure_lower_kpa
    if span_kpa <= 0:
        msg = "pressure_upper_kpa must be greater than pressure_lower_kpa"
        raise ValueError(msg)
    if charger_efficiency <= 0:
        msg = "charger_efficiency must be > 0"
        raise ValueError(msg)

    def signal(pressure_kpa: float) -> float:
        return 4.0 + 16.0 * ((pressure_kpa - pressure_lower_kpa) / span_kpa)

    pressure_signal_ma = signal(residual_pressure_kpa)
    low_alarm_current_ma = signal(low_alarm_pressure_kpa)
    pump_start_current_ma = signal(pump_start_pressure_kpa)
    low_alarm_margin_kpa = residual_pressure_kpa - low_alarm_pressure_kpa
    pump_start_margin_kpa = residual_pressure_kpa - pump_start_pressure_kpa
    nac_load_a = nac_device_count * nac_device_current_a
    nac_panel_margin_a = nac_panel_capacity_a - nac_load_a
    battery_required_kwh = (control_load_w * standby_duration_h + nac_load_a * dc_voltage_v * alarm_duration_h) / (
        1000.0 * charger_efficiency
    )
    battery_margin_kwh = battery_capacity_kwh - battery_required_kwh
    overall_pass_score = (
        1.0
        if low_alarm_margin_kpa >= 0.0
        and pump_start_margin_kpa >= 0.0
        and nac_panel_margin_a >= 0.0
        and battery_margin_kwh >= 0.0
        else 0.0
    )

    return {
        "pressure_signal_ma": round(pressure_signal_ma, 3),
        "low_alarm_current_ma": round(low_alarm_current_ma, 3),
        "pump_start_current_ma": round(pump_start_current_ma, 3),
        "low_alarm_margin_kpa": round(low_alarm_margin_kpa, 3),
        "pump_start_margin_kpa": round(pump_start_margin_kpa, 3),
        "nac_load_a": round(nac_load_a, 3),
        "nac_panel_margin_a": round(nac_panel_margin_a, 3),
        "battery_required_kwh": round(battery_required_kwh, 3),
        "battery_margin_kwh": round(battery_margin_kwh, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
