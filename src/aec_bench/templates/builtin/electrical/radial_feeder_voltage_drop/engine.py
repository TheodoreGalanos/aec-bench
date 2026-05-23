# ABOUTME: Computes voltage drop and losses for a single-section radial feeder.
# ABOUTME: Uses feeder R/X, length, load kW/kVAr, and source voltage.

import math


def _validate_inputs(
    feeder_resistance_ohm_per_km: float,
    feeder_reactance_ohm_per_km: float,
    feeder_length_km: float,
    load_real_power_kw: float,
    load_reactive_power_kvar: float,
    source_voltage_v: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if feeder_resistance_ohm_per_km < 0:
        msg = "feeder_resistance_ohm_per_km must be >= 0"
        raise ValueError(msg)
    if feeder_reactance_ohm_per_km < 0:
        msg = "feeder_reactance_ohm_per_km must be >= 0"
        raise ValueError(msg)
    for name, value in {
        "feeder_length_km": feeder_length_km,
        "load_real_power_kw": load_real_power_kw,
        "source_voltage_v": source_voltage_v,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    feeder_resistance_ohm_per_km: float,
    feeder_reactance_ohm_per_km: float,
    feeder_length_km: float,
    load_real_power_kw: float,
    load_reactive_power_kvar: float,
    source_voltage_v: float,
) -> dict[str, float]:
    """Compute radial feeder current, voltage drop, receiving voltage, and loss."""
    _validate_inputs(
        feeder_resistance_ohm_per_km,
        feeder_reactance_ohm_per_km,
        feeder_length_km,
        load_real_power_kw,
        load_reactive_power_kvar,
        source_voltage_v,
    )

    total_resistance_ohm = feeder_resistance_ohm_per_km * feeder_length_km
    total_reactance_ohm = feeder_reactance_ohm_per_km * feeder_length_km
    apparent_power_kva = math.hypot(load_real_power_kw, load_reactive_power_kvar)
    feeder_current_a = apparent_power_kva * 1000.0 / (math.sqrt(3.0) * source_voltage_v)
    power_factor = load_real_power_kw / apparent_power_kva
    reactive_factor = load_reactive_power_kvar / apparent_power_kva
    voltage_drop_v = (
        math.sqrt(3.0)
        * feeder_current_a
        * (total_resistance_ohm * power_factor + total_reactance_ohm * reactive_factor)
    )
    voltage_drop_pct = voltage_drop_v / source_voltage_v * 100.0
    receiving_end_voltage_v = source_voltage_v - voltage_drop_v
    feeder_loss_kw = 3.0 * feeder_current_a**2 * total_resistance_ohm / 1000.0

    return {
        "feeder_current_a": round(feeder_current_a, 2),
        "voltage_drop_v": round(voltage_drop_v, 2),
        "voltage_drop_pct": round(voltage_drop_pct, 2),
        "receiving_end_voltage_v": round(receiving_end_voltage_v, 2),
        "feeder_loss_kw": round(feeder_loss_kw, 2),
    }
