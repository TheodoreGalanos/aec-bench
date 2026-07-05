# ABOUTME: Computes SSC-02 rail drainage, flood-clearance, and speed-restriction metrics.
# ABOUTME: Combines rational-method peak flow, culvert margin, freeboard, and exposure checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    catchment_area_ha: float,
    rainfall_intensity_mm_h: float,
    runoff_coefficient: float,
    culvert_capacity_m3_s: float,
    track_low_rail_level_m: float,
    flood_level_m: float,
    required_freeboard_m: float,
    equipment_plinth_level_m: float,
    minimum_equipment_clearance_m: float,
    normal_speed_kmh: float,
    restricted_speed_kmh: float,
) -> dict[str, float]:
    """Compute source-bound rail drainage, clearance, and speed-restriction metrics."""
    _require_positive(
        catchment_area_ha=catchment_area_ha,
        rainfall_intensity_mm_h=rainfall_intensity_mm_h,
        runoff_coefficient=runoff_coefficient,
        culvert_capacity_m3_s=culvert_capacity_m3_s,
        required_freeboard_m=required_freeboard_m,
        minimum_equipment_clearance_m=minimum_equipment_clearance_m,
        normal_speed_kmh=normal_speed_kmh,
        restricted_speed_kmh=restricted_speed_kmh,
    )
    if runoff_coefficient > 1.0:
        msg = "runoff_coefficient must be <= 1"
        raise ValueError(msg)
    if restricted_speed_kmh > normal_speed_kmh:
        msg = "restricted_speed_kmh must be <= normal_speed_kmh"
        raise ValueError(msg)

    peak_flow_m3_s = 0.00278 * runoff_coefficient * rainfall_intensity_mm_h * catchment_area_ha
    culvert_capacity_margin_m3_s = culvert_capacity_m3_s - peak_flow_m3_s
    track_freeboard_m = track_low_rail_level_m - flood_level_m
    freeboard_margin_m = track_freeboard_m - required_freeboard_m
    equipment_freeboard_m = equipment_plinth_level_m - flood_level_m
    equipment_exposure_margin_m = equipment_freeboard_m - minimum_equipment_clearance_m
    speed_reduction_kmh = normal_speed_kmh - restricted_speed_kmh
    restriction_pass_score = (
        1.0 if min(culvert_capacity_margin_m3_s, freeboard_margin_m, equipment_exposure_margin_m) >= 0.0 else 0.0
    )
    overall_pass_score = restriction_pass_score

    return {
        "peak_flow_m3_s": round(peak_flow_m3_s, 3),
        "culvert_capacity_margin_m3_s": round(culvert_capacity_margin_m3_s, 3),
        "track_freeboard_m": round(track_freeboard_m, 3),
        "freeboard_margin_m": round(freeboard_margin_m, 3),
        "equipment_freeboard_m": round(equipment_freeboard_m, 3),
        "equipment_exposure_margin_m": round(equipment_exposure_margin_m, 3),
        "speed_reduction_kmh": round(speed_reduction_kmh, 3),
        "restriction_pass_score": round(restriction_pass_score, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
