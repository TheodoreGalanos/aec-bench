# ABOUTME: Tests for mechanical and structural built-in formula templates.
# ABOUTME: Verifies closed-form engine outputs and registry loading for backlog batches.

from pathlib import Path

import pytest

from aec_bench.generation.sampler import sample_instance
from aec_bench.templates.builtin.mechanical.a_weighting.engine import (
    compute as compute_a_weighting,
)
from aec_bench.templates.builtin.mechanical.air_changes.engine import (
    compute as compute_air_changes,
)
from aec_bench.templates.builtin.mechanical.air_demand.engine import (
    compute as compute_air_demand,
)
from aec_bench.templates.builtin.mechanical.available_flow_calculation.engine import (
    compute as compute_available_flow,
)
from aec_bench.templates.builtin.mechanical.biogas_production.engine import (
    compute as compute_biogas_production,
)
from aec_bench.templates.builtin.mechanical.braking_distance.engine import (
    compute as compute_braking_distance,
)
from aec_bench.templates.builtin.mechanical.chemical_dosing.engine import (
    compute as compute_chemical_dosing,
)
from aec_bench.templates.builtin.mechanical.cstr_volume.engine import (
    compute as compute_cstr_volume,
)
from aec_bench.templates.builtin.mechanical.davis_resistance.engine import (
    compute as compute_davis_resistance,
)
from aec_bench.templates.builtin.mechanical.distance_attenuation.engine import (
    compute as compute_distance_attenuation,
)
from aec_bench.templates.builtin.mechanical.egress_width.engine import (
    compute as compute_egress_width,
)
from aec_bench.templates.builtin.mechanical.elevation_pressure.engine import (
    compute as compute_elevation_pressure,
)
from aec_bench.templates.builtin.mechanical.friction_loss_hazen_williams.engine import (
    compute as compute_friction_loss_hazen_williams,
)
from aec_bench.templates.builtin.mechanical.gas_load_calculation.engine import (
    compute as compute_gas_load,
)
from aec_bench.templates.builtin.mechanical.gci_calculation.engine import (
    compute as compute_gci_calculation,
)
from aec_bench.templates.builtin.mechanical.hazen_williams_friction.engine import (
    compute as compute_hazen_williams_friction,
)
from aec_bench.templates.builtin.mechanical.hrt_calculation.engine import (
    compute as compute_hrt,
)
from aec_bench.templates.builtin.mechanical.joukowsky_pressure.engine import (
    compute as compute_joukowsky_pressure,
)
from aec_bench.templates.builtin.mechanical.lmtd_calculation.engine import (
    compute as compute_lmtd,
)
from aec_bench.templates.builtin.mechanical.mass_balance.engine import (
    compute as compute_mass_balance,
)
from aec_bench.templates.builtin.mechanical.miner_fatigue.engine import (
    compute as compute_miner_fatigue,
)
from aec_bench.templates.builtin.mechanical.minor_losses_calculation.engine import (
    compute as compute_minor_losses,
)
from aec_bench.templates.builtin.mechanical.mlss_inventory.engine import (
    compute as compute_mlss_inventory,
)
from aec_bench.templates.builtin.mechanical.nac_load_calculation.engine import (
    compute as compute_nac_load,
)
from aec_bench.templates.builtin.mechanical.nitrification_srt.engine import (
    compute as compute_nitrification_srt,
)
from aec_bench.templates.builtin.mechanical.npsh_available.engine import (
    compute as compute_npsh_available,
)
from aec_bench.templates.builtin.mechanical.occupant_load.engine import (
    compute as compute_occupant_load,
)
from aec_bench.templates.builtin.mechanical.oxygen_requirements.engine import (
    compute as compute_oxygen_requirements,
)
from aec_bench.templates.builtin.mechanical.pfr_volume.engine import (
    compute as compute_pfr_volume,
)
from aec_bench.templates.builtin.mechanical.por_aor_compliance.engine import (
    compute as compute_por_aor_compliance,
)
from aec_bench.templates.builtin.mechanical.pressure_loss_calculation.engine import (
    compute as compute_pressure_loss_calculation,
)
from aec_bench.templates.builtin.mechanical.pump_affinity_laws.engine import (
    compute as compute_pump_affinity,
)
from aec_bench.templates.builtin.mechanical.pump_head_calculation.engine import (
    compute as compute_pump_head,
)
from aec_bench.templates.builtin.mechanical.pump_power_calculation.engine import (
    compute as compute_pump_power,
)
from aec_bench.templates.builtin.mechanical.pump_power_efficiency.engine import (
    compute as compute_pump_power_efficiency,
)
from aec_bench.templates.builtin.mechanical.sabine_rt60.engine import (
    compute as compute_sabine_rt60,
)
from aec_bench.templates.builtin.mechanical.slr_calculation.engine import (
    compute as compute_slr,
)
from aec_bench.templates.builtin.mechanical.sludge_production.engine import (
    compute as compute_sludge_production,
)
from aec_bench.templates.builtin.mechanical.sor_calculation.engine import (
    compute as compute_sor,
)
from aec_bench.templates.builtin.mechanical.spl_log_sum.engine import (
    compute as compute_spl_log_sum,
)
from aec_bench.templates.builtin.mechanical.sprinkler_discharge.engine import (
    compute as compute_sprinkler_discharge,
)
from aec_bench.templates.builtin.mechanical.srt_calculation.engine import (
    compute as compute_srt,
)
from aec_bench.templates.builtin.mechanical.steel_critical_temp.engine import (
    compute as compute_steel_critical_temp,
)
from aec_bench.templates.builtin.mechanical.t_squared_hrr.engine import (
    compute as compute_t_squared_hrr,
)
from aec_bench.templates.builtin.mechanical.thrust_force_calculation.engine import (
    compute as compute_thrust_force,
)
from aec_bench.templates.builtin.mechanical.velocity_check.engine import (
    compute as compute_velocity_check,
)
from aec_bench.templates.builtin.mechanical.vibration_transmissibility.engine import (
    compute as compute_vibration_transmissibility,
)
from aec_bench.templates.builtin.mechanical.visibility_criterion.engine import (
    compute as compute_visibility_criterion,
)
from aec_bench.templates.builtin.mechanical.water_supply_curve.engine import (
    compute as compute_water_supply_curve,
)
from aec_bench.templates.builtin.mechanical.wave_speed_calculation.engine import (
    compute as compute_wave_speed,
)
from aec_bench.templates.builtin.structural.berthing_energy_calc.engine import (
    compute as compute_berthing_energy,
)
from aec_bench.templates.builtin.structural.bracket_load_calc.engine import (
    compute as compute_bracket_load,
)
from aec_bench.templates.builtin.structural.carbon_equivalent_calc.engine import (
    compute as compute_carbon_equivalent,
)
from aec_bench.templates.builtin.structural.composite_section.engine import (
    compute as compute_composite_section,
)
from aec_bench.templates.builtin.structural.construction_tolerance.engine import (
    compute as compute_construction_tolerance,
)
from aec_bench.templates.builtin.structural.effective_wind_area.engine import (
    compute as compute_effective_wind_area,
)
from aec_bench.templates.builtin.structural.fender_energy_check.engine import (
    compute as compute_fender_energy,
)
from aec_bench.templates.builtin.structural.gravity_base_stability.engine import (
    compute as compute_gravity_base_stability,
)
from aec_bench.templates.builtin.structural.lap_splice_length.engine import (
    compute as compute_lap_splice_length,
)
from aec_bench.templates.builtin.structural.load_combinations.engine import (
    compute as compute_load_combinations,
)
from aec_bench.templates.builtin.structural.mooring_line_capacity.engine import (
    compute as compute_mooring_line_capacity,
)
from aec_bench.templates.builtin.structural.pipe_support_dead_load.engine import (
    compute as compute_pipe_support_dead_load,
)
from aec_bench.templates.builtin.structural.scm_substitution.engine import (
    compute as compute_scm_substitution,
)
from aec_bench.templates.builtin.structural.target_strength_calc.engine import (
    compute as compute_target_strength,
)
from aec_bench.templates.builtin.structural.thermal_movement_calc.engine import (
    compute as compute_thermal_movement,
)
from aec_bench.templates.registry import load_template

