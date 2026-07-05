# ABOUTME: Computes SSC-16 construction stage control metrics from task-owned source-pack values.
# ABOUTME: Aggregates runoff, sediment basin, temporary traffic, monitoring power, and inspection calculations.

from __future__ import annotations

from math import ceil

_FT3_PER_ACRE_FOOT = 43_560.0
_LITRES_PER_FT3 = 28.316846592
_MG_PER_LB = 453_592.37


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _temporary_traffic_taper_length_ft(*, speed_mph: float, lane_shift_ft: float) -> float:
    """Return MUTCD-style merging taper length for the task-owned TTC design case."""
    if speed_mph <= 40.0:
        return lane_shift_ft * speed_mph**2 / 60.0
    return lane_shift_ft * speed_mph


def compute(
    disturbed_area_ac: float,
    design_storm_depth_in: float,
    runoff_coefficient: float,
    provided_basin_volume_ft3: float,
    provided_freeboard_ft: float,
    required_freeboard_ft: float,
    tss_event_mean_concentration_mg_l: float,
    work_zone_speed_mph: float,
    lane_shift_width_ft: float,
    provided_taper_length_ft: float,
    channelizer_spacing_ft: float,
    provided_channelizer_count: float,
    turbidity_logger_load_w: float,
    weather_station_load_w: float,
    cellular_router_load_w: float,
    work_zone_camera_load_w: float,
    battery_capacity_wh: float,
    usable_battery_fraction: float,
    solar_panel_power_w: float,
    peak_sun_hours: float,
    solar_derate_factor: float,
    camera_data_mbps: float,
    turbidity_logger_data_mbps: float,
    weather_station_data_mbps: float,
    gateway_data_mbps: float,
    inspection_interval_days: float,
    days_since_last_inspection: float,
) -> dict[str, float]:
    """Compute construction environmental, TTC, and monitoring readiness metrics."""
    _require_positive(
        disturbed_area_ac=disturbed_area_ac,
        design_storm_depth_in=design_storm_depth_in,
        runoff_coefficient=runoff_coefficient,
        provided_basin_volume_ft3=provided_basin_volume_ft3,
        provided_freeboard_ft=provided_freeboard_ft,
        required_freeboard_ft=required_freeboard_ft,
        tss_event_mean_concentration_mg_l=tss_event_mean_concentration_mg_l,
        work_zone_speed_mph=work_zone_speed_mph,
        lane_shift_width_ft=lane_shift_width_ft,
        provided_taper_length_ft=provided_taper_length_ft,
        channelizer_spacing_ft=channelizer_spacing_ft,
        provided_channelizer_count=provided_channelizer_count,
        turbidity_logger_load_w=turbidity_logger_load_w,
        weather_station_load_w=weather_station_load_w,
        cellular_router_load_w=cellular_router_load_w,
        work_zone_camera_load_w=work_zone_camera_load_w,
        battery_capacity_wh=battery_capacity_wh,
        usable_battery_fraction=usable_battery_fraction,
        solar_panel_power_w=solar_panel_power_w,
        peak_sun_hours=peak_sun_hours,
        solar_derate_factor=solar_derate_factor,
        camera_data_mbps=camera_data_mbps,
        turbidity_logger_data_mbps=turbidity_logger_data_mbps,
        weather_station_data_mbps=weather_station_data_mbps,
        gateway_data_mbps=gateway_data_mbps,
        inspection_interval_days=inspection_interval_days,
    )
    if not 0.0 < usable_battery_fraction <= 1.0:
        msg = "usable_battery_fraction must be between 0 and 1"
        raise ValueError(msg)
    if not 0.0 < solar_derate_factor <= 1.0:
        msg = "solar_derate_factor must be between 0 and 1"
        raise ValueError(msg)
    if days_since_last_inspection < 0:
        msg = "days_since_last_inspection must be >= 0"
        raise ValueError(msg)

    runoff_volume_ft3 = disturbed_area_ac * _FT3_PER_ACRE_FOOT * (design_storm_depth_in / 12.0) * runoff_coefficient
    required_basin_volume_ft3 = runoff_volume_ft3
    basin_storage_headroom_ft3 = provided_basin_volume_ft3 - required_basin_volume_ft3
    freeboard_margin_ft = provided_freeboard_ft - required_freeboard_ft
    tss_load_lb = runoff_volume_ft3 * _LITRES_PER_FT3 * tss_event_mean_concentration_mg_l / _MG_PER_LB

    taper_length_ft = _temporary_traffic_taper_length_ft(
        speed_mph=work_zone_speed_mph,
        lane_shift_ft=lane_shift_width_ft,
    )
    taper_headroom_ft = provided_taper_length_ft - taper_length_ft
    minimum_channelizer_count = float(ceil(taper_length_ft / channelizer_spacing_ft) + 1)
    channelizer_headroom_count = provided_channelizer_count - minimum_channelizer_count

    total_monitoring_data_mbps = (
        camera_data_mbps + turbidity_logger_data_mbps + weather_station_data_mbps + gateway_data_mbps
    )
    monitoring_load_w = (
        turbidity_logger_load_w + weather_station_load_w + cellular_router_load_w + work_zone_camera_load_w
    )
    battery_autonomy_h = battery_capacity_wh * usable_battery_fraction / monitoring_load_w
    solar_daily_energy_wh = solar_panel_power_w * peak_sun_hours * solar_derate_factor
    monitoring_daily_load_wh = monitoring_load_w * 24.0
    solar_daily_headroom_wh = solar_daily_energy_wh - monitoring_daily_load_wh
    inspection_days_remaining = inspection_interval_days - days_since_last_inspection

    return {
        "runoff_volume_ft3": round(runoff_volume_ft3, 3),
        "required_basin_volume_ft3": round(required_basin_volume_ft3, 3),
        "basin_storage_headroom_ft3": round(basin_storage_headroom_ft3, 3),
        "freeboard_margin_ft": round(freeboard_margin_ft, 3),
        "tss_load_lb": round(tss_load_lb, 3),
        "taper_length_ft": round(taper_length_ft, 3),
        "taper_headroom_ft": round(taper_headroom_ft, 3),
        "minimum_channelizer_count": round(minimum_channelizer_count, 3),
        "channelizer_headroom_count": round(channelizer_headroom_count, 3),
        "total_monitoring_data_mbps": round(total_monitoring_data_mbps, 3),
        "monitoring_load_w": round(monitoring_load_w, 3),
        "battery_autonomy_h": round(battery_autonomy_h, 3),
        "solar_daily_headroom_wh": round(solar_daily_headroom_wh, 3),
        "inspection_days_remaining": round(inspection_days_remaining, 3),
    }
