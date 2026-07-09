# ABOUTME: Computes SSC-10 wastewater process, blower, biogas, and energy-island metrics.
# ABOUTME: Combines source-bound oxygen demand, air flow, energy, BESS, and feeder checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _require_nonnegative(**values: float) -> None:
    """Raise ValueError when any supplied value is negative."""
    for name, value in values.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)


def _require_fraction(**values: float) -> None:
    """Raise ValueError when any supplied value is outside (0, 1]."""
    for name, value in values.items():
        if value <= 0 or value > 1.0:
            msg = f"{name} must be > 0 and <= 1"
            raise ValueError(msg)


def compute(
    flow_rate_m3_d: float,
    influent_bod_mg_l: float,
    effluent_bod_mg_l: float,
    influent_tkn_mg_l: float,
    effluent_tkn_mg_l: float,
    sludge_production_kg_d: float,
    denitrified_nitrogen_mg_l: float,
    field_transfer_efficiency: float,
    air_oxygen_mass_fraction: float,
    air_density_kg_nm3: float,
    blower_airflow_capacity_nm3_h: float,
    blower_discharge_pressure_kpa: float,
    blower_efficiency: float,
    blower_motor_efficiency: float,
    selected_blower_motor_kw: float,
    mixer_load_kw: float,
    recycle_pump_load_kw: float,
    controls_load_kw: float,
    volatile_solids_feed_kg_d: float,
    volatile_solids_destruction_pct: float,
    biogas_yield_m3_kg_vs: float,
    methane_fraction: float,
    methane_energy_kwh_m3: float,
    chp_electrical_efficiency: float,
    pv_generation_kwh_d: float,
    bess_nominal_kwh: float,
    bess_usable_soc_fraction: float,
    bess_inverter_efficiency: float,
    bess_reserve_kwh: float,
    feeder_voltage_v: float,
    feeder_length_km: float,
    feeder_resistance_ohm_per_km: float,
    feeder_reactance_ohm_per_km: float,
    feeder_power_factor: float,
    max_voltage_drop_percent: float,
) -> dict[str, float]:
    """Compute source-bound SSC-10 process-energy island metrics."""
    _require_positive(
        flow_rate_m3_d=flow_rate_m3_d,
        influent_bod_mg_l=influent_bod_mg_l,
        influent_tkn_mg_l=influent_tkn_mg_l,
        field_transfer_efficiency=field_transfer_efficiency,
        air_oxygen_mass_fraction=air_oxygen_mass_fraction,
        air_density_kg_nm3=air_density_kg_nm3,
        blower_airflow_capacity_nm3_h=blower_airflow_capacity_nm3_h,
        blower_discharge_pressure_kpa=blower_discharge_pressure_kpa,
        blower_efficiency=blower_efficiency,
        blower_motor_efficiency=blower_motor_efficiency,
        selected_blower_motor_kw=selected_blower_motor_kw,
        volatile_solids_feed_kg_d=volatile_solids_feed_kg_d,
        biogas_yield_m3_kg_vs=biogas_yield_m3_kg_vs,
        methane_energy_kwh_m3=methane_energy_kwh_m3,
        chp_electrical_efficiency=chp_electrical_efficiency,
        bess_nominal_kwh=bess_nominal_kwh,
        bess_usable_soc_fraction=bess_usable_soc_fraction,
        bess_inverter_efficiency=bess_inverter_efficiency,
        feeder_voltage_v=feeder_voltage_v,
        feeder_length_km=feeder_length_km,
        feeder_power_factor=feeder_power_factor,
        max_voltage_drop_percent=max_voltage_drop_percent,
    )
    _require_nonnegative(
        effluent_bod_mg_l=effluent_bod_mg_l,
        effluent_tkn_mg_l=effluent_tkn_mg_l,
        sludge_production_kg_d=sludge_production_kg_d,
        denitrified_nitrogen_mg_l=denitrified_nitrogen_mg_l,
        mixer_load_kw=mixer_load_kw,
        recycle_pump_load_kw=recycle_pump_load_kw,
        controls_load_kw=controls_load_kw,
        volatile_solids_destruction_pct=volatile_solids_destruction_pct,
        pv_generation_kwh_d=pv_generation_kwh_d,
        bess_reserve_kwh=bess_reserve_kwh,
        feeder_resistance_ohm_per_km=feeder_resistance_ohm_per_km,
        feeder_reactance_ohm_per_km=feeder_reactance_ohm_per_km,
    )
    _require_fraction(
        field_transfer_efficiency=field_transfer_efficiency,
        air_oxygen_mass_fraction=air_oxygen_mass_fraction,
        blower_efficiency=blower_efficiency,
        blower_motor_efficiency=blower_motor_efficiency,
        methane_fraction=methane_fraction,
        chp_electrical_efficiency=chp_electrical_efficiency,
        bess_usable_soc_fraction=bess_usable_soc_fraction,
        bess_inverter_efficiency=bess_inverter_efficiency,
        feeder_power_factor=feeder_power_factor,
    )
    if influent_bod_mg_l < effluent_bod_mg_l:
        msg = "influent_bod_mg_l must be >= effluent_bod_mg_l"
        raise ValueError(msg)
    if influent_tkn_mg_l < effluent_tkn_mg_l:
        msg = "influent_tkn_mg_l must be >= effluent_tkn_mg_l"
        raise ValueError(msg)
    if volatile_solids_destruction_pct > 100.0:
        msg = "volatile_solids_destruction_pct must be <= 100"
        raise ValueError(msg)
    bess_dispatchable_kwh = bess_nominal_kwh * bess_usable_soc_fraction * bess_inverter_efficiency
    if bess_reserve_kwh > bess_dispatchable_kwh:
        msg = "bess_reserve_kwh must be <= dispatchable BESS energy"
        raise ValueError(msg)

    bod_removed_kg_d = flow_rate_m3_d * (influent_bod_mg_l - effluent_bod_mg_l) / 1000.0
    nitrogen_removed_kg_d = flow_rate_m3_d * (influent_tkn_mg_l - effluent_tkn_mg_l) / 1000.0
    denitrified_nitrogen_kg_d = flow_rate_m3_d * denitrified_nitrogen_mg_l / 1000.0
    carbonaceous_oxygen_kg_d = max(bod_removed_kg_d - 1.42 * sludge_production_kg_d, 0.0)
    nitrogenous_oxygen_kg_d = 4.57 * nitrogen_removed_kg_d
    denitrification_credit_kg_d = 2.86 * denitrified_nitrogen_kg_d
    total_oxygen_kg_d = max(
        carbonaceous_oxygen_kg_d + nitrogenous_oxygen_kg_d - denitrification_credit_kg_d,
        0.0,
    )

    oxygen_transfer_kg_nm3 = air_oxygen_mass_fraction * air_density_kg_nm3 * field_transfer_efficiency
    required_airflow_nm3_h = total_oxygen_kg_d / 24.0 / oxygen_transfer_kg_nm3
    blower_capacity_oxygen_kg_d = blower_airflow_capacity_nm3_h * 24.0 * oxygen_transfer_kg_nm3
    oxygen_capacity_margin_kg_d = blower_capacity_oxygen_kg_d - total_oxygen_kg_d

    blower_airflow_m3_s = required_airflow_nm3_h / 3600.0
    blower_shaft_power_kw = blower_airflow_m3_s * blower_discharge_pressure_kpa / blower_efficiency
    blower_input_power_kw = blower_shaft_power_kw / blower_motor_efficiency
    blower_motor_margin_kw = selected_blower_motor_kw - blower_input_power_kw

    volatile_solids_destroyed_kg_d = volatile_solids_feed_kg_d * volatile_solids_destruction_pct / 100.0
    biogas_m3_d = volatile_solids_destroyed_kg_d * biogas_yield_m3_kg_vs
    methane_m3_d = biogas_m3_d * methane_fraction
    methane_energy_kwh_d = methane_m3_d * methane_energy_kwh_m3
    biogas_electric_energy_kwh_d = methane_energy_kwh_d * chp_electrical_efficiency

    critical_process_load_kw = blower_input_power_kw + mixer_load_kw + recycle_pump_load_kw + controls_load_kw
    daily_process_energy_kwh = critical_process_load_kw * 24.0
    usable_bess_energy_kwh = bess_dispatchable_kwh - bess_reserve_kwh
    onsite_energy_available_kwh = biogas_electric_energy_kwh_d + pv_generation_kwh_d + usable_bess_energy_kwh
    island_energy_margin_kwh = onsite_energy_available_kwh - daily_process_energy_kwh
    process_energy_intensity_kwh_m3 = daily_process_energy_kwh / flow_rate_m3_d
    onsite_energy_fraction = min(onsite_energy_available_kwh / daily_process_energy_kwh, 1.0)

    apparent_power_kva = critical_process_load_kw / feeder_power_factor
    feeder_current_a = apparent_power_kva * 1000.0 / (math.sqrt(3.0) * feeder_voltage_v)
    reactive_factor = math.sqrt(max(1.0 - feeder_power_factor**2, 0.0))
    voltage_drop_v = (
        math.sqrt(3.0)
        * feeder_current_a
        * feeder_length_km
        * (feeder_resistance_ohm_per_km * feeder_power_factor + feeder_reactance_ohm_per_km * reactive_factor)
    )
    feeder_voltage_drop_percent = voltage_drop_v / feeder_voltage_v * 100.0
    voltage_drop_margin_percent = max_voltage_drop_percent - feeder_voltage_drop_percent

    overall_pass_score = (
        1.0
        if min(
            oxygen_capacity_margin_kg_d,
            blower_motor_margin_kw,
            island_energy_margin_kwh,
            voltage_drop_margin_percent,
        )
        >= 0.0
        else 0.0
    )

    return {
        "bod_removed_kg_d": round(bod_removed_kg_d, 3),
        "carbonaceous_oxygen_kg_d": round(carbonaceous_oxygen_kg_d, 3),
        "nitrogenous_oxygen_kg_d": round(nitrogenous_oxygen_kg_d, 3),
        "denitrification_credit_kg_d": round(denitrification_credit_kg_d, 3),
        "total_oxygen_kg_d": round(total_oxygen_kg_d, 3),
        "required_airflow_nm3_h": round(required_airflow_nm3_h, 3),
        "blower_capacity_oxygen_kg_d": round(blower_capacity_oxygen_kg_d, 3),
        "oxygen_capacity_margin_kg_d": round(oxygen_capacity_margin_kg_d, 3),
        "blower_shaft_power_kw": round(blower_shaft_power_kw, 3),
        "blower_input_power_kw": round(blower_input_power_kw, 3),
        "blower_motor_margin_kw": round(blower_motor_margin_kw, 3),
        "volatile_solids_destroyed_kg_d": round(volatile_solids_destroyed_kg_d, 3),
        "biogas_m3_d": round(biogas_m3_d, 3),
        "methane_m3_d": round(methane_m3_d, 3),
        "methane_energy_kwh_d": round(methane_energy_kwh_d, 3),
        "biogas_electric_energy_kwh_d": round(biogas_electric_energy_kwh_d, 3),
        "critical_process_load_kw": round(critical_process_load_kw, 3),
        "daily_process_energy_kwh": round(daily_process_energy_kwh, 3),
        "usable_bess_energy_kwh": round(usable_bess_energy_kwh, 3),
        "onsite_energy_available_kwh": round(onsite_energy_available_kwh, 3),
        "island_energy_margin_kwh": round(island_energy_margin_kwh, 3),
        "process_energy_intensity_kwh_m3": round(process_energy_intensity_kwh_m3, 3),
        "onsite_energy_fraction": round(onsite_energy_fraction, 3),
        "feeder_current_a": round(feeder_current_a, 3),
        "feeder_voltage_drop_percent": round(feeder_voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