TEMPLATE_ROOT = Path("src/aec_bench/templates/builtin")


@pytest.mark.parametrize(
    "template_dir, expected_name, expected_discipline",
    [
        ("mechanical/pump_affinity_laws", "pump-affinity-laws", "mechanical"),
        ("mechanical/distance_attenuation", "distance-attenuation", "mechanical"),
        ("mechanical/t_squared_hrr", "t-squared-hrr", "mechanical"),
        ("mechanical/npsh_available", "npsh-available", "mechanical"),
        ("mechanical/pump_head_calculation", "pump-head-calculation", "mechanical"),
        ("mechanical/wave_speed_calculation", "wave-speed-calculation", "mechanical"),
        ("mechanical/steel_critical_temp", "steel-critical-temp", "mechanical"),
        ("mechanical/hrt_calculation", "hrt-calculation", "mechanical"),
        ("mechanical/mlss_inventory", "mlss-inventory", "mechanical"),
        ("mechanical/chemical_dosing", "chemical-dosing", "mechanical"),
        ("mechanical/pfr_volume", "pfr-volume", "mechanical"),
        ("mechanical/cstr_volume", "cstr-volume", "mechanical"),
        ("mechanical/sabine_rt60", "sabine-rt60", "mechanical"),
        ("mechanical/lmtd_calculation", "lmtd-calculation", "mechanical"),
        ("mechanical/braking_distance", "braking-distance", "mechanical"),
        ("mechanical/spl_log_sum", "spl-log-sum", "mechanical"),
        ("mechanical/srt_calculation", "srt-calculation", "mechanical"),
        ("mechanical/oxygen_requirements", "oxygen-requirements", "mechanical"),
        ("mechanical/sludge_production", "sludge-production", "mechanical"),
        ("mechanical/sor_calculation", "sor-calculation", "mechanical"),
        ("mechanical/slr_calculation", "slr-calculation", "mechanical"),
        ("mechanical/minor_losses_calculation", "minor-losses-calculation", "mechanical"),
        ("mechanical/air_changes", "air-changes", "mechanical"),
        ("mechanical/nac_load_calculation", "nac-load-calculation", "mechanical"),
        ("mechanical/joukowsky_pressure", "joukowsky-pressure", "mechanical"),
        ("mechanical/elevation_pressure", "elevation-pressure", "mechanical"),
        ("mechanical/sprinkler_discharge", "sprinkler-discharge", "mechanical"),
        (
            "mechanical/vibration_transmissibility",
            "vibration-transmissibility",
            "mechanical",
        ),
        ("mechanical/occupant_load", "occupant-load", "mechanical"),
        ("mechanical/egress_width", "egress-width", "mechanical"),
        ("mechanical/pump_power_calculation", "pump-power-calculation", "mechanical"),
        ("mechanical/thrust_force_calculation", "thrust-force-calculation", "mechanical"),
        ("mechanical/gas_load_calculation", "gas-load-calculation", "mechanical"),
        ("mechanical/air_demand", "air-demand", "mechanical"),
        ("mechanical/velocity_check", "velocity-check", "mechanical"),
        ("mechanical/biogas_production", "biogas-production", "mechanical"),
        ("mechanical/por_aor_compliance", "por-aor-compliance", "mechanical"),
        ("mechanical/miner_fatigue", "miner-fatigue", "mechanical"),
        ("mechanical/visibility_criterion", "visibility-criterion", "mechanical"),
        ("mechanical/mass_balance", "mass-balance", "mechanical"),
        (
            "mechanical/available_flow_calculation",
            "available-flow-calculation",
            "mechanical",
        ),
        (
            "mechanical/hazen_williams_friction",
            "hazen-williams-friction",
            "mechanical",
        ),
        ("mechanical/nitrification_srt", "nitrification-srt", "mechanical"),
        ("mechanical/davis_resistance", "davis-resistance", "mechanical"),
        ("mechanical/a_weighting", "a-weighting", "mechanical"),
        ("mechanical/water_supply_curve", "water-supply-curve", "mechanical"),
        ("mechanical/gci_calculation", "gci-calculation", "mechanical"),
        (
            "mechanical/pressure_loss_calculation",
            "pressure-loss-calculation",
            "mechanical",
        ),
        ("mechanical/pump_power_efficiency", "pump-power-efficiency", "mechanical"),
        (
            "mechanical/friction_loss_hazen_williams",
            "friction-loss-hazen-williams",
            "mechanical",
        ),
        ("structural/thermal_movement_calc", "thermal-movement-calc", "structural"),
        ("structural/target_strength_calc", "target-strength-calc", "structural"),
        ("structural/carbon_equivalent_calc", "carbon-equivalent-calc", "structural"),
        ("structural/berthing_energy_calc", "berthing-energy-calc", "structural"),
        ("structural/fender_energy_check", "fender-energy-check", "structural"),
        ("structural/effective_wind_area", "effective-wind-area", "structural"),
        ("structural/load_combinations", "load-combinations", "structural"),
        ("structural/mooring_line_capacity", "mooring-line-capacity", "structural"),
        ("structural/construction_tolerance", "construction-tolerance", "structural"),
        ("structural/pipe_support_dead_load", "pipe-support-dead-load", "structural"),
        ("structural/bracket_load_calc", "bracket-load-calc", "structural"),
        ("structural/scm_substitution", "scm-substitution", "structural"),
        ("structural/lap_splice_length", "lap-splice-length", "structural"),
        (
            "structural/gravity_base_stability",
            "gravity-base-stability",
            "structural",
        ),
        ("structural/composite_section", "composite-section", "structural"),
    ],
)
def test_backlog_templates_load_from_registry(
    template_dir: str,
    expected_name: str,
    expected_discipline: str,
) -> None:
    config, path = load_template(TEMPLATE_ROOT / template_dir)

    assert path == TEMPLATE_ROOT / template_dir
    assert config.meta.name == expected_name
    assert config.meta.discipline == expected_discipline
    assert config.meta.long_description
    assert config.params
    assert config.outputs
    assert config.archetypes
    assert {"easy", "medium", "hard"} <= set(config.difficulty)


