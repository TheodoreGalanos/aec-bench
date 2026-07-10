# ABOUTME: Computes SSC-17/SSC-19 BESS fire, containment, ventilation, and feeder metrics.
# ABOUTME: Combines storage energy, ventilation, HRR containment, safety load, and feeder checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    bess_nominal_kwh: float,
    max_depth_of_discharge: float,
    inverter_efficiency: float,
    room_volume_m3: float,
    required_air_changes_h: float,
    fan_power_density_kw_m3_s: float,
    emergency_duration_hr: float,
    battery_module_count: float,
    module_hrr_kw: float,
    propagation_factor: float,
    containment_rating_kw: float,
    alarm_load_kw: float,
    suppression_load_kw: float,
    feeder_voltage_v: float,
    feeder_length_m: float,
    feeder_current_a: float,
    conductor_resistance_ohm_km: float,
    max_voltage_drop_percent: float,
) -> dict[str, float]:
    """Compute deterministic BESS safety and feeder metrics."""
    _require_positive(
        bess_nominal_kwh=bess_nominal_kwh,
        max_depth_of_discharge=max_depth_of_discharge,
        inverter_efficiency=inverter_efficiency,
        room_volume_m3=room_volume_m3,
        required_air_changes_h=required_air_changes_h,
        fan_power_density_kw_m3_s=fan_power_density_kw_m3_s,
        emergency_duration_hr=emergency_duration_hr,
        battery_module_count=battery_module_count,
        module_hrr_kw=module_hrr_kw,
        propagation_factor=propagation_factor,
        containment_rating_kw=containment_rating_kw,
        alarm_load_kw=alarm_load_kw,
        suppression_load_kw=suppression_load_kw,
        feeder_voltage_v=feeder_voltage_v,
        feeder_length_m=feeder_length_m,
        feeder_current_a=feeder_current_a,
        conductor_resistance_ohm_km=conductor_resistance_ohm_km,
        max_voltage_drop_percent=max_voltage_drop_percent,
    )
    if max(max_depth_of_discharge, inverter_efficiency, propagation_factor) > 1.0:
        msg = "fractional storage and propagation values must be <= 1"
        raise ValueError(msg)

    usable_bess_energy_kwh = bess_nominal_kwh * max_depth_of_discharge * inverter_efficiency
    ventilation_airflow_m3_s = room_volume_m3 * required_air_changes_h / 3600.0
    ventilation_fan_power_kw = ventilation_airflow_m3_s * fan_power_density_kw_m3_s
    ventilation_energy_kwh = ventilation_fan_power_kw * emergency_duration_hr
    design_hrr_kw = battery_module_count * module_hrr_kw * propagation_factor
    containment_hrr_margin_kw = containment_rating_kw - design_hrr_kw
    safety_load_kw = ventilation_fan_power_kw + alarm_load_kw + suppression_load_kw
    safety_energy_required_kwh = safety_load_kw * emergency_duration_hr
    safety_energy_margin_kwh = usable_bess_energy_kwh - safety_energy_required_kwh
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
        containment_hrr_margin_kw >= 0.0,
        safety_energy_margin_kwh >= 0.0,
        voltage_drop_margin_percent >= 0.0,
    ]

    return {
        "usable_bess_energy_kwh": round(usable_bess_energy_kwh, 3),
        "ventilation_airflow_m3_s": round(ventilation_airflow_m3_s, 3),
        "ventilation_fan_power_kw": round(ventilation_fan_power_kw, 3),
        "ventilation_energy_kwh": round(ventilation_energy_kwh, 3),
        "design_hrr_kw": round(design_hrr_kw, 3),
        "containment_hrr_margin_kw": round(containment_hrr_margin_kw, 3),
        "safety_load_kw": round(safety_load_kw, 3),
        "safety_energy_required_kwh": round(safety_energy_required_kwh, 3),
        "safety_energy_margin_kwh": round(safety_energy_margin_kwh, 3),
        "feeder_voltage_drop_percent": round(feeder_voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
