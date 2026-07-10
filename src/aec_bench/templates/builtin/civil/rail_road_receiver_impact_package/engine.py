# ABOUTME: Computes SSC-12 rail or road receiver impact metrics from source-pack values.
# ABOUTME: Combines corridor source level, receiver noise, vibration, and mitigation margins.

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
    base_source_level_dba: float,
    traffic_volume_vph: float,
    reference_volume_vph: float,
    speed_kmh: float,
    reference_speed_kmh: float,
    speed_adjustment_db_per_kmh: float,
    receiver_distance_m: float,
    barrier_insertion_loss_db: float,
    background_level_dba: float,
    corridor_noise_criterion_dba: float,
    base_vibration_velocity_mm_s: float,
    vibration_reference_speed_kmh: float,
    vibration_path_factor: float,
    vibration_criterion_mm_s: float,
    provided_barrier_height_m: float,
    required_barrier_height_m: float,
) -> dict[str, float]:
    """Compute deterministic corridor receiver noise and vibration checks."""
    _require_positive(
        base_source_level_dba=base_source_level_dba,
        traffic_volume_vph=traffic_volume_vph,
        reference_volume_vph=reference_volume_vph,
        speed_kmh=speed_kmh,
        reference_speed_kmh=reference_speed_kmh,
        receiver_distance_m=receiver_distance_m,
        background_level_dba=background_level_dba,
        corridor_noise_criterion_dba=corridor_noise_criterion_dba,
        base_vibration_velocity_mm_s=base_vibration_velocity_mm_s,
        vibration_reference_speed_kmh=vibration_reference_speed_kmh,
        vibration_path_factor=vibration_path_factor,
        vibration_criterion_mm_s=vibration_criterion_mm_s,
        provided_barrier_height_m=provided_barrier_height_m,
        required_barrier_height_m=required_barrier_height_m,
    )
    if barrier_insertion_loss_db < 0:
        msg = "barrier_insertion_loss_db must be >= 0"
        raise ValueError(msg)

    traffic_source_level_dba = (
        base_source_level_dba
        + 10.0 * math.log10(traffic_volume_vph / reference_volume_vph)
        + speed_adjustment_db_per_kmh * (speed_kmh - reference_speed_kmh)
    )
    receiver_noise_level_dba = (
        traffic_source_level_dba - (20.0 * math.log10(receiver_distance_m) + 11.0) - barrier_insertion_loss_db
    )
    combined_corridor_level_dba = _log_sum((receiver_noise_level_dba, background_level_dba))
    corridor_noise_margin_db = corridor_noise_criterion_dba - combined_corridor_level_dba
    corridor_vibration_velocity_mm_s = (
        base_vibration_velocity_mm_s * (speed_kmh / vibration_reference_speed_kmh) ** 2 * vibration_path_factor
    )
    corridor_vibration_margin_mm_s = vibration_criterion_mm_s - corridor_vibration_velocity_mm_s
    mitigation_height_margin_m = provided_barrier_height_m - required_barrier_height_m

    pass_checks = [
        corridor_noise_margin_db >= 0.0,
        corridor_vibration_margin_mm_s >= 0.0,
        mitigation_height_margin_m >= 0.0,
    ]

    return {
        "traffic_source_level_dba": round(traffic_source_level_dba, 3),
        "receiver_noise_level_dba": round(receiver_noise_level_dba, 3),
        "combined_corridor_level_dba": round(combined_corridor_level_dba, 3),
        "corridor_noise_margin_db": round(corridor_noise_margin_db, 3),
        "corridor_vibration_velocity_mm_s": round(corridor_vibration_velocity_mm_s, 3),
        "corridor_vibration_margin_mm_s": round(corridor_vibration_margin_mm_s, 3),
        "mitigation_height_margin_m": round(mitigation_height_margin_m, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