def test_pump_affinity_laws_engine_matches_speed_scaling() -> None:
    result = compute_pump_affinity(
        original_speed_rpm=1500.0,
        new_speed_rpm=1800.0,
        original_flow_l_s=100.0,
        original_head_m=40.0,
        original_power_kw=75.0,
    )

    assert result == {
        "speed_ratio": 1.2,
        "new_flow_l_s": 120.0,
        "new_head_m": 57.6,
        "new_power_kw": 129.6,
    }


def test_distance_attenuation_engine_matches_inverse_square_law() -> None:
    result = compute_distance_attenuation(
        reference_spl_db=90.0,
        reference_distance_m=1.0,
        target_distance_m=10.0,
    )

    assert result == {
        "distance_ratio": 10.0,
        "attenuation_db": 20.0,
        "target_spl_db": 70.0,
    }


def test_thermal_movement_engine_matches_first_principles() -> None:
    result = compute_thermal_movement(
        member_length_mm=6000.0,
        temperature_range_c=50.0,
        coefficient_thermal_expansion_microstrain_c=23.0,
        joint_safety_factor=1.25,
    )

    assert result == {
        "thermal_movement_mm": 6.9,
        "expansion_movement_mm": 3.45,
        "contraction_movement_mm": 3.45,
        "accommodation_required_mm": 8.62,
    }


def test_target_strength_engine_uses_governing_margin() -> None:
    result = compute_target_strength(
        specified_strength_mpa=40.0,
        standard_deviation_mpa=4.0,
        k_factor=1.65,
        minimum_margin_mpa=8.0,
    )

    assert result == {
        "statistical_margin_mpa": 6.6,
        "governing_margin_mpa": 8.0,
        "target_mean_strength_mpa": 48.0,
        "margin_above_specified_mpa": 8.0,
    }


def test_carbon_equivalent_engine_matches_iiw_formula() -> None:
    result = compute_carbon_equivalent(
        carbon_pct=0.18,
        manganese_pct=1.2,
        chromium_pct=0.3,
        molybdenum_pct=0.1,
        vanadium_pct=0.05,
        nickel_pct=0.2,
        copper_pct=0.1,
        caution_threshold_pct=0.4,
        high_risk_threshold_pct=0.55,
    )

    assert result == {
        "carbon_equivalent_pct": 0.49,
        "caution_margin_pct": 0.09,
        "high_risk_margin_pct": -0.06,
        "weldability_risk_index": 1.0,
        "preheat_indicated": 1.0,
    }


def test_t_squared_hrr_engine_applies_peak_limit() -> None:
    result = compute_t_squared_hrr(
        growth_coefficient_kw_s2=0.012,
        time_from_ignition_s=300.0,
        peak_hrr_kw=1000.0,
    )

    assert result == {
        "unclipped_hrr_kw": 1080.0,
        "hrr_at_time_kw": 1000.0,
        "time_to_peak_s": 288.68,
        "peak_limited": 1.0,
    }


def test_npsh_available_engine_converts_pressure_terms_to_head() -> None:
    result = compute_npsh_available(
        suction_vessel_pressure_kpa_abs=101.325,
        liquid_level_above_pump_m=3.0,
        suction_pipe_losses_kpa=10.0,
        vapor_pressure_kpa_abs=2.34,
        fluid_density_kg_m3=998.0,
        npsh_required_m=4.0,
    )

    assert result == {
        "pressure_head_m": 10.35,
        "vapor_pressure_head_m": 0.24,
        "loss_head_m": 1.02,
        "npsh_available_m": 12.09,
        "cavitation_margin_m": 8.09,
        "margin_ratio": 3.02,
    }


def test_pump_head_engine_converts_pressure_and_loss_to_head() -> None:
    result = compute_pump_head(
        flow_rate_m3_h=360.0,
        suction_pressure_kpa=100.0,
        discharge_pressure_kpa=500.0,
        elevation_difference_m=20.0,
        pipe_friction_losses_kpa=50.0,
        fluid_density_kg_m3=1000.0,
    )

    assert result == {
        "static_head_m": 20.0,
        "pressure_head_differential_m": 40.77,
        "friction_head_m": 5.1,
        "total_dynamic_head_m": 65.87,
        "hydraulic_power_kw": 64.62,
    }


