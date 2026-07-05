# ABOUTME: Computes SSC-14 construction tolerance and connection repair package metrics.
# ABOUTME: Combines as-built offset, slot/shim repair capacity, bracket moment, and weld screening.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    measured_offset_mm: float,
    permitted_tolerance_mm: float,
    available_slot_adjustment_mm: float,
    maximum_repair_shim_mm: float,
    bracket_service_load_kn: float,
    bracket_arm_m: float,
    bracket_moment_capacity_knm: float,
    carbon_percent: float,
    manganese_percent: float,
    chromium_percent: float,
    molybdenum_percent: float,
    vanadium_percent: float,
    nickel_percent: float,
    copper_percent: float,
    weld_carbon_equivalent_limit: float,
    minimum_remaining_slot_margin_mm: float,
) -> dict[str, float]:
    """Compute deterministic SSC-14 tolerance and field repair metrics."""
    _require_positive(
        permitted_tolerance_mm=permitted_tolerance_mm,
        available_slot_adjustment_mm=available_slot_adjustment_mm,
        maximum_repair_shim_mm=maximum_repair_shim_mm,
        bracket_service_load_kn=bracket_service_load_kn,
        bracket_arm_m=bracket_arm_m,
        bracket_moment_capacity_knm=bracket_moment_capacity_knm,
        weld_carbon_equivalent_limit=weld_carbon_equivalent_limit,
        minimum_remaining_slot_margin_mm=minimum_remaining_slot_margin_mm,
    )

    tolerance_exceedance_mm = max(measured_offset_mm - permitted_tolerance_mm, 0.0)
    required_slot_adjustment_mm = measured_offset_mm
    remaining_slot_margin_mm = available_slot_adjustment_mm - required_slot_adjustment_mm
    repair_shim_margin_mm = maximum_repair_shim_mm - tolerance_exceedance_mm
    baseline_moment_knm = bracket_service_load_kn * bracket_arm_m
    added_moment_knm = bracket_service_load_kn * tolerance_exceedance_mm / 1000.0
    bracket_moment_utilization = (baseline_moment_knm + added_moment_knm) / bracket_moment_capacity_knm
    weld_carbon_equivalent = (
        carbon_percent
        + manganese_percent / 6.0
        + (chromium_percent + molybdenum_percent + vanadium_percent) / 5.0
        + (nickel_percent + copper_percent) / 15.0
    )
    carbon_equivalent_margin = weld_carbon_equivalent_limit - weld_carbon_equivalent

    repair_acceptance_score = (
        1.0
        if (
            remaining_slot_margin_mm >= minimum_remaining_slot_margin_mm
            and repair_shim_margin_mm >= 0.0
            and bracket_moment_utilization <= 1.0
            and carbon_equivalent_margin >= 0.0
        )
        else 0.0
    )

    return {
        "tolerance_exceedance_mm": round(tolerance_exceedance_mm, 3),
        "required_slot_adjustment_mm": round(required_slot_adjustment_mm, 3),
        "remaining_slot_margin_mm": round(remaining_slot_margin_mm, 3),
        "repair_shim_margin_mm": round(repair_shim_margin_mm, 3),
        "baseline_moment_knm": round(baseline_moment_knm, 3),
        "added_moment_knm": round(added_moment_knm, 3),
        "bracket_moment_utilization": round(bracket_moment_utilization, 3),
        "weld_carbon_equivalent": round(weld_carbon_equivalent, 3),
        "carbon_equivalent_margin": round(carbon_equivalent_margin, 3),
        "repair_acceptance_score": round(repair_acceptance_score, 3),
        "overall_pass_score": round(repair_acceptance_score, 3),
    }
