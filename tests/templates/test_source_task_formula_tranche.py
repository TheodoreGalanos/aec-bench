# ABOUTME: Tests source-task seeds converted into built-in formula templates.
# ABOUTME: Covers direct civil and electrical calculations added from seed-only tasks.

import pytest

from aec_bench.templates.builtin.civil.tidal_prism.engine import (
    compute as compute_tidal_prism,
)
from aec_bench.templates.builtin.electrical.access_controller_sizing.engine import (
    compute as compute_access_controller_sizing,
)
from aec_bench.templates.builtin.electrical.all_red_interval_calculation.engine import (
    compute as compute_all_red_interval_calculation,
)
from aec_bench.templates.builtin.electrical.bandwidth_calculation.engine import (
    compute as compute_bandwidth_calculation,
)
from aec_bench.templates.builtin.electrical.battery_sizing.engine import (
    compute as compute_battery_sizing,
)
from aec_bench.templates.builtin.electrical.bess_sizing_basic.engine import (
    compute as compute_bess_sizing_basic,
)
from aec_bench.templates.builtin.electrical.car_dimensions_check.engine import (
    compute as compute_car_dimensions_check,
)
from aec_bench.templates.builtin.electrical.cctv_storage_calculation.engine import (
    compute as compute_cctv_storage_calculation,
)
from aec_bench.templates.builtin.electrical.conduit_fill_calculation.engine import (
    compute as compute_conduit_fill_calculation,
)
from aec_bench.templates.builtin.electrical.escalator_capacity.engine import (
    compute as compute_escalator_capacity,
)
from aec_bench.templates.builtin.electrical.fiber_link_loss_budget.engine import (
    compute as compute_fiber_link_loss_budget,
)
from aec_bench.templates.builtin.electrical.four_twenty_ma_scaling.engine import (
    compute as compute_four_twenty_ma_scaling,
)
from aec_bench.templates.builtin.electrical.handling_capacity.engine import (
    compute as compute_handling_capacity,
)
from aec_bench.templates.builtin.electrical.ice_load_calculation.engine import (
    compute as compute_ice_load_calculation,
)
from aec_bench.templates.builtin.electrical.interior_uniformity.engine import (
    compute as compute_interior_uniformity,
)
from aec_bench.templates.builtin.electrical.interval_calculation.engine import (
    compute as compute_interval_calculation,
)
from aec_bench.templates.builtin.electrical.leni_calculation.engine import (
    compute as compute_leni_calculation,
)
from aec_bench.templates.builtin.electrical.line_capacitance.engine import (
    compute as compute_line_capacitance,
)
from aec_bench.templates.builtin.electrical.line_inductance.engine import (
    compute as compute_line_inductance,
)
from aec_bench.templates.builtin.electrical.lux_level_calculation.engine import (
    compute as compute_lux_level_calculation,
)
from aec_bench.templates.builtin.electrical.overlap_calculation.engine import (
    compute as compute_overlap_calculation,
)
from aec_bench.templates.builtin.electrical.pedestrian_clearance_time.engine import (
    compute as compute_pedestrian_clearance_time,
)
from aec_bench.templates.builtin.electrical.pfc_sizing.engine import (
    compute as compute_pfc_sizing,
)
from aec_bench.templates.builtin.electrical.poe_power_budget.engine import (
    compute as compute_poe_power_budget,
)
from aec_bench.templates.builtin.electrical.power_load_calculation.engine import (
    compute as compute_power_load_calculation,
)
from aec_bench.templates.builtin.electrical.ppm_calculation.engine import (
    compute as compute_ppm_calculation,
)
from aec_bench.templates.builtin.electrical.radial_feeder_voltage_drop.engine import (
    compute as compute_radial_feeder_voltage_drop,
)
from aec_bench.templates.builtin.electrical.rf_link_budget.engine import (
    compute as compute_rf_link_budget,
)
from aec_bench.templates.builtin.electrical.road_aeci_calculation.engine import (
    compute as compute_road_aeci_calculation,
)
from aec_bench.templates.builtin.electrical.road_pdi_calculation.engine import (
    compute as compute_road_pdi_calculation,
)
from aec_bench.templates.builtin.electrical.road_uniformity_check.engine import (
    compute as compute_road_uniformity_check,
)
from aec_bench.templates.builtin.electrical.shaft_dimensions.engine import (
    compute as compute_shaft_dimensions,
)
from aec_bench.templates.builtin.electrical.signal_sighting_distance.engine import (
    compute as compute_signal_sighting_distance,
)
from aec_bench.templates.builtin.electrical.sports_illuminance_uniformity.engine import (
    compute as compute_sports_illuminance_uniformity,
)
from aec_bench.templates.builtin.electrical.vms_legibility_distance.engine import (
    compute as compute_vms_legibility_distance,
)
from aec_bench.templates.builtin.electrical.voltage_drop_dc.engine import (
    compute as compute_voltage_drop_dc,
)
from aec_bench.templates.builtin.electrical.voltage_regulation.engine import (
    compute as compute_voltage_regulation,
)
from aec_bench.templates.builtin.electrical.warning_time_calculation.engine import (
    compute as compute_warning_time_calculation,
)
from aec_bench.templates.builtin.electrical.wind_load_conductor.engine import (
    compute as compute_wind_load_conductor,
)
from aec_bench.templates.builtin.electrical.yellow_interval_calculation.engine import (
    compute as compute_yellow_interval,
)
from aec_bench.templates.registry import discover_templates


