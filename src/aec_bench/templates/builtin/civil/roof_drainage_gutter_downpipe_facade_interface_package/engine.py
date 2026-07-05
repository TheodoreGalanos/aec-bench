# ABOUTME: Computes SSC-03/SSC-09 roof drainage, downpipe, overflow, and facade interface metrics.
# ABOUTME: Combines roof runoff, gutter/downpipe capacity, overflow route, freeboard, and fixing pressure.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    roof_catchment_area_m2: float,
    rainfall_intensity_mm_h: float,
    runoff_coefficient: float,
    gutter_capacity_l_s: float,
    downpipe_count: float,
    downpipe_capacity_l_s: float,
    overflow_weir_coefficient: float,
    overflow_weir_length_m: float,
    overflow_head_m: float,
    parapet_freeboard_m: float,
    minimum_freeboard_m: float,
    facade_zone_pressure_kpa: float,
    fixing_allowable_pressure_kpa: float,
) -> dict[str, float]:
    """Compute deterministic roof drainage and facade interface metrics."""
    _require_positive(
        roof_catchment_area_m2=roof_catchment_area_m2,
        rainfall_intensity_mm_h=rainfall_intensity_mm_h,
        runoff_coefficient=runoff_coefficient,
        gutter_capacity_l_s=gutter_capacity_l_s,
        downpipe_count=downpipe_count,
        downpipe_capacity_l_s=downpipe_capacity_l_s,
        overflow_weir_coefficient=overflow_weir_coefficient,
        overflow_weir_length_m=overflow_weir_length_m,
        overflow_head_m=overflow_head_m,
        minimum_freeboard_m=minimum_freeboard_m,
        fixing_allowable_pressure_kpa=fixing_allowable_pressure_kpa,
    )

    roof_runoff_l_s = roof_catchment_area_m2 * rainfall_intensity_mm_h * runoff_coefficient / 3600.0
    gutter_capacity_margin_l_s = gutter_capacity_l_s - roof_runoff_l_s
    downpipe_total_capacity_l_s = downpipe_count * downpipe_capacity_l_s
    downpipe_capacity_margin_l_s = downpipe_total_capacity_l_s - roof_runoff_l_s
    overflow_demand_l_s = max(roof_runoff_l_s - gutter_capacity_l_s, 0.0)
    overflow_capacity_l_s = overflow_weir_coefficient * overflow_weir_length_m * overflow_head_m**1.5 * 1000.0
    overflow_capacity_margin_l_s = overflow_capacity_l_s - overflow_demand_l_s
    freeboard_margin_m = parapet_freeboard_m - minimum_freeboard_m
    facade_fixing_pressure_margin_kpa = fixing_allowable_pressure_kpa - facade_zone_pressure_kpa

    pass_checks = [
        gutter_capacity_margin_l_s >= 0.0,
        downpipe_capacity_margin_l_s >= 0.0,
        overflow_capacity_margin_l_s >= 0.0,
        freeboard_margin_m >= 0.0,
        facade_fixing_pressure_margin_kpa >= 0.0,
    ]

    return {
        "roof_runoff_l_s": round(roof_runoff_l_s, 3),
        "gutter_capacity_margin_l_s": round(gutter_capacity_margin_l_s, 3),
        "downpipe_total_capacity_l_s": round(downpipe_total_capacity_l_s, 3),
        "downpipe_capacity_margin_l_s": round(downpipe_capacity_margin_l_s, 3),
        "overflow_capacity_l_s": round(overflow_capacity_l_s, 3),
        "overflow_capacity_margin_l_s": round(overflow_capacity_margin_l_s, 3),
        "freeboard_margin_m": round(freeboard_margin_m, 3),
        "facade_fixing_pressure_margin_kpa": round(facade_fixing_pressure_margin_kpa, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
