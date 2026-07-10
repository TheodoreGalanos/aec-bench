# ABOUTME: Computes SSC-02 wayside cabinet load, backup battery, feeder, UPS, and fiber metrics.
# ABOUTME: Combines critical load, autonomy, DC voltage drop, optical link budget, and UPS sizing.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _require_nonnegative(**values: float) -> None:
    for name, value in values.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)


def compute(
    signal_processor_w: float,
    axle_counter_w: float,
    comms_switch_w: float,
    radio_w: float,
    point_machine_heater_w: float,
    spare_allowance_pct: float,
    autonomy_h: float,
    dc_voltage_v: float,
    usable_battery_fraction: float,
    installed_battery_ah: float,
    feeder_length_m: float,
    conductor_resistance_milliohm_per_m: float,
    max_voltage_drop_percent: float,
    fiber_length_km: float,
    fiber_attenuation_db_per_km: float,
    fiber_connector_count: float,
    connector_loss_db: float,
    fiber_splice_count: float,
    splice_loss_db: float,
    patch_panel_allowance_db: float,
    optical_tx_power_dbm: float,
    receiver_sensitivity_dbm: float,
    required_fiber_margin_db: float,
    selected_ups_rating_va: float,
    load_power_factor: float,
) -> dict[str, float]:
    """Compute source-bound wayside cabinet load, backup, and communications metrics."""
    _require_positive(
        signal_processor_w=signal_processor_w,
        axle_counter_w=axle_counter_w,
        comms_switch_w=comms_switch_w,
        radio_w=radio_w,
        point_machine_heater_w=point_machine_heater_w,
        autonomy_h=autonomy_h,
        dc_voltage_v=dc_voltage_v,
        usable_battery_fraction=usable_battery_fraction,
        installed_battery_ah=installed_battery_ah,
        feeder_length_m=feeder_length_m,
        conductor_resistance_milliohm_per_m=conductor_resistance_milliohm_per_m,
        max_voltage_drop_percent=max_voltage_drop_percent,
        fiber_length_km=fiber_length_km,
        fiber_attenuation_db_per_km=fiber_attenuation_db_per_km,
        required_fiber_margin_db=required_fiber_margin_db,
        selected_ups_rating_va=selected_ups_rating_va,
        load_power_factor=load_power_factor,
    )
    _require_nonnegative(
        spare_allowance_pct=spare_allowance_pct,
        fiber_connector_count=fiber_connector_count,
        connector_loss_db=connector_loss_db,
        fiber_splice_count=fiber_splice_count,
        splice_loss_db=splice_loss_db,
        patch_panel_allowance_db=patch_panel_allowance_db,
    )
    if usable_battery_fraction > 1.0:
        msg = "usable_battery_fraction must be <= 1"
        raise ValueError(msg)
    if load_power_factor > 1.0:
        msg = "load_power_factor must be <= 1"
        raise ValueError(msg)

    connected_load_w = signal_processor_w + axle_counter_w + comms_switch_w + radio_w + point_machine_heater_w
    design_load_w = connected_load_w * (1.0 + spare_allowance_pct / 100.0)
    required_energy_kwh = design_load_w * autonomy_h / 1000.0
    required_battery_capacity_ah = design_load_w * autonomy_h / (dc_voltage_v * usable_battery_fraction)
    battery_capacity_margin_ah = installed_battery_ah - required_battery_capacity_ah
    feeder_current_a = design_load_w / dc_voltage_v
    feeder_voltage_drop_v = 2.0 * feeder_current_a * feeder_length_m * conductor_resistance_milliohm_per_m / 1000.0
    feeder_voltage_drop_percent = feeder_voltage_drop_v / dc_voltage_v * 100.0
    voltage_drop_margin_percent = max_voltage_drop_percent - feeder_voltage_drop_percent
    fiber_total_loss_db = (
        fiber_length_km * fiber_attenuation_db_per_km
        + fiber_connector_count * connector_loss_db
        + fiber_splice_count * splice_loss_db
        + patch_panel_allowance_db
    )
    fiber_receive_power_dbm = optical_tx_power_dbm - fiber_total_loss_db
    fiber_link_margin_db = fiber_receive_power_dbm - receiver_sensitivity_dbm
    fiber_excess_margin_db = fiber_link_margin_db - required_fiber_margin_db
    required_ups_rating_va = design_load_w / load_power_factor
    ups_rating_margin_va = selected_ups_rating_va - required_ups_rating_va
    overall_pass_score = (
        1.0
        if min(battery_capacity_margin_ah, voltage_drop_margin_percent, fiber_excess_margin_db, ups_rating_margin_va)
        >= 0.0
        else 0.0
    )

    return {
        "connected_load_w": round(connected_load_w, 3),
        "design_load_w": round(design_load_w, 3),
        "required_energy_kwh": round(required_energy_kwh, 3),
        "required_battery_capacity_ah": round(required_battery_capacity_ah, 3),
        "battery_capacity_margin_ah": round(battery_capacity_margin_ah, 3),
        "feeder_current_a": round(feeder_current_a, 3),
        "feeder_voltage_drop_v": round(feeder_voltage_drop_v, 3),
        "feeder_voltage_drop_percent": round(feeder_voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "fiber_total_loss_db": round(fiber_total_loss_db, 3),
        "fiber_receive_power_dbm": round(fiber_receive_power_dbm, 3),
        "fiber_link_margin_db": round(fiber_link_margin_db, 3),
        "fiber_excess_margin_db": round(fiber_excess_margin_db, 3),
        "required_ups_rating_va": round(required_ups_rating_va, 3),
        "ups_rating_margin_va": round(ups_rating_margin_va, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