def test_wave_speed_engine_combines_fluid_and_pipe_flexibility() -> None:
    result = compute_wave_speed(
        fluid_bulk_modulus_gpa=2.2,
        fluid_density_kg_m3=1000.0,
        pipe_elastic_modulus_gpa=200.0,
        pipe_diameter_mm=500.0,
        pipe_wall_thickness_mm=10.0,
        restraint_condition="fully_restrained",
    )

    assert result == {
        "fluid_only_wave_speed_m_s": 1483.24,
        "flexibility_factor": 1.24,
        "wave_speed_m_s": 1191.37,
        "pipe_flexibility_ratio": 0.55,
    }


def test_steel_critical_temperature_engine_uses_load_ratio_formula() -> None:
    result = compute_steel_critical_temp(
        load_ratio=0.5,
        protection_trigger_c=550.0,
    )

    assert result == {
        "critical_temperature_c": 584.67,
        "protection_margin_c": 34.67,
        "protection_required": 0.0,
    }


def test_berthing_energy_engine_applies_vessel_coefficients() -> None:
    result = compute_berthing_energy(
        vessel_displacement_t=10000.0,
        approach_velocity_m_s=0.15,
        added_mass_coefficient=1.5,
        eccentricity_coefficient=0.75,
        berth_configuration_coefficient=1.0,
        softness_coefficient=0.9,
        safety_factor=1.25,
    )

    assert result == {
        "kinetic_energy_knm": 112.5,
        "characteristic_energy_knm": 113.91,
        "design_energy_knm": 142.38,
        "coefficient_product": 1.01,
    }


def test_fender_energy_engine_applies_capacity_correction_factors() -> None:
    result = compute_fender_energy(
        design_berthing_energy_knm=1000.0,
        fender_rated_energy_knm=1500.0,
        temperature_factor=0.9,
        velocity_factor=1.1,
        angular_factor=0.8,
        manufacturing_tolerance_factor=0.95,
    )

    assert result == {
        "correction_factor": 0.75,
        "corrected_capacity_knm": 1128.6,
        "energy_utilisation_ratio": 0.89,
        "capacity_margin_knm": 128.6,
    }


def test_effective_wind_area_engine_uses_governing_area() -> None:
    result = compute_effective_wind_area(
        panel_width_m=1.2,
        panel_height_m=2.4,
        supporting_member_span_m=3.0,
        tributary_width_m=1.5,
        minimum_effective_area_m2=1.0,
    )

    assert result == {
        "panel_area_m2": 2.88,
        "member_tributary_area_m2": 4.5,
        "effective_wind_area_m2": 4.5,
        "area_averaging_ratio": 4.5,
    }


def test_hrt_engine_converts_days_to_hours() -> None:
    result = compute_hrt(
        reactor_volume_m3=1200.0,
        flow_rate_m3_d=4800.0,
    )

    assert result == {
        "hrt_days": 0.25,
        "hrt_hours": 6.0,
        "flow_rate_m3_h": 200.0,
    }


def test_mlss_inventory_engine_converts_concentration_to_mass() -> None:
    result = compute_mlss_inventory(
        aeration_volume_m3=5000.0,
        mlss_concentration_mg_l=3000.0,
        mlvss_fraction=0.7,
    )

    assert result == {
        "mlss_inventory_kg": 15000.0,
        "mlvss_inventory_kg": 10500.0,
        "inert_solids_inventory_kg": 4500.0,
    }


def test_chemical_dosing_engine_converts_active_dose_to_product_feed() -> None:
    result = compute_chemical_dosing(
        flow_rate_m3_d=10000.0,
        target_dose_mg_l=5.0,
        product_strength_pct=12.5,
        product_density_kg_l=1.2,
    )

    assert result == {
        "active_mass_feed_kg_d": 50.0,
        "product_mass_feed_kg_d": 400.0,
        "volume_feed_l_d": 333.33,
        "annual_product_consumption_t": 146.0,
    }


def test_pfr_volume_engine_uses_first_order_design_equation() -> None:
    result = compute_pfr_volume(
        volumetric_flow_m3_h=10.0,
        inlet_concentration_kmol_m3=2.0,
        required_conversion_pct=80.0,
        rate_constant_h_inv=0.5,
    )

    assert result == {
        "molar_feed_kmol_h": 20.0,
        "outlet_concentration_kmol_m3": 0.4,
        "space_time_h": 3.22,
        "required_volume_m3": 32.19,
    }


def test_cstr_volume_engine_uses_first_order_outlet_rate() -> None:
    result = compute_cstr_volume(
        volumetric_flow_m3_h=10.0,
        inlet_concentration_kmol_m3=2.0,
        required_conversion_pct=80.0,
        rate_constant_h_inv=0.5,
    )

    assert result == {
        "outlet_concentration_kmol_m3": 0.4,
        "outlet_reaction_rate_kmol_m3_h": 0.2,
        "space_time_h": 8.0,
        "required_volume_m3": 80.0,
    }


def test_sabine_rt60_engine_sums_equivalent_absorption_area() -> None:
    result = compute_sabine_rt60(
        room_volume_m3=300.0,
        floor_area_m2=100.0,
        floor_absorption=0.1,
        wall_area_m2=200.0,
        wall_absorption=0.05,
        ceiling_area_m2=100.0,
        ceiling_absorption=0.7,
    )

    assert result == {
        "equivalent_absorption_area_m2": 90.0,
        "average_absorption_coefficient": 0.23,
        "rt60_s": 0.54,
    }


def test_lmtd_engine_calculates_counterflow_heat_duty() -> None:
    result = compute_lmtd(
        hot_inlet_c=150.0,
        hot_outlet_c=90.0,
        cold_inlet_c=30.0,
        cold_outlet_c=70.0,
        overall_u_kw_m2_c=0.5,
        heat_transfer_area_m2=100.0,
        correction_factor=0.9,
        flow_arrangement="counterflow",
    )

    assert result == {
        "delta_t1_c": 80.0,
        "delta_t2_c": 60.0,
        "lmtd_c": 69.52,
        "corrected_mtd_c": 62.57,
        "heat_duty_kw": 3128.45,
        "minimum_approach_c": 60.0,
    }


