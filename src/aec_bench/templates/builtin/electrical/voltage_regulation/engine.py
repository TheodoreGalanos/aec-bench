# ABOUTME: Computes approximate three-phase line voltage regulation and loss.
# ABOUTME: Uses R, X, line length, real/reactive load, and sending-end voltage.

import math


def _validate_inputs(
    line_resistance_ohm_per_km: float,
    line_reactance_ohm_per_km: float,
    line_length_km: float,
    load_real_power_mw: float,
    load_reactive_power_mvar: float,
    sending_voltage_kv: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if line_resistance_ohm_per_km < 0:
        msg = "line_resistance_ohm_per_km must be >= 0"
        raise ValueError(msg)
    if line_reactance_ohm_per_km < 0:
        msg = "line_reactance_ohm_per_km must be >= 0"
        raise ValueError(msg)
    for name, value in {
        "line_length_km": line_length_km,
        "load_real_power_mw": load_real_power_mw,
        "sending_voltage_kv": sending_voltage_kv,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    line_resistance_ohm_per_km: float,
    line_reactance_ohm_per_km: float,
    line_length_km: float,
    load_real_power_mw: float,
    load_reactive_power_mvar: float,
    sending_voltage_kv: float,
) -> dict[str, float]:
    """Compute approximate voltage drop, regulation, receiving voltage, and loss."""
    _validate_inputs(
        line_resistance_ohm_per_km,
        line_reactance_ohm_per_km,
        line_length_km,
        load_real_power_mw,
        load_reactive_power_mvar,
        sending_voltage_kv,
    )

    total_resistance_ohm = line_resistance_ohm_per_km * line_length_km
    total_reactance_ohm = line_reactance_ohm_per_km * line_length_km
    voltage_drop_kv = (
        total_resistance_ohm * load_real_power_mw + total_reactance_ohm * load_reactive_power_mvar
    ) / sending_voltage_kv
    voltage_regulation_pct = voltage_drop_kv / sending_voltage_kv * 100.0
    receiving_end_voltage_kv = sending_voltage_kv - voltage_drop_kv
    load_apparent_power_mva = math.hypot(load_real_power_mw, load_reactive_power_mvar)
    line_current_a = load_apparent_power_mva * 1_000_000.0 / (math.sqrt(3.0) * sending_voltage_kv * 1000.0)
    power_loss_mw = 3.0 * line_current_a**2 * total_resistance_ohm / 1_000_000.0

    return {
        "voltage_drop_kv": round(voltage_drop_kv, 2),
        "voltage_regulation_pct": round(voltage_regulation_pct, 2),
        "receiving_end_voltage_kv": round(receiving_end_voltage_kv, 2),
        "power_loss_mw": round(power_loss_mw, 2),
    }
