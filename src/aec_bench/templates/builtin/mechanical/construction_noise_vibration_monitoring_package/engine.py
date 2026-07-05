# ABOUTME: Computes SSC-12 construction noise and vibration monitoring metrics.
# ABOUTME: Combines receiver noise, vibration, telemetry, and action-response margins.

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
    source_sound_power_dba: float,
    receiver_distance_m: float,
    barrier_insertion_loss_db: float,
    background_level_dba: float,
    noise_action_threshold_dba: float,
    forcing_frequency_hz: float,
    ground_natural_frequency_hz: float,
    damping_ratio: float,
    source_vibration_velocity_mm_s: float,
    vibration_path_factor: float,
    vibration_action_threshold_mm_s: float,
    telemetry_capacity_mb_day: float,
    telemetry_load_mb_day: float,
    allowed_response_h: float,
    planned_response_h: float,
) -> dict[str, float]:
    """Compute deterministic construction noise, vibration, and monitoring checks."""
    _require_positive(
        source_sound_power_dba=source_sound_power_dba,
        receiver_distance_m=receiver_distance_m,
        background_level_dba=background_level_dba,
        noise_action_threshold_dba=noise_action_threshold_dba,
        forcing_frequency_hz=forcing_frequency_hz,
        ground_natural_frequency_hz=ground_natural_frequency_hz,
        source_vibration_velocity_mm_s=source_vibration_velocity_mm_s,
        vibration_path_factor=vibration_path_factor,
        vibration_action_threshold_mm_s=vibration_action_threshold_mm_s,
        telemetry_capacity_mb_day=telemetry_capacity_mb_day,
        telemetry_load_mb_day=telemetry_load_mb_day,
        allowed_response_h=allowed_response_h,
        planned_response_h=planned_response_h,
    )
    if min(barrier_insertion_loss_db, damping_ratio) < 0:
        msg = "barrier_insertion_loss_db and damping_ratio must be >= 0"
        raise ValueError(msg)

    distance_attenuation_db = 20.0 * math.log10(receiver_distance_m) + 11.0
    receiver_construction_noise_dba = source_sound_power_dba - distance_attenuation_db - barrier_insertion_loss_db
    combined_construction_noise_dba = _log_sum((receiver_construction_noise_dba, background_level_dba))
    noise_action_margin_db = noise_action_threshold_dba - combined_construction_noise_dba
    frequency_ratio = forcing_frequency_hz / ground_natural_frequency_hz
    damping_term = 2.0 * damping_ratio * frequency_ratio
    vibration_transmissibility = math.sqrt(1.0 + damping_term**2) / math.sqrt(
        (1.0 - frequency_ratio**2) ** 2 + damping_term**2
    )
    receiver_vibration_velocity_mm_s = (
        source_vibration_velocity_mm_s * vibration_transmissibility * vibration_path_factor
    )
    vibration_action_margin_mm_s = vibration_action_threshold_mm_s - receiver_vibration_velocity_mm_s
    monitoring_data_headroom_mb = telemetry_capacity_mb_day - telemetry_load_mb_day
    complaint_response_margin_h = allowed_response_h - planned_response_h

    pass_checks = [
        noise_action_margin_db >= 0.0,
        vibration_action_margin_mm_s >= 0.0,
        monitoring_data_headroom_mb >= 0.0,
        complaint_response_margin_h >= 0.0,
    ]

    return {
        "receiver_construction_noise_dba": round(receiver_construction_noise_dba, 3),
        "combined_construction_noise_dba": round(combined_construction_noise_dba, 3),
        "noise_action_margin_db": round(noise_action_margin_db, 3),
        "vibration_transmissibility": round(vibration_transmissibility, 3),
        "receiver_vibration_velocity_mm_s": round(receiver_vibration_velocity_mm_s, 3),
        "vibration_action_margin_mm_s": round(vibration_action_margin_mm_s, 3),
        "monitoring_data_headroom_mb": round(monitoring_data_headroom_mb, 3),
        "complaint_response_margin_h": round(complaint_response_margin_h, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