def test_lmtd_template_samples_valid_parallel_temperature_differences() -> None:
    config, _ = load_template(TEMPLATE_ROOT / "mechanical/lmtd_calculation")

    instance = sample_instance(
        config,
        compute_lmtd,
        "medium",
        seed=20260936,
        instance_index=412,
    )

    assert instance.all_params["flow_arrangement"] == "parallel"
    assert instance.ground_truth["delta_t1_c"] > 0.0
    assert instance.ground_truth["delta_t2_c"] > 0.0
    assert instance.ground_truth["lmtd_c"] > 0.0


def test_braking_distance_engine_applies_adhesion_limit_and_gradient() -> None:
    result = compute_braking_distance(
        train_mass_t=100.0,
        initial_speed_km_h=80.0,
        brake_effort_kn=300.0,
        adhesion_coefficient=0.2,
        track_gradient_pct=1.0,
    )

    assert result == {
        "adhesion_limited_brake_effort_kn": 196.2,
        "net_deceleration_m_s2": 1.86,
        "stopping_distance_m": 132.47,
        "stopping_time_s": 11.92,
    }


def test_spl_log_sum_engine_adds_three_sources_logarithmically() -> None:
    result = compute_spl_log_sum(
        source_1_spl_db=80.0,
        source_2_spl_db=77.0,
        source_3_spl_db=74.0,
    )

    assert result == {
        "total_linear_energy": 175237587.68,
        "combined_spl_db": 82.44,
        "dominant_source_spl_db": 80.0,
    }


def test_srt_engine_includes_effluent_solids_loss() -> None:
    result = compute_srt(
        aeration_volume_m3=5000.0,
        mlss_concentration_mg_l=3000.0,
        was_flow_m3_d=100.0,
        was_tss_mg_l=8000.0,
        effluent_tss_mg_l=10.0,
        effluent_flow_m3_d=10000.0,
    )

    assert result == {
        "solids_in_system_kg": 15000.0,
        "solids_wasted_kg_d": 800.0,
        "effluent_solids_loss_kg_d": 100.0,
        "total_solids_loss_kg_d": 900.0,
        "srt_days": 16.67,
    }


def test_oxygen_requirements_engine_applies_nitrification_and_denitrification() -> None:
    result = compute_oxygen_requirements(
        flow_rate_m3_d=10000.0,
        influent_bod_mg_l=250.0,
        effluent_bod_mg_l=20.0,
        influent_tkn_mg_l=40.0,
        effluent_tkn_mg_l=5.0,
        sludge_production_kg_d=800.0,
        denitrified_nitrogen_mg_l=20.0,
    )

    assert result == {
        "bod_removed_kg_d": 2300.0,
        "carbonaceous_oxygen_kg_d": 1164.0,
        "nitrogenous_oxygen_kg_d": 1599.5,
        "denitrification_credit_kg_d": 572.0,
        "total_oxygen_kg_d": 2191.5,
    }


def test_sludge_production_engine_calculates_observed_yield_and_total_tss() -> None:
    result = compute_sludge_production(
        flow_rate_m3_d=10000.0,
        influent_bod_mg_l=250.0,
        effluent_bod_mg_l=20.0,
        influent_tss_mg_l=250.0,
        primary_tss_removal_pct=50.0,
        yield_coefficient=0.5,
        decay_coefficient_d_inv=0.06,
        srt_days=10.0,
        vss_to_tss_ratio=0.75,
    )

    assert result == {
        "bod_removed_kg_d": 2300.0,
        "observed_yield_vss_per_bod": 0.31,
        "biomass_production_kg_vss_d": 718.75,
        "primary_solids_kg_tss_d": 1250.0,
        "total_sludge_kg_tss_d": 2208.33,
    }


def test_sor_engine_calculates_surface_overflow_and_margin() -> None:
    result = compute_sor(
        flow_rate_m3_d=12000.0,
        clarifier_surface_area_m2=500.0,
        maximum_sor_m3_m2_d=30.0,
    )

    assert result == {
        "surface_overflow_rate_m3_m2_d": 24.0,
        "utilisation_ratio": 0.8,
        "compliance_margin_m3_m2_d": 6.0,
        "criterion_satisfied": 1.0,
    }


def test_slr_engine_converts_mlss_to_hourly_area_loading() -> None:
    result = compute_slr(
        total_flow_m3_d=15000.0,
        mlss_concentration_mg_l=3000.0,
        clarifier_surface_area_m2=750.0,
        maximum_slr_kg_m2_h=3.0,
    )

    assert result == {
        "solids_mass_flow_kg_d": 45000.0,
        "solids_loading_rate_kg_m2_h": 2.5,
        "utilisation_ratio": 0.83,
        "compliance_margin_kg_m2_h": 0.5,
        "criterion_satisfied": 1.0,
    }


def test_minor_losses_engine_sums_fitting_k_values() -> None:
    result = compute_minor_losses(
        fitting_1_k=0.3,
        fitting_1_quantity=4.0,
        fitting_2_k=1.5,
        fitting_2_quantity=2.0,
        fitting_3_k=0.8,
        fitting_3_quantity=1.0,
        flow_velocity_m_s=2.0,
        pipe_diameter_mm=200.0,
        darcy_friction_factor=0.02,
    )

    assert result == {
        "total_k": 5.0,
        "velocity_head_m": 0.2,
        "total_minor_loss_m": 1.02,
        "equivalent_length_m": 50.0,
    }


def test_load_combinations_engine_selects_governing_moment_case() -> None:
    result = compute_load_combinations(
        dead_moment_knm=100.0,
        live_moment_knm=80.0,
        wind_moment_knm=120.0,
        seismic_moment_knm=60.0,
        dead_shear_kn=20.0,
        live_shear_kn=16.0,
        wind_shear_kn=24.0,
        seismic_shear_kn=12.0,
        combo_1_dead_factor=1.2,
        combo_1_live_factor=1.5,
        combo_2_dead_factor=1.0,
        combo_2_wind_factor=1.6,
        combo_3_dead_factor=1.0,
        combo_3_seismic_factor=1.0,
    )

    assert result == {
        "combo_1_moment_knm": 240.0,
        "combo_2_moment_knm": 292.0,
        "combo_3_moment_knm": 160.0,
        "governing_moment_knm": 292.0,
        "governing_shear_kn": 58.4,
        "governing_combination_index": 2.0,
    }


