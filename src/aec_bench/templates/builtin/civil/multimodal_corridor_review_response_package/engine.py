# ABOUTME: Computes SSC-01 multimodal corridor review response metrics.
# ABOUTME: Combines changed chainage, drainage, pedestrian, VMS, voltage, and comment checks.

from __future__ import annotations

_FT_TO_M = 0.3048


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    original_chainage_m: float,
    revised_chainage_m: float,
    revised_road_level_m: float,
    revised_hgl_m: float,
    minimum_hgl_clearance_mm: float,
    pedestrian_startup_time_s: float,
    revised_crossing_width_m: float,
    pedestrian_walk_speed_m_s: float,
    available_ped_clearance_s: float,
    vms_character_height_in: float,
    approach_speed_kmh: float,
    reading_rate_chars_s: float,
    revised_message_length_chars: float,
    revised_device_load_w: float,
    feeder_length_km: float,
    conductor_resistance_ohm_km: float,
    feeder_voltage_v: float,
    power_factor: float,
    allowable_voltage_drop_pct: float,
    review_comments_total: float,
    review_comments_closed: float,
    impacted_calculation_count: float,
) -> dict[str, float]:
    """Compute deterministic SSC-01 multimodal corridor review response metrics."""
    _require_positive(
        revised_crossing_width_m=revised_crossing_width_m,
        pedestrian_walk_speed_m_s=pedestrian_walk_speed_m_s,
        available_ped_clearance_s=available_ped_clearance_s,
        vms_character_height_in=vms_character_height_in,
        approach_speed_kmh=approach_speed_kmh,
        reading_rate_chars_s=reading_rate_chars_s,
        revised_device_load_w=revised_device_load_w,
        feeder_length_km=feeder_length_km,
        conductor_resistance_ohm_km=conductor_resistance_ohm_km,
        feeder_voltage_v=feeder_voltage_v,
        power_factor=power_factor,
        allowable_voltage_drop_pct=allowable_voltage_drop_pct,
        review_comments_total=review_comments_total,
        impacted_calculation_count=impacted_calculation_count,
    )
    changed_chainage_delta_m = revised_chainage_m - original_chainage_m
    hgl_clearance_mm = (revised_road_level_m - revised_hgl_m) * 1000.0
    hgl_clearance_margin_mm = hgl_clearance_mm - minimum_hgl_clearance_mm
    ped_clearance_required_s = pedestrian_startup_time_s + revised_crossing_width_m / pedestrian_walk_speed_m_s
    ped_clearance_margin_s = available_ped_clearance_s - ped_clearance_required_s
    vms_reading_time_s = vms_character_height_in * 40.0 * _FT_TO_M / (approach_speed_kmh / 3.6)
    vms_message_margin_chars = vms_reading_time_s * reading_rate_chars_s - revised_message_length_chars
    feeder_current_a = revised_device_load_w / (feeder_voltage_v * power_factor)
    feeder_voltage_drop_percent = (
        2.0 * feeder_length_km * conductor_resistance_ohm_km * feeder_current_a / feeder_voltage_v * 100.0
    )
    voltage_drop_margin_percent = allowable_voltage_drop_pct - feeder_voltage_drop_percent
    comment_closeout_percent = review_comments_closed / review_comments_total * 100.0

    pass_checks = [
        hgl_clearance_margin_mm >= 0.0,
        ped_clearance_margin_s >= 0.0,
        vms_message_margin_chars >= 0.0,
        voltage_drop_margin_percent >= 0.0,
        comment_closeout_percent >= 100.0,
    ]

    return {
        "changed_chainage_delta_m": round(changed_chainage_delta_m, 3),
        "hgl_clearance_mm": round(hgl_clearance_mm, 3),
        "hgl_clearance_margin_mm": round(hgl_clearance_margin_mm, 3),
        "ped_clearance_required_s": round(ped_clearance_required_s, 3),
        "ped_clearance_margin_s": round(ped_clearance_margin_s, 3),
        "vms_reading_time_s": round(vms_reading_time_s, 3),
        "vms_message_margin_chars": round(vms_message_margin_chars, 3),
        "feeder_voltage_drop_percent": round(feeder_voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "comment_closeout_percent": round(comment_closeout_percent, 3),
        "impacted_calculation_count": round(impacted_calculation_count, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
