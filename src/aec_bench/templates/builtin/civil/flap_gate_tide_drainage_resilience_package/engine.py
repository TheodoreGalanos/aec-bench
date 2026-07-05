# ABOUTME: Computes SSC-04 flap-gate tide, drainage HGL, and resilience metrics.
# ABOUTME: Combines tailwater, flap headloss, upstream HGL, storage, pump, and battery checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    pipe_diameter_m: float,
    design_flow_m3_s: float,
    tide_level_m: float,
    surge_allowance_m: float,
    outfall_invert_m: float,
    flap_gate_loss_coefficient: float,
    pipe_friction_loss_m: float,
    road_low_point_level_m: float,
    incoming_flow_m3_s: float,
    gravity_relief_capacity_m3_s: float,
    tide_locked_duration_h: float,
    backup_storage_m3: float,
    pump_assist_flow_m3_s: float,
    pump_assist_head_m: float,
    pump_efficiency: float,
    control_battery_capacity_kwh: float,
    control_load_kw: float,
    required_control_runtime_h: float,
) -> dict[str, float]:
    """Compute deterministic flap-gate drainage resilience metrics."""
    _require_positive(
        pipe_diameter_m=pipe_diameter_m,
        design_flow_m3_s=design_flow_m3_s,
        flap_gate_loss_coefficient=flap_gate_loss_coefficient,
        road_low_point_level_m=road_low_point_level_m,
        incoming_flow_m3_s=incoming_flow_m3_s,
        tide_locked_duration_h=tide_locked_duration_h,
        backup_storage_m3=backup_storage_m3,
        pump_assist_flow_m3_s=pump_assist_flow_m3_s,
        pump_assist_head_m=pump_assist_head_m,
        pump_efficiency=pump_efficiency,
        control_battery_capacity_kwh=control_battery_capacity_kwh,
        control_load_kw=control_load_kw,
        required_control_runtime_h=required_control_runtime_h,
    )

    pipe_area_m2 = math.pi * pipe_diameter_m**2 / 4.0
    outlet_velocity_m_s = design_flow_m3_s / pipe_area_m2
    tailwater_level_m = tide_level_m + surge_allowance_m
    outfall_submergence_depth_m = max(tailwater_level_m - outfall_invert_m, 0.0)
    flap_gate_headloss_m = flap_gate_loss_coefficient * outlet_velocity_m_s**2 / (2.0 * 9.81)
    upstream_hgl_m = tailwater_level_m + flap_gate_headloss_m + pipe_friction_loss_m
    road_low_point_hgl_margin_m = road_low_point_level_m - upstream_hgl_m
    blocked_volume_m3 = max(incoming_flow_m3_s - gravity_relief_capacity_m3_s, 0.0) * tide_locked_duration_h * 3600.0
    storage_margin_m3 = backup_storage_m3 - blocked_volume_m3
    pump_input_power_kw = 1000.0 * 9.81 * pump_assist_flow_m3_s * pump_assist_head_m / pump_efficiency / 1000.0
    control_battery_margin_kwh = control_battery_capacity_kwh - control_load_kw * required_control_runtime_h

    pass_checks = [
        road_low_point_hgl_margin_m >= 0.0,
        storage_margin_m3 >= 0.0,
        control_battery_margin_kwh >= 0.0,
    ]

    return {
        "pipe_area_m2": round(pipe_area_m2, 3),
        "outlet_velocity_m_s": round(outlet_velocity_m_s, 3),
        "tailwater_level_m": round(tailwater_level_m, 3),
        "outfall_submergence_depth_m": round(outfall_submergence_depth_m, 3),
        "flap_gate_headloss_m": round(flap_gate_headloss_m, 3),
        "upstream_hgl_m": round(upstream_hgl_m, 3),
        "road_low_point_hgl_margin_m": round(road_low_point_hgl_margin_m, 3),
        "storage_margin_m3": round(storage_margin_m3, 3),
        "pump_input_power_kw": round(pump_input_power_kw, 3),
        "control_battery_margin_kwh": round(control_battery_margin_kwh, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
