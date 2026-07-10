# ABOUTME: Computes SSC-10 wet-weather process and bypass resilience metrics.
# ABOUTME: Combines storage, reactor HRT, clarifier SOR, pump energy, backup energy, and bypass checks.

from __future__ import annotations


def compute(
    peak_inflow_m3_h: float,
    process_capacity_m3_h: float,
    peak_duration_h: float,
    reactor_volume_m3: float,
    min_hrt_hr: float,
    clarifier_area_m2: float,
    max_peak_sor_m3_m2_d: float,
    available_storage_m3: float,
    pump_head_m: float,
    pump_efficiency: float,
    pump_motor_efficiency: float,
    backup_bess_kwh: float,
    bess_usable_soc_fraction: float,
    bess_inverter_efficiency: float,
    bess_reserve_kwh: float,
    outage_duration_h: float,
    allowed_bypass_m3: float,
) -> dict[str, float]:
    """Compute source-bound SSC-10 wet-weather resilience metrics."""
    required_storage_m3 = max(peak_inflow_m3_h - process_capacity_m3_h, 0.0) * peak_duration_h
    storage_margin_m3 = available_storage_m3 - required_storage_m3
    reactor_hrt_hr = reactor_volume_m3 / peak_inflow_m3_h
    hrt_margin_hr = reactor_hrt_hr - min_hrt_hr
    clarifier_peak_sor_m3_m2_d = peak_inflow_m3_h * 24.0 / clarifier_area_m2
    sor_margin_m3_m2_d = max_peak_sor_m3_m2_d - clarifier_peak_sor_m3_m2_d
    pump_hydraulic_power_kw = 1000.0 * 9.81 * (peak_inflow_m3_h / 3600.0) * pump_head_m / 1000.0
    pump_input_power_kw = pump_hydraulic_power_kw / pump_efficiency / pump_motor_efficiency
    outage_energy_kwh = pump_input_power_kw * outage_duration_h
    usable_backup_energy_kwh = backup_bess_kwh * bess_usable_soc_fraction * bess_inverter_efficiency - bess_reserve_kwh
    backup_energy_margin_kwh = usable_backup_energy_kwh - outage_energy_kwh
    bypass_volume_m3 = max(
        (peak_inflow_m3_h - process_capacity_m3_h - available_storage_m3 / peak_duration_h) * peak_duration_h,
        0.0,
    )
    bypass_margin_m3 = allowed_bypass_m3 - bypass_volume_m3
    overall_pass_score = (
        1.0
        if min(storage_margin_m3, hrt_margin_hr, sor_margin_m3_m2_d, backup_energy_margin_kwh, bypass_margin_m3) >= 0.0
        else 0.0
    )

    return {
        "required_storage_m3": round(required_storage_m3, 3),
        "storage_margin_m3": round(storage_margin_m3, 3),
        "reactor_hrt_hr": round(reactor_hrt_hr, 3),
        "hrt_margin_hr": round(hrt_margin_hr, 3),
        "clarifier_peak_sor_m3_m2_d": round(clarifier_peak_sor_m3_m2_d, 3),
        "sor_margin_m3_m2_d": round(sor_margin_m3_m2_d, 3),
        "pump_input_power_kw": round(pump_input_power_kw, 3),
        "outage_energy_kwh": round(outage_energy_kwh, 3),
        "usable_backup_energy_kwh": round(usable_backup_energy_kwh, 3),
        "backup_energy_margin_kwh": round(backup_energy_margin_kwh, 3),
        "bypass_volume_m3": round(bypass_volume_m3, 3),
        "bypass_margin_m3": round(bypass_margin_m3, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
