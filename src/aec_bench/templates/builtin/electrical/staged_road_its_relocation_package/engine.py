# ABOUTME: Computes SSC-16 staged road and ITS relocation metrics.
# ABOUTME: Combines pedestrian timing, VMS legibility, network, PoE, battery, and detour checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    crossing_width_m: float,
    pedestrian_walk_speed_m_s: float,
    pedestrian_startup_time_s: float,
    provided_ped_clearance_s: float,
    vms_character_height_mm: float,
    vms_legibility_factor_m_per_mm: float,
    available_vms_viewing_distance_m: float,
    signal_controller_data_mbps: float,
    vms_data_mbps: float,
    cctv_data_mbps: float,
    detector_data_mbps: float,
    gateway_overhead_mbps: float,
    network_capacity_mbps: float,
    cctv_poe_w: float,
    detector_poe_w: float,
    router_poe_w: float,
    vms_modem_poe_w: float,
    poe_budget_w: float,
    signal_controller_load_w: float,
    vms_power_load_w: float,
    battery_backup_hours: float,
    provided_battery_kwh: float,
    allowable_detour_delay_s: float,
    estimated_detour_delay_s: float,
) -> dict[str, float]:
    """Compute deterministic staged road and ITS relocation checks."""
    _require_positive(
        crossing_width_m=crossing_width_m,
        pedestrian_walk_speed_m_s=pedestrian_walk_speed_m_s,
        provided_ped_clearance_s=provided_ped_clearance_s,
        vms_character_height_mm=vms_character_height_mm,
        vms_legibility_factor_m_per_mm=vms_legibility_factor_m_per_mm,
        available_vms_viewing_distance_m=available_vms_viewing_distance_m,
        network_capacity_mbps=network_capacity_mbps,
        cctv_poe_w=cctv_poe_w,
        detector_poe_w=detector_poe_w,
        router_poe_w=router_poe_w,
        vms_modem_poe_w=vms_modem_poe_w,
        poe_budget_w=poe_budget_w,
        signal_controller_load_w=signal_controller_load_w,
        vms_power_load_w=vms_power_load_w,
        battery_backup_hours=battery_backup_hours,
        provided_battery_kwh=provided_battery_kwh,
        allowable_detour_delay_s=allowable_detour_delay_s,
        estimated_detour_delay_s=estimated_detour_delay_s,
    )
    if pedestrian_startup_time_s < 0:
        msg = "pedestrian_startup_time_s must be >= 0"
        raise ValueError(msg)
    if min(signal_controller_data_mbps, vms_data_mbps, cctv_data_mbps, detector_data_mbps, gateway_overhead_mbps) < 0:
        msg = "data loads must be >= 0"
        raise ValueError(msg)

    pedestrian_clearance_time_s = crossing_width_m / pedestrian_walk_speed_m_s + pedestrian_startup_time_s
    pedestrian_clearance_margin_s = provided_ped_clearance_s - pedestrian_clearance_time_s
    required_vms_legibility_distance_m = vms_character_height_mm * vms_legibility_factor_m_per_mm
    vms_legibility_margin_m = available_vms_viewing_distance_m - required_vms_legibility_distance_m
    network_load_mbps = (
        signal_controller_data_mbps + vms_data_mbps + cctv_data_mbps + detector_data_mbps + gateway_overhead_mbps
    )
    network_headroom_mbps = network_capacity_mbps - network_load_mbps
    poe_load_w = cctv_poe_w + detector_poe_w + router_poe_w + vms_modem_poe_w
    poe_headroom_w = poe_budget_w - poe_load_w
    battery_required_kwh = (signal_controller_load_w + vms_power_load_w + poe_load_w) * battery_backup_hours / 1000.0
    battery_margin_kwh = provided_battery_kwh - battery_required_kwh
    detour_delay_margin_s = allowable_detour_delay_s - estimated_detour_delay_s

    pass_checks = [
        pedestrian_clearance_margin_s >= 0.0,
        vms_legibility_margin_m >= 0.0,
        network_headroom_mbps >= 0.0,
        poe_headroom_w >= 0.0,
        battery_margin_kwh >= 0.0,
        detour_delay_margin_s >= 0.0,
    ]

    return {
        "pedestrian_clearance_time_s": round(pedestrian_clearance_time_s, 3),
        "pedestrian_clearance_margin_s": round(pedestrian_clearance_margin_s, 3),
        "required_vms_legibility_distance_m": round(required_vms_legibility_distance_m, 3),
        "vms_legibility_margin_m": round(vms_legibility_margin_m, 3),
        "network_load_mbps": round(network_load_mbps, 3),
        "network_headroom_mbps": round(network_headroom_mbps, 3),
        "poe_load_w": round(poe_load_w, 3),
        "poe_headroom_w": round(poe_headroom_w, 3),
        "battery_required_kwh": round(battery_required_kwh, 3),
        "battery_margin_kwh": round(battery_margin_kwh, 3),
        "detour_delay_margin_s": round(detour_delay_margin_s, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
