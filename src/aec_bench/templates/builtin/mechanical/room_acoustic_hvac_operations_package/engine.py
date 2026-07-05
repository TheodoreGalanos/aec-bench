# ABOUTME: Computes SSC-12 room acoustic and HVAC operations metrics.
# ABOUTME: Combines Sabine RT60, air-change, source level, occupancy, and criterion checks.

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
    room_volume_m3: float,
    absorption_area_m2: float,
    max_rt60_s: float,
    supply_airflow_m3_h: float,
    hvac_sound_power_dba: float,
    hvac_receiver_distance_m: float,
    hvac_insertion_loss_db: float,
    equipment_sound_power_dba: float,
    equipment_receiver_distance_m: float,
    equipment_insertion_loss_db: float,
    room_noise_criterion_dba: float,
    room_area_m2: float,
    area_per_occupant_m2: float,
) -> dict[str, float]:
    """Compute deterministic room acoustic and HVAC operations checks."""
    _require_positive(
        room_volume_m3=room_volume_m3,
        absorption_area_m2=absorption_area_m2,
        max_rt60_s=max_rt60_s,
        supply_airflow_m3_h=supply_airflow_m3_h,
        hvac_sound_power_dba=hvac_sound_power_dba,
        hvac_receiver_distance_m=hvac_receiver_distance_m,
        equipment_sound_power_dba=equipment_sound_power_dba,
        equipment_receiver_distance_m=equipment_receiver_distance_m,
        room_noise_criterion_dba=room_noise_criterion_dba,
        room_area_m2=room_area_m2,
        area_per_occupant_m2=area_per_occupant_m2,
    )
    if min(hvac_insertion_loss_db, equipment_insertion_loss_db) < 0:
        msg = "insertion losses must be >= 0"
        raise ValueError(msg)

    room_rt60_s = 0.161 * room_volume_m3 / absorption_area_m2
    rt60_margin_s = max_rt60_s - room_rt60_s
    air_changes_per_h = supply_airflow_m3_h / room_volume_m3
    hvac_source_a_level_dba = (
        hvac_sound_power_dba - 20.0 * math.log10(hvac_receiver_distance_m) - hvac_insertion_loss_db
    )
    equipment_source_a_level_dba = (
        equipment_sound_power_dba - 20.0 * math.log10(equipment_receiver_distance_m) - equipment_insertion_loss_db
    )
    combined_room_level_dba = _log_sum((hvac_source_a_level_dba, equipment_source_a_level_dba))
    room_noise_margin_db = room_noise_criterion_dba - combined_room_level_dba
    design_occupants = float(math.ceil(room_area_m2 / area_per_occupant_m2))

    pass_checks = [
        rt60_margin_s >= 0.0,
        room_noise_margin_db >= 0.0,
        air_changes_per_h > 0.0,
    ]

    return {
        "room_rt60_s": round(room_rt60_s, 3),
        "rt60_margin_s": round(rt60_margin_s, 3),
        "air_changes_per_h": round(air_changes_per_h, 3),
        "hvac_source_a_level_dba": round(hvac_source_a_level_dba, 3),
        "equipment_source_a_level_dba": round(equipment_source_a_level_dba, 3),
        "combined_room_level_dba": round(combined_room_level_dba, 3),
        "room_noise_margin_db": round(room_noise_margin_db, 3),
        "design_occupants": round(design_occupants, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