def test_tidal_prism_engine_calculates_prism_and_velocity() -> None:
    result = compute_tidal_prism(
        basin_surface_area_m2=2_000_000.0,
        tidal_range_m=1.8,
        inlet_width_m=120.0,
        inlet_average_depth_m=6.0,
        exchange_duration_h=6.2,
    )

    assert result == {
        "tidal_prism_m3": 3_600_000.0,
        "inlet_flow_area_m2": 720.0,
        "mean_tidal_flow_m3_s": 161.29,
        "mean_tidal_velocity_m_s": 0.22,
    }


def test_line_inductance_engine_calculates_gmd_and_phase_inductance() -> None:
    result = compute_line_inductance(
        conductor_gmr_m=0.008,
        phase_spacing_ab_m=3.0,
        phase_spacing_bc_m=3.0,
        phase_spacing_ca_m=6.0,
        bundle_count="single",
        bundle_spacing_m=0.45,
    )

    assert result["geometric_mean_distance_m"] == pytest.approx(3.78, abs=0.01)
    assert result["equivalent_gmr_mm"] == 8.0
    assert result["inductance_mh_per_km"] == pytest.approx(1.23, abs=0.01)


def test_line_capacitance_engine_calculates_charging_and_surge_impedance() -> None:
    result = compute_line_capacitance(
        conductor_radius_m=0.015,
        phase_spacing_ab_m=4.0,
        phase_spacing_bc_m=4.0,
        phase_spacing_ca_m=8.0,
        nominal_voltage_kv=132.0,
        frequency_hz=50.0,
        inductance_mh_per_km=1.2,
    )

    assert result == {
        "geometric_mean_distance_m": 5.04,
        "capacitance_nf_per_km": 9.56,
        "charging_mvar_per_100km": 5.24,
        "surge_impedance_ohm": 354.22,
    }


def test_voltage_regulation_engine_calculates_line_drop_and_loss() -> None:
    result = compute_voltage_regulation(
        line_resistance_ohm_per_km=0.08,
        line_reactance_ohm_per_km=0.35,
        line_length_km=50.0,
        load_real_power_mw=40.0,
        load_reactive_power_mvar=15.0,
        sending_voltage_kv=132.0,
    )

    assert result == {
        "voltage_drop_kv": 3.2,
        "voltage_regulation_pct": 2.42,
        "receiving_end_voltage_kv": 128.8,
        "power_loss_mw": 0.42,
    }


def test_pfc_sizing_engine_calculates_required_capacitor_kvar() -> None:
    result = compute_pfc_sizing(
        real_power_kw=500.0,
        initial_power_factor=0.8,
        target_power_factor=0.95,
    )

    assert result == {
        "initial_apparent_power_kva": 625.0,
        "corrected_apparent_power_kva": 526.32,
        "required_reactive_power_kvar": 210.66,
        "current_reduction_pct": 15.79,
    }


