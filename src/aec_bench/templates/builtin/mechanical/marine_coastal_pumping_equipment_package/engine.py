# ABOUTME: Computes SSC-06 marine and coastal pumping equipment metrics.
# ABOUTME: Combines tidal head, pump power, backup runtime, freeboard, and corrosion margin checks.

from __future__ import annotations


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


def compute(
    pump_flow_l_s: float,
    static_lift_m: float,
    tailwater_surcharge_m: float,
    pipe_loss_m: float,
    flap_gate_loss_m: float,
    seawater_density_kg_m3: float,
    pump_efficiency: float,
    motor_efficiency: float,
    controls_load_kw: float,
    generator_capacity_kw: float,
    fuel_available_l: float,
    generator_energy_kwh_per_l: float,
    equipment_elevation_m: float,
    design_flood_level_m: float,
    minimum_freeboard_m: float,
    corrosion_allowance_mm: float,
    required_corrosion_allowance_mm: float,
) -> dict[str, float]:
    """Compute source-bound coastal pumping, backup, freeboard, and corrosion metrics."""
    _require_positive(
        pump_flow_l_s=pump_flow_l_s,
        static_lift_m=static_lift_m,
        seawater_density_kg_m3=seawater_density_kg_m3,
        pump_efficiency=pump_efficiency,
        motor_efficiency=motor_efficiency,
        generator_capacity_kw=generator_capacity_kw,
        fuel_available_l=fuel_available_l,
        generator_energy_kwh_per_l=generator_energy_kwh_per_l,
        equipment_elevation_m=equipment_elevation_m,
        design_flood_level_m=design_flood_level_m,
        minimum_freeboard_m=minimum_freeboard_m,
        corrosion_allowance_mm=corrosion_allowance_mm,
        required_corrosion_allowance_mm=required_corrosion_allowance_mm,
    )
    _require_nonnegative(
        tailwater_surcharge_m=tailwater_surcharge_m,
        pipe_loss_m=pipe_loss_m,
        flap_gate_loss_m=flap_gate_loss_m,
        controls_load_kw=controls_load_kw,
    )
    if pump_efficiency > 1.0 or motor_efficiency > 1.0:
        msg = "efficiency values must be <= 1"
        raise ValueError(msg)

    total_pumping_head_m = static_lift_m + tailwater_surcharge_m + pipe_loss_m + flap_gate_loss_m
    pump_hydraulic_power_kw = seawater_density_kg_m3 * 9.81 * (pump_flow_l_s / 1000.0) * total_pumping_head_m / 1000.0
    pump_input_power_kw = pump_hydraulic_power_kw / (pump_efficiency * motor_efficiency)
    backup_generator_load_kw = pump_input_power_kw + controls_load_kw
    generator_capacity_margin_kw = generator_capacity_kw - backup_generator_load_kw
    backup_runtime_hr = fuel_available_l * generator_energy_kwh_per_l / backup_generator_load_kw
    equipment_freeboard_m = equipment_elevation_m - design_flood_level_m
    equipment_freeboard_margin_m = equipment_freeboard_m - minimum_freeboard_m
    corrosion_allowance_margin_mm = corrosion_allowance_mm - required_corrosion_allowance_mm
    overall_pass_score = (
        1.0
        if min(generator_capacity_margin_kw, equipment_freeboard_margin_m, corrosion_allowance_margin_mm) >= 0.0
        else 0.0
    )

    return {
        "total_pumping_head_m": round(total_pumping_head_m, 3),
        "pump_hydraulic_power_kw": round(pump_hydraulic_power_kw, 3),
        "pump_input_power_kw": round(pump_input_power_kw, 3),
        "backup_generator_load_kw": round(backup_generator_load_kw, 3),
        "generator_capacity_margin_kw": round(generator_capacity_margin_kw, 3),
        "backup_runtime_hr": round(backup_runtime_hr, 3),
        "equipment_freeboard_m": round(equipment_freeboard_m, 3),
        "equipment_freeboard_margin_m": round(equipment_freeboard_margin_m, 3),
        "corrosion_allowance_margin_mm": round(corrosion_allowance_margin_mm, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
