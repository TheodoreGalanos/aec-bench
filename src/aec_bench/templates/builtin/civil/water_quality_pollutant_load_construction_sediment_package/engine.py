# ABOUTME: Computes SSC-03 water-quality, pollutant-load, and sediment basin metrics.
# ABOUTME: Combines runoff volume, pollutant load, basin sizing, temporary discharge, and capture checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    disturbed_area_ha: float,
    runoff_depth_mm: float,
    pollutant_concentration_mg_l: float,
    removal_efficiency: float,
    sediment_basin_volume_m3: float,
    required_volume_per_ha_m3: float,
    dewatering_flow_l_s: float,
    temporary_channel_capacity_l_s: float,
    weir_discharge_coefficient: float,
    outlet_weir_length_m: float,
    outlet_weir_head_m: float,
    target_capture_percent: float,
) -> dict[str, float]:
    """Compute deterministic SSC-03 water-quality and sediment metrics."""
    _require_positive(
        disturbed_area_ha=disturbed_area_ha,
        runoff_depth_mm=runoff_depth_mm,
        pollutant_concentration_mg_l=pollutant_concentration_mg_l,
        sediment_basin_volume_m3=sediment_basin_volume_m3,
        required_volume_per_ha_m3=required_volume_per_ha_m3,
        dewatering_flow_l_s=dewatering_flow_l_s,
        temporary_channel_capacity_l_s=temporary_channel_capacity_l_s,
        weir_discharge_coefficient=weir_discharge_coefficient,
        outlet_weir_length_m=outlet_weir_length_m,
        outlet_weir_head_m=outlet_weir_head_m,
        target_capture_percent=target_capture_percent,
    )
    if removal_efficiency < 0 or removal_efficiency > 1:
        msg = "removal_efficiency must be between 0 and 1"
        raise ValueError(msg)

    runoff_volume_m3 = disturbed_area_ha * 10000.0 * runoff_depth_mm / 1000.0
    pollutant_load_kg = runoff_volume_m3 * pollutant_concentration_mg_l / 1000.0
    removed_load_kg = pollutant_load_kg * removal_efficiency
    residual_load_kg = pollutant_load_kg - removed_load_kg
    required_basin_volume_m3 = disturbed_area_ha * required_volume_per_ha_m3
    basin_volume_margin_m3 = sediment_basin_volume_m3 - required_basin_volume_m3
    temporary_discharge_margin_l_s = temporary_channel_capacity_l_s - dewatering_flow_l_s
    weir_release_l_s = weir_discharge_coefficient * outlet_weir_length_m * outlet_weir_head_m**1.5 * 1000.0
    capture_percent = removal_efficiency * 100.0
    capture_margin_percent = capture_percent - target_capture_percent

    pass_checks = [
        basin_volume_margin_m3 >= 0.0,
        temporary_discharge_margin_l_s >= 0.0,
        capture_margin_percent >= 0.0,
    ]

    return {
        "runoff_volume_m3": round(runoff_volume_m3, 3),
        "pollutant_load_kg": round(pollutant_load_kg, 3),
        "removed_load_kg": round(removed_load_kg, 3),
        "residual_load_kg": round(residual_load_kg, 3),
        "required_basin_volume_m3": round(required_basin_volume_m3, 3),
        "basin_volume_margin_m3": round(basin_volume_margin_m3, 3),
        "temporary_discharge_margin_l_s": round(temporary_discharge_margin_l_s, 3),
        "weir_release_l_s": round(weir_release_l_s, 3),
        "capture_percent": round(capture_percent, 3),
        "capture_margin_percent": round(capture_margin_percent, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
