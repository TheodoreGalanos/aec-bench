# ABOUTME: Computes SSC-12 vibration isolation and support metrics from source-pack values.
# ABOUTME: Combines transmissibility, receiver vibration, support reaction, and fatigue checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    equipment_mass_kg: float,
    dynamic_allowance_factor: float,
    support_count: float,
    support_capacity_kn: float,
    forcing_frequency_hz: float,
    isolator_natural_frequency_hz: float,
    damping_ratio: float,
    source_vibration_velocity_mm_s: float,
    structural_path_factor: float,
    vibration_velocity_criterion_mm_s: float,
    cycles_per_hour: float,
    operating_hours_per_day: float,
    design_life_days: float,
    allowable_fatigue_cycles: float,
) -> dict[str, float]:
    """Compute deterministic isolation, support, and fatigue checks."""
    _require_positive(
        equipment_mass_kg=equipment_mass_kg,
        dynamic_allowance_factor=dynamic_allowance_factor,
        support_count=support_count,
        support_capacity_kn=support_capacity_kn,
        forcing_frequency_hz=forcing_frequency_hz,
        isolator_natural_frequency_hz=isolator_natural_frequency_hz,
        source_vibration_velocity_mm_s=source_vibration_velocity_mm_s,
        structural_path_factor=structural_path_factor,
        vibration_velocity_criterion_mm_s=vibration_velocity_criterion_mm_s,
        cycles_per_hour=cycles_per_hour,
        operating_hours_per_day=operating_hours_per_day,
        design_life_days=design_life_days,
        allowable_fatigue_cycles=allowable_fatigue_cycles,
    )
    if damping_ratio < 0:
        msg = "damping_ratio must be >= 0"
        raise ValueError(msg)

    frequency_ratio = forcing_frequency_hz / isolator_natural_frequency_hz
    damping_term = 2.0 * damping_ratio * frequency_ratio
    vibration_transmissibility = math.sqrt(1.0 + damping_term**2) / math.sqrt(
        (1.0 - frequency_ratio**2) ** 2 + damping_term**2
    )
    receiver_vibration_velocity_mm_s = (
        source_vibration_velocity_mm_s * vibration_transmissibility * structural_path_factor
    )
    vibration_margin_mm_s = vibration_velocity_criterion_mm_s - receiver_vibration_velocity_mm_s
    support_service_reaction_kn = equipment_mass_kg * 9.81 / 1000.0 * dynamic_allowance_factor / support_count
    support_reaction_margin_kn = support_capacity_kn - support_service_reaction_kn
    fatigue_damage_ratio = cycles_per_hour * operating_hours_per_day * design_life_days / allowable_fatigue_cycles
    fatigue_margin = 1.0 - fatigue_damage_ratio

    pass_checks = [
        vibration_margin_mm_s >= 0.0,
        support_reaction_margin_kn >= 0.0,
        fatigue_margin >= 0.0,
    ]

    return {
        "frequency_ratio": round(frequency_ratio, 3),
        "vibration_transmissibility": round(vibration_transmissibility, 3),
        "receiver_vibration_velocity_mm_s": round(receiver_vibration_velocity_mm_s, 3),
        "vibration_margin_mm_s": round(vibration_margin_mm_s, 3),
        "support_service_reaction_kn": round(support_service_reaction_kn, 3),
        "support_reaction_margin_kn": round(support_reaction_margin_kn, 3),
        "fatigue_damage_ratio": round(fatigue_damage_ratio, 3),
        "fatigue_margin": round(fatigue_margin, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
