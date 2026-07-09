# ABOUTME: Computes SSC-13 remote ITS backup communications metrics.
# ABOUTME: Combines RF, fibre, bandwidth, PoE, and battery autonomy checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    rf_tx_power_dbm: float,
    rf_tx_gain_db: float,
    rf_rx_gain_db: float,
    rf_path_loss_db: float,
    rf_misc_loss_db: float,
    rf_receiver_sensitivity_dbm: float,
    fibre_length_km: float,
    fibre_loss_db_per_km: float,
    connector_count: float,
    connector_loss_db: float,
    splice_count: float,
    splice_loss_db: float,
    reserve_loss_db: float,
    fibre_budget_db: float,
    cctv_network_mbps: float,
    vms_network_mbps: float,
    sensor_network_mbps: float,
    controller_network_mbps: float,
    network_overhead_factor: float,
    backhaul_capacity_mbps: float,
    camera_count: float,
    camera_poe_w: float,
    radio_poe_w: float,
    vms_poe_w: float,
    sensor_poe_w: float,
    poe_budget_w: float,
    backup_load_w: float,
    autonomy_h: float,
    inverter_efficiency: float,
    allowable_depth_of_discharge: float,
    battery_capacity_kwh: float,
) -> dict[str, float]:
    _require_positive(
        fibre_length_km=fibre_length_km,
        fibre_loss_db_per_km=fibre_loss_db_per_km,
        connector_count=connector_count,
        connector_loss_db=connector_loss_db,
        splice_count=splice_count,
        splice_loss_db=splice_loss_db,
        fibre_budget_db=fibre_budget_db,
        network_overhead_factor=network_overhead_factor,
        backhaul_capacity_mbps=backhaul_capacity_mbps,
        camera_count=camera_count,
        poe_budget_w=poe_budget_w,
        backup_load_w=backup_load_w,
        autonomy_h=autonomy_h,
        inverter_efficiency=inverter_efficiency,
        allowable_depth_of_discharge=allowable_depth_of_discharge,
        battery_capacity_kwh=battery_capacity_kwh,
    )

    rf_received_power_dbm = rf_tx_power_dbm + rf_tx_gain_db + rf_rx_gain_db - rf_path_loss_db - rf_misc_loss_db
    rf_fade_margin_db = rf_received_power_dbm - rf_receiver_sensitivity_dbm
    fibre_loss_db = (
        fibre_length_km * fibre_loss_db_per_km
        + connector_count * connector_loss_db
        + splice_count * splice_loss_db
        + reserve_loss_db
    )
    fibre_margin_db = fibre_budget_db - fibre_loss_db
    network_load_mbps = (
        cctv_network_mbps + vms_network_mbps + sensor_network_mbps + controller_network_mbps
    ) * network_overhead_factor
    network_headroom_mbps = backhaul_capacity_mbps - network_load_mbps
    poe_load_w = camera_count * camera_poe_w + radio_poe_w + vms_poe_w + sensor_poe_w
    poe_headroom_w = poe_budget_w - poe_load_w
    battery_required_kwh = backup_load_w * autonomy_h / inverter_efficiency / allowable_depth_of_discharge / 1000.0
    battery_margin_kwh = battery_capacity_kwh - battery_required_kwh
    overall_pass_score = (
        1.0
        if (
            rf_fade_margin_db >= 0.0
            and fibre_margin_db >= 0.0
            and network_headroom_mbps >= 0.0
            and poe_headroom_w >= 0.0
            and battery_margin_kwh >= 0.0
        )
        else 0.0
    )

    return {
        "rf_received_power_dbm": round(rf_received_power_dbm, 3),
        "rf_fade_margin_db": round(rf_fade_margin_db, 3),
        "fibre_loss_db": round(fibre_loss_db, 3),
        "fibre_margin_db": round(fibre_margin_db, 3),
        "network_load_mbps": round(network_load_mbps, 3),
        "network_headroom_mbps": round(network_headroom_mbps, 3),
        "poe_load_w": round(poe_load_w, 3),
        "poe_headroom_w": round(poe_headroom_w, 3),
        "battery_required_kwh": round(battery_required_kwh, 3),
        "battery_margin_kwh": round(battery_margin_kwh, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
