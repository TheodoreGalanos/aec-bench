# ABOUTME: Computes SSC-07 excavation dewatering and temporary power metrics.
# ABOUTME: Keeps drawdown, seepage, pump power, backup runtime, and uplift checks source-bound.

from __future__ import annotations

import math


def compute(
    water_head_above_base_m: float,
    seepage_path_m: float,
    critical_gradient: float,
    slope_angle_deg: float,
    friction_angle_deg: float,
    pore_pressure_ratio: float,
    pump_flow_m3_s: float,
    pump_head_m: float,
    pump_efficiency: float,
    pump_count: float,
    controls_load_kw: float,
    generator_capacity_kw: float,
    battery_capacity_kwh: float,
    autonomy_load_kw: float,
    required_runtime_h: float,
    slab_resisting_pressure_kpa: float,
) -> dict[str, float]:
    """Compute excavation/dewatering source-pack metrics."""
    exit_gradient = water_head_above_base_m / seepage_path_m
    exit_gradient_fs = critical_gradient / exit_gradient
    rapid_drawdown_fs = (
        math.tan(math.radians(friction_angle_deg))
        / math.tan(math.radians(slope_angle_deg))
        * (1.0 - pore_pressure_ratio)
    )
    pump_power_kw = 9.81 * pump_flow_m3_s * pump_head_m / pump_efficiency
    temporary_power_kw = pump_power_kw * pump_count + controls_load_kw
    generator_margin_kw = generator_capacity_kw - temporary_power_kw
    battery_runtime_h = battery_capacity_kwh / autonomy_load_kw
    battery_runtime_margin_h = battery_runtime_h - required_runtime_h
    uplift_pressure_kpa = 9.81 * water_head_above_base_m
    uplift_margin_kpa = slab_resisting_pressure_kpa - uplift_pressure_kpa
    overall_pass_score = (
        1.0
        if (
            exit_gradient_fs >= 3.0
            and rapid_drawdown_fs >= 1.1
            and generator_margin_kw >= 0.0
            and battery_runtime_margin_h >= 0.0
            and uplift_margin_kpa >= 0.0
        )
        else 0.0
    )

    return {
        "exit_gradient": round(exit_gradient, 3),
        "exit_gradient_fs": round(exit_gradient_fs, 3),
        "rapid_drawdown_fs": round(rapid_drawdown_fs, 3),
        "pump_power_kw": round(pump_power_kw, 3),
        "temporary_power_kw": round(temporary_power_kw, 3),
        "generator_margin_kw": round(generator_margin_kw, 3),
        "battery_runtime_h": round(battery_runtime_h, 3),
        "battery_runtime_margin_h": round(battery_runtime_margin_h, 3),
        "uplift_pressure_kpa": round(uplift_pressure_kpa, 3),
        "uplift_margin_kpa": round(uplift_margin_kpa, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
