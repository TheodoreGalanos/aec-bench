# ABOUTME: Computes SSC-12 fire alarm audibility and occupancy metrics.
# ABOUTME: Combines room RT60, NAC audibility, notification current, and battery checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    room_area_m2: float,
    ceiling_height_m: float,
    absorption_area_m2: float,
    max_rt60_s: float,
    nac_sound_level_dba: float,
    farthest_receiver_distance_m: float,
    room_loss_db: float,
    audible_nac_count: float,
    audibility_criterion_dba: float,
    horn_count: float,
    horn_current_a: float,
    strobe_count: float,
    strobe_current_a: float,
    panel_current_a: float,
    nac_supply_capacity_a: float,
    alarm_load_w: float,
    backup_runtime_h: float,
    alarm_battery_capacity_kwh: float,
) -> dict[str, float]:
    """Compute deterministic alarm audibility, current, and battery checks."""
    _require_positive(
        room_area_m2=room_area_m2,
        ceiling_height_m=ceiling_height_m,
        absorption_area_m2=absorption_area_m2,
        max_rt60_s=max_rt60_s,
        nac_sound_level_dba=nac_sound_level_dba,
        farthest_receiver_distance_m=farthest_receiver_distance_m,
        audible_nac_count=audible_nac_count,
        audibility_criterion_dba=audibility_criterion_dba,
        horn_count=horn_count,
        horn_current_a=horn_current_a,
        strobe_count=strobe_count,
        strobe_current_a=strobe_current_a,
        nac_supply_capacity_a=nac_supply_capacity_a,
        alarm_load_w=alarm_load_w,
        backup_runtime_h=backup_runtime_h,
        alarm_battery_capacity_kwh=alarm_battery_capacity_kwh,
    )
    if min(room_loss_db, panel_current_a) < 0:
        msg = "room_loss_db and panel_current_a must be >= 0"
        raise ValueError(msg)

    room_volume_m3 = room_area_m2 * ceiling_height_m
    room_rt60_s = 0.161 * room_volume_m3 / absorption_area_m2
    rt60_margin_s = max_rt60_s - room_rt60_s
    farthest_nac_level_dba = nac_sound_level_dba - 20.0 * math.log10(farthest_receiver_distance_m) - room_loss_db
    combined_alarm_level_dba = 10.0 * math.log10(audible_nac_count * 10.0 ** (farthest_nac_level_dba / 10.0))
    audibility_margin_db = audibility_criterion_dba - combined_alarm_level_dba
    nac_current_a = horn_count * horn_current_a + strobe_count * strobe_current_a + panel_current_a
    nac_headroom_a = nac_supply_capacity_a - nac_current_a
    alarm_battery_required_kwh = alarm_load_w * backup_runtime_h / 1000.0
    alarm_battery_margin_kwh = alarm_battery_capacity_kwh - alarm_battery_required_kwh

    pass_checks = [
        rt60_margin_s >= 0.0,
        audibility_margin_db >= 0.0,
        nac_headroom_a >= 0.0,
        alarm_battery_margin_kwh >= 0.0,
    ]

    return {
        "room_rt60_s": round(room_rt60_s, 3),
        "rt60_margin_s": round(rt60_margin_s, 3),
        "farthest_nac_level_dba": round(farthest_nac_level_dba, 3),
        "combined_alarm_level_dba": round(combined_alarm_level_dba, 3),
        "audibility_margin_db": round(audibility_margin_db, 3),
        "nac_current_a": round(nac_current_a, 3),
        "nac_headroom_a": round(nac_headroom_a, 3),
        "alarm_battery_required_kwh": round(alarm_battery_required_kwh, 3),
        "alarm_battery_margin_kwh": round(alarm_battery_margin_kwh, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
