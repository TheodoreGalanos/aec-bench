# ABOUTME: Computes SSC-01 road low-point resilience metrics from source-pack values.
# ABOUTME: Combines runoff, gutter spread, HGL, cabinet, VMS, network, and battery checks.

from __future__ import annotations

import math

_G = 9.81
_GUTTER_KU_SI = 0.376
_FT_TO_M = 0.3048


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


def _rational_peak_flow(
    *,
    runoff_coefficient: float,
    rainfall_intensity_mm_h: float,
    catchment_area_ha: float,
) -> float:
    """Return rational-method peak runoff in m3/s for SI inputs."""
    if runoff_coefficient < 0.0 or runoff_coefficient > 1.0:
        msg = "runoff_coefficient must be between 0 and 1"
        raise ValueError(msg)
    _require_positive(rainfall_intensity_mm_h=rainfall_intensity_mm_h, catchment_area_ha=catchment_area_ha)
    return runoff_coefficient * rainfall_intensity_mm_h * catchment_area_ha / 360.0


def _triangular_gutter_spread(
    *,
    gutter_flow_m3_s: float,
    cross_slope_pct: float,
    longitudinal_slope_pct: float,
    mannings_n: float,
) -> tuple[float, float]:
    """Return spread width and curb depth for a triangular pavement gutter."""
    _require_positive(
        gutter_flow_m3_s=gutter_flow_m3_s,
        cross_slope_pct=cross_slope_pct,
        longitudinal_slope_pct=longitudinal_slope_pct,
        mannings_n=mannings_n,
    )
    sx = cross_slope_pct / 100.0
    sl = longitudinal_slope_pct / 100.0
    spread_width_m = (gutter_flow_m3_s * mannings_n / (_GUTTER_KU_SI * sx ** (5.0 / 3.0) * math.sqrt(sl))) ** (
        3.0 / 8.0
    )
    return spread_width_m, spread_width_m * sx


def _hgl_at_upstream_pit(
    *,
    design_flow_m3_s: float,
    pipe_diameter_mm: float,
    pipe_length_m: float,
    mannings_n: float,
    pit_loss_coefficient: float,
    tailwater_level_m: float,
) -> float:
    """Return upstream HGL for one full-pipe stormwater reach."""
    _require_positive(
        design_flow_m3_s=design_flow_m3_s,
        pipe_diameter_mm=pipe_diameter_mm,
        pipe_length_m=pipe_length_m,
        mannings_n=mannings_n,
    )
    _require_nonnegative(pit_loss_coefficient=pit_loss_coefficient)

    diameter_m = pipe_diameter_mm / 1000.0
    area_m2 = math.pi * diameter_m**2 / 4.0
    hydraulic_radius_m = diameter_m / 4.0
    velocity_m_s = design_flow_m3_s / area_m2
    friction_slope = (velocity_m_s * mannings_n / hydraulic_radius_m ** (2.0 / 3.0)) ** 2
    friction_loss_m = friction_slope * pipe_length_m
    pit_loss_m = pit_loss_coefficient * velocity_m_s**2 / (2.0 * _G)
    return tailwater_level_m + friction_loss_m + pit_loss_m


