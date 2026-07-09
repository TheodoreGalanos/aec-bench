# ABOUTME: Computes SSC-12 acoustic receiver impact metrics from task-owned source-pack values.
# ABOUTME: Aggregates octave-band attenuation, A-weighting, background addition, and vibration isolation.

from __future__ import annotations

from math import log10, sqrt

_OCTAVE_BANDS_HZ: tuple[float, ...] = (63.0, 125.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0)
_A_WEIGHTING_DB: tuple[float, ...] = (-26.2, -16.1, -8.6, -3.2, 0.0, 1.2, 1.0, -1.1)


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _log_sum(levels_db: tuple[float, ...]) -> float:
    """Return the logarithmic sum of decibel levels."""
    return 10.0 * log10(sum(10.0 ** (level / 10.0) for level in levels_db))


def _vibration_transmissibility(
    *,
    forcing_frequency_hz: float,
    natural_frequency_hz: float,
    damping_ratio: float,
) -> float:
    """Return damped single-degree-of-freedom vibration transmissibility."""
    frequency_ratio = forcing_frequency_hz / natural_frequency_hz
    damping_term = 2.0 * damping_ratio * frequency_ratio
    numerator = sqrt(1.0 + damping_term**2)
    denominator = sqrt((1.0 - frequency_ratio**2) ** 2 + damping_term**2)
    return numerator / denominator


def compute(
    source_lw_63_hz_db: float,
    source_lw_125_hz_db: float,
    source_lw_250_hz_db: float,
    source_lw_500_hz_db: float,
    source_lw_1000_hz_db: float,
    source_lw_2000_hz_db: float,
    source_lw_4000_hz_db: float,
    source_lw_8000_hz_db: float,
    receiver_distance_m: float,
    mitigation_insertion_loss_db: float,
    background_sound_level_dba: float,
    night_noise_criterion_dba: float,
    forcing_frequency_hz: float,
    isolator_natural_frequency_hz: float,
    damping_ratio: float,
    source_vibration_velocity_mm_s: float,
    structural_path_factor: float,
    vibration_velocity_criterion_mm_s: float,
) -> dict[str, float]:
    """Compute acoustic receiver and vibration-isolation metrics for the SSC-12 source pack."""
    _require_positive(
        source_lw_63_hz_db=source_lw_63_hz_db,
        source_lw_125_hz_db=source_lw_125_hz_db,
        source_lw_250_hz_db=source_lw_250_hz_db,
        source_lw_500_hz_db=source_lw_500_hz_db,
        source_lw_1000_hz_db=source_lw_1000_hz_db,
        source_lw_2000_hz_db=source_lw_2000_hz_db,
        source_lw_4000_hz_db=source_lw_4000_hz_db,
        source_lw_8000_hz_db=source_lw_8000_hz_db,
        receiver_distance_m=receiver_distance_m,
        background_sound_level_dba=background_sound_level_dba,
        night_noise_criterion_dba=night_noise_criterion_dba,
        forcing_frequency_hz=forcing_frequency_hz,
        isolator_natural_frequency_hz=isolator_natural_frequency_hz,
        source_vibration_velocity_mm_s=source_vibration_velocity_mm_s,
        structural_path_factor=structural_path_factor,
        vibration_velocity_criterion_mm_s=vibration_velocity_criterion_mm_s,
    )
    if mitigation_insertion_loss_db < 0:
        msg = "mitigation_insertion_loss_db must be >= 0"
        raise ValueError(msg)
    if damping_ratio < 0:
        msg = "damping_ratio must be >= 0"
        raise ValueError(msg)
    if structural_path_factor > 1.0:
        msg = "structural_path_factor must be <= 1"
        raise ValueError(msg)

    source_levels = (
        source_lw_63_hz_db,
        source_lw_125_hz_db,
        source_lw_250_hz_db,
        source_lw_500_hz_db,
        source_lw_1000_hz_db,
        source_lw_2000_hz_db,
        source_lw_4000_hz_db,
        source_lw_8000_hz_db,
    )

    distance_attenuation_db = 20.0 * log10(receiver_distance_m) + 11.0
    receiver_linear_bands = tuple(
        level - distance_attenuation_db - mitigation_insertion_loss_db for level in source_levels
    )
    receiver_weighted_bands = tuple(
        level + correction for level, correction in zip(receiver_linear_bands, _A_WEIGHTING_DB, strict=True)
    )

    receiver_linear_level_db = _log_sum(receiver_linear_bands)
    receiver_a_weighted_level_dba = _log_sum(receiver_weighted_bands)
    combined_ambient_level_dba = _log_sum((receiver_a_weighted_level_dba, background_sound_level_dba))
    increase_over_background_db = combined_ambient_level_dba - background_sound_level_dba
    criterion_margin_db = night_noise_criterion_dba - combined_ambient_level_dba

    dominant_index = max(range(len(receiver_weighted_bands)), key=receiver_weighted_bands.__getitem__)
    dominant_octave_hz = _OCTAVE_BANDS_HZ[dominant_index]

    frequency_ratio = forcing_frequency_hz / isolator_natural_frequency_hz
    transmissibility = _vibration_transmissibility(
        forcing_frequency_hz=forcing_frequency_hz,
        natural_frequency_hz=isolator_natural_frequency_hz,
        damping_ratio=damping_ratio,
    )
    receiver_vibration_velocity_mm_s = source_vibration_velocity_mm_s * transmissibility * structural_path_factor
    vibration_margin_mm_s = vibration_velocity_criterion_mm_s - receiver_vibration_velocity_mm_s
    overall_pass_score = 1.0 if criterion_margin_db >= 0.0 and vibration_margin_mm_s >= 0.0 else 0.0

    return {
        "distance_attenuation_db": round(distance_attenuation_db, 3),
        "receiver_linear_level_db": round(receiver_linear_level_db, 3),
        "receiver_a_weighted_level_dba": round(receiver_a_weighted_level_dba, 3),
        "combined_ambient_level_dba": round(combined_ambient_level_dba, 3),
        "increase_over_background_db": round(increase_over_background_db, 3),
        "criterion_margin_db": round(criterion_margin_db, 3),
        "dominant_octave_hz": round(dominant_octave_hz, 3),
        "frequency_ratio": round(frequency_ratio, 3),
        "vibration_transmissibility": round(transmissibility, 3),
        "receiver_vibration_velocity_mm_s": round(receiver_vibration_velocity_mm_s, 3),
        "vibration_margin_mm_s": round(vibration_margin_mm_s, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
