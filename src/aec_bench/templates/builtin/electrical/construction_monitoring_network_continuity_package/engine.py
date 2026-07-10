# ABOUTME: Computes SSC-16 construction monitoring network continuity metrics.
# ABOUTME: Combines sensor data, RF margin, PoE, battery, solar, and voltage-drop checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    turbidity_sensor_count: float,
    turbidity_sensor_data_mbps: float,
    vibration_sensor_count: float,
    vibration_sensor_data_mbps: float,
    camera_count: float,
    camera_data_mbps: float,
    weather_station_data_mbps: float,
    gateway_overhead_mbps: float,
    network_capacity_mbps: float,
    rf_tx_power_dbm: float,
    rf_tx_gain_db: float,
    rf_rx_gain_db: float,
    rf_path_loss_db: float,
    rf_misc_loss_db: float,
    rf_receiver_sensitivity_dbm: float,
    camera_poe_w: float,
    gateway_poe_w: float,
    sensor_poe_w: float,
    poe_budget_w: float,
    battery_capacity_kwh: float,
    usable_battery_fraction: float,
    backup_runtime_h: float,
    solar_panel_power_w: float,
    peak_sun_hours: float,
    solar_derate_factor: float,
    dc_voltage_v: float,
    feeder_length_km: float,
    feeder_resistance_ohm_km: float,
    allowed_voltage_drop_percent: float,
) -> dict[str, float]:
    """Compute deterministic construction monitoring continuity checks."""
    _require_positive(
        turbidity_sensor_count=turbidity_sensor_count,
        vibration_sensor_count=vibration_sensor_count,
        camera_count=camera_count,
        network_capacity_mbps=network_capacity_mbps,
        camera_poe_w=camera_poe_w,
        gateway_poe_w=gateway_poe_w,
        sensor_poe_w=sensor_poe_w,
        poe_budget_w=poe_budget_w,
        battery_capacity_kwh=battery_capacity_kwh,
        usable_battery_fraction=usable_battery_fraction,
        backup_runtime_h=backup_runtime_h,
        solar_panel_power_w=solar_panel_power_w,
        peak_sun_hours=peak_sun_hours,
        solar_derate_factor=solar_derate_factor,
        dc_voltage_v=dc_voltage_v,
        feeder_length_km=feeder_length_km,
        feeder_resistance_ohm_km=feeder_resistance_ohm_km,
        allowed_voltage_drop_percent=allowed_voltage_drop_percent,
    )
    if (
        min(
            turbidity_sensor_data_mbps,
            vibration_sensor_data_mbps,
            camera_data_mbps,
            weather_station_data_mbps,
            gateway_overhead_mbps,
        )
        < 0
    ):
        msg = "data loads must be >= 0"
        raise ValueError(msg)

    sensor_data_load_mbps = (
        turbidity_sensor_count * turbidity_sensor_data_mbps
        + vibration_sensor_count * vibration_sensor_data_mbps
        + camera_count * camera_data_mbps
        + weather_station_data_mbps
        + gateway_overhead_mbps
    )
    network_headroom_mbps = network_capacity_mbps - sensor_data_load_mbps
    rf_received_power_dbm = rf_tx_power_dbm + rf_tx_gain_db + rf_rx_gain_db - rf_path_loss_db - rf_misc_loss_db
    rf_fade_margin_db = rf_received_power_dbm - rf_receiver_sensitivity_dbm
    poe_load_w = (
        camera_count * camera_poe_w + gateway_poe_w + (turbidity_sensor_count + vibration_sensor_count) * sensor_poe_w
    )
    poe_headroom_w = poe_budget_w - poe_load_w
    battery_required_kwh = poe_load_w * backup_runtime_h / 1000.0
    battery_margin_kwh = battery_capacity_kwh * usable_battery_fraction - battery_required_kwh
    solar_daily_headroom_wh = solar_panel_power_w * peak_sun_hours * solar_derate_factor - poe_load_w * 24.0
    feeder_current_a = poe_load_w / dc_voltage_v
    voltage_drop_percent = feeder_current_a * feeder_length_km * feeder_resistance_ohm_km / dc_voltage_v * 100.0
    voltage_drop_margin_percent = allowed_voltage_drop_percent - voltage_drop_percent

    pass_checks = [
        network_headroom_mbps >= 0.0,
        rf_fade_margin_db >= 0.0,
        poe_headroom_w >= 0.0,
        battery_margin_kwh >= 0.0,
        solar_daily_headroom_wh >= 0.0,
        voltage_drop_margin_percent >= 0.0,
    ]

    return {
        "sensor_data_load_mbps": round(sensor_data_load_mbps, 3),
        "network_headroom_mbps": round(network_headroom_mbps, 3),
        "rf_received_power_dbm": round(rf_received_power_dbm, 3),
        "rf_fade_margin_db": round(rf_fade_margin_db, 3),
        "poe_load_w": round(poe_load_w, 3),
        "poe_headroom_w": round(poe_headroom_w, 3),
        "battery_required_kwh": round(battery_required_kwh, 3),
        "battery_margin_kwh": round(battery_margin_kwh, 3),
        "solar_daily_headroom_wh": round(solar_daily_headroom_wh, 3),
        "voltage_drop_percent": round(voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