def test_ppm_calculation_engine_calculates_camera_pixel_density() -> None:
    result = compute_ppm_calculation(
        horizontal_pixels=3840.0,
        sensor_width_mm=6.4,
        lens_focal_length_mm=8.0,
        target_distance_m=20.0,
        target_ppm=250.0,
    )

    assert result == {
        "horizontal_field_of_view_m": 16.0,
        "pixels_per_meter": 240.0,
        "target_ppm_margin_pct": -4.0,
    }


def test_yellow_interval_engine_applies_metric_ite_formula() -> None:
    result = compute_yellow_interval(
        approach_speed_kmh=60.0,
        perception_reaction_time_s=1.0,
        deceleration_rate_m_s2=3.0,
        road_grade_pct=-3.0,
    )

    assert result == {
        "approach_speed_m_s": 16.67,
        "grade_adjusted_denominator": 5.41,
        "yellow_interval_s": 4.08,
        "yellow_interval_rounded_s": 4.1,
    }


def test_four_twenty_ma_engine_scales_process_variable() -> None:
    result = compute_four_twenty_ma_scaling(
        process_value=75.0,
        lower_range_value=0.0,
        upper_range_value=100.0,
    )

    assert result == {
        "span_pct": 75.0,
        "current_signal_ma": 16.0,
        "reconstructed_process_value": 75.0,
    }


def test_fiber_link_loss_engine_calculates_margin() -> None:
    result = compute_fiber_link_loss_budget(
        fiber_length_km=2.5,
        fiber_attenuation_db_per_km=0.35,
        connector_count=4.0,
        connector_loss_db=0.5,
        splice_count=6.0,
        splice_loss_db=0.1,
        system_loss_budget_db=8.0,
    )

    assert result == {
        "fiber_loss_db": 0.88,
        "connector_loss_total_db": 2.0,
        "splice_loss_total_db": 0.6,
        "total_link_loss_db": 3.48,
        "power_margin_db": 4.53,
    }


def test_bandwidth_engine_sizes_its_network_capacity() -> None:
    result = compute_bandwidth_calculation(
        camera_count=12.0,
        camera_data_rate_mbps=4.0,
        controller_count=8.0,
        controller_data_rate_mbps=0.2,
        sensor_count=20.0,
        sensor_data_rate_mbps=0.05,
        network_overhead_pct=15.0,
        future_capacity_buffer_pct=25.0,
    )

    assert result == {
        "base_bandwidth_mbps": 50.6,
        "peak_demand_mbps": 58.19,
        "required_bandwidth_mbps": 72.74,
    }


def test_cctv_storage_engine_calculates_retention_storage() -> None:
    result = compute_cctv_storage_calculation(
        camera_count=24.0,
        average_bitrate_mbps=4.0,
        recording_hours_per_day=24.0,
        retention_days=30.0,
        storage_overhead_pct=20.0,
    )

    assert result == {
        "daily_storage_per_camera_gb": 43.2,
        "usable_storage_required_tb": 31.1,
        "raw_storage_with_overhead_tb": 37.32,
    }


def test_pedestrian_clearance_engine_calculates_flash_interval() -> None:
    result = compute_pedestrian_clearance_time(
        crosswalk_length_m=18.0,
        walking_speed_m_s=1.2,
    )

    assert result == {
        "pedestrian_clearance_time_s": 15.0,
        "pedestrian_clearance_rounded_s": 15.0,
    }


def test_poe_power_budget_engine_calculates_switch_headroom() -> None:
    result = compute_poe_power_budget(
        device_count=24.0,
        power_draw_per_device_w=15.4,
        switch_poe_budget_w=740.0,
        required_headroom_pct=20.0,
    )

    assert result == {
        "total_power_requirement_w": 369.6,
        "utilization_pct": 49.95,
        "available_headroom_w": 370.4,
        "required_headroom_w": 73.92,
        "headroom_margin_w": 296.48,
    }


