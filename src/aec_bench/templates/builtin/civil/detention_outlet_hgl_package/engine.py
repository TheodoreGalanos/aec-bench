# ABOUTME: Computes SSC-03 detention, outlet-control, and HGL package metrics.
# ABOUTME: Combines Rational Method runoff, storage, orifice/weir, freeboard, and HGL checks.

from __future__ import annotations

import math

_G = 9.81


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


def _triangular_detention_volume_m3(
    *,
    post_development_peak_flow_m3_s: float,
    allowable_release_rate_m3_s: float,
    storm_duration_hr: float,
) -> float:
    """Return simplified triangular-hydrograph detention volume."""
    q_post = post_development_peak_flow_m3_s
    q_allow = min(allowable_release_rate_m3_s, q_post)
    storm_duration_s = storm_duration_hr * 3600.0

    if q_allow >= q_post:
        return 0.0
    if q_allow < q_post / 2.0:
        return storm_duration_s * (q_post / 2.0 - q_allow)
    return (q_post - q_allow) ** 2 * storm_duration_s / (2.0 * q_post)


def compute(
    catchment_area_ha: float,
    runoff_coefficient: float,
    rainfall_intensity_mm_h: float,
    climate_factor: float,
    allowable_release_rate_m3_s: float,
    storm_duration_hr: float,
    storage_bottom_area_m2: float,
    storage_top_area_m2: float,
    active_storage_depth_m: float,
    orifice_diameter_mm: float,
    orifice_discharge_coefficient: float,
    orifice_head_m: float,
    major_event_peak_flow_m3_s: float,
    emergency_weir_length_m: float,
    emergency_weir_head_m: float,
    weir_discharge_coefficient: float,
    basin_bottom_elevation_m: float,
    embankment_crest_elevation_m: float,
    minimum_freeboard_m: float,
    downstream_tailwater_elevation_m: float,
    outlet_loss_m: float,
    downstream_rim_elevation_m: float,
) -> dict[str, float]:
    """Compute detention outlet and HGL metrics for the SSC-03 source pack."""
    _require_positive(
        catchment_area_ha=catchment_area_ha,
        rainfall_intensity_mm_h=rainfall_intensity_mm_h,
        climate_factor=climate_factor,
        allowable_release_rate_m3_s=allowable_release_rate_m3_s,
        storm_duration_hr=storm_duration_hr,
        storage_bottom_area_m2=storage_bottom_area_m2,
        storage_top_area_m2=storage_top_area_m2,
        active_storage_depth_m=active_storage_depth_m,
        orifice_diameter_mm=orifice_diameter_mm,
        orifice_discharge_coefficient=orifice_discharge_coefficient,
        orifice_head_m=orifice_head_m,
        major_event_peak_flow_m3_s=major_event_peak_flow_m3_s,
        emergency_weir_length_m=emergency_weir_length_m,
        emergency_weir_head_m=emergency_weir_head_m,
        weir_discharge_coefficient=weir_discharge_coefficient,
        minimum_freeboard_m=minimum_freeboard_m,
    )
    _require_nonnegative(
        runoff_coefficient=runoff_coefficient,
        basin_bottom_elevation_m=basin_bottom_elevation_m,
        embankment_crest_elevation_m=embankment_crest_elevation_m,
        downstream_tailwater_elevation_m=downstream_tailwater_elevation_m,
        outlet_loss_m=outlet_loss_m,
        downstream_rim_elevation_m=downstream_rim_elevation_m,
    )
    if runoff_coefficient > 1.0:
        msg = "runoff_coefficient must be <= 1"
        raise ValueError(msg)
    if orifice_discharge_coefficient > 1.0:
        msg = "orifice_discharge_coefficient must be <= 1"
        raise ValueError(msg)
    if weir_discharge_coefficient > 1.0:
        msg = "weir_discharge_coefficient must be <= 1"
        raise ValueError(msg)
    if embankment_crest_elevation_m <= basin_bottom_elevation_m:
        msg = "embankment_crest_elevation_m must exceed basin_bottom_elevation_m"
        raise ValueError(msg)

    adjusted_rainfall_intensity_mm_h = rainfall_intensity_mm_h * climate_factor
    post_development_peak_flow_m3_s = runoff_coefficient * adjusted_rainfall_intensity_mm_h * catchment_area_ha / 360.0
    required_storage_volume_m3 = _triangular_detention_volume_m3(
        post_development_peak_flow_m3_s=post_development_peak_flow_m3_s,
        allowable_release_rate_m3_s=allowable_release_rate_m3_s,
        storm_duration_hr=storm_duration_hr,
    )

    available_storage_volume_m3 = (storage_bottom_area_m2 + storage_top_area_m2) / 2.0 * active_storage_depth_m
    storage_volume_margin_m3 = available_storage_volume_m3 - required_storage_volume_m3

    orifice_diameter_m = orifice_diameter_mm / 1000.0
    orifice_area_m2 = math.pi * orifice_diameter_m**2 / 4.0
    orifice_velocity_m_s = math.sqrt(2.0 * _G * orifice_head_m)
    controlled_orifice_release_m3_s = orifice_discharge_coefficient * orifice_area_m2 * orifice_velocity_m_s
    outlet_release_margin_m3_s = allowable_release_rate_m3_s - controlled_orifice_release_m3_s

    weir_coefficient = weir_discharge_coefficient * math.sqrt(2.0 * _G)
    emergency_weir_release_m3_s = weir_coefficient * emergency_weir_length_m * emergency_weir_head_m**1.5
    major_event_excess_flow_m3_s = major_event_peak_flow_m3_s - controlled_orifice_release_m3_s
    emergency_weir_margin_m3_s = emergency_weir_release_m3_s - major_event_excess_flow_m3_s

    design_water_surface_elevation_m = basin_bottom_elevation_m + active_storage_depth_m
    basin_freeboard_m = embankment_crest_elevation_m - design_water_surface_elevation_m
    freeboard_margin_m = basin_freeboard_m - minimum_freeboard_m

    downstream_hgl_m = downstream_tailwater_elevation_m + outlet_loss_m
    hgl_clearance_m = downstream_rim_elevation_m - downstream_hgl_m

    overall_pass_score = (
        1.0
        if min(
            storage_volume_margin_m3,
            outlet_release_margin_m3_s,
            emergency_weir_margin_m3_s,
            freeboard_margin_m,
            hgl_clearance_m,
        )
        >= 0.0
        else 0.0
    )

    return {
        "adjusted_rainfall_intensity_mm_h": round(adjusted_rainfall_intensity_mm_h, 3),
        "post_development_peak_flow_m3_s": round(post_development_peak_flow_m3_s, 3),
        "required_storage_volume_m3": round(required_storage_volume_m3, 3),
        "available_storage_volume_m3": round(available_storage_volume_m3, 3),
        "storage_volume_margin_m3": round(storage_volume_margin_m3, 3),
        "orifice_area_m2": round(orifice_area_m2, 3),
        "controlled_orifice_release_m3_s": round(controlled_orifice_release_m3_s, 3),
        "outlet_release_margin_m3_s": round(outlet_release_margin_m3_s, 3),
        "emergency_weir_release_m3_s": round(emergency_weir_release_m3_s, 3),
        "major_event_excess_flow_m3_s": round(major_event_excess_flow_m3_s, 3),
        "emergency_weir_margin_m3_s": round(emergency_weir_margin_m3_s, 3),
        "design_water_surface_elevation_m": round(design_water_surface_elevation_m, 3),
        "basin_freeboard_m": round(basin_freeboard_m, 3),
        "freeboard_margin_m": round(freeboard_margin_m, 3),
        "downstream_hgl_m": round(downstream_hgl_m, 3),
        "hgl_clearance_m": round(hgl_clearance_m, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
