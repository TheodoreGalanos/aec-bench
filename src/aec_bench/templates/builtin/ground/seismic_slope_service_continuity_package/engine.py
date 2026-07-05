# ABOUTME: Computes SSC-07 seismic slope and service continuity metrics.
# ABOUTME: Combines pseudo-static slope screening with utility capacity and voltage-drop checks.

from __future__ import annotations

import math


def compute(
    slope_angle_deg: float,
    friction_angle_deg: float,
    cohesion_kpa: float,
    soil_unit_weight_kn_m3: float,
    failure_depth_m: float,
    seismic_coefficient: float,
    service_load_kw: float,
    backup_capacity_kw: float,
    feeder_current_a: float,
    feeder_resistance_ohm_km: float,
    feeder_length_km: float,
    feeder_voltage_v: float,
    allowable_voltage_drop_percent: float,
) -> dict[str, float]:
    """Compute seismic slope and service-continuity source-pack metrics."""
    slope_angle_rad = math.radians(slope_angle_deg)
    friction_angle_rad = math.radians(friction_angle_deg)
    slope_resisting_kpa = cohesion_kpa + (
        soil_unit_weight_kn_m3 * failure_depth_m * math.cos(slope_angle_rad) ** 2 * math.tan(friction_angle_rad)
    )
    static_driving_kpa = (
        soil_unit_weight_kn_m3 * failure_depth_m * math.sin(slope_angle_rad) * math.cos(slope_angle_rad)
    )
    seismic_increment_kpa = (
        seismic_coefficient * soil_unit_weight_kn_m3 * failure_depth_m * math.cos(slope_angle_rad) ** 2
    )
    static_slope_fs = slope_resisting_kpa / static_driving_kpa
    seismic_slope_fs = slope_resisting_kpa / (static_driving_kpa + seismic_increment_kpa)
    seismic_fs_margin = seismic_slope_fs - 1.1
    service_capacity_margin_kw = backup_capacity_kw - service_load_kw
    feeder_voltage_drop_percent = (
        math.sqrt(3.0) * feeder_current_a * feeder_resistance_ohm_km * feeder_length_km / feeder_voltage_v * 100.0
    )
    voltage_drop_margin_percent = allowable_voltage_drop_percent - feeder_voltage_drop_percent
    overall_pass_score = (
        1.0
        if (seismic_fs_margin >= 0.0 and service_capacity_margin_kw >= 0.0 and voltage_drop_margin_percent >= 0.0)
        else 0.0
    )

    return {
        "slope_resisting_kpa": round(slope_resisting_kpa, 3),
        "static_driving_kpa": round(static_driving_kpa, 3),
        "seismic_increment_kpa": round(seismic_increment_kpa, 3),
        "static_slope_fs": round(static_slope_fs, 3),
        "seismic_slope_fs": round(seismic_slope_fs, 3),
        "seismic_fs_margin": round(seismic_fs_margin, 3),
        "service_capacity_margin_kw": round(service_capacity_margin_kw, 3),
        "feeder_voltage_drop_percent": round(feeder_voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