def test_power_load_engine_calculates_signalling_supply_size() -> None:
    result = compute_power_load_calculation(
        equipment_power_w=120.0,
        equipment_quantity=15.0,
        diversity_factor=0.8,
        future_expansion_pct=25.0,
        supply_power_factor=0.9,
    )

    assert result == {
        "total_connected_load_w": 1800.0,
        "maximum_demand_w": 1440.0,
        "future_allowance_w": 360.0,
        "recommended_supply_size_kva": 2.0,
    }


def test_rf_link_budget_engine_calculates_received_signal_margin() -> None:
    result = compute_rf_link_budget(
        transmit_power_dbm=20.0,
        transmit_antenna_gain_dbi=5.0,
        distance_m=1000.0,
        frequency_ghz=2.4,
        receive_antenna_gain_dbi=5.0,
        obstacle_losses_db=10.0,
        required_receive_sensitivity_dbm=-85.0,
    )

    assert result == {
        "free_space_path_loss_db": 100.04,
        "total_path_loss_db": 110.04,
        "received_signal_level_dbm": -80.04,
        "link_margin_db": 4.96,
    }


def test_warning_time_engine_calculates_strike_in_distance() -> None:
    result = compute_warning_time_calculation(
        maximum_train_speed_kmh=110.0,
        minimum_warning_time_s=25.0,
        road_user_clearance_time_s=8.0,
        barrier_lowering_time_s=7.0,
        system_delay_s=3.0,
    )

    assert result == {
        "maximum_train_speed_m_s": 30.56,
        "total_warning_time_s": 43.0,
        "strike_in_distance_m": 1313.89,
        "minimum_warning_margin_s": 18.0,
    }


def test_vms_legibility_engine_calculates_reading_capacity() -> None:
    result = compute_vms_legibility_distance(
        character_height_in=12.0,
        design_speed_mph=55.0,
        reading_rate_chars_s=3.0,
    )

    assert result == {
        "minimum_legibility_distance_ft": 480.0,
        "design_speed_ft_s": 80.67,
        "reading_time_available_s": 5.95,
        "message_length_limit_chars": 17.85,
    }


def test_radial_feeder_voltage_drop_engine_calculates_single_section_drop() -> None:
    result = compute_radial_feeder_voltage_drop(
        feeder_resistance_ohm_per_km=0.4,
        feeder_reactance_ohm_per_km=0.25,
        feeder_length_km=2.0,
        load_real_power_kw=500.0,
        load_reactive_power_kvar=200.0,
        source_voltage_v=11000.0,
    )

    assert result == {
        "feeder_current_a": 28.26,
        "voltage_drop_v": 45.45,
        "voltage_drop_pct": 0.41,
        "receiving_end_voltage_v": 10954.55,
        "feeder_loss_kw": 1.92,
    }


def test_signal_sighting_distance_engine_calculates_reaction_and_braking() -> None:
    result = compute_signal_sighting_distance(
        maximum_line_speed_kmh=100.0,
        service_braking_rate_m_s2=0.8,
        driver_reaction_time_s=2.5,
        track_gradient_pct=-1.0,
    )

    assert result == {
        "line_speed_m_s": 27.78,
        "reaction_distance_m": 69.44,
        "grade_adjusted_braking_rate_m_s2": 0.7,
        "braking_distance_m": 549.65,
        "required_sighting_distance_m": 619.1,
    }


def test_battery_sizing_engine_calculates_capacity_and_blocks() -> None:
    result = compute_battery_sizing(
        critical_load_w=800.0,
        required_autonomy_h=4.0,
        system_voltage_v=48.0,
        depth_of_discharge_pct=80.0,
        temperature_derating_factor=0.9,
        inverter_efficiency_pct=92.0,
        load_power_factor=0.85,
        battery_block_voltage_v=12.0,
    )

    assert result == {
        "required_energy_kwh": 3.2,
        "required_battery_capacity_ah": 100.64,
        "ups_rating_va": 941.18,
        "battery_block_count": 4.0,
    }


def test_all_red_interval_engine_calculates_clearance_time() -> None:
    result = compute_all_red_interval_calculation(
        intersection_width_m=18.0,
        vehicle_length_m=6.0,
        vehicle_speed_m_s=12.0,
    )

    assert result == {
        "clearance_distance_m": 24.0,
        "raw_all_red_interval_s": 2.0,
        "all_red_interval_s": 2.0,
    }


