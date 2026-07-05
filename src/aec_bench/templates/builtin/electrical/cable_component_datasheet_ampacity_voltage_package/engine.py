# ABOUTME: Computes SSC-15 cable datasheet ampacity and voltage-drop metrics.
# ABOUTME: Combines derating, AC resistance, identity, and temperature checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    design_current_a: float,
    datasheet_ampacity_a: float,
    ambient_derating_factor: float,
    grouping_derating_factor: float,
    installation_derating_factor: float,
    base_resistance_ohm_km: float,
    temperature_coefficient: float,
    operating_temperature_c: float,
    reference_temperature_c: float,
    skin_effect_factor: float,
    reactance_ohm_km: float,
    power_factor: float,
    circuit_length_m: float,
    voltage_v: float,
    max_voltage_drop_percent: float,
    temperature_rating_c: float,
    matching_identity_fields: float,
    required_identity_fields: float,
) -> dict[str, float]:
    _require_positive(
        design_current_a=design_current_a,
        datasheet_ampacity_a=datasheet_ampacity_a,
        ambient_derating_factor=ambient_derating_factor,
        grouping_derating_factor=grouping_derating_factor,
        installation_derating_factor=installation_derating_factor,
        base_resistance_ohm_km=base_resistance_ohm_km,
        skin_effect_factor=skin_effect_factor,
        circuit_length_m=circuit_length_m,
        voltage_v=voltage_v,
        max_voltage_drop_percent=max_voltage_drop_percent,
        required_identity_fields=required_identity_fields,
    )
    if not 0.0 <= power_factor <= 1.0:
        msg = "power_factor must be between 0 and 1"
        raise ValueError(msg)

    derated_ampacity_a = (
        datasheet_ampacity_a * ambient_derating_factor * grouping_derating_factor * installation_derating_factor
    )
    ampacity_margin_a = derated_ampacity_a - design_current_a
    ampacity_utilization = design_current_a / derated_ampacity_a
    ac_resistance_ohm_km = (
        base_resistance_ohm_km
        * (1.0 + temperature_coefficient * (operating_temperature_c - reference_temperature_c))
        * skin_effect_factor
    )
    sin_phi = math.sqrt(1.0 - power_factor**2)
    voltage_drop_percent = (
        math.sqrt(3.0)
        * design_current_a
        * (circuit_length_m / 1000.0)
        * (ac_resistance_ohm_km * power_factor + reactance_ohm_km * sin_phi)
        / voltage_v
        * 100.0
    )
    voltage_drop_margin_percent = max_voltage_drop_percent - voltage_drop_percent
    temperature_rating_margin_c = temperature_rating_c - operating_temperature_c
    product_identity_match_fraction = matching_identity_fields / required_identity_fields

    overall_pass_score = (
        1.0
        if (
            ampacity_margin_a >= 0.0
            and voltage_drop_margin_percent >= 0.0
            and temperature_rating_margin_c >= 0.0
            and product_identity_match_fraction >= 1.0
        )
        else 0.0
    )

    return {
        "derated_ampacity_a": round(derated_ampacity_a, 3),
        "ampacity_margin_a": round(ampacity_margin_a, 3),
        "ampacity_utilization": round(ampacity_utilization, 3),
        "ac_resistance_ohm_km": round(ac_resistance_ohm_km, 3),
        "voltage_drop_percent": round(voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "temperature_rating_margin_c": round(temperature_rating_margin_c, 3),
        "product_identity_match_fraction": round(product_identity_match_fraction, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
