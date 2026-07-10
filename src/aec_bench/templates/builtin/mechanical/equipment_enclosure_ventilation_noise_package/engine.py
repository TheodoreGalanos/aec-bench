# ABOUTME: Computes SSC-12 equipment enclosure ventilation and receiver noise metrics.
# ABOUTME: Combines air-change, enclosure attenuation, thermal, and receiver criteria.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _log_sum(levels_db: tuple[float, ...]) -> float:
    return 10.0 * math.log10(sum(10.0 ** (level / 10.0) for level in levels_db))


def compute(
    enclosure_volume_m3: float,
    ventilation_flow_m3_h: float,
    minimum_air_changes_per_h: float,
    internal_equipment_level_dba: float,
    wall_transmission_loss_db: float,
    louvre_insertion_loss_db: float,
    receiver_distance_m: float,
    background_level_dba: float,
    receiver_noise_criterion_dba: float,
    ventilation_heat_capacity_kw: float,
    equipment_heat_load_kw: float,
) -> dict[str, float]:
    """Compute deterministic equipment enclosure ventilation and noise checks."""
    _require_positive(
        enclosure_volume_m3=enclosure_volume_m3,
        ventilation_flow_m3_h=ventilation_flow_m3_h,
        minimum_air_changes_per_h=minimum_air_changes_per_h,
        internal_equipment_level_dba=internal_equipment_level_dba,
        receiver_distance_m=receiver_distance_m,
        background_level_dba=background_level_dba,
        receiver_noise_criterion_dba=receiver_noise_criterion_dba,
        ventilation_heat_capacity_kw=ventilation_heat_capacity_kw,
        equipment_heat_load_kw=equipment_heat_load_kw,
    )
    if min(wall_transmission_loss_db, louvre_insertion_loss_db) < 0:
        msg = "attenuation values must be >= 0"
        raise ValueError(msg)

    air_changes_per_h = ventilation_flow_m3_h / enclosure_volume_m3
    ventilation_margin_ach = air_changes_per_h - minimum_air_changes_per_h
    treatment_insertion_loss_db = wall_transmission_loss_db + louvre_insertion_loss_db
    receiver_enclosure_noise_dba = (
        internal_equipment_level_dba - treatment_insertion_loss_db - (20.0 * math.log10(receiver_distance_m) + 11.0)
    )
    combined_receiver_level_dba = _log_sum((receiver_enclosure_noise_dba, background_level_dba))
    noise_criterion_margin_db = receiver_noise_criterion_dba - combined_receiver_level_dba
    thermal_capacity_margin_kw = ventilation_heat_capacity_kw - equipment_heat_load_kw

    pass_checks = [
        ventilation_margin_ach >= 0.0,
        noise_criterion_margin_db >= 0.0,
        thermal_capacity_margin_kw >= 0.0,
    ]

    return {
        "air_changes_per_h": round(air_changes_per_h, 3),
        "ventilation_margin_ach": round(ventilation_margin_ach, 3),
        "receiver_enclosure_noise_dba": round(receiver_enclosure_noise_dba, 3),
        "combined_receiver_level_dba": round(combined_receiver_level_dba, 3),
        "noise_criterion_margin_db": round(noise_criterion_margin_db, 3),
        "thermal_capacity_margin_kw": round(thermal_capacity_margin_kw, 3),
        "treatment_insertion_loss_db": round(treatment_insertion_loss_db, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
