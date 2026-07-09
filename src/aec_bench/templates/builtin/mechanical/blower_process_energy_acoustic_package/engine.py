# ABOUTME: Computes SSC-06 blower process, energy, and acoustic impact metrics.
# ABOUTME: Combines oxygen demand, blower power, motor margin, and receiver noise checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    influent_flow_mld: float,
    bod_mg_l: float,
    ammonia_mg_l: float,
    bod_oxygen_factor: float,
    nitrification_oxygen_factor: float,
    blower_air_m3_per_kg_o2: float,
    blower_discharge_pressure_kpa: float,
    blower_efficiency: float,
    motor_efficiency: float,
    selected_motor_kw: float,
    source_sound_power_dba: float,
    receiver_distance_m: float,
    enclosure_insertion_loss_db: float,
    receiver_criterion_dba: float,
) -> dict[str, float]:
    """Compute source-bound blower process, motor, and acoustic metrics."""
    _require_positive(
        influent_flow_mld=influent_flow_mld,
        bod_mg_l=bod_mg_l,
        ammonia_mg_l=ammonia_mg_l,
        bod_oxygen_factor=bod_oxygen_factor,
        nitrification_oxygen_factor=nitrification_oxygen_factor,
        blower_air_m3_per_kg_o2=blower_air_m3_per_kg_o2,
        blower_discharge_pressure_kpa=blower_discharge_pressure_kpa,
        blower_efficiency=blower_efficiency,
        motor_efficiency=motor_efficiency,
        selected_motor_kw=selected_motor_kw,
        source_sound_power_dba=source_sound_power_dba,
        receiver_distance_m=receiver_distance_m,
        receiver_criterion_dba=receiver_criterion_dba,
    )
    if blower_efficiency > 1.0 or motor_efficiency > 1.0:
        msg = "efficiency values must be <= 1"
        raise ValueError(msg)
    if enclosure_insertion_loss_db < 0.0:
        msg = "enclosure_insertion_loss_db must be >= 0"
        raise ValueError(msg)

    flow_m3_d = influent_flow_mld * 1000.0
    oxygen_demand_kg_d = (
        flow_m3_d * (bod_mg_l * bod_oxygen_factor + ammonia_mg_l * nitrification_oxygen_factor) / 1000.0
    )
    required_airflow_m3_min = oxygen_demand_kg_d * blower_air_m3_per_kg_o2 / (24.0 * 60.0)
    blower_shaft_power_kw = (
        (required_airflow_m3_min / 60.0) * blower_discharge_pressure_kpa * 1000.0 / blower_efficiency / 1000.0
    )
    motor_input_power_kw = blower_shaft_power_kw / motor_efficiency
    motor_size_margin_kw = selected_motor_kw - motor_input_power_kw
    distance_attenuation_db = 20.0 * math.log10(receiver_distance_m)
    receiver_spl_dba = source_sound_power_dba - distance_attenuation_db - enclosure_insertion_loss_db
    criterion_margin_db = receiver_criterion_dba - receiver_spl_dba
    overall_pass_score = 1.0 if min(motor_size_margin_kw, criterion_margin_db) >= 0.0 else 0.0

    return {
        "oxygen_demand_kg_d": round(oxygen_demand_kg_d, 3),
        "required_airflow_m3_min": round(required_airflow_m3_min, 3),
        "blower_shaft_power_kw": round(blower_shaft_power_kw, 3),
        "motor_input_power_kw": round(motor_input_power_kw, 3),
        "motor_size_margin_kw": round(motor_size_margin_kw, 3),
        "distance_attenuation_db": round(distance_attenuation_db, 3),
        "receiver_spl_dba": round(receiver_spl_dba, 3),
        "criterion_margin_db": round(criterion_margin_db, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
