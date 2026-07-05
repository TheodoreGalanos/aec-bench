# ABOUTME: Computes SSC-06 heat exchanger and thermal plant equipment metrics.
# ABOUTME: Combines heat load, LMTD, UA margin, pump duty, motor power, and support reaction.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _lmtd(delta_t_1_c: float, delta_t_2_c: float) -> float:
    """Return log mean temperature difference, including the equal-delta limit."""
    _require_positive(delta_t_1_c=delta_t_1_c, delta_t_2_c=delta_t_2_c)
    if math.isclose(delta_t_1_c, delta_t_2_c):
        return delta_t_1_c
    return (delta_t_1_c - delta_t_2_c) / math.log(delta_t_1_c / delta_t_2_c)


def compute(
    hot_flow_kg_s: float,
    fluid_cp_kj_kg_c: float,
    hot_inlet_c: float,
    hot_outlet_c: float,
    cold_inlet_c: float,
    cold_outlet_c: float,
    selected_ua_kw_per_c: float,
    fluid_density_kg_m3: float,
    circulation_pump_head_m: float,
    pump_efficiency: float,
    motor_efficiency: float,
    selected_motor_kw: float,
    heat_exchanger_mass_kg: float,
    pump_mass_kg: float,
    support_count: int,
) -> dict[str, float]:
    """Compute source-bound thermal equipment, pump, motor, and support metrics."""
    _require_positive(
        hot_flow_kg_s=hot_flow_kg_s,
        fluid_cp_kj_kg_c=fluid_cp_kj_kg_c,
        selected_ua_kw_per_c=selected_ua_kw_per_c,
        fluid_density_kg_m3=fluid_density_kg_m3,
        circulation_pump_head_m=circulation_pump_head_m,
        pump_efficiency=pump_efficiency,
        motor_efficiency=motor_efficiency,
        selected_motor_kw=selected_motor_kw,
        heat_exchanger_mass_kg=heat_exchanger_mass_kg,
        pump_mass_kg=pump_mass_kg,
    )
    if hot_inlet_c <= hot_outlet_c:
        msg = "hot_inlet_c must be greater than hot_outlet_c"
        raise ValueError(msg)
    if hot_inlet_c <= cold_outlet_c or hot_outlet_c <= cold_inlet_c:
        msg = "hot-side temperatures must exceed cold-side temperatures at both ends"
        raise ValueError(msg)
    if pump_efficiency > 1.0 or motor_efficiency > 1.0:
        msg = "efficiency values must be <= 1"
        raise ValueError(msg)
    if support_count <= 0:
        msg = "support_count must be > 0"
        raise ValueError(msg)

    heat_load_kw = hot_flow_kg_s * fluid_cp_kj_kg_c * (hot_inlet_c - hot_outlet_c)
    lmtd_c = _lmtd(hot_inlet_c - cold_outlet_c, hot_outlet_c - cold_inlet_c)
    required_ua_kw_per_c = heat_load_kw / lmtd_c
    ua_margin_kw_per_c = selected_ua_kw_per_c - required_ua_kw_per_c
    process_flow_m3_h = hot_flow_kg_s / fluid_density_kg_m3 * 3600.0
    pump_hydraulic_power_kw = (
        fluid_density_kg_m3 * 9.81 * (process_flow_m3_h / 3600.0) * circulation_pump_head_m / 1000.0
    )
    pump_shaft_power_kw = pump_hydraulic_power_kw / pump_efficiency
    motor_input_power_kw = pump_shaft_power_kw / motor_efficiency
    motor_margin_kw = selected_motor_kw - motor_input_power_kw
    support_service_reaction_kn = (heat_exchanger_mass_kg + pump_mass_kg) * 9.81 / 1000.0 / support_count
    overall_pass_score = 1.0 if min(ua_margin_kw_per_c, motor_margin_kw) >= 0.0 else 0.0

    return {
        "heat_load_kw": round(heat_load_kw, 3),
        "lmtd_c": round(lmtd_c, 3),
        "required_ua_kw_per_c": round(required_ua_kw_per_c, 3),
        "ua_margin_kw_per_c": round(ua_margin_kw_per_c, 3),
        "process_flow_m3_h": round(process_flow_m3_h, 3),
        "pump_hydraulic_power_kw": round(pump_hydraulic_power_kw, 3),
        "pump_shaft_power_kw": round(pump_shaft_power_kw, 3),
        "motor_input_power_kw": round(motor_input_power_kw, 3),
        "motor_margin_kw": round(motor_margin_kw, 3),
        "support_service_reaction_kn": round(support_service_reaction_kn, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
