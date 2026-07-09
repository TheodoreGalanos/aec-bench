# ABOUTME: Computes SSC-17 wastewater process energy island resilience metrics.
# ABOUTME: Combines oxygen demand, blower energy, biogas CHP, BESS energy, and autonomy checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    influent_flow_mld: float,
    bod_mg_l: float,
    ammonia_mg_l: float,
    bod_oxygen_factor: float,
    nitrification_oxygen_factor: float,
    blower_specific_energy_kwh_kg_o2: float,
    auxiliary_critical_load_kw: float,
    outage_duration_hr: float,
    volatile_solids_kg_d: float,
    biogas_yield_m3_kg_vs: float,
    methane_fraction: float,
    methane_energy_kwh_m3: float,
    chp_efficiency: float,
    bess_nominal_kwh: float,
    max_depth_of_discharge: float,
    inverter_efficiency: float,
) -> dict[str, float]:
    """Compute source-bound wastewater energy island resilience metrics."""
    _require_positive(
        influent_flow_mld=influent_flow_mld,
        bod_mg_l=bod_mg_l,
        ammonia_mg_l=ammonia_mg_l,
        bod_oxygen_factor=bod_oxygen_factor,
        nitrification_oxygen_factor=nitrification_oxygen_factor,
        blower_specific_energy_kwh_kg_o2=blower_specific_energy_kwh_kg_o2,
        auxiliary_critical_load_kw=auxiliary_critical_load_kw,
        outage_duration_hr=outage_duration_hr,
        volatile_solids_kg_d=volatile_solids_kg_d,
        biogas_yield_m3_kg_vs=biogas_yield_m3_kg_vs,
        methane_fraction=methane_fraction,
        methane_energy_kwh_m3=methane_energy_kwh_m3,
        chp_efficiency=chp_efficiency,
        bess_nominal_kwh=bess_nominal_kwh,
        max_depth_of_discharge=max_depth_of_discharge,
        inverter_efficiency=inverter_efficiency,
    )
    if max(methane_fraction, chp_efficiency, max_depth_of_discharge, inverter_efficiency) > 1.0:
        msg = "fractional process, CHP, and storage values must be <= 1"
        raise ValueError(msg)

    flow_m3_d = influent_flow_mld * 1000.0
    oxygen_demand_kg_d = (
        flow_m3_d * (bod_mg_l * bod_oxygen_factor + ammonia_mg_l * nitrification_oxygen_factor) / 1000.0
    )
    blower_energy_kwh_d = oxygen_demand_kg_d * blower_specific_energy_kwh_kg_o2
    blower_average_kw = blower_energy_kwh_d / 24.0
    biogas_production_m3_d = volatile_solids_kg_d * biogas_yield_m3_kg_vs
    chp_energy_available_kwh = (
        biogas_production_m3_d * methane_fraction * methane_energy_kwh_m3 * chp_efficiency * outage_duration_hr / 24.0
    )
    bess_usable_energy_kwh = bess_nominal_kwh * max_depth_of_discharge * inverter_efficiency
    critical_process_energy_kwh = (blower_average_kw + auxiliary_critical_load_kw) * outage_duration_hr
    resilience_energy_available_kwh = chp_energy_available_kwh + bess_usable_energy_kwh
    energy_margin_kwh = resilience_energy_available_kwh - critical_process_energy_kwh
    battery_only_runtime_hr = bess_usable_energy_kwh / (blower_average_kw + auxiliary_critical_load_kw)

    return {
        "oxygen_demand_kg_d": round(oxygen_demand_kg_d, 3),
        "blower_energy_kwh_d": round(blower_energy_kwh_d, 3),
        "blower_average_kw": round(blower_average_kw, 3),
        "biogas_production_m3_d": round(biogas_production_m3_d, 3),
        "chp_energy_available_kwh": round(chp_energy_available_kwh, 3),
        "bess_usable_energy_kwh": round(bess_usable_energy_kwh, 3),
        "critical_process_energy_kwh": round(critical_process_energy_kwh, 3),
        "resilience_energy_available_kwh": round(resilience_energy_available_kwh, 3),
        "energy_margin_kwh": round(energy_margin_kwh, 3),
        "battery_only_runtime_hr": round(battery_only_runtime_hr, 3),
        "overall_pass_score": 1.0 if energy_margin_kwh >= 0.0 else 0.0,
    }