def test_air_changes_engine_calculates_room_ach() -> None:
    result = compute_air_changes(
        supply_airflow_m3_h=1200.0,
        room_volume_m3=300.0,
    )

    assert result == {"air_changes_per_h": 4.0}


def test_nac_load_engine_sums_appliance_currents() -> None:
    result = compute_nac_load(
        strobe_quantity=10,
        strobe_current_a=0.075,
        horn_quantity=4,
        horn_current_a=0.05,
        speaker_quantity=2,
        speaker_current_a=0.025,
        circuit_capacity_a=3.0,
    )

    assert result == {
        "total_load_a": 1.0,
        "utilisation_pct": 33.33,
        "spare_capacity_a": 2.0,
        "passes_capacity_check": 1.0,
    }


def test_joukowsky_pressure_engine_calculates_transient_pressure() -> None:
    result = compute_joukowsky_pressure(
        fluid_density_kg_m3=1000.0,
        wave_speed_m_s=1200.0,
        velocity_change_m_s=1.5,
    )

    assert result == {
        "pressure_rise_pa": 1800000.0,
        "pressure_rise_kpa": 1800.0,
        "pressure_head_m": 183.49,
    }


def test_mooring_line_capacity_engine_checks_design_tension() -> None:
    result = compute_mooring_line_capacity(
        line_tension_kn=500.0,
        dynamic_factor=1.2,
        consequence_factor=1.1,
        mbl_kn=1000.0,
    )

    assert result == {
        "design_tension_kn": 660.0,
        "capacity_margin_ratio": 1.515,
        "reserve_capacity_kn": 340.0,
        "utilisation_ratio": 0.66,
        "passes_capacity_check": 1.0,
    }


def test_construction_tolerance_engine_calculates_slot_allowance() -> None:
    result = compute_construction_tolerance(
        fabrication_tolerance_mm=5.0,
        erection_tolerance_mm=8.0,
        survey_tolerance_mm=3.0,
        movement_allowance_mm=10.0,
        clearance_mm=4.0,
        component_length_mm=200.0,
    )

    assert result == {
        "total_allowance_mm": 30.0,
        "rss_tolerance_mm": 14.07,
        "required_slot_length_mm": 260.0,
        "clearance_included_mm": 4.0,
    }


def test_pipe_support_dead_load_engine_calculates_operating_line_load() -> None:
    result = compute_pipe_support_dead_load(
        pipe_outer_diameter_mm=200.0,
        pipe_wall_thickness_mm=10.0,
        steel_density_kg_m3=7850.0,
        contents_density_kg_m3=1000.0,
        insulation_thickness_mm=25.0,
        insulation_density_kg_m3=80.0,
        hydrotest_density_kg_m3=1000.0,
    )

    assert result == {
        "steel_pipe_load_kn_m": 0.46,
        "contents_load_kn_m": 0.25,
        "insulation_load_kn_m": 0.014,
        "operating_line_load_kn_m": 0.723,
        "hydrotest_line_load_kn_m": 0.723,
    }


def test_elevation_pressure_engine_calculates_static_pressure_change() -> None:
    result = compute_elevation_pressure(
        fluid_density_kg_m3=1000.0,
        elevation_change_m=25.0,
    )

    assert result == {
        "elevation_head_m": 25.0,
        "pressure_change_kpa": 245.25,
        "pressure_change_bar": 2.453,
    }


def test_sprinkler_discharge_engine_uses_k_factor_formula() -> None:
    result = compute_sprinkler_discharge(
        k_factor_l_min_sqrt_bar=80.0,
        pressure_bar=2.25,
    )

    assert result == {
        "discharge_l_min": 120.0,
        "discharge_l_s": 2.0,
        "pressure_kpa": 225.0,
    }


def test_vibration_transmissibility_engine_calculates_isolation_efficiency() -> None:
    result = compute_vibration_transmissibility(
        forcing_frequency_hz=30.0,
        natural_frequency_hz=10.0,
        damping_ratio=0.1,
    )

    assert result == {
        "frequency_ratio": 3.0,
        "transmissibility": 0.145,
        "isolation_efficiency_pct": 85.46,
    }


def test_bracket_load_engine_calculates_factored_resultant() -> None:
    result = compute_bracket_load(
        dead_load_kn=10.0,
        live_load_kn=5.0,
        wind_load_kn=8.0,
        dead_load_factor=1.2,
        live_load_factor=1.5,
        wind_load_factor=1.3,
    )

    assert result == {
        "service_vertical_load_kn": 15.0,
        "factored_vertical_load_kn": 19.5,
        "factored_lateral_load_kn": 10.4,
        "factored_resultant_load_kn": 22.1,
    }


def test_scm_substitution_engine_splits_binder_mass() -> None:
    result = compute_scm_substitution(
        total_binder_kg_m3=400.0,
        scm_replacement_pct=35.0,
        water_content_kg_m3=160.0,
    )

    assert result == {
        "cement_content_kg_m3": 260.0,
        "scm_content_kg_m3": 140.0,
        "cement_reduction_kg_m3": 140.0,
        "water_binder_ratio": 0.4,
    }


def test_lap_splice_length_engine_rounds_up_required_lap() -> None:
    result = compute_lap_splice_length(
        development_length_mm=650.0,
        splice_class_factor=1.3,
        bar_location_factor=1.2,
        coating_factor=1.0,
        provided_lap_length_mm=1050.0,
    )

    assert result == {
        "calculated_lap_length_mm": 1014.0,
        "rounded_lap_length_mm": 1020.0,
        "provided_margin_mm": 30.0,
        "provided_lap_satisfies": 1.0,
    }


def test_occupant_load_engine_rounds_up_design_occupants() -> None:
    result = compute_occupant_load(
        floor_area_m2=123.0,
        area_per_occupant_m2=10.0,
    )

    assert result == {
        "calculated_occupants": 12.3,
        "design_occupants": 13.0,
        "occupant_density_person_m2": 0.106,
    }


def test_egress_width_engine_calculates_width_margin() -> None:
    result = compute_egress_width(
        occupant_load=250.0,
        width_per_occupant_mm=5.0,
        provided_width_mm=1500.0,
    )

    assert result == {
        "required_width_mm": 1250.0,
        "provided_margin_mm": 250.0,
        "utilisation_ratio": 0.833,
        "width_satisfies": 1.0,
    }


