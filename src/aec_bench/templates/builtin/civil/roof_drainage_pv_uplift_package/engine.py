# ABOUTME: Computes SSC-09 roof drainage, PV layout, and wind uplift metrics.
# ABOUTME: Combines roof runoff, gutter/downpipe capacity, PV uplift, fixing, and obstruction checks.

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
    pv_array_area_m2: float,
    pv_uplift_pressure_kpa: float,
    pv_dead_load_kpa: float,
    pv_fixing_capacity_kn: float,
    drainage_obstruction_area_m2: float,
    max_drainage_obstruction_area_m2: float,
) -> dict[str, float]:
    """Compute deterministic roof drainage, PV uplift, and fixing metrics."""
    _require_positive(
        roof_catchment_area_m2=roof_catchment_area_m2,
        rainfall_intensity_mm_h=rainfall_intensity_mm_h,
        runoff_coefficient=runoff_coefficient,
        gutter_capacity_l_s=gutter_capacity_l_s,
        downpipe_count=downpipe_count,
        downpipe_capacity_l_s=downpipe_capacity_l_s,
        pv_array_area_m2=pv_array_area_m2,
        pv_uplift_pressure_kpa=pv_uplift_pressure_kpa,
        pv_dead_load_kpa=pv_dead_load_kpa,
        pv_fixing_capacity_kn=pv_fixing_capacity_kn,
        max_drainage_obstruction_area_m2=max_drainage_obstruction_area_m2,
    )

    roof_runoff_l_s = roof_catchment_area_m2 * rainfall_intensity_mm_h * runoff_coefficient / 3600.0
    gutter_capacity_margin_l_s = gutter_capacity_l_s - roof_runoff_l_s
    downpipe_total_capacity_l_s = downpipe_count * downpipe_capacity_l_s
    downpipe_capacity_margin_l_s = downpipe_total_capacity_l_s - roof_runoff_l_s
    pv_uplift_force_kn = pv_array_area_m2 * pv_uplift_pressure_kpa
    pv_dead_load_kn = pv_array_area_m2 * pv_dead_load_kpa
    pv_fixing_margin_kn = pv_fixing_capacity_kn - pv_uplift_force_kn
    drainage_obstruction_margin_m2 = max_drainage_obstruction_area_m2 - drainage_obstruction_area_m2

    pass_checks = [
        gutter_capacity_margin_l_s >= 0.0,
        downpipe_capacity_margin_l_s >= 0.0,
        pv_fixing_margin_kn >= 0.0,
        drainage_obstruction_margin_m2 >= 0.0,
    ]

    return {
        "roof_runoff_l_s": round(roof_runoff_l_s, 3),
        "gutter_capacity_margin_l_s": round(gutter_capacity_margin_l_s, 3),
        "downpipe_total_capacity_l_s": round(downpipe_total_capacity_l_s, 3),
        "downpipe_capacity_margin_l_s": round(downpipe_capacity_margin_l_s, 3),
        "pv_uplift_force_kn": round(pv_uplift_force_kn, 3),
        "pv_dead_load_kn": round(pv_dead_load_kn, 3),
        "pv_fixing_margin_kn": round(pv_fixing_margin_kn, 3),
        "drainage_obstruction_margin_m2": round(drainage_obstruction_margin_m2, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