def test_interval_engine_calculates_average_lift_interval() -> None:
    result = compute_interval_calculation(
        round_trip_time_s=120.0,
        lift_count=4.0,
    )

    assert result == {
        "interval_s": 30.0,
        "arrivals_per_5min": 10.0,
    }


def test_handling_capacity_engine_calculates_five_minute_capacity() -> None:
    result = compute_handling_capacity(
        building_population=1200.0,
        round_trip_time_s=120.0,
        car_capacity_persons=16.0,
        lift_count=4.0,
        car_loading_factor_pct=80.0,
    )

    assert result == {
        "passengers_per_5min": 128.0,
        "handling_capacity_pct": 10.67,
    }


def test_escalator_capacity_engine_calculates_passenger_capacity() -> None:
    result = compute_escalator_capacity(
        escalator_speed_m_s=0.5,
        step_width_mm=1000.0,
        step_pitch_mm=400.0,
        practical_loading_factor_pct=65.0,
    )

    assert result == {
        "steps_per_second": 1.25,
        "persons_per_step": 2.0,
        "theoretical_capacity_persons_per_h": 9000.0,
        "practical_capacity_persons_per_h": 5850.0,
    }


def test_conduit_fill_engine_calculates_fill_ratio() -> None:
    result = compute_conduit_fill_calculation(
        conduit_internal_diameter_mm=32.0,
        cable_count=12.0,
        cable_outer_diameter_mm=6.0,
        maximum_fill_pct=40.0,
    )

    assert result == {
        "total_cable_area_mm2": 339.29,
        "conduit_area_mm2": 804.25,
        "fill_percentage": 42.19,
        "fill_margin_pct": -2.19,
    }


def test_road_pdi_engine_calculates_power_density_index() -> None:
    result = compute_road_pdi_calculation(
        total_system_power_w=2000.0,
        maintained_illuminance_lux=15.0,
        illuminated_area_m2=1000.0,
    )

    assert result == {
        "power_density_index_w_per_lux_m2": 0.13,
        "specific_power_density_w_per_m2": 2.0,
    }


def test_road_aeci_engine_calculates_annual_energy_index() -> None:
    result = compute_road_aeci_calculation(
        system_power_w=2000.0,
        full_output_hours_per_year=3000.0,
        dimmed_hours_per_year=1000.0,
        dimming_level_pct=50.0,
        illuminated_area_m2=1000.0,
    )

    assert result == {
        "annual_energy_kwh": 7000.0,
        "aeci_kwh_per_m2_year": 7.0,
    }


def test_leni_engine_calculates_lighting_energy_indicator() -> None:
    result = compute_leni_calculation(
        installed_lighting_power_w=10000.0,
        annual_operating_hours=2500.0,
        control_factor=0.8,
        daylight_factor=0.7,
        zone_area_m2=1000.0,
        reference_leni_kwh_m2_year=20.0,
    )

    assert result == {
        "annual_lighting_energy_kwh": 14000.0,
        "leni_kwh_m2_year": 14.0,
        "reference_saving_pct": 30.0,
    }


def test_road_uniformity_engine_calculates_lighting_ratios() -> None:
    result = compute_road_uniformity_check(
        minimum_luminance_cd_m2=0.6,
        average_luminance_cd_m2=1.5,
        longitudinal_min_luminance_cd_m2=0.7,
        longitudinal_max_luminance_cd_m2=1.2,
        target_overall_uniformity=0.35,
    )

    assert result == {
        "overall_uniformity_uo": 0.4,
        "longitudinal_uniformity_ul": 0.58,
        "overall_uniformity_margin_pct": 14.29,
    }


def test_interior_uniformity_engine_calculates_task_and_surround_ratios() -> None:
    result = compute_interior_uniformity(
        task_min_illuminance_lux=320.0,
        task_average_illuminance_lux=500.0,
        surround_average_illuminance_lux=350.0,
        background_average_illuminance_lux=120.0,
    )

    assert result == {
        "task_uniformity_uo": 0.64,
        "surround_to_task_ratio": 0.7,
        "background_to_task_ratio": 0.24,
    }