def test_pump_power_engine_calculates_shaft_power() -> None:
    result = compute_pump_power(
        flow_rate_l_s=100.0,
        total_dynamic_head_m=50.0,
        fluid_density_kg_m3=1000.0,
        pump_efficiency_pct=75.0,
    )

    assert result == {
        "flow_rate_m3_s": 0.1,
        "hydraulic_power_kw": 49.05,
        "shaft_power_kw": 65.4,
        "efficiency_fraction": 0.75,
    }


def test_thrust_force_engine_calculates_bend_thrust() -> None:
    result = compute_thrust_force(
        internal_pressure_kpa=1000.0,
        pipe_internal_diameter_mm=500.0,
        bend_angle_deg=90.0,
    )

    assert result == {
        "pipe_area_m2": 0.196,
        "pressure_force_kn": 196.35,
        "bend_thrust_force_kn": 277.68,
    }


def test_gas_load_engine_applies_diversity_and_unit_conversion() -> None:
    result = compute_gas_load(
        appliance_1_load_mj_h=100.0,
        appliance_1_quantity=3.0,
        appliance_2_load_mj_h=50.0,
        appliance_2_quantity=2.0,
        appliance_3_load_mj_h=20.0,
        appliance_3_quantity=5.0,
        diversity_factor=0.8,
    )

    assert result == {
        "connected_load_mj_h": 500.0,
        "diversified_load_mj_h": 400.0,
        "connected_load_kw": 138.89,
        "diversified_load_kw": 111.11,
    }


def test_gravity_base_stability_engine_checks_eccentricity_and_bearing() -> None:
    result = compute_gravity_base_stability(
        vertical_load_kn=1000.0,
        overturning_moment_knm=100.0,
        base_width_m=4.0,
        base_length_m=5.0,
        allowable_bearing_kpa=200.0,
    )

    assert result == {
        "eccentricity_m": 0.1,
        "middle_third_limit_m": 0.667,
        "maximum_bearing_kpa": 57.5,
        "bearing_utilisation_ratio": 0.287,
        "middle_third_satisfied": 1.0,
    }


def test_air_demand_engine_applies_simultaneity() -> None:
    result = compute_air_demand(
        tool_1_flow_l_s=10.0,
        tool_1_quantity=3.0,
        tool_2_flow_l_s=5.0,
        tool_2_quantity=4.0,
        tool_3_flow_l_s=2.0,
        tool_3_quantity=5.0,
        simultaneity_factor=0.6,
    )

    assert result == {
        "connected_demand_l_s": 60.0,
        "simultaneous_demand_l_s": 36.0,
        "connected_demand_m3_min": 3.6,
        "simultaneous_demand_m3_min": 2.16,
    }


def test_velocity_check_engine_calculates_pipe_velocity_and_margins() -> None:
    result = compute_velocity_check(
        flow_rate_l_s=50.0,
        pipe_internal_diameter_mm=200.0,
        minimum_velocity_m_s=0.5,
        maximum_velocity_m_s=2.5,
    )

    assert result == {
        "pipe_area_m2": 0.031,
        "velocity_m_s": 1.59,
        "min_margin_m_s": 1.09,
        "max_margin_m_s": 0.91,
        "velocity_within_range": 1.0,
    }


def test_biogas_production_engine_calculates_methane_energy() -> None:
    result = compute_biogas_production(
        volatile_solids_feed_kg_d=1000.0,
        volatile_solids_destruction_pct=50.0,
        biogas_yield_m3_kg_vs=1.0,
        methane_fraction=0.65,
    )

    assert result == {
        "volatile_solids_destroyed_kg_d": 500.0,
        "biogas_m3_d": 500.0,
        "methane_m3_d": 325.0,
        "methane_energy_kwh_d": 3240.25,
    }


def test_por_aor_compliance_engine_checks_operating_ranges() -> None:
    result = compute_por_aor_compliance(
        operating_flow_l_s=90.0,
        best_efficiency_flow_l_s=100.0,
        por_min_ratio=0.7,
        por_max_ratio=1.2,
        aor_min_ratio=0.5,
        aor_max_ratio=1.4,
    )

    assert result == {
        "flow_ratio": 0.9,
        "por_margin_low": 0.2,
        "por_margin_high": 0.3,
        "within_por": 1.0,
        "within_aor": 1.0,
    }


def test_miner_fatigue_engine_sums_damage_bins() -> None:
    result = compute_miner_fatigue(
        applied_cycles_1=1000.0,
        allowable_cycles_1=10000.0,
        applied_cycles_2=2000.0,
        allowable_cycles_2=20000.0,
        applied_cycles_3=3000.0,
        allowable_cycles_3=100000.0,
    )

    assert result == {
        "damage_bin_1": 0.1,
        "damage_bin_2": 0.1,
        "damage_bin_3": 0.03,
        "cumulative_damage": 0.23,
        "remaining_damage_margin": 0.77,
        "fatigue_satisfies": 1.0,
    }


def test_visibility_criterion_engine_checks_tenability_margin() -> None:
    result = compute_visibility_criterion(
        extinction_coefficient_m_inv=0.5,
        visibility_constant=3.0,
        minimum_visibility_m=5.0,
    )

    assert result == {
        "visibility_m": 6.0,
        "visibility_margin_m": 1.0,
        "visibility_utilisation_ratio": 0.833,
        "criterion_satisfied": 1.0,
    }


def test_mass_balance_engine_checks_global_closure() -> None:
    result = compute_mass_balance(
        inlet_1_kg_h=100.0,
        inlet_2_kg_h=50.0,
        outlet_1_kg_h=120.0,
        outlet_2_kg_h=25.0,
        closure_tolerance_pct=5.0,
    )

    assert result == {
        "total_inlet_kg_h": 150.0,
        "total_outlet_kg_h": 145.0,
        "imbalance_kg_h": 5.0,
        "closure_error_pct": 3.333,
        "closure_satisfied": 1.0,
    }


def test_available_flow_engine_extrapolates_hydrant_test_flow() -> None:
    result = compute_available_flow(
        static_pressure_kpa=700.0,
        residual_pressure_kpa=500.0,
        test_flow_l_s=50.0,
        target_residual_pressure_kpa=200.0,
    )

    assert result == {
        "pressure_drop_test_kpa": 200.0,
        "pressure_drop_target_kpa": 500.0,
        "available_flow_l_s": 82.01,
        "available_flow_m3_h": 295.23,
    }


