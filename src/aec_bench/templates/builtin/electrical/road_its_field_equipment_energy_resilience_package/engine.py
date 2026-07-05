# ABOUTME: Computes SSC-17 road and ITS field equipment energy resilience metrics.
# ABOUTME: Combines field loads, battery/PV autonomy, cabinet freeboard, and PoE budget checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    luminaire_count: float,
    luminaire_kw_each: float,
    vms_kw: float,
    cctv_count: float,
    cctv_kw_each: float,
    comms_kw: float,
    outage_duration_hr: float,
    cabinet_battery_kwh: float,
    max_depth_of_discharge: float,
    inverter_efficiency: float,
    pv_kw: float,
    solar_hours: float,
    pv_performance_ratio: float,
    cabinet_threshold_level_m: float,
    flood_hgl_m: float,
    required_freeboard_m: float,
    poe_budget_w: float,
    poe_camera_w_each: float,
    poe_switch_w: float,
    required_vms_runtime_hr: float,
) -> dict[str, float]:
    """Compute deterministic SSC-17 road ITS energy resilience metrics."""
    _require_positive(
        luminaire_count=luminaire_count,
        luminaire_kw_each=luminaire_kw_each,
        vms_kw=vms_kw,
        cctv_count=cctv_count,
        cctv_kw_each=cctv_kw_each,
        comms_kw=comms_kw,
        outage_duration_hr=outage_duration_hr,
        cabinet_battery_kwh=cabinet_battery_kwh,
        max_depth_of_discharge=max_depth_of_discharge,
        inverter_efficiency=inverter_efficiency,
        pv_kw=pv_kw,
        solar_hours=solar_hours,
        pv_performance_ratio=pv_performance_ratio,
        required_freeboard_m=required_freeboard_m,
        poe_budget_w=poe_budget_w,
        poe_camera_w_each=poe_camera_w_each,
        poe_switch_w=poe_switch_w,
        required_vms_runtime_hr=required_vms_runtime_hr,
    )
    if max(max_depth_of_discharge, inverter_efficiency, pv_performance_ratio) > 1.0:
        msg = "fractional storage and PV values must be <= 1"
        raise ValueError(msg)

    field_device_load_kw = luminaire_count * luminaire_kw_each + vms_kw + cctv_count * cctv_kw_each + comms_kw
    outage_energy_required_kwh = field_device_load_kw * outage_duration_hr
    usable_battery_energy_kwh = cabinet_battery_kwh * max_depth_of_discharge * inverter_efficiency
    pv_energy_available_kwh = pv_kw * solar_hours * pv_performance_ratio
    backup_energy_available_kwh = usable_battery_energy_kwh + pv_energy_available_kwh
    backup_energy_margin_kwh = backup_energy_available_kwh - outage_energy_required_kwh
    battery_only_runtime_hr = usable_battery_energy_kwh / field_device_load_kw
    vms_runtime_margin_hr = battery_only_runtime_hr - required_vms_runtime_hr
    cabinet_freeboard_m = cabinet_threshold_level_m - flood_hgl_m
    cabinet_freeboard_margin_m = cabinet_freeboard_m - required_freeboard_m
    poe_load_w = cctv_count * poe_camera_w_each + poe_switch_w
    poe_margin_w = poe_budget_w - poe_load_w

    pass_checks = [
        backup_energy_margin_kwh >= 0.0,
        vms_runtime_margin_hr >= 0.0,
        cabinet_freeboard_margin_m >= 0.0,
        poe_margin_w >= 0.0,
    ]

    return {
        "field_device_load_kw": round(field_device_load_kw, 3),
        "outage_energy_required_kwh": round(outage_energy_required_kwh, 3),
        "usable_battery_energy_kwh": round(usable_battery_energy_kwh, 3),
        "pv_energy_available_kwh": round(pv_energy_available_kwh, 3),
        "backup_energy_available_kwh": round(backup_energy_available_kwh, 3),
        "backup_energy_margin_kwh": round(backup_energy_margin_kwh, 3),
        "battery_only_runtime_hr": round(battery_only_runtime_hr, 3),
        "vms_runtime_margin_hr": round(vms_runtime_margin_hr, 3),
        "cabinet_freeboard_m": round(cabinet_freeboard_m, 3),
        "cabinet_freeboard_margin_m": round(cabinet_freeboard_margin_m, 3),
        "poe_load_w": round(poe_load_w, 3),
        "poe_margin_w": round(poe_margin_w, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