def test_bess_sizing_engine_calculates_required_storage_capacity() -> None:
    result = compute_bess_sizing_basic(
        required_discharge_power_mw=50.0,
        required_discharge_duration_h=4.0,
        usable_soc_range_pct=80.0,
        round_trip_efficiency_pct=90.0,
        end_of_life_capacity_retention_pct=85.0,
    )

    assert result == {
        "nominal_power_rating_mw": 50.0,
        "usable_energy_mwh": 200.0,
        "nominal_energy_capacity_mwh": 277.78,
        "beginning_of_life_capacity_mwh": 326.8,
    }


def test_wind_load_conductor_engine_calculates_height_adjusted_load() -> None:
    result = compute_wind_load_conductor(
        wind_pressure_pa=600.0,
        conductor_diameter_mm=30.0,
        span_length_m=300.0,
        drag_coefficient=1.2,
        terrain_category="open",
        height_above_ground_m=20.0,
    )

    assert result == {
        "height_adjusted_wind_pressure_pa": 670.37,
        "wind_load_per_unit_length_n_m": 24.13,
        "transverse_wind_load_n": 7240.02,
    }


def test_ice_load_engine_calculates_combined_conductor_load() -> None:
    result = compute_ice_load_calculation(
        conductor_diameter_mm=25.0,
        ice_thickness_mm=10.0,
        ice_density_kg_m3=900.0,
        wind_on_ice_pressure_pa=400.0,
        span_length_m=250.0,
    )

    assert result == {
        "iced_conductor_diameter_mm": 45.0,
        "ice_weight_n_per_m": 9.71,
        "total_vertical_load_n_per_m": 9.71,
        "wind_on_ice_load_n_per_m": 18.0,
        "combined_ice_wind_load_n_per_m": 20.45,
        "span_combined_load_n": 5112.76,
    }


def test_overlap_engine_calculates_gradient_adjusted_signal_overlap() -> None:
    result = compute_overlap_calculation(
        maximum_approach_speed_kmh=80.0,
        emergency_braking_rate_m_s2=0.9,
        track_gradient_pct=-1.0,
        reaction_time_s=2.0,
        danger_point_distance_m=500.0,
        low_adhesion_factor=0.8,
    )

    assert result == {
        "approach_speed_m_s": 22.22,
        "gradient_adjusted_braking_rate_m_s2": 0.62,
        "reaction_distance_m": 44.44,
        "full_speed_overlap_m": 441.48,
        "timed_overlap_option_m": 397.03,
        "danger_point_clearance_m": 58.52,
    }


def test_voltage_drop_dc_engine_calculates_string_drop_and_loss() -> None:
    result = compute_voltage_drop_dc(
        string_current_a=9.0,
        dc_cable_length_m=60.0,
        cable_cross_section_mm2=6.0,
        cable_resistivity_ohm_mm2_m=0.0175,
        string_voltage_v=600.0,
        annual_operating_hours=1800.0,
        maximum_voltage_drop_pct=3.0,
    )

    assert result == {
        "voltage_drop_v": 3.15,
        "voltage_drop_pct": 0.53,
        "annual_energy_loss_kwh": 51.03,
        "voltage_drop_margin_pct": 2.48,
    }


def test_lux_level_engine_calculates_room_lumen_method_outputs() -> None:
    result = compute_lux_level_calculation(
        room_length_m=20.0,
        room_width_m=10.0,
        luminaire_count=20.0,
        luminaire_luminous_flux_lm=4000.0,
        utilisation_factor=0.7,
        maintenance_factor=0.8,
        total_lighting_power_w=800.0,
        minimum_illuminance_lux=180.0,
        target_illuminance_lux=200.0,
    )

    assert result == {
        "average_illuminance_lux": 224.0,
        "uniformity_ratio_uo": 0.8,
        "specific_luminaire_power_density_w_m2_100lux": 1.79,
        "target_illuminance_margin_pct": 12.0,
    }


