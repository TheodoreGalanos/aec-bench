# ABOUTME: Computes SSC-07 buried pipe thrust block and soil resistance metrics.
# ABOUTME: Combines transient thrust, passive resistance, bearing, uplift, and headloss checks.

from __future__ import annotations

import math


def compute(
    pipe_diameter_m: float,
    transient_pressure_kpa: float,
    bend_angle_deg: float,
    passive_resistance_kn: float,
    thrust_block_vertical_load_kn: float,
    thrust_block_base_area_m2: float,
    allowable_bearing_kpa: float,
    groundwater_head_m: float,
    cover_resisting_pressure_kpa: float,
    pipe_length_m: float,
    flow_m3_s: float,
    hazen_williams_c: float,
) -> dict[str, float]:
    """Compute buried-pipe thrust and soil-resistance source-pack metrics."""
    pipe_internal_area_m2 = math.pi * pipe_diameter_m**2 / 4.0
    transient_thrust_kn = (
        2.0 * transient_pressure_kpa * pipe_internal_area_m2 * math.sin(math.radians(bend_angle_deg / 2.0))
    )
    thrust_resistance_margin_kn = passive_resistance_kn - transient_thrust_kn
    thrust_utilization = transient_thrust_kn / passive_resistance_kn
    bearing_pressure_kpa = thrust_block_vertical_load_kn / thrust_block_base_area_m2
    bearing_margin_kpa = allowable_bearing_kpa - bearing_pressure_kpa
    uplift_pressure_kpa = 9.81 * groundwater_head_m
    uplift_margin_kpa = cover_resisting_pressure_kpa - uplift_pressure_kpa
    hazen_williams_headloss_m = (
        10.67 * pipe_length_m * flow_m3_s**1.852 / (hazen_williams_c**1.852 * pipe_diameter_m**4.871)
    )
    overall_pass_score = (
        1.0 if thrust_resistance_margin_kn >= 0.0 and bearing_margin_kpa >= 0.0 and uplift_margin_kpa >= 0.0 else 0.0
    )

    return {
        "pipe_internal_area_m2": round(pipe_internal_area_m2, 3),
        "transient_thrust_kn": round(transient_thrust_kn, 3),
        "thrust_resistance_margin_kn": round(thrust_resistance_margin_kn, 3),
        "thrust_utilization": round(thrust_utilization, 3),
        "bearing_pressure_kpa": round(bearing_pressure_kpa, 3),
        "bearing_margin_kpa": round(bearing_margin_kpa, 3),
        "uplift_pressure_kpa": round(uplift_pressure_kpa, 3),
        "uplift_margin_kpa": round(uplift_margin_kpa, 3),
        "hazen_williams_headloss_m": round(hazen_williams_headloss_m, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
