# ABOUTME: Computes SSC-01 bus priority signal corridor and cabinet load metrics.
# ABOUTME: Combines signal timing, person capacity, cabinet load, feeder, and battery checks.

from __future__ import annotations

_G = 9.81


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    bus_approach_speed_kmh: float,
    bus_approach_grade_pct: float,
    yellow_reaction_time_s: float,
    yellow_deceleration_m_s2: float,
    intersection_width_m: float,
    bus_length_m: float,
    all_red_speed_kmh: float,
    buses_per_hour: float,
    bus_occupancy_pax: float,
    peak_passenger_demand_pax_h: float,
    controller_load_w: float,
    detector_count: float,
    detector_load_w: float,
    transit_radio_load_w: float,
    vms_load_w: float,
    signal_heads_load_w: float,
    cabinet_capacity_w: float,
    feeder_voltage_v: float,
    power_factor: float,
    feeder_length_km: float,
    conductor_resistance_ohm_km: float,
    allowable_voltage_drop_pct: float,
    battery_capacity_kwh: float,
    battery_efficiency: float,
    required_backup_h: float,
) -> dict[str, float]:
    """Compute deterministic SSC-01 bus priority signal corridor metrics."""
    _require_positive(
        bus_approach_speed_kmh=bus_approach_speed_kmh,
        yellow_reaction_time_s=yellow_reaction_time_s,
        yellow_deceleration_m_s2=yellow_deceleration_m_s2,
        intersection_width_m=intersection_width_m,
        bus_length_m=bus_length_m,
        all_red_speed_kmh=all_red_speed_kmh,
        buses_per_hour=buses_per_hour,
        bus_occupancy_pax=bus_occupancy_pax,
        peak_passenger_demand_pax_h=peak_passenger_demand_pax_h,
        cabinet_capacity_w=cabinet_capacity_w,
        feeder_voltage_v=feeder_voltage_v,
        power_factor=power_factor,
        feeder_length_km=feeder_length_km,
        conductor_resistance_ohm_km=conductor_resistance_ohm_km,
        allowable_voltage_drop_pct=allowable_voltage_drop_pct,
        battery_capacity_kwh=battery_capacity_kwh,
        battery_efficiency=battery_efficiency,
        required_backup_h=required_backup_h,
    )
    speed_m_s = bus_approach_speed_kmh / 3.6
    grade_fraction = bus_approach_grade_pct / 100.0
    yellow_interval_s = yellow_reaction_time_s + speed_m_s / (
        2.0 * yellow_deceleration_m_s2 + 2.0 * _G * grade_fraction
    )
    all_red_interval_s = (intersection_width_m + bus_length_m) / (all_red_speed_kmh / 3.6)
    bus_handling_capacity_pax_h = buses_per_hour * bus_occupancy_pax
    bus_capacity_margin_pax_h = bus_handling_capacity_pax_h - peak_passenger_demand_pax_h
    cabinet_load_w = (
        controller_load_w + detector_count * detector_load_w + transit_radio_load_w + vms_load_w + signal_heads_load_w
    )
    cabinet_load_margin_w = cabinet_capacity_w - cabinet_load_w
    feeder_current_a = cabinet_load_w / (feeder_voltage_v * power_factor)
    feeder_voltage_drop_percent = (
        2.0 * feeder_length_km * conductor_resistance_ohm_km * feeder_current_a / feeder_voltage_v * 100.0
    )
    voltage_drop_margin_percent = allowable_voltage_drop_pct - feeder_voltage_drop_percent
    battery_runtime_h = battery_capacity_kwh * battery_efficiency / (cabinet_load_w / 1000.0)
    battery_margin_h = battery_runtime_h - required_backup_h

    pass_checks = [
        yellow_interval_s > 0.0,
        all_red_interval_s > 0.0,
        bus_capacity_margin_pax_h >= 0.0,
        cabinet_load_margin_w >= 0.0,
        voltage_drop_margin_percent >= 0.0,
        battery_margin_h >= 0.0,
    ]

    return {
        "yellow_interval_s": round(yellow_interval_s, 3),
        "all_red_interval_s": round(all_red_interval_s, 3),
        "bus_handling_capacity_pax_h": round(bus_handling_capacity_pax_h, 3),
        "bus_capacity_margin_pax_h": round(bus_capacity_margin_pax_h, 3),
        "cabinet_load_w": round(cabinet_load_w, 3),
        "cabinet_load_margin_w": round(cabinet_load_margin_w, 3),
        "feeder_current_a": round(feeder_current_a, 3),
        "feeder_voltage_drop_percent": round(feeder_voltage_drop_percent, 3),
        "voltage_drop_margin_percent": round(voltage_drop_margin_percent, 3),
        "battery_runtime_h": round(battery_runtime_h, 3),
        "battery_margin_h": round(battery_margin_h, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
