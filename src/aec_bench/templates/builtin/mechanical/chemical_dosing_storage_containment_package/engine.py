# ABOUTME: Computes SSC-10 chemical dosing, storage, and containment metrics.
# ABOUTME: Combines dose mass, solution volume, storage refill, bund, pump, and signal checks.

from __future__ import annotations


def compute(
    flow_rate_m3_d: float,
    chemical_dose_mg_l: float,
    solution_strength_kg_l: float,
    required_storage_days: float,
    installed_storage_m3: float,
    largest_tank_m3: float,
    bund_factor: float,
    rain_allowance_m3: float,
    bund_available_m3: float,
    pump_operating_hours_d: float,
    selected_pump_capacity_l_h: float,
    signal_range_l_h: float,
) -> dict[str, float]:
    """Compute source-bound SSC-10 chemical dosing and containment metrics."""
    chemical_mass_kg_d = flow_rate_m3_d * chemical_dose_mg_l / 1000.0
    solution_volume_l_d = chemical_mass_kg_d / solution_strength_kg_l
    required_storage_m3 = solution_volume_l_d * required_storage_days / 1000.0
    refill_margin_d = installed_storage_m3 * 1000.0 / solution_volume_l_d - required_storage_days
    bund_required_m3 = largest_tank_m3 * bund_factor + rain_allowance_m3
    bund_margin_m3 = bund_available_m3 - bund_required_m3
    dosing_pump_flow_l_h = solution_volume_l_d / pump_operating_hours_d
    pump_capacity_margin_l_h = selected_pump_capacity_l_h - dosing_pump_flow_l_h
    design_signal_ma = 4.0 + 16.0 * dosing_pump_flow_l_h / signal_range_l_h
    signal_headroom_ma = 20.0 - design_signal_ma
    overall_pass_score = (
        1.0 if min(refill_margin_d, bund_margin_m3, pump_capacity_margin_l_h, signal_headroom_ma) >= 0.0 else 0.0
    )

    return {
        "chemical_mass_kg_d": round(chemical_mass_kg_d, 3),
        "solution_volume_l_d": round(solution_volume_l_d, 3),
        "required_storage_m3": round(required_storage_m3, 3),
        "refill_margin_d": round(refill_margin_d, 3),
        "bund_required_m3": round(bund_required_m3, 3),
        "bund_margin_m3": round(bund_margin_m3, 3),
        "dosing_pump_flow_l_h": round(dosing_pump_flow_l_h, 3),
        "pump_capacity_margin_l_h": round(pump_capacity_margin_l_h, 3),
        "design_signal_ma": round(design_signal_ma, 3),
        "signal_headroom_ma": round(signal_headroom_ma, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
