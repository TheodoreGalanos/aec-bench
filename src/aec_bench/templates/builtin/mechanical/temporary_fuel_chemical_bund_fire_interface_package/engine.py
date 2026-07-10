# ABOUTME: Computes SSC-16 temporary fuel chemical bund and fire interface metrics.
# ABOUTME: Combines bund volume, fire HRR, visibility, alarm load, battery, and response checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    largest_container_l: float,
    rainfall_allowance_l: float,
    provided_bund_volume_l: float,
    fire_growth_alpha_kw_s2: float,
    design_fire_time_s: float,
    provided_visibility_m: float,
    required_visibility_m: float,
    horn_count: float,
    horn_current_a: float,
    strobe_count: float,
    strobe_current_a: float,
    panel_current_a: float,
    nac_supply_capacity_a: float,
    alarm_load_w: float,
    alarm_runtime_h: float,
    alarm_battery_capacity_kwh: float,
    isolated_drain_count: float,
    total_drain_count: float,
    allowed_spill_response_min: float,
    planned_spill_response_min: float,
) -> dict[str, float]:
    """Compute deterministic temporary bund and fire interface checks."""
    _require_positive(
        largest_container_l=largest_container_l,
        rainfall_allowance_l=rainfall_allowance_l,
        provided_bund_volume_l=provided_bund_volume_l,
        fire_growth_alpha_kw_s2=fire_growth_alpha_kw_s2,
        design_fire_time_s=design_fire_time_s,
        provided_visibility_m=provided_visibility_m,
        required_visibility_m=required_visibility_m,
        horn_count=horn_count,
        horn_current_a=horn_current_a,
        strobe_count=strobe_count,
        strobe_current_a=strobe_current_a,
        nac_supply_capacity_a=nac_supply_capacity_a,
        alarm_load_w=alarm_load_w,
        alarm_runtime_h=alarm_runtime_h,
        alarm_battery_capacity_kwh=alarm_battery_capacity_kwh,
        total_drain_count=total_drain_count,
        allowed_spill_response_min=allowed_spill_response_min,
        planned_spill_response_min=planned_spill_response_min,
    )
    if min(panel_current_a, isolated_drain_count) < 0:
        msg = "panel_current_a and isolated_drain_count must be >= 0"
        raise ValueError(msg)

    required_bund_volume_l = largest_container_l + rainfall_allowance_l
    bund_volume_margin_l = provided_bund_volume_l - required_bund_volume_l
    fire_hrr_kw = fire_growth_alpha_kw_s2 * design_fire_time_s**2
    visibility_margin_m = provided_visibility_m - required_visibility_m
    nac_current_a = horn_count * horn_current_a + strobe_count * strobe_current_a + panel_current_a
    nac_headroom_a = nac_supply_capacity_a - nac_current_a
    alarm_battery_required_kwh = alarm_load_w * alarm_runtime_h / 1000.0
    alarm_battery_margin_kwh = alarm_battery_capacity_kwh - alarm_battery_required_kwh
    drain_isolation_fraction = isolated_drain_count / total_drain_count
    spill_response_margin_min = allowed_spill_response_min - planned_spill_response_min

    pass_checks = [
        bund_volume_margin_l >= 0.0,
        visibility_margin_m >= 0.0,
        nac_headroom_a >= 0.0,
        alarm_battery_margin_kwh >= 0.0,
        drain_isolation_fraction >= 1.0,
        spill_response_margin_min >= 0.0,
    ]

    return {
        "required_bund_volume_l": round(required_bund_volume_l, 3),
        "bund_volume_margin_l": round(bund_volume_margin_l, 3),
        "fire_hrr_kw": round(fire_hrr_kw, 3),
        "visibility_margin_m": round(visibility_margin_m, 3),
        "nac_current_a": round(nac_current_a, 3),
        "nac_headroom_a": round(nac_headroom_a, 3),
        "alarm_battery_required_kwh": round(alarm_battery_required_kwh, 3),
        "alarm_battery_margin_kwh": round(alarm_battery_margin_kwh, 3),
        "drain_isolation_fraction": round(drain_isolation_fraction, 3),
        "spill_response_margin_min": round(spill_response_margin_min, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
