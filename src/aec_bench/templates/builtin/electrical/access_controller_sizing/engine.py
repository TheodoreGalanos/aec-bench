# ABOUTME: Computes access controller count, system current, power supplies, and backup capacity.
# ABOUTME: Uses door count, per-door device currents, controller load, supply size, and autonomy.

import math


def _validate_inputs(
    door_count: float,
    doors_per_controller: float,
    reader_current_ma_per_door: float,
    lock_current_ma_per_door: float,
    request_to_exit_current_ma_per_door: float,
    controller_current_ma: float,
    power_supply_capacity_a: float,
    backup_duration_h: float,
    battery_derating_factor: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "door_count": door_count,
        "doors_per_controller": doors_per_controller,
        "power_supply_capacity_a": power_supply_capacity_a,
        "backup_duration_h": backup_duration_h,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)
    for name, value in {
        "reader_current_ma_per_door": reader_current_ma_per_door,
        "lock_current_ma_per_door": lock_current_ma_per_door,
        "request_to_exit_current_ma_per_door": request_to_exit_current_ma_per_door,
        "controller_current_ma": controller_current_ma,
    }.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)
    if not 0 < battery_derating_factor <= 1:
        msg = "battery_derating_factor must be > 0 and <= 1"
        raise ValueError(msg)


def compute(
    door_count: float,
    doors_per_controller: float,
    reader_current_ma_per_door: float,
    lock_current_ma_per_door: float,
    request_to_exit_current_ma_per_door: float,
    controller_current_ma: float,
    power_supply_capacity_a: float,
    backup_duration_h: float,
    battery_derating_factor: float,
) -> dict[str, float]:
    """Compute controller, current, power supply, and battery requirements."""
    _validate_inputs(
        door_count,
        doors_per_controller,
        reader_current_ma_per_door,
        lock_current_ma_per_door,
        request_to_exit_current_ma_per_door,
        controller_current_ma,
        power_supply_capacity_a,
        backup_duration_h,
        battery_derating_factor,
    )

    controllers_required = math.ceil(door_count / doors_per_controller)
    door_device_load_a = (
        door_count
        * (reader_current_ma_per_door + lock_current_ma_per_door + request_to_exit_current_ma_per_door)
        / 1000.0
    )
    controller_load_a = controllers_required * controller_current_ma / 1000.0
    total_system_load_a = door_device_load_a + controller_load_a
    power_supplies_required = math.ceil(total_system_load_a / power_supply_capacity_a)
    battery_capacity_ah = total_system_load_a * backup_duration_h / battery_derating_factor

    return {
        "controllers_required": round(float(controllers_required), 2),
        "door_device_load_a": round(door_device_load_a, 2),
        "total_system_load_a": round(total_system_load_a, 2),
        "power_supplies_required": round(float(power_supplies_required), 2),
        "battery_capacity_ah": round(battery_capacity_ah, 2),
    }
