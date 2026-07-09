# ABOUTME: Computes SSC-02 level-crossing warning and backup-power package metrics.
# ABOUTME: Combines strike-in distance, signal loads, battery autonomy, DC drop, and fiber loss.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _require_nonnegative(**values: float) -> None:
    """Raise ValueError when any supplied value is negative."""
    for name, value in values.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)


def _require_percent(name: str, value: float) -> None:
    """Raise ValueError unless a percent is in the inclusive 0..100 range."""
    if value <= 0.0 or value > 100.0:
        msg = f"{name} must be > 0 and <= 100"
        raise ValueError(msg)


def compute(
    maximum_train_speed_kmh: float,
    minimum_warning_time_s: float,
    road_user_clearance_time_s: float,
    gate_lowering_time_s: float,
    system_delay_s: float,
    gate_start_delay_s: float,
    required_gate_horizontal_before_arrival_s: float,
    controller_load_w: float,
    flashing_light_load_w: float,
    flashing_light_count: float,
    gate_mechanism_load_w: float,
    gate_mechanism_count: float,
    comms_switch_load_w: float,
    track_circuit_load_w: float,
    event_recorder_load_w: float,
    load_future_allowance_pct: float,
    required_autonomy_h: float,
    dc_system_voltage_v: float,
    depth_of_discharge_pct: float,
    temperature_derating_factor: float,
    inverter_efficiency_pct: float,
    installed_battery_capacity_ah: float,
    battery_block_voltage_v: float,
    load_power_factor: float,
    selected_ups_rating_va: float,
    feeder_length_m: float,
    feeder_resistance_milliohm_per_m: float,
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
) -> dict[str, float]:
    """Compute source-bound level-crossing warning, backup-power, and comms metrics."""
    _require_positive(
        maximum_train_speed_kmh=maximum_train_speed_kmh,
        controller_load_w=controller_load_w,
        flashing_light_load_w=flashing_light_load_w,
        flashing_light_count=flashing_light_count,
        gate_mechanism_load_w=gate_mechanism_load_w,
        gate_mechanism_count=gate_mechanism_count,
        required_autonomy_h=required_autonomy_h,
        dc_system_voltage_v=dc_system_voltage_v,
        temperature_derating_factor=temperature_derating_factor,
        installed_battery_capacity_ah=installed_battery_capacity_ah,
        battery_block_voltage_v=battery_block_voltage_v,
        load_power_factor=load_power_factor,
        selected_ups_rating_va=selected_ups_rating_va,
        feeder_length_m=feeder_length_m,
        feeder_resistance_milliohm_per_m=feeder_resistance_milliohm_per_m,
        max_voltage_drop_percent=max_voltage_drop_percent,
        fiber_length_km=fiber_length_km,
        fiber_attenuation_db_per_km=fiber_attenuation_db_per_km,
        required_fiber_margin_db=required_fiber_margin_db,
    )
    _require_nonnegative(
        minimum_warning_time_s=minimum_warning_time_s,
        road_user_clearance_time_s=road_user_clearance_time_s,
        gate_lowering_time_s=gate_lowering_time_s,
        system_delay_s=system_delay_s,
        gate_start_delay_s=gate_start_delay_s,
        required_gate_horizontal_before_arrival_s=required_gate_horizontal_before_arrival_s,
        comms_switch_load_w=comms_switch_load_w,
        track_circuit_load_w=track_circuit_load_w,
        event_recorder_load_w=event_recorder_load_w,
        load_future_allowance_pct=load_future_allowance_pct,
        fiber_connector_count=fiber_connector_count,
        connector_loss_db=connector_loss_db,
        fiber_splice_count=fiber_splice_count,
        splice_loss_db=splice_loss_db,
        patch_panel_allowance_db=patch_panel_allowance_db,
    )
    _require_percent("depth_of_discharge_pct", depth_of_discharge_pct)
    _require_percent("inverter_efficiency_pct", inverter_efficiency_pct)
    if temperature_derating_factor > 1.0:
        msg = "temperature_derating_factor must be <= 1"
        raise ValueError(msg)
    if load_power_factor > 1.0:
        msg = "load_power_factor must be <= 1"
        raise ValueError(msg)

    maximum_train_speed_m_s = maximum_train_speed_kmh / 3.6
    total_warning_time_s = minimum_warning_time_s + road_user_clearance_time_s + gate_lowering_time_s + system_delay_s
    strike_in_distance_m = maximum_train_speed_m_s * total_warning_time_s
    minimum_warning_margin_s = total_warning_time_s - minimum_warning_time_s
    gate_horizontal_margin_s = (
        total_warning_time_s - gate_start_delay_s - gate_lowering_time_s - required_gate_horizontal_before_arrival_s
    )

    connected_signal_load_w = (
        controller_load_w
        + flashing_light_load_w * flashing_light_count
        + gate_mechanism_load_w * gate_mechanism_count
        + comms_switch_load_w
        + track_circuit_load_w
        + event_recorder_load_w
    )
    design_signal_load_w = connected_signal_load_w * (1.0 + load_future_allowance_pct / 100.0)

    required_energy_kwh = design_signal_load_w * required_autonomy_h / 1000.0
    usable_fraction = depth_of_discharge_pct / 100.0 * temperature_derating_factor * inverter_efficiency_pct / 100.0
    required_battery_capacity_ah = design_signal_load_w * required_autonomy_h / (dc_system_voltage_v * usable_fraction)
    battery_capacity_margin_ah = installed_battery_capacity_ah - required_battery_capacity_ah
    required_ups_rating_va = design_signal_load_w / load_power_factor
    ups_rating_margin_va = selected_ups_rating_va - required_ups_rating_va
    battery_block_count = math.ceil(dc_system_voltage_v / battery_block_voltage_v)

    dc_feeder_current_a = design_signal_load_w / dc_system_voltage_v
    dc_feeder_voltage_drop_v = 2.0 * dc_feeder_current_a * feeder_length_m * feeder_resistance_milliohm_per_m / 1000.0
    dc_feeder_voltage_drop_percent = dc_feeder_voltage_drop_v / dc_system_voltage_v * 100.0
    dc_voltage_drop_margin_percent = max_voltage_drop_percent - dc_feeder_voltage_drop_percent

    fiber_total_loss_db = (
        fiber_length_km * fiber_attenuation_db_per_km
        + fiber_connector_count * connector_loss_db
        + fiber_splice_count * splice_loss_db
        + patch_panel_allowance_db
    )
    fiber_receive_power_dbm = optical_tx_power_dbm - fiber_total_loss_db
    fiber_link_margin_db = fiber_receive_power_dbm - receiver_sensitivity_dbm
    fiber_excess_margin_db = fiber_link_margin_db - required_fiber_margin_db

    overall_pass_score = (
        1.0
        if min(
            minimum_warning_margin_s,
            gate_horizontal_margin_s,
            battery_capacity_margin_ah,
            ups_rating_margin_va,
            dc_voltage_drop_margin_percent,
            fiber_excess_margin_db,
        )
        >= 0.0
        else 0.0
    )

    return {
        "maximum_train_speed_m_s": round(maximum_train_speed_m_s, 3),
        "total_warning_time_s": round(total_warning_time_s, 3),
        "strike_in_distance_m": round(strike_in_distance_m, 3),
        "minimum_warning_margin_s": round(minimum_warning_margin_s, 3),
        "gate_horizontal_margin_s": round(gate_horizontal_margin_s, 3),
        "connected_signal_load_w": round(connected_signal_load_w, 3),
        "design_signal_load_w": round(design_signal_load_w, 3),
        "required_energy_kwh": round(required_energy_kwh, 3),
        "required_battery_capacity_ah": round(required_battery_capacity_ah, 3),
        "battery_capacity_margin_ah": round(battery_capacity_margin_ah, 3),
        "required_ups_rating_va": round(required_ups_rating_va, 3),
        "ups_rating_margin_va": round(ups_rating_margin_va, 3),
        "battery_block_count": round(float(battery_block_count), 3),
        "dc_feeder_current_a": round(dc_feeder_current_a, 3),
        "dc_feeder_voltage_drop_v": round(dc_feeder_voltage_drop_v, 3),
        "dc_feeder_voltage_drop_percent": round(dc_feeder_voltage_drop_percent, 3),
        "dc_voltage_drop_margin_percent": round(dc_voltage_drop_margin_percent, 3),
        "fiber_total_loss_db": round(fiber_total_loss_db, 3),
        "fiber_receive_power_dbm": round(fiber_receive_power_dbm, 3),
        "fiber_link_margin_db": round(fiber_link_margin_db, 3),
        "fiber_excess_margin_db": round(fiber_excess_margin_db, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
