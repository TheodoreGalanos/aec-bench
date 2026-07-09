# ABOUTME: Computes SSC-17 rail corridor weather and backup operations metrics.
# ABOUTME: Combines signalling loads, weather heating, backup energy, rail margins, and feeder checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    signal_load_kw: float,
    communications_load_kw: float,
    weather_heating_kw: float,
    outage_duration_hr: float,
    weather_heating_duration_hr: float,
    battery_nominal_kwh: float,
    max_depth_of_discharge: float,
    inverter_efficiency: float,
    generator_kw: float,
    generator_runtime_hr: float,
    derated_thermal_rating_a: float,
    operating_current_a: float,
    allowable_sag_m: float,
    calculated_sag_m: float,
    feeder_voltage_v: float,
    feeder_length_m: float,
    feeder_current_a: float,
    conductor_resistance_ohm_km: float,
    max_voltage_drop_percent: float,
) -> dict[str, float]:
    """Compute deterministic SSC-17 rail backup operations metrics."""
    _require_positive(
        signal_load_kw=signal_load_kw,
        communications_load_kw=communications_load_kw,
        weather_heating_kw=weather_heating_kw,
        outage_duration_hr=outage_duration_hr,
        weather_heating_duration_hr=weather_heating_duration_hr,
        battery_nominal_kwh=battery_nominal_kwh,
        max_depth_of_discharge=max_depth_of_discharge,
        inverter_efficiency=inverter_efficiency,
        generator_kw=generator_kw,
        generator_runtime_hr=generator_runtime_hr,
        derated_thermal_rating_a=derated_thermal_rating_a,
        operating_current_a=operating_current_a,
        allowable_sag_m=allowable_sag_m,
        calculated_sag_m=calculated_sag_m,
        feeder_voltage_v=feeder_voltage_v,
        feeder_length_m=feeder_length_m,
        feeder_current_a=feeder_current_a,
        conductor_resistance_ohm_km=conductor_resistance_ohm_km,
        max_voltage_drop_percent=max_voltage_drop_percent,
    )
    if max(max_depth_of_discharge, inverter_efficiency) > 1.0:
        msg = "fractional storage values must be <= 1"
        raise ValueError(msg)

    signal_comms_load_kw = signal_load_kw + communications_load_kw
    weather_heating_energy_kwh = weather_heating_kw * weather_heating_duration_hr
    required_backup_energy_kwh = signal_comms_load_kw * outage_duration_hr + weather_heating_energy_kwh
    usable_battery_energy_kwh = battery_nominal_kwh * max_depth_of_discharge * inverter_efficiency
    generator_energy_kwh = generator_kw * generator_runtime_hr
    backup_energy_available_kwh = usable_battery_energy_kwh + generator_energy_kwh
    backup_energy_margin_kwh = backup_energy_available_kwh - required_backup_energy_kwh
    battery_only_runtime_hr = usable_battery_energy_kwh / signal_comms_load_kw
    thermal_rating_margin_a = derated_thermal_rating_a - operating_current_a
    sag_margin_m = allowable_sag_m - calculated_sag_m
    feeder_voltage_drop_percent = (
        math.sqrt(3.0)
        * feeder_current_a
        * feeder_length_m
        * conductor_resistance_ohm_km
        / 1000.0
        / feeder_voltage_v
        * 100.0
    )
    voltage_drop_margin_percent = max_voltage_drop_percent - feeder_voltage_drop_percent

    pass_checks = [
        backup_energy_margin_kwh >= 0.0,
        thermal_rating_margin_a >= 0.0,
        sag_margin_m >= 0.0,
        voltage_drop_margin_percent >= 0.0,
    ]

    return {
        "signal_comms_load_kw": round(signal_comms_load_kw, 3),
        "weather_heating_energy_kwh": round(weather_heating_energy_kwh, 3),
        "required_backup_energy_kwh": round(required_backup_energy_kwh, 3),
        "usable_battery_energy_kwh": round(usable_battery_energy_kwh, 3),
        "generator_energy_kwh": round(generator_energy_kwh, 3),
        "backup_energy_available_kwh": round(backup_energy_available_kwh, 3),
        "backup_energy_margin_kwh": round(backup_energy_margin_kwh, 3),
        "battery_only_runtime_hr": round(battery_only_runtime_hr, 3),
        "thermal_rating_margin_a": round(thermal_rating_margin_a, 3),
        "sag_margin_m": round(sag_margin_m, 3),
        "feeder_voltage_drop_percent": round(feeder_voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
