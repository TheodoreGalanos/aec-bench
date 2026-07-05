# ABOUTME: Computes SSC-05 PV/BESS interconnection and export-control metrics.
# ABOUTME: Combines PV AC output, export limit, BESS autonomy, feeder, and breaker checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _require_fraction(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        msg = f"{name} must be between 0 and 1"
        raise ValueError(msg)


def compute(
    pv_dc_kw: float,
    dc_ac_derate_factor: float,
    inverter_ac_kw: float,
    site_minimum_load_kw: float,
    export_limit_kw: float,
    bess_nominal_kwh: float,
    bess_usable_fraction: float,
    bess_inverter_efficiency: float,
    reserved_energy_kwh: float,
    critical_load_kw: float,
    outage_duration_h: float,
    feeder_voltage_v: float,
    feeder_power_factor: float,
    feeder_length_m: float,
    voltage_drop_mv_per_a_m: float,
    breaker_allowable_current_a: float,
    max_voltage_drop_percent: float,
) -> dict[str, float]:
    """Compute source-bound PV/BESS export, autonomy, and feeder metrics."""
    _require_positive(
        pv_dc_kw=pv_dc_kw,
        dc_ac_derate_factor=dc_ac_derate_factor,
        inverter_ac_kw=inverter_ac_kw,
        site_minimum_load_kw=site_minimum_load_kw,
        export_limit_kw=export_limit_kw,
        bess_nominal_kwh=bess_nominal_kwh,
        bess_inverter_efficiency=bess_inverter_efficiency,
        critical_load_kw=critical_load_kw,
        outage_duration_h=outage_duration_h,
        feeder_voltage_v=feeder_voltage_v,
        feeder_power_factor=feeder_power_factor,
        feeder_length_m=feeder_length_m,
        voltage_drop_mv_per_a_m=voltage_drop_mv_per_a_m,
        breaker_allowable_current_a=breaker_allowable_current_a,
        max_voltage_drop_percent=max_voltage_drop_percent,
    )
    if reserved_energy_kwh < 0.0:
        msg = "reserved_energy_kwh must be >= 0"
        raise ValueError(msg)
    _require_fraction("bess_usable_fraction", bess_usable_fraction)
    _require_fraction("feeder_power_factor", feeder_power_factor)

    pv_ac_output_kw = min(pv_dc_kw * dc_ac_derate_factor, inverter_ac_kw)
    export_kw = max(pv_ac_output_kw - site_minimum_load_kw, 0.0)
    export_excess_kw = max(export_kw - export_limit_kw, 0.0)

    usable_bess_energy_kwh = bess_nominal_kwh * bess_usable_fraction * bess_inverter_efficiency - reserved_energy_kwh
    backup_energy_required_kwh = critical_load_kw * outage_duration_h
    backup_energy_margin_kwh = usable_bess_energy_kwh - backup_energy_required_kwh

    feeder_current_a = pv_ac_output_kw * 1000.0 / (math.sqrt(3.0) * feeder_voltage_v * feeder_power_factor)
    voltage_drop_v = voltage_drop_mv_per_a_m * feeder_current_a * feeder_length_m / 1000.0
    feeder_voltage_drop_percent = voltage_drop_v / feeder_voltage_v * 100.0
    voltage_drop_excess_percent = max(feeder_voltage_drop_percent - max_voltage_drop_percent, 0.0)
    breaker_margin_a = breaker_allowable_current_a - feeder_current_a

    overall_pass_score = (
        1.0
        if min(
            export_limit_kw - export_kw,
            backup_energy_margin_kwh,
            max_voltage_drop_percent - feeder_voltage_drop_percent,
            breaker_margin_a,
        )
        >= 0.0
        else 0.0
    )

    return {
        "pv_ac_output_kw": round(pv_ac_output_kw, 3),
        "export_kw": round(export_kw, 3),
        "export_excess_kw": round(export_excess_kw, 3),
        "usable_bess_energy_kwh": round(usable_bess_energy_kwh, 3),
        "backup_energy_required_kwh": round(backup_energy_required_kwh, 3),
        "backup_energy_margin_kwh": round(backup_energy_margin_kwh, 3),
        "feeder_current_a": round(feeder_current_a, 3),
        "feeder_voltage_drop_percent": round(feeder_voltage_drop_percent, 3),
        "voltage_drop_excess_percent": round(voltage_drop_excess_percent, 3),
        "breaker_margin_a": round(breaker_margin_a, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