def test_sports_illuminance_engine_calculates_field_uniformity() -> None:
    result = compute_sports_illuminance_uniformity(
        field_length_m=100.0,
        field_width_m=60.0,
        luminaire_count=24.0,
        luminaire_luminous_flux_lm=150000.0,
        utilisation_factor=0.55,
        maintenance_factor=0.8,
        minimum_illuminance_lux=180.0,
        maximum_illuminance_lux=420.0,
        target_average_illuminance_lux=200.0,
        target_uniformity_u2=0.6,
    )

    assert result == {
        "average_horizontal_illuminance_lux": 264.0,
        "uniformity_u1_min_max": 0.43,
        "uniformity_u2_min_avg": 0.68,
        "average_illuminance_margin_pct": 32.0,
        "uniformity_u2_margin_pct": 13.64,
    }


def test_shaft_dimensions_engine_calculates_lift_clearance_envelope() -> None:
    result = compute_shaft_dimensions(
        car_internal_width_mm=1600.0,
        car_internal_depth_mm=1400.0,
        side_clearance_mm=200.0,
        front_clearance_mm=300.0,
        rear_clearance_mm=150.0,
        counterweight_width_mm=350.0,
        rated_speed_m_s=1.6,
        car_count=1.0,
        inter_car_clearance_mm=200.0,
    )

    assert result == {
        "shaft_width_mm": 2350.0,
        "shaft_depth_mm": 1850.0,
        "pit_depth_mm": 1600.0,
        "headroom_mm": 4400.0,
    }


def test_car_dimensions_engine_calculates_accessibility_margins() -> None:
    result = compute_car_dimensions_check(
        car_internal_width_mm=1200.0,
        car_internal_depth_mm=1500.0,
        door_clear_opening_mm=950.0,
        rated_load_kg=1000.0,
        minimum_width_mm=1100.0,
        minimum_depth_mm=1400.0,
        minimum_door_opening_mm=900.0,
    )

    assert result == {
        "width_margin_mm": 100.0,
        "depth_margin_mm": 100.0,
        "door_opening_margin_mm": 50.0,
        "car_floor_area_m2": 1.8,
        "rated_load_density_kg_m2": 555.56,
    }


def test_access_controller_engine_sizes_controllers_power_and_backup() -> None:
    result = compute_access_controller_sizing(
        door_count=18.0,
        doors_per_controller=4.0,
        reader_current_ma_per_door=120.0,
        lock_current_ma_per_door=500.0,
        request_to_exit_current_ma_per_door=30.0,
        controller_current_ma=250.0,
        power_supply_capacity_a=5.0,
        backup_duration_h=4.0,
        battery_derating_factor=0.8,
    )

    assert result == {
        "controllers_required": 5.0,
        "door_device_load_a": 11.7,
        "total_system_load_a": 12.95,
        "power_supplies_required": 3.0,
        "battery_capacity_ah": 64.75,
    }


def test_source_task_tranche_templates_are_discoverable() -> None:
    registry = {config.meta.name for config, _ in discover_templates()}

    for template_name in [
        "tidal-prism",
        "line-inductance",
        "pfc-sizing",
        "ppm-calculation",
        "yellow-interval-calculation",
        "4-20ma-scaling",
        "fiber-link-loss-budget",
        "bandwidth-calculation",
        "cctv-storage-calculation",
        "pedestrian-clearance-time",
        "poe-power-budget",
        "power-load-calculation",
        "rf-link-budget",
        "warning-time-calculation",
        "vms-legibility-distance",
        "line-capacitance",
        "voltage-regulation",
        "radial-feeder-voltage-drop",
        "signal-sighting-distance",
        "battery-sizing",
        "all-red-interval-calculation",
        "interval-calculation",
        "handling-capacity",
        "escalator-capacity",
        "conduit-fill-calculation",
        "road-pdi-calculation",
        "road-aeci-calculation",
        "leni-calculation",
        "road-uniformity-check",
        "interior-uniformity",
        "bess-sizing-basic",
        "wind-load-conductor",
        "ice-load-calculation",
        "overlap-calculation",
        "voltage-drop-dc",
        "lux-level-calculation",
        "sports-illuminance-uniformity",
        "shaft-dimensions",
        "car-dimensions-check",
        "access-controller-sizing",
    ]:
        assert template_name in registry
