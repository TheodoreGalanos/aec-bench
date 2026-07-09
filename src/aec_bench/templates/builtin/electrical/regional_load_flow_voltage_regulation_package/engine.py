# ABOUTME: Computes SSC-05 regional load-flow and voltage-regulation metrics.
# ABOUTME: Combines load-growth, transformer loading, feeder voltage-drop, tap, PFC, and loss checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _require_fraction(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        msg = f"{name} must be between 0 and 1"
        raise ValueError(msg)


def compute(
    base_load_kw: float,
    growth_fraction: float,
    transformer_kva: float,
    source_power_factor: float,
    target_power_factor: float,
    feeder_voltage_kv: float,
    feeder_r_ohm_per_km: float,
    feeder_x_ohm_per_km: float,
    feeder_length_km: float,
    regulator_boost_pu: float,
    minimum_voltage_pu: float,
    feeder_loss_percent: float,
) -> dict[str, float]:
    """Compute source-bound regional load-flow, voltage-regulation, and PFC metrics."""
    _require_positive(
        base_load_kw=base_load_kw,
        transformer_kva=transformer_kva,
        source_power_factor=source_power_factor,
        target_power_factor=target_power_factor,
        feeder_voltage_kv=feeder_voltage_kv,
        feeder_r_ohm_per_km=feeder_r_ohm_per_km,
        feeder_x_ohm_per_km=feeder_x_ohm_per_km,
        feeder_length_km=feeder_length_km,
        minimum_voltage_pu=minimum_voltage_pu,
        feeder_loss_percent=feeder_loss_percent,
    )
    if growth_fraction < 0.0:
        msg = "growth_fraction must be >= 0"
        raise ValueError(msg)
    for name, value in {
        "source_power_factor": source_power_factor,
        "target_power_factor": target_power_factor,
        "minimum_voltage_pu": minimum_voltage_pu,
    }.items():
        _require_fraction(name, value)
    if target_power_factor <= source_power_factor:
        msg = "target_power_factor must be greater than source_power_factor"
        raise ValueError(msg)

    peak_load_kw = base_load_kw * (1.0 + growth_fraction)
    transformer_loading_percent = peak_load_kw / source_power_factor / transformer_kva * 100.0
    transformer_margin_percent = 100.0 - transformer_loading_percent
    feeder_current_a = peak_load_kw * 1000.0 / (math.sqrt(3.0) * feeder_voltage_kv * 1000.0 * source_power_factor)
    reactive_factor = math.sin(math.acos(source_power_factor))
    voltage_drop_v = (
        math.sqrt(3.0)
        * feeder_current_a
        * (feeder_r_ohm_per_km * source_power_factor + feeder_x_ohm_per_km * reactive_factor)
        * feeder_length_km
    )
    voltage_drop_percent = voltage_drop_v / (feeder_voltage_kv * 1000.0) * 100.0
    regulated_voltage_pu = 1.0 - voltage_drop_percent / 100.0 + regulator_boost_pu
    minimum_voltage_margin_pu = regulated_voltage_pu - minimum_voltage_pu
    required_pfc_kvar = peak_load_kw * (
        math.tan(math.acos(source_power_factor)) - math.tan(math.acos(target_power_factor))
    )
    feeder_loss_kw = peak_load_kw * feeder_loss_percent / 100.0

    overall_pass_score = (
        1.0 if min(transformer_margin_percent, minimum_voltage_margin_pu, required_pfc_kvar) >= 0.0 else 0.0
    )

    return {
        "peak_load_kw": round(peak_load_kw, 3),
        "transformer_loading_percent": round(transformer_loading_percent, 3),
        "transformer_margin_percent": round(transformer_margin_percent, 3),
        "feeder_current_a": round(feeder_current_a, 3),
        "voltage_drop_percent": round(voltage_drop_percent, 3),
        "regulated_voltage_pu": round(regulated_voltage_pu, 3),
        "minimum_voltage_margin_pu": round(minimum_voltage_margin_pu, 3),
        "required_pfc_kvar": round(required_pfc_kvar, 3),
        "feeder_loss_kw": round(feeder_loss_kw, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
