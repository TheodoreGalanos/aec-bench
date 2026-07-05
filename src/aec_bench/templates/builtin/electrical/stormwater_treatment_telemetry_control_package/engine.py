# ABOUTME: Computes SSC-18 telemetry control metrics from source-owned loop values.
# ABOUTME: Combines 4-20 mA level scaling, pump setpoints, communications load, and backup energy.

from __future__ import annotations


def compute(
    current_level_m: float,
    lower_range_level_m: float,
    upper_range_level_m: float,
    high_level_alarm_m: float,
    pump_start_level_m: float,
    pump_stop_level_m: float,
    sensor_accuracy_pct_span: float,
    device_count: float,
    device_power_w: float,
    radio_power_w: float,
    backup_duration_h: float,
    battery_voltage_v: float,
    battery_capacity_ah: float,
    battery_usable_fraction: float,
    inverter_efficiency: float,
) -> dict[str, float]:
    """Compute deterministic telemetry scaling and backup-power checks."""
    level_span_m = upper_range_level_m - lower_range_level_m
    if level_span_m <= 0:
        msg = "upper_range_level_m must be greater than lower_range_level_m"
        raise ValueError(msg)
    if inverter_efficiency <= 0:
        msg = "inverter_efficiency must be > 0"
        raise ValueError(msg)

    def signal(level_m: float) -> float:
        return 4.0 + 16.0 * ((level_m - lower_range_level_m) / level_span_m)

    current_signal_ma = signal(current_level_m)
    high_level_current_ma = signal(high_level_alarm_m)
    pump_start_current_ma = signal(pump_start_level_m)
    pump_stop_current_ma = signal(pump_stop_level_m)
    sensor_accuracy_m = level_span_m * sensor_accuracy_pct_span / 100.0
    pump_start_margin_m = pump_start_level_m - current_level_m
    telemetry_load_w = device_count * device_power_w + radio_power_w
    backup_energy_required_kwh = telemetry_load_w * backup_duration_h / (1000.0 * inverter_efficiency)
    battery_usable_kwh = battery_voltage_v * battery_capacity_ah * battery_usable_fraction / 1000.0
    backup_energy_margin_kwh = battery_usable_kwh - backup_energy_required_kwh
    overall_pass_score = (
        1.0
        if high_level_current_ma > current_signal_ma and pump_start_margin_m >= 0.0 and backup_energy_margin_kwh >= 0.0
        else 0.0
    )

    return {
        "level_span_m": round(level_span_m, 3),
        "current_signal_ma": round(current_signal_ma, 3),
        "high_level_current_ma": round(high_level_current_ma, 3),
        "pump_start_current_ma": round(pump_start_current_ma, 3),
        "pump_stop_current_ma": round(pump_stop_current_ma, 3),
        "sensor_accuracy_m": round(sensor_accuracy_m, 3),
        "pump_start_margin_m": round(pump_start_margin_m, 3),
        "telemetry_load_w": round(telemetry_load_w, 3),
        "backup_energy_required_kwh": round(backup_energy_required_kwh, 3),
        "battery_usable_kwh": round(battery_usable_kwh, 3),
        "backup_energy_margin_kwh": round(backup_energy_margin_kwh, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
