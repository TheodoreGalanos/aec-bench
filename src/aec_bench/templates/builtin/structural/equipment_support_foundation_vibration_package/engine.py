# ABOUTME: Computes SSC-06 equipment support, foundation, and vibration metrics.
# ABOUTME: Combines skid reactions, bearing, vibration transmissibility, and fatigue screening.

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
    support_count: int,
    reaction_load_factor: float,
    foundation_self_weight_kn: float,
    foundation_length_m: float,
    foundation_width_m: float,
    allowable_bearing_kpa: float,
    operating_frequency_hz: float,
    support_natural_frequency_hz: float,
    damping_ratio: float,
    cycles_per_day: float,
    design_life_days: float,
    stress_range_mpa: float,
    fatigue_constant: float,
    fatigue_exponent: float,
    support_factored_capacity_kn: float,
) -> dict[str, float]:
    """Compute source-bound equipment support, foundation, and vibration metrics."""
    _require_positive(
        equipment_mass_kg=equipment_mass_kg,
        dynamic_allowance_factor=dynamic_allowance_factor,
        reaction_load_factor=reaction_load_factor,
        foundation_self_weight_kn=foundation_self_weight_kn,
        foundation_length_m=foundation_length_m,
        foundation_width_m=foundation_width_m,
        allowable_bearing_kpa=allowable_bearing_kpa,
        operating_frequency_hz=operating_frequency_hz,
        support_natural_frequency_hz=support_natural_frequency_hz,
        damping_ratio=damping_ratio,
        cycles_per_day=cycles_per_day,
        design_life_days=design_life_days,
        stress_range_mpa=stress_range_mpa,
        fatigue_constant=fatigue_constant,
        fatigue_exponent=fatigue_exponent,
        support_factored_capacity_kn=support_factored_capacity_kn,
    )
    if support_count <= 0:
        msg = "support_count must be > 0"
        raise ValueError(msg)

    equipment_weight_kn = equipment_mass_kg * 9.81 / 1000.0
    support_service_reaction_kn = equipment_weight_kn * dynamic_allowance_factor / support_count
    factored_support_reaction_kn = support_service_reaction_kn * reaction_load_factor
    bearing_pressure_kpa = (equipment_weight_kn + foundation_self_weight_kn) / (
        foundation_length_m * foundation_width_m
    )
    bearing_utilization = bearing_pressure_kpa / allowable_bearing_kpa
    frequency_ratio = operating_frequency_hz / support_natural_frequency_hz
    vibration_transmissibility = math.sqrt(1.0 + (2.0 * damping_ratio * frequency_ratio) ** 2) / math.sqrt(
        (1.0 - frequency_ratio**2) ** 2 + (2.0 * damping_ratio * frequency_ratio) ** 2
    )
    transmitted_dynamic_force_kn = support_service_reaction_kn * vibration_transmissibility
    fatigue_cycles = cycles_per_day * design_life_days
    fatigue_damage_ratio = fatigue_cycles * stress_range_mpa**fatigue_exponent / fatigue_constant
    load_combination_margin_kn = support_factored_capacity_kn - factored_support_reaction_kn
    overall_pass_score = (
        1.0 if min(1.0 - bearing_utilization, 1.0 - fatigue_damage_ratio, load_combination_margin_kn) >= 0.0 else 0.0
    )

    return {
        "support_service_reaction_kn": round(support_service_reaction_kn, 3),
        "factored_support_reaction_kn": round(factored_support_reaction_kn, 3),
        "bearing_pressure_kpa": round(bearing_pressure_kpa, 3),
        "bearing_utilization": round(bearing_utilization, 3),
        "frequency_ratio": round(frequency_ratio, 3),
        "vibration_transmissibility": round(vibration_transmissibility, 3),
        "transmitted_dynamic_force_kn": round(transmitted_dynamic_force_kn, 3),
        "fatigue_damage_ratio": round(fatigue_damage_ratio, 3),
        "load_combination_margin_kn": round(load_combination_margin_kn, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
