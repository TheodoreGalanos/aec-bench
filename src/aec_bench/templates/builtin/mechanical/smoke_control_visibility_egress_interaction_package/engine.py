# ABOUTME: Computes SSC-08 smoke control, visibility, and egress interaction metrics.
# ABOUTME: Combines ACH, smoke layer, visibility, egress width/time, and battery checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    fire_zone_volume_m3: float,
    smoke_exhaust_flow_m3_h: float,
    required_air_changes_per_h: float,
    smoke_layer_height_m: float,
    minimum_smoke_layer_height_m: float,
    visibility_m: float,
    required_visibility_m: float,
    population_persons: float,
    egress_width_factor_mm_per_person: float,
    provided_egress_width_mm: float,
    egress_flow_rate_person_m_s: float,
    max_egress_time_s: float,
    ventilation_load_kw: float,
    alarm_load_kw: float,
    battery_capacity_kwh: float,
    battery_usable_fraction: float,
    required_runtime_h: float,
) -> dict[str, float]:
    """Compute deterministic smoke-control and egress interaction metrics."""
    _require_positive(
        fire_zone_volume_m3=fire_zone_volume_m3,
        smoke_exhaust_flow_m3_h=smoke_exhaust_flow_m3_h,
        required_air_changes_per_h=required_air_changes_per_h,
        smoke_layer_height_m=smoke_layer_height_m,
        minimum_smoke_layer_height_m=minimum_smoke_layer_height_m,
        visibility_m=visibility_m,
        required_visibility_m=required_visibility_m,
        population_persons=population_persons,
        egress_width_factor_mm_per_person=egress_width_factor_mm_per_person,
        provided_egress_width_mm=provided_egress_width_mm,
        egress_flow_rate_person_m_s=egress_flow_rate_person_m_s,
        max_egress_time_s=max_egress_time_s,
        ventilation_load_kw=ventilation_load_kw,
        alarm_load_kw=alarm_load_kw,
        battery_capacity_kwh=battery_capacity_kwh,
        battery_usable_fraction=battery_usable_fraction,
        required_runtime_h=required_runtime_h,
    )

    smoke_exhaust_air_changes_per_h = smoke_exhaust_flow_m3_h / fire_zone_volume_m3
    ach_margin = smoke_exhaust_air_changes_per_h - required_air_changes_per_h
    smoke_layer_height_margin_m = smoke_layer_height_m - minimum_smoke_layer_height_m
    visibility_margin_m = visibility_m - required_visibility_m
    required_egress_width_mm = population_persons * egress_width_factor_mm_per_person
    egress_width_margin_mm = provided_egress_width_mm - required_egress_width_mm
    egress_flow_time_s = population_persons / ((provided_egress_width_mm / 1000.0) * egress_flow_rate_person_m_s)
    egress_time_margin_s = max_egress_time_s - egress_flow_time_s
    life_safety_battery_margin_kwh = battery_capacity_kwh * battery_usable_fraction
    life_safety_battery_margin_kwh -= (ventilation_load_kw + alarm_load_kw) * required_runtime_h

    pass_checks = [
        ach_margin >= 0.0,
        smoke_layer_height_margin_m >= 0.0,
        visibility_margin_m >= 0.0,
        egress_width_margin_mm >= 0.0,
        egress_time_margin_s >= 0.0,
        life_safety_battery_margin_kwh >= 0.0,
    ]

    return {
        "smoke_exhaust_air_changes_per_h": round(smoke_exhaust_air_changes_per_h, 3),
        "ach_margin": round(ach_margin, 3),
        "smoke_layer_height_margin_m": round(smoke_layer_height_margin_m, 3),
        "visibility_margin_m": round(visibility_margin_m, 3),
        "required_egress_width_mm": round(required_egress_width_mm, 3),
        "egress_width_margin_mm": round(egress_width_margin_mm, 3),
        "egress_flow_time_s": round(egress_flow_time_s, 3),
        "egress_time_margin_s": round(egress_time_margin_s, 3),
        "life_safety_battery_margin_kwh": round(life_safety_battery_margin_kwh, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
