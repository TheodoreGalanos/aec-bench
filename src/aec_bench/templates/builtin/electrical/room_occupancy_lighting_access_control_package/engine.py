# ABOUTME: Computes SSC-08 room occupancy, lighting energy, and access-control metrics.
# ABOUTME: Combines occupant load, lumen-method lighting, LENI, reader count, and battery checks.

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
    area_per_occupant_m2: float,
    luminaire_lumens: float,
    luminaire_count: float,
    light_loss_factor: float,
    utilization_factor: float,
    minimum_illuminance_lux: float,
    target_illuminance_lux: float,
    minimum_uniformity_ratio: float,
    luminaire_power_w: float,
    operating_hours_per_year: float,
    max_leni_kwh_m2_y: float,
    access_door_count: float,
    readers_per_door: float,
    controller_reader_capacity: float,
    reader_load_w: float,
    controller_panel_load_w: float,
    backup_runtime_h: float,
    battery_derate_factor: float,
) -> dict[str, float]:
    """Compute deterministic room operations metrics for the SSC-08 source pack."""
    _require_positive(
        room_area_m2=room_area_m2,
        area_per_occupant_m2=area_per_occupant_m2,
        luminaire_lumens=luminaire_lumens,
        luminaire_count=luminaire_count,
        light_loss_factor=light_loss_factor,
        utilization_factor=utilization_factor,
        minimum_illuminance_lux=minimum_illuminance_lux,
        target_illuminance_lux=target_illuminance_lux,
        minimum_uniformity_ratio=minimum_uniformity_ratio,
        luminaire_power_w=luminaire_power_w,
        operating_hours_per_year=operating_hours_per_year,
        max_leni_kwh_m2_y=max_leni_kwh_m2_y,
        access_door_count=access_door_count,
        readers_per_door=readers_per_door,
        controller_reader_capacity=controller_reader_capacity,
        reader_load_w=reader_load_w,
        controller_panel_load_w=controller_panel_load_w,
        backup_runtime_h=backup_runtime_h,
        battery_derate_factor=battery_derate_factor,
    )

    design_occupants = float(math.ceil(room_area_m2 / area_per_occupant_m2))
    average_illuminance_lux = luminaire_lumens * luminaire_count * light_loss_factor * utilization_factor / room_area_m2
    illuminance_margin_lux = average_illuminance_lux - target_illuminance_lux
    uniformity_ratio = minimum_illuminance_lux / average_illuminance_lux
    lighting_power_w = luminaire_power_w * luminaire_count
    lighting_power_density_w_m2 = lighting_power_w / room_area_m2
    leni_kwh_m2_y = lighting_power_w * operating_hours_per_year / 1000.0 / room_area_m2
    access_reader_count = access_door_count * readers_per_door
    access_controller_spare_points = controller_reader_capacity - access_reader_count
    access_control_load_w = access_reader_count * reader_load_w + controller_panel_load_w
    access_battery_required_wh = access_control_load_w * backup_runtime_h / battery_derate_factor

    pass_checks = [
        illuminance_margin_lux >= 0.0,
        uniformity_ratio >= minimum_uniformity_ratio,
        leni_kwh_m2_y <= max_leni_kwh_m2_y,
        access_controller_spare_points >= 0.0,
    ]

    return {
        "design_occupants": round(design_occupants, 3),
        "average_illuminance_lux": round(average_illuminance_lux, 3),
        "illuminance_margin_lux": round(illuminance_margin_lux, 3),
        "uniformity_ratio": round(uniformity_ratio, 3),
        "lighting_power_density_w_m2": round(lighting_power_density_w_m2, 3),
        "leni_kwh_m2_y": round(leni_kwh_m2_y, 3),
        "access_reader_count": round(access_reader_count, 3),
        "access_controller_spare_points": round(access_controller_spare_points, 3),
        "access_battery_required_wh": round(access_battery_required_wh, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
