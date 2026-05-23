# ABOUTME: Computes backup battery capacity and UPS apparent power rating.
# ABOUTME: Applies autonomy, voltage, depth of discharge, derating, and efficiency.

import math


def _validate_inputs(
    critical_load_w: float,
    required_autonomy_h: float,
    system_voltage_v: float,
    depth_of_discharge_pct: float,
    temperature_derating_factor: float,
    inverter_efficiency_pct: float,
    load_power_factor: float,
    battery_block_voltage_v: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "critical_load_w": critical_load_w,
        "required_autonomy_h": required_autonomy_h,
        "system_voltage_v": system_voltage_v,
        "battery_block_voltage_v": battery_block_voltage_v,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)
    if depth_of_discharge_pct <= 0 or depth_of_discharge_pct > 100:
        msg = "depth_of_discharge_pct must be > 0 and <= 100"
        raise ValueError(msg)
    if temperature_derating_factor <= 0 or temperature_derating_factor > 1:
        msg = "temperature_derating_factor must be > 0 and <= 1"
        raise ValueError(msg)
    if inverter_efficiency_pct <= 0 or inverter_efficiency_pct > 100:
        msg = "inverter_efficiency_pct must be > 0 and <= 100"
        raise ValueError(msg)
    if load_power_factor <= 0 or load_power_factor > 1:
        msg = "load_power_factor must be > 0 and <= 1"
        raise ValueError(msg)


def compute(
    critical_load_w: float,
    required_autonomy_h: float,
    system_voltage_v: float,
    depth_of_discharge_pct: float,
    temperature_derating_factor: float,
    inverter_efficiency_pct: float,
    load_power_factor: float,
    battery_block_voltage_v: float,
) -> dict[str, float]:
    """Compute backup battery energy, capacity, UPS rating, and block count."""
    _validate_inputs(
        critical_load_w,
        required_autonomy_h,
        system_voltage_v,
        depth_of_discharge_pct,
        temperature_derating_factor,
        inverter_efficiency_pct,
        load_power_factor,
        battery_block_voltage_v,
    )

    required_energy_kwh = critical_load_w * required_autonomy_h / 1000.0
    usable_fraction = depth_of_discharge_pct / 100.0 * temperature_derating_factor * inverter_efficiency_pct / 100.0
    required_battery_capacity_ah = critical_load_w * required_autonomy_h / (system_voltage_v * usable_fraction)
    ups_rating_va = critical_load_w / load_power_factor
    battery_block_count = math.ceil(system_voltage_v / battery_block_voltage_v)

    return {
        "required_energy_kwh": round(required_energy_kwh, 2),
        "required_battery_capacity_ah": round(required_battery_capacity_ah, 2),
        "ups_rating_va": round(ups_rating_va, 2),
        "battery_block_count": round(float(battery_block_count), 2),
    }
