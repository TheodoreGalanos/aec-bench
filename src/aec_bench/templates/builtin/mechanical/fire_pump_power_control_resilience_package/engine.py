# ABOUTME: Computes SSC-19 fire pump fuel, power, control, and resilience metrics.
# ABOUTME: Combines pump horsepower, fuel runtime, battery energy, feeder voltage drop, and fire flow.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    pump_flow_gpm: float,
    pump_head_psi: float,
    pump_efficiency: float,
    motor_efficiency: float,
    selected_motor_hp: float,
    fuel_rate_gal_h: float,
    required_runtime_h: float,
    fuel_tank_gal: float,
    controller_load_kw: float,
    jockey_pump_load_kw: float,
    battery_voltage_v: float,
    battery_capacity_ah: float,
    usable_battery_fraction: float,
    feeder_voltage_v: float,
    feeder_current_a: float,
    feeder_length_m: float,
    conductor_resistance_ohm_km: float,
    max_voltage_drop_percent: float,
    available_fire_flow_gpm: float,
    required_fire_flow_gpm: float,
) -> dict[str, float]:
    """Compute deterministic fire pump resilience metrics."""
    _require_positive(
        pump_flow_gpm=pump_flow_gpm,
        pump_head_psi=pump_head_psi,
        pump_efficiency=pump_efficiency,
        motor_efficiency=motor_efficiency,
        selected_motor_hp=selected_motor_hp,
        fuel_rate_gal_h=fuel_rate_gal_h,
        required_runtime_h=required_runtime_h,
        fuel_tank_gal=fuel_tank_gal,
        controller_load_kw=controller_load_kw,
        jockey_pump_load_kw=jockey_pump_load_kw,
        battery_voltage_v=battery_voltage_v,
        battery_capacity_ah=battery_capacity_ah,
        usable_battery_fraction=usable_battery_fraction,
        feeder_voltage_v=feeder_voltage_v,
        feeder_current_a=feeder_current_a,
        feeder_length_m=feeder_length_m,
        conductor_resistance_ohm_km=conductor_resistance_ohm_km,
        max_voltage_drop_percent=max_voltage_drop_percent,
        available_fire_flow_gpm=available_fire_flow_gpm,
        required_fire_flow_gpm=required_fire_flow_gpm,
    )
    if max(pump_efficiency, motor_efficiency, usable_battery_fraction) > 1.0:
        msg = "efficiency and usable fraction values must be <= 1"
        raise ValueError(msg)

    water_horsepower_hp = pump_flow_gpm * pump_head_psi / 1714.0
    brake_horsepower_hp = water_horsepower_hp / pump_efficiency
    motor_input_hp = brake_horsepower_hp / motor_efficiency
    motor_margin_hp = selected_motor_hp - motor_input_hp
    fuel_required_gal = fuel_rate_gal_h * required_runtime_h
    fuel_margin_gal = fuel_tank_gal - fuel_required_gal
    control_energy_required_kwh = (controller_load_kw + jockey_pump_load_kw) * required_runtime_h
    battery_energy_available_kwh = battery_voltage_v * battery_capacity_ah * usable_battery_fraction / 1000.0
    battery_energy_margin_kwh = battery_energy_available_kwh - control_energy_required_kwh
    feeder_voltage_drop_percent = (
        math.sqrt(3.0)
        * feeder_current_a
        * feeder_length_m
        * conductor_resistance_ohm_km
        / 1000.0
        / feeder_voltage_v
        * 100.0
    )
    voltage_drop_margin_percent = max_voltage_drop_percent - feeder_voltage_drop_percent
    fire_flow_margin_gpm = available_fire_flow_gpm - required_fire_flow_gpm

    pass_checks = [
        motor_margin_hp >= 0.0,
        fuel_margin_gal >= 0.0,
        battery_energy_margin_kwh >= 0.0,
        voltage_drop_margin_percent >= 0.0,
        fire_flow_margin_gpm >= 0.0,
    ]

    return {
        "water_horsepower_hp": round(water_horsepower_hp, 3),
        "brake_horsepower_hp": round(brake_horsepower_hp, 3),
        "motor_input_hp": round(motor_input_hp, 3),
        "motor_margin_hp": round(motor_margin_hp, 3),
        "fuel_required_gal": round(fuel_required_gal, 3),
        "fuel_margin_gal": round(fuel_margin_gal, 3),
        "control_energy_required_kwh": round(control_energy_required_kwh, 3),
        "battery_energy_available_kwh": round(battery_energy_available_kwh, 3),
        "battery_energy_margin_kwh": round(battery_energy_margin_kwh, 3),
        "feeder_voltage_drop_percent": round(feeder_voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "fire_flow_margin_gpm": round(fire_flow_margin_gpm, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
