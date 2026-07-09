# ABOUTME: Computes SSC-17 DER resilience and feeder interconnection metrics.
# ABOUTME: Combines PV output, export, backup energy, feeder voltage drop, and ampacity checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    pv_dc_kw: float,
    pv_ac_derate: float,
    inverter_ac_rating_kw: float,
    site_minimum_load_kw: float,
    export_limit_kw: float,
    critical_load_kw: float,
    outage_duration_hr: float,
    bess_nominal_kwh: float,
    max_depth_of_discharge: float,
    inverter_efficiency: float,
    generator_kw: float,
    generator_runtime_hr: float,
    feeder_voltage_v: float,
    feeder_length_m: float,
    feeder_current_a: float,
    conductor_resistance_ohm_km: float,
    max_voltage_drop_percent: float,
    feeder_ampacity_a: float,
) -> dict[str, float]:
    """Compute deterministic SSC-17 DER resilience and interconnection metrics."""
    _require_positive(
        pv_dc_kw=pv_dc_kw,
        pv_ac_derate=pv_ac_derate,
        inverter_ac_rating_kw=inverter_ac_rating_kw,
        export_limit_kw=export_limit_kw,
        critical_load_kw=critical_load_kw,
        outage_duration_hr=outage_duration_hr,
        bess_nominal_kwh=bess_nominal_kwh,
        max_depth_of_discharge=max_depth_of_discharge,
        inverter_efficiency=inverter_efficiency,
        generator_kw=generator_kw,
        generator_runtime_hr=generator_runtime_hr,
        feeder_voltage_v=feeder_voltage_v,
        feeder_length_m=feeder_length_m,
        feeder_current_a=feeder_current_a,
        conductor_resistance_ohm_km=conductor_resistance_ohm_km,
        max_voltage_drop_percent=max_voltage_drop_percent,
        feeder_ampacity_a=feeder_ampacity_a,
    )
    if min(pv_ac_derate, max_depth_of_discharge, inverter_efficiency) > 1.0:
        msg = "fractional derate, depth of discharge, and efficiency values must be <= 1"
        raise ValueError(msg)

    pv_ac_output_kw = min(pv_dc_kw * pv_ac_derate, inverter_ac_rating_kw)
    export_kw = max(pv_ac_output_kw - site_minimum_load_kw, 0.0)
    export_margin_kw = export_limit_kw - export_kw
    critical_energy_required_kwh = critical_load_kw * outage_duration_hr
    usable_bess_energy_kwh = bess_nominal_kwh * max_depth_of_discharge * inverter_efficiency
    generator_energy_kwh = generator_kw * generator_runtime_hr
    resilience_energy_available_kwh = usable_bess_energy_kwh + generator_energy_kwh
    autonomy_energy_margin_kwh = resilience_energy_available_kwh - critical_energy_required_kwh
    battery_only_runtime_hr = usable_bess_energy_kwh / critical_load_kw
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
    feeder_ampacity_margin_a = feeder_ampacity_a - feeder_current_a

    pass_checks = [
        export_margin_kw >= 0.0,
        autonomy_energy_margin_kwh >= 0.0,
        voltage_drop_margin_percent >= 0.0,
        feeder_ampacity_margin_a >= 0.0,
    ]

    return {
        "pv_ac_output_kw": round(pv_ac_output_kw, 3),
        "export_kw": round(export_kw, 3),
        "export_margin_kw": round(export_margin_kw, 3),
        "critical_energy_required_kwh": round(critical_energy_required_kwh, 3),
        "usable_bess_energy_kwh": round(usable_bess_energy_kwh, 3),
        "generator_energy_kwh": round(generator_energy_kwh, 3),
        "resilience_energy_available_kwh": round(resilience_energy_available_kwh, 3),
        "autonomy_energy_margin_kwh": round(autonomy_energy_margin_kwh, 3),
        "battery_only_runtime_hr": round(battery_only_runtime_hr, 3),
        "feeder_voltage_drop_percent": round(feeder_voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "feeder_ampacity_margin_a": round(feeder_ampacity_margin_a, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
