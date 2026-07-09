# ABOUTME: Computes SSC-16 dewatering, settlement, and temporary power metrics.
# ABOUTME: Combines drawdown flow, pump power, settlement, backup battery, and feeder checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    excavation_area_m2: float,
    drawdown_m: float,
    hydraulic_conductivity_m_day: float,
    dewatering_influence_factor: float,
    pump_head_m: float,
    pump_efficiency: float,
    motor_efficiency: float,
    selected_generator_kw: float,
    compressible_layer_thickness_m: float,
    consolidation_strain: float,
    allowable_settlement_mm: float,
    telemetry_load_kw: float,
    backup_runtime_h: float,
    provided_battery_kwh: float,
    feeder_voltage_v: float,
    feeder_power_factor: float,
    feeder_length_km: float,
    feeder_resistance_ohm_km: float,
    allowed_voltage_drop_percent: float,
) -> dict[str, float]:
    """Compute deterministic dewatering and temporary power checks."""
    _require_positive(
        excavation_area_m2=excavation_area_m2,
        drawdown_m=drawdown_m,
        hydraulic_conductivity_m_day=hydraulic_conductivity_m_day,
        dewatering_influence_factor=dewatering_influence_factor,
        pump_head_m=pump_head_m,
        pump_efficiency=pump_efficiency,
        motor_efficiency=motor_efficiency,
        selected_generator_kw=selected_generator_kw,
        compressible_layer_thickness_m=compressible_layer_thickness_m,
        consolidation_strain=consolidation_strain,
        allowable_settlement_mm=allowable_settlement_mm,
        backup_runtime_h=backup_runtime_h,
        provided_battery_kwh=provided_battery_kwh,
        feeder_voltage_v=feeder_voltage_v,
        feeder_power_factor=feeder_power_factor,
        feeder_length_km=feeder_length_km,
        feeder_resistance_ohm_km=feeder_resistance_ohm_km,
        allowed_voltage_drop_percent=allowed_voltage_drop_percent,
    )
    if telemetry_load_kw < 0:
        msg = "telemetry_load_kw must be >= 0"
        raise ValueError(msg)

    dewatering_flow_l_s = excavation_area_m2 * drawdown_m * hydraulic_conductivity_m_day * dewatering_influence_factor
    pump_hydraulic_power_kw = 1000.0 * 9.81 * (dewatering_flow_l_s / 1000.0) * pump_head_m / 1000.0
    pump_input_power_kw = pump_hydraulic_power_kw / (pump_efficiency * motor_efficiency)
    generator_headroom_kw = selected_generator_kw - pump_input_power_kw
    predicted_settlement_mm = compressible_layer_thickness_m * consolidation_strain * 1000.0
    settlement_margin_mm = allowable_settlement_mm - predicted_settlement_mm
    battery_required_kwh = (pump_input_power_kw + telemetry_load_kw) * backup_runtime_h
    battery_margin_kwh = provided_battery_kwh - battery_required_kwh
    feeder_current_a = pump_input_power_kw * 1000.0 / (feeder_voltage_v * feeder_power_factor)
    voltage_drop_v = 2.0 * feeder_current_a * feeder_length_km * feeder_resistance_ohm_km
    voltage_drop_percent = voltage_drop_v / feeder_voltage_v * 100.0
    voltage_drop_margin_percent = allowed_voltage_drop_percent - voltage_drop_percent

    pass_checks = [
        generator_headroom_kw >= 0.0,
        settlement_margin_mm >= 0.0,
        battery_margin_kwh >= 0.0,
        voltage_drop_margin_percent >= 0.0,
    ]

    return {
        "dewatering_flow_l_s": round(dewatering_flow_l_s, 3),
        "pump_hydraulic_power_kw": round(pump_hydraulic_power_kw, 3),
        "pump_input_power_kw": round(pump_input_power_kw, 3),
        "generator_headroom_kw": round(generator_headroom_kw, 3),
        "predicted_settlement_mm": round(predicted_settlement_mm, 3),
        "settlement_margin_mm": round(settlement_margin_mm, 3),
        "battery_required_kwh": round(battery_required_kwh, 3),
        "battery_margin_kwh": round(battery_margin_kwh, 3),
        "feeder_current_a": round(feeder_current_a, 3),
        "voltage_drop_percent": round(voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