def compute(
    runoff_coefficient: float,
    rainfall_intensity_mm_h: float,
    catchment_area_ha: float,
    upstream_bypass_flow_m3_s: float,
    cross_slope_pct: float,
    longitudinal_slope_pct: float,
    gutter_mannings_n_thousandths: float,
    allowable_spread_m: float,
    inlet_efficiency: float,
    inlet_capture_capacity_m3_s: float,
    pipe_diameter_mm: float,
    pipe_length_m: float,
    pipe_mannings_n_thousandths: float,
    pit_loss_coefficient: float,
    tailwater_level_m: float,
    road_low_point_level_m: float,
    cabinet_pad_level_m: float,
    minimum_cabinet_freeboard_m: float,
    vms_character_height_in: float,
    road_design_speed_kmh: float,
    reading_rate_chars_s: float,
    vms_message_length_chars: float,
    camera_count: float,
    camera_data_rate_mbps: float,
    vms_data_rate_mbps: float,
    controller_data_rate_mbps: float,
    sensor_data_rate_mbps: float,
    network_overhead_pct: float,
    future_capacity_buffer_pct: float,
    uplink_capacity_mbps: float,
    battery_capacity_kwh: float,
    battery_efficiency: float,
    critical_load_w: float,
    required_autonomy_h: float,
    minimum_hgl_clearance_mm: float,
) -> dict[str, float]:
    """Compute the SSC-01 low-point drainage and field-equipment resilience metrics."""
    _require_nonnegative(
        upstream_bypass_flow_m3_s=upstream_bypass_flow_m3_s,
        minimum_cabinet_freeboard_m=minimum_cabinet_freeboard_m,
        camera_count=camera_count,
        vms_data_rate_mbps=vms_data_rate_mbps,
        controller_data_rate_mbps=controller_data_rate_mbps,
        sensor_data_rate_mbps=sensor_data_rate_mbps,
        network_overhead_pct=network_overhead_pct,
        future_capacity_buffer_pct=future_capacity_buffer_pct,
        minimum_hgl_clearance_mm=minimum_hgl_clearance_mm,
    )
    _require_positive(
        allowable_spread_m=allowable_spread_m,
        inlet_capture_capacity_m3_s=inlet_capture_capacity_m3_s,
        vms_character_height_in=vms_character_height_in,
        road_design_speed_kmh=road_design_speed_kmh,
        reading_rate_chars_s=reading_rate_chars_s,
        uplink_capacity_mbps=uplink_capacity_mbps,
        battery_capacity_kwh=battery_capacity_kwh,
        battery_efficiency=battery_efficiency,
        critical_load_w=critical_load_w,
        required_autonomy_h=required_autonomy_h,
    )
    if inlet_efficiency < 0.0 or inlet_efficiency > 1.0:
        msg = "inlet_efficiency must be between 0 and 1"
        raise ValueError(msg)
    if battery_efficiency > 1.0:
        msg = "battery_efficiency must be <= 1"
        raise ValueError(msg)

    peak_runoff_m3_s = _rational_peak_flow(
        runoff_coefficient=runoff_coefficient,
        rainfall_intensity_mm_h=rainfall_intensity_mm_h,
        catchment_area_ha=catchment_area_ha,
    )
    gutter_mannings_n = gutter_mannings_n_thousandths / 1000.0
    pipe_mannings_n = pipe_mannings_n_thousandths / 1000.0
    gutter_approach_flow_m3_s = peak_runoff_m3_s + upstream_bypass_flow_m3_s
    spread_width_m, curb_depth_m = _triangular_gutter_spread(
        gutter_flow_m3_s=gutter_approach_flow_m3_s,
        cross_slope_pct=cross_slope_pct,
        longitudinal_slope_pct=longitudinal_slope_pct,
        mannings_n=gutter_mannings_n,
    )
    spread_margin_m = allowable_spread_m - spread_width_m

    inlet_intercepted_flow_m3_s = min(gutter_approach_flow_m3_s * inlet_efficiency, inlet_capture_capacity_m3_s)
    residual_ponding_flow_m3_s = max(gutter_approach_flow_m3_s - inlet_intercepted_flow_m3_s, 0.0)
    hgl_upstream_m = _hgl_at_upstream_pit(
        design_flow_m3_s=inlet_intercepted_flow_m3_s,
        pipe_diameter_mm=pipe_diameter_mm,
        pipe_length_m=pipe_length_m,
        mannings_n=pipe_mannings_n,
        pit_loss_coefficient=pit_loss_coefficient,
        tailwater_level_m=tailwater_level_m,
    )
    hgl_clearance_mm = (road_low_point_level_m - hgl_upstream_m) * 1000.0

    pavement_water_level_m = road_low_point_level_m + curb_depth_m
    controlling_water_level_m = max(pavement_water_level_m, hgl_upstream_m)
    cabinet_freeboard_m = cabinet_pad_level_m - controlling_water_level_m
    cabinet_flood_depth_m = max(controlling_water_level_m - cabinet_pad_level_m, 0.0)

    legibility_distance_m = vms_character_height_in * 40.0 * _FT_TO_M
    reading_time_available_s = legibility_distance_m / (road_design_speed_kmh / 3.6)
    message_length_limit_chars = reading_time_available_s * reading_rate_chars_s
    vms_message_margin_chars = message_length_limit_chars - vms_message_length_chars

    base_network_load_mbps = (
        camera_count * camera_data_rate_mbps + vms_data_rate_mbps + controller_data_rate_mbps + sensor_data_rate_mbps
    )
    required_network_mbps = (
        base_network_load_mbps * (1.0 + network_overhead_pct / 100.0) * (1.0 + future_capacity_buffer_pct / 100.0)
    )
    network_headroom_mbps = uplink_capacity_mbps - required_network_mbps

    battery_runtime_h = battery_capacity_kwh * battery_efficiency / (critical_load_w / 1000.0)
    battery_margin_h = battery_runtime_h - required_autonomy_h

    pass_checks = [
        spread_margin_m >= 0.0,
        hgl_clearance_mm >= minimum_hgl_clearance_mm,
        cabinet_freeboard_m >= minimum_cabinet_freeboard_m,
        vms_message_margin_chars >= 0.0,
        network_headroom_mbps >= 0.0,
        battery_margin_h >= 0.0,
    ]

    return {
        "peak_runoff_m3_s": round(peak_runoff_m3_s, 3),
        "gutter_approach_flow_m3_s": round(gutter_approach_flow_m3_s, 3),
        "spread_width_m": round(spread_width_m, 3),
        "spread_margin_m": round(spread_margin_m, 3),
        "curb_depth_m": round(curb_depth_m, 3),
        "inlet_intercepted_flow_m3_s": round(inlet_intercepted_flow_m3_s, 3),
        "residual_ponding_flow_m3_s": round(residual_ponding_flow_m3_s, 3),
        "hgl_upstream_m": round(hgl_upstream_m, 3),
        "hgl_clearance_mm": round(hgl_clearance_mm, 3),
        "cabinet_freeboard_m": round(cabinet_freeboard_m, 3),
        "cabinet_flood_depth_m": round(cabinet_flood_depth_m, 3),
        "vms_reading_time_s": round(reading_time_available_s, 3),
        "vms_message_margin_chars": round(vms_message_margin_chars, 3),
        "network_headroom_mbps": round(network_headroom_mbps, 3),
        "battery_runtime_h": round(battery_runtime_h, 3),
        "battery_margin_h": round(battery_margin_h, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