def test_hazen_williams_engine_calculates_pipe_friction_loss() -> None:
    result = compute_hazen_williams_friction(
        pipe_length_m=1000.0,
        pipe_internal_diameter_mm=300.0,
        flow_rate_l_s=50.0,
        hazen_williams_c=120.0,
        fluid_density_kg_m3=1000.0,
    )

    assert result == {
        "flow_rate_m3_s": 0.05,
        "head_loss_m": 2.07,
        "pressure_loss_kpa": 20.26,
        "hydraulic_gradient_m_per_m": 0.0021,
    }


def test_nitrification_srt_engine_applies_growth_limitation_factors() -> None:
    result = compute_nitrification_srt(
        max_specific_growth_d=0.9,
        theta=1.08,
        wastewater_temperature_c=15.0,
        ammonia_n_mg_l=2.0,
        half_saturation_n_mg_l=1.0,
        dissolved_oxygen_mg_l=2.0,
        oxygen_half_saturation_mg_l=0.5,
        decay_rate_d=0.05,
        safety_factor=1.5,
    )

    assert result == {
        "temperature_corrected_growth_d": 0.613,
        "substrate_factor": 0.667,
        "oxygen_factor": 0.8,
        "net_growth_d": 0.277,
        "required_srt_days": 5.42,
    }


def test_davis_resistance_engine_calculates_tractive_power() -> None:
    result = compute_davis_resistance(
        train_mass_t=200.0,
        speed_km_h=80.0,
        coefficient_a_n_t=20.0,
        coefficient_b_n_t_km_h=0.5,
        coefficient_c_n_t_km_h2=0.01,
    )

    assert result == {
        "speed_m_s": 22.22,
        "resistance_n_per_t": 124.0,
        "total_resistance_kn": 24.8,
        "tractive_power_kw": 551.11,
    }


def test_a_weighting_engine_applies_octave_band_corrections() -> None:
    result = compute_a_weighting(
        level_31_5_hz_db=80.0,
        level_63_hz_db=78.0,
        level_125_hz_db=76.0,
        level_250_hz_db=74.0,
        level_500_hz_db=72.0,
        level_1000_hz_db=70.0,
        level_2000_hz_db=68.0,
        level_4000_hz_db=66.0,
    )

    assert result == {
        "total_linear_level_db": 84.22,
        "a_weighted_total_dba": 75.51,
        "a_weighting_adjustment_db": -8.71,
    }


def test_water_supply_curve_engine_calculates_hydrant_curve() -> None:
    result = compute_water_supply_curve(
        static_pressure_psi=100.0,
        residual_pressure_psi=60.0,
        test_flow_gpm=1000.0,
        target_residual_pressure_psi=20.0,
    )

    assert result == {
        "pressure_drop_test_psi": 40.0,
        "curve_coefficient": 136.423,
        "flow_at_target_residual_gpm": 1453.97,
        "available_flow_20psi_gpm": 1453.97,
    }


def test_gci_engine_calculates_three_grid_convergence_index() -> None:
    result = compute_gci_calculation(
        coarse_grid_value=0.70,
        medium_grid_value=0.46,
        fine_grid_value=0.36,
        refinement_ratio=2.0,
    )

    assert result == {
        "observed_order": 1.263,
        "extrapolated_value": 0.289,
        "approximate_relative_error_pct": 27.778,
        "gci_fine_pct": 24.802,
        "asymptotic_range_ratio": 0.783,
    }


def test_pressure_loss_engine_combines_pipe_and_fitting_losses() -> None:
    result = compute_pressure_loss_calculation(
        flow_rate_l_s=20.0,
        pipe_internal_diameter_mm=100.0,
        pipe_length_m=100.0,
        hazen_williams_c=120.0,
        total_fitting_k=10.0,
        fluid_density_kg_m3=1000.0,
    )

    assert result == {
        "velocity_m_s": 2.55,
        "friction_loss_kpa": 78.29,
        "fitting_loss_kpa": 32.42,
        "total_pressure_loss_kpa": 110.71,
    }


def test_pump_power_efficiency_engine_sizes_motor_power() -> None:
    result = compute_pump_power_efficiency(
        flow_rate_m3_h=360.0,
        total_dynamic_head_m=50.0,
        fluid_density_kg_m3=1000.0,
        pump_efficiency_pct=75.0,
        motor_efficiency_pct=90.0,
        motor_sizing_factor=1.15,
    )

    assert result == {
        "hydraulic_power_kw": 49.05,
        "shaft_power_kw": 65.4,
        "motor_input_power_kw": 72.67,
        "recommended_motor_size_kw": 83.57,
    }


def test_sprinkler_hazen_williams_engine_includes_equivalent_length() -> None:
    result = compute_friction_loss_hazen_williams(
        flow_rate_gpm=500.0,
        pipe_length_ft=100.0,
        pipe_internal_diameter_in=4.0,
        hazen_williams_c=120.0,
        fitting_equivalent_length_ft=30.0,
    )

    assert result == {
        "friction_loss_per_ft_psi": 0.0741,
        "equivalent_length_ft": 130.0,
        "pipe_friction_loss_psi": 7.41,
        "total_pressure_loss_psi": 9.63,
    }


def test_composite_section_engine_calculates_transformed_properties() -> None:
    result = compute_composite_section(
        top_flange_width_mm=300.0,
        top_flange_thickness_mm=20.0,
        web_depth_mm=900.0,
        web_thickness_mm=12.0,
        bottom_flange_width_mm=400.0,
        bottom_flange_thickness_mm=25.0,
        slab_width_mm=2500.0,
        slab_thickness_mm=200.0,
        haunch_width_mm=400.0,
        haunch_thickness_mm=100.0,
        modular_ratio=8.0,
    )

    assert result == {
        "transformed_area_mm2": 94300.0,
        "neutral_axis_from_bottom_mm": 926.86,
        "transformed_inertia_mm4": 14505558571.93,
        "bottom_section_modulus_mm3": 15650286.59,
        "top_section_modulus_mm3": 45594285.97,
    }
