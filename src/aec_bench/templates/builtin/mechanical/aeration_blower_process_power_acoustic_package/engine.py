# ABOUTME: Computes SSC-10 aeration blower process, power, and acoustic metrics.
# ABOUTME: Combines oxygen demand, airflow, blower power, motor margin, and receiver sound checks.

from __future__ import annotations

import math


def compute(
    flow_rate_m3_d: float,
    influent_bod_mg_l: float,
    effluent_bod_mg_l: float,
    influent_tkn_mg_l: float,
    effluent_tkn_mg_l: float,
    sludge_production_kg_d: float,
    denitrified_nitrogen_mg_l: float,
    field_transfer_efficiency: float,
    air_oxygen_mass_fraction: float,
    air_density_kg_m3: float,
    blower_capacity_m3_min: float,
    blower_discharge_pressure_kpa: float,
    blower_efficiency: float,
    motor_efficiency: float,
    selected_motor_kw: float,
    blower_sound_level_dba: float,
    header_sound_level_dba: float,
    enclosure_sound_level_dba: float,
    receiver_distance_m: float,
    receiver_criterion_dba: float,
) -> dict[str, float]:
    """Compute source-bound SSC-10 aeration blower and acoustic metrics."""
    bod_removed_kg_d = flow_rate_m3_d * (influent_bod_mg_l - effluent_bod_mg_l) / 1000.0
    nitrogen_removed_kg_d = flow_rate_m3_d * (influent_tkn_mg_l - effluent_tkn_mg_l) / 1000.0
    denitrified_nitrogen_kg_d = flow_rate_m3_d * denitrified_nitrogen_mg_l / 1000.0
    oxygen_demand_kg_d = max(
        bod_removed_kg_d
        - 1.42 * sludge_production_kg_d
        + 4.57 * nitrogen_removed_kg_d
        - 2.86 * denitrified_nitrogen_kg_d,
        0.0,
    )

    oxygen_transfer_kg_m3 = air_oxygen_mass_fraction * air_density_kg_m3 * field_transfer_efficiency
    required_airflow_m3_min = oxygen_demand_kg_d / 24.0 / oxygen_transfer_kg_m3 / 60.0
    blower_oxygen_capacity_margin_kg_d = (
        blower_capacity_m3_min * 60.0 * 24.0 * oxygen_transfer_kg_m3 - oxygen_demand_kg_d
    )
    blower_shaft_power_kw = (required_airflow_m3_min / 60.0) * blower_discharge_pressure_kpa / blower_efficiency
    blower_input_power_kw = blower_shaft_power_kw / motor_efficiency
    motor_margin_kw = selected_motor_kw - blower_input_power_kw

    combined_source_spl_dba = 10.0 * math.log10(
        sum(
            10.0 ** (source_level / 10.0)
            for source_level in [blower_sound_level_dba, header_sound_level_dba, enclosure_sound_level_dba]
        ),
    )
    receiver_spl_dba = combined_source_spl_dba - 20.0 * math.log10(receiver_distance_m)
    acoustic_margin_db = receiver_criterion_dba - receiver_spl_dba
    overall_pass_score = (
        1.0 if min(blower_oxygen_capacity_margin_kg_d, motor_margin_kw, acoustic_margin_db) >= 0.0 else 0.0
    )

    return {
        "bod_removed_kg_d": round(bod_removed_kg_d, 3),
        "nitrogen_removed_kg_d": round(nitrogen_removed_kg_d, 3),
        "oxygen_demand_kg_d": round(oxygen_demand_kg_d, 3),
        "required_airflow_m3_min": round(required_airflow_m3_min, 3),
        "blower_oxygen_capacity_margin_kg_d": round(blower_oxygen_capacity_margin_kg_d, 3),
        "blower_input_power_kw": round(blower_input_power_kw, 3),
        "motor_margin_kw": round(motor_margin_kw, 3),
        "combined_source_spl_dba": round(combined_source_spl_dba, 3),
        "receiver_spl_dba": round(receiver_spl_dba, 3),
        "acoustic_margin_db": round(acoustic_margin_db, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
