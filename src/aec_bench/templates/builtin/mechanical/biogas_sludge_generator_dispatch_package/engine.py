# ABOUTME: Computes SSC-10 biogas, sludge, and generator dispatch metrics.
# ABOUTME: Combines volatile solids destruction, biogas yield, generator output, dispatch, and heat checks.

from __future__ import annotations


def compute(
    sludge_production_kg_d: float,
    volatile_solids_fraction: float,
    volatile_solids_destruction_fraction: float,
    biogas_yield_m3_kg_vs: float,
    methane_fraction: float,
    methane_energy_kwh_m3: float,
    generator_electrical_efficiency: float,
    generator_rated_kw: float,
    critical_process_load_kw: float,
    dispatch_runtime_h: float,
    parasitic_load_kw: float,
    heat_recovery_efficiency: float,
    heat_load_kwh_d: float,
) -> dict[str, float]:
    """Compute source-bound SSC-10 biogas and generator dispatch metrics."""
    volatile_solids_feed_kg_d = sludge_production_kg_d * volatile_solids_fraction
    volatile_solids_destroyed_kg_d = volatile_solids_feed_kg_d * volatile_solids_destruction_fraction
    biogas_m3_d = volatile_solids_destroyed_kg_d * biogas_yield_m3_kg_vs
    methane_m3_d = biogas_m3_d * methane_fraction
    methane_energy_kwh_d = methane_m3_d * methane_energy_kwh_m3
    generator_electric_energy_kwh_d = methane_energy_kwh_d * generator_electrical_efficiency
    average_generator_kw = generator_electric_energy_kwh_d / 24.0
    generator_capacity_margin_kw = generator_rated_kw - critical_process_load_kw - parasitic_load_kw
    critical_dispatch_energy_kwh = critical_process_load_kw * dispatch_runtime_h
    dispatch_energy_margin_kwh = generator_electric_energy_kwh_d - critical_dispatch_energy_kwh
    available_runtime_hr = generator_electric_energy_kwh_d / (critical_process_load_kw + parasitic_load_kw)
    heat_recovery_kwh_d = methane_energy_kwh_d * heat_recovery_efficiency
    heat_recovery_margin_kwh_d = heat_recovery_kwh_d - heat_load_kwh_d
    overall_pass_score = (
        1.0 if min(generator_capacity_margin_kw, dispatch_energy_margin_kwh, heat_recovery_margin_kwh_d) >= 0.0 else 0.0
    )

    return {
        "volatile_solids_feed_kg_d": round(volatile_solids_feed_kg_d, 3),
        "volatile_solids_destroyed_kg_d": round(volatile_solids_destroyed_kg_d, 3),
        "biogas_m3_d": round(biogas_m3_d, 3),
        "methane_m3_d": round(methane_m3_d, 3),
        "methane_energy_kwh_d": round(methane_energy_kwh_d, 3),
        "generator_electric_energy_kwh_d": round(generator_electric_energy_kwh_d, 3),
        "average_generator_kw": round(average_generator_kw, 3),
        "generator_capacity_margin_kw": round(generator_capacity_margin_kw, 3),
        "critical_dispatch_energy_kwh": round(critical_dispatch_energy_kwh, 3),
        "dispatch_energy_margin_kwh": round(dispatch_energy_margin_kwh, 3),
        "available_runtime_hr": round(available_runtime_hr, 3),
        "heat_recovery_kwh_d": round(heat_recovery_kwh_d, 3),
        "heat_recovery_margin_kwh_d": round(heat_recovery_margin_kwh_d, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
