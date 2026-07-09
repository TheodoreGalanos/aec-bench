# ABOUTME: Computes SSC-08 lift shaft, car dimension, and accessibility service metrics.
# ABOUTME: Combines car/shaft margins, accessible lift capacity, emergency load, and feeder checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    car_internal_width_m: float,
    required_car_width_m: float,
    car_internal_depth_m: float,
    required_car_depth_m: float,
    shaft_width_m: float,
    shaft_depth_m: float,
    side_clearance_m: float,
    front_rear_clearance_m: float,
    lift_count: float,
    car_capacity_persons: float,
    loading_factor: float,
    round_trip_time_s: float,
    accessible_demand_persons_per_5min: float,
    lift_motor_kw: float,
    fire_service_lift_count: float,
    controls_load_kw: float,
    generator_allocation_kw: float,
    voltage_v: float,
    power_factor: float,
    feeder_length_km: float,
    feeder_resistance_ohm_per_km: float,
    feeder_reactance_ohm_per_km: float,
    allowable_voltage_drop_percent: float,
) -> dict[str, float]:
    """Compute deterministic lift accessibility and service metrics."""
    _require_positive(
        car_internal_width_m=car_internal_width_m,
        required_car_width_m=required_car_width_m,
        car_internal_depth_m=car_internal_depth_m,
        required_car_depth_m=required_car_depth_m,
        shaft_width_m=shaft_width_m,
        shaft_depth_m=shaft_depth_m,
        side_clearance_m=side_clearance_m,
        front_rear_clearance_m=front_rear_clearance_m,
        lift_count=lift_count,
        car_capacity_persons=car_capacity_persons,
        loading_factor=loading_factor,
        round_trip_time_s=round_trip_time_s,
        accessible_demand_persons_per_5min=accessible_demand_persons_per_5min,
        lift_motor_kw=lift_motor_kw,
        fire_service_lift_count=fire_service_lift_count,
        generator_allocation_kw=generator_allocation_kw,
        voltage_v=voltage_v,
        power_factor=power_factor,
        feeder_length_km=feeder_length_km,
        feeder_resistance_ohm_per_km=feeder_resistance_ohm_per_km,
        feeder_reactance_ohm_per_km=feeder_reactance_ohm_per_km,
        allowable_voltage_drop_percent=allowable_voltage_drop_percent,
    )
    if power_factor > 1.0:
        msg = "power_factor must be <= 1"
        raise ValueError(msg)

    car_width_margin_m = car_internal_width_m - required_car_width_m
    car_depth_margin_m = car_internal_depth_m - required_car_depth_m
    shaft_width_margin_m = shaft_width_m - (car_internal_width_m + 2.0 * side_clearance_m)
    shaft_depth_margin_m = shaft_depth_m - (car_internal_depth_m + 2.0 * front_rear_clearance_m)
    accessible_lift_capacity_persons_per_5min = 300.0 * lift_count * car_capacity_persons * loading_factor
    accessible_lift_capacity_persons_per_5min /= round_trip_time_s
    accessible_capacity_margin_persons_per_5min = (
        accessible_lift_capacity_persons_per_5min - accessible_demand_persons_per_5min
    )
    emergency_power_load_kw = lift_motor_kw * fire_service_lift_count + controls_load_kw
    generator_allocation_margin_kw = generator_allocation_kw - emergency_power_load_kw
    lift_feeder_current_a = emergency_power_load_kw * 1000.0 / (math.sqrt(3.0) * voltage_v * power_factor)
    sine_factor = math.sqrt(1.0 - power_factor**2)
    feeder_voltage_drop_percent = (
        math.sqrt(3.0)
        * lift_feeder_current_a
        * (feeder_resistance_ohm_per_km * power_factor + feeder_reactance_ohm_per_km * sine_factor)
        * feeder_length_km
        / voltage_v
        * 100.0
    )
    feeder_voltage_drop_margin_percent = allowable_voltage_drop_percent - feeder_voltage_drop_percent

    pass_checks = [
        car_width_margin_m >= 0.0,
        car_depth_margin_m >= 0.0,
        shaft_width_margin_m >= 0.0,
        shaft_depth_margin_m >= 0.0,
        accessible_capacity_margin_persons_per_5min >= 0.0,
        generator_allocation_margin_kw >= 0.0,
        feeder_voltage_drop_margin_percent >= 0.0,
    ]

    return {
        "car_width_margin_m": round(car_width_margin_m, 3),
        "car_depth_margin_m": round(car_depth_margin_m, 3),
        "shaft_width_margin_m": round(shaft_width_margin_m, 3),
        "shaft_depth_margin_m": round(shaft_depth_margin_m, 3),
        "accessible_lift_capacity_persons_per_5min": round(accessible_lift_capacity_persons_per_5min, 3),
        "accessible_capacity_margin_persons_per_5min": round(accessible_capacity_margin_persons_per_5min, 3),
        "emergency_power_load_kw": round(emergency_power_load_kw, 3),
        "generator_allocation_margin_kw": round(generator_allocation_margin_kw, 3),
        "lift_feeder_current_a": round(lift_feeder_current_a, 3),
        "feeder_voltage_drop_margin_percent": round(feeder_voltage_drop_margin_percent, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
