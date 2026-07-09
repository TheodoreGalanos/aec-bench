# ABOUTME: Computes SSC-19 alarm, smoke control, and emergency power metrics.
# ABOUTME: Combines NAC current, smoke loads, battery autonomy, generator sizing, and ACH checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    strobe_count: float,
    strobe_current_a: float,
    speaker_count: float,
    speaker_current_a: float,
    nac_capacity_a: float,
    smoke_fan_count: float,
    smoke_fan_power_kw: float,
    smoke_control_load_kw: float,
    battery_autonomy_h: float,
    battery_dc_voltage_v: float,
    usable_battery_fraction: float,
    installed_battery_ah: float,
    generator_rating_kw: float,
    starting_factor: float,
    smoke_zone_volume_m3: float,
    exhaust_flow_m3_s: float,
    required_smoke_exhaust_ach: float,
) -> dict[str, float]:
    """Compute deterministic alarm, smoke control, and emergency power metrics."""
    _require_positive(
        strobe_count=strobe_count,
        strobe_current_a=strobe_current_a,
        speaker_count=speaker_count,
        speaker_current_a=speaker_current_a,
        nac_capacity_a=nac_capacity_a,
        smoke_fan_count=smoke_fan_count,
        smoke_fan_power_kw=smoke_fan_power_kw,
        smoke_control_load_kw=smoke_control_load_kw,
        battery_autonomy_h=battery_autonomy_h,
        battery_dc_voltage_v=battery_dc_voltage_v,
        usable_battery_fraction=usable_battery_fraction,
        installed_battery_ah=installed_battery_ah,
        generator_rating_kw=generator_rating_kw,
        starting_factor=starting_factor,
        smoke_zone_volume_m3=smoke_zone_volume_m3,
        exhaust_flow_m3_s=exhaust_flow_m3_s,
        required_smoke_exhaust_ach=required_smoke_exhaust_ach,
    )
    if usable_battery_fraction > 1.0:
        msg = "usable_battery_fraction must be <= 1"
        raise ValueError(msg)

    nac_current_a = strobe_count * strobe_current_a + speaker_count * speaker_current_a
    nac_current_margin_a = nac_capacity_a - nac_current_a
    smoke_control_total_kw = smoke_fan_count * smoke_fan_power_kw + smoke_control_load_kw
    battery_required_ah = nac_current_a * battery_autonomy_h / usable_battery_fraction
    battery_capacity_margin_ah = installed_battery_ah - battery_required_ah
    generator_required_kw = smoke_control_total_kw * starting_factor + nac_current_a * battery_dc_voltage_v / 1000.0
    generator_margin_kw = generator_rating_kw - generator_required_kw
    smoke_exhaust_ach = exhaust_flow_m3_s * 3600.0 / smoke_zone_volume_m3
    smoke_exhaust_ach_margin = smoke_exhaust_ach - required_smoke_exhaust_ach

    pass_checks = [
        nac_current_margin_a >= 0.0,
        battery_capacity_margin_ah >= 0.0,
        generator_margin_kw >= 0.0,
        smoke_exhaust_ach_margin >= 0.0,
    ]

    return {
        "nac_current_a": round(nac_current_a, 3),
        "nac_current_margin_a": round(nac_current_margin_a, 3),
        "smoke_control_load_kw": round(smoke_control_total_kw, 3),
        "battery_required_ah": round(battery_required_ah, 3),
        "battery_capacity_margin_ah": round(battery_capacity_margin_ah, 3),
        "generator_required_kw": round(generator_required_kw, 3),
        "generator_margin_kw": round(generator_margin_kw, 3),
        "smoke_exhaust_ach": round(smoke_exhaust_ach, 3),
        "smoke_exhaust_ach_margin": round(smoke_exhaust_ach_margin, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
