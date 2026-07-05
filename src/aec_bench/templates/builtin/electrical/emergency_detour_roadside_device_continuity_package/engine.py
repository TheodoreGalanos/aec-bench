# ABOUTME: Computes SSC-01 emergency detour and roadside device continuity metrics.
# ABOUTME: Combines VMS, network, RF link, backup battery, and feeder voltage checks.

from __future__ import annotations

_FT_TO_M = 0.3048


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    vms_character_height_in: float,
    detour_speed_kmh: float,
    reading_rate_chars_s: float,
    detour_message_length_chars: float,
    cctv_count: float,
    cctv_load_mbps: float,
    vms_count: float,
    vms_load_mbps: float,
    radio_load_mbps: float,
    controller_load_mbps: float,
    network_overhead_pct: float,
    uplink_capacity_mbps: float,
    rf_tx_power_dbm: float,
    rf_tx_gain_db: float,
    rf_rx_gain_db: float,
    rf_path_loss_db: float,
    rf_misc_loss_db: float,
    rf_fade_margin_db: float,
    rf_receiver_sensitivity_dbm: float,
    battery_capacity_kwh: float,
    battery_efficiency: float,
    critical_load_w: float,
    required_detour_duration_h: float,
    feeder_length_km: float,
    conductor_resistance_ohm_km: float,
    feeder_voltage_v: float,
    power_factor: float,
    allowable_voltage_drop_pct: float,
) -> dict[str, float]:
    """Compute deterministic SSC-01 emergency detour continuity metrics."""
    _require_positive(
        vms_character_height_in=vms_character_height_in,
        detour_speed_kmh=detour_speed_kmh,
        reading_rate_chars_s=reading_rate_chars_s,
        cctv_count=cctv_count,
        cctv_load_mbps=cctv_load_mbps,
        vms_count=vms_count,
        vms_load_mbps=vms_load_mbps,
        uplink_capacity_mbps=uplink_capacity_mbps,
        battery_capacity_kwh=battery_capacity_kwh,
        battery_efficiency=battery_efficiency,
        critical_load_w=critical_load_w,
        required_detour_duration_h=required_detour_duration_h,
        feeder_length_km=feeder_length_km,
        conductor_resistance_ohm_km=conductor_resistance_ohm_km,
        feeder_voltage_v=feeder_voltage_v,
        power_factor=power_factor,
        allowable_voltage_drop_pct=allowable_voltage_drop_pct,
    )
    vms_reading_time_s = vms_character_height_in * 40.0 * _FT_TO_M / (detour_speed_kmh / 3.6)
    vms_message_margin_chars = vms_reading_time_s * reading_rate_chars_s - detour_message_length_chars
    base_network_mbps = cctv_count * cctv_load_mbps + vms_count * vms_load_mbps + radio_load_mbps + controller_load_mbps
    required_network_mbps = base_network_mbps * (1.0 + network_overhead_pct / 100.0)
    network_headroom_mbps = uplink_capacity_mbps - required_network_mbps
    rf_received_power_dbm = (
        rf_tx_power_dbm + rf_tx_gain_db + rf_rx_gain_db - rf_path_loss_db - rf_misc_loss_db - rf_fade_margin_db
    )
    rf_link_margin_db = rf_received_power_dbm - rf_receiver_sensitivity_dbm
    battery_runtime_h = battery_capacity_kwh * battery_efficiency / (critical_load_w / 1000.0)
    battery_margin_h = battery_runtime_h - required_detour_duration_h
    feeder_current_a = critical_load_w / (feeder_voltage_v * power_factor)
    feeder_voltage_drop_percent = (
        2.0 * feeder_length_km * conductor_resistance_ohm_km * feeder_current_a / feeder_voltage_v * 100.0
    )
    voltage_drop_margin_percent = allowable_voltage_drop_pct - feeder_voltage_drop_percent

    pass_checks = [
        vms_message_margin_chars >= 0.0,
        network_headroom_mbps >= 0.0,
        rf_link_margin_db >= 0.0,
        battery_margin_h >= 0.0,
        voltage_drop_margin_percent >= 0.0,
    ]

    return {
        "vms_reading_time_s": round(vms_reading_time_s, 3),
        "vms_message_margin_chars": round(vms_message_margin_chars, 3),
        "required_network_mbps": round(required_network_mbps, 3),
        "network_headroom_mbps": round(network_headroom_mbps, 3),
        "rf_received_power_dbm": round(rf_received_power_dbm, 3),
        "rf_link_margin_db": round(rf_link_margin_db, 3),
        "battery_runtime_h": round(battery_runtime_h, 3),
        "battery_margin_h": round(battery_margin_h, 3),
        "feeder_voltage_drop_percent": round(feeder_voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
