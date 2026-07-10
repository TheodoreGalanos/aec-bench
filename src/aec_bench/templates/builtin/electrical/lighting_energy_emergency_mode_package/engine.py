# ABOUTME: Computes SSC-13 lighting energy and emergency-mode metrics.
# ABOUTME: Combines normal lighting, LENI, and emergency battery checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    grid_lux_01: float,
    grid_lux_02: float,
    grid_lux_03: float,
    grid_lux_04: float,
    grid_lux_05: float,
    grid_lux_06: float,
    required_illuminance_lux: float,
    emergency_illuminance_lux: float,
    required_emergency_illuminance_lux: float,
    luminaire_count: float,
    normal_luminaire_power_w: float,
    control_factor: float,
    annual_operating_hours: float,
    area_m2: float,
    target_leni_kwh_m2_year: float,
    emergency_luminaire_power_w: float,
    exit_sign_count: float,
    exit_sign_power_w: float,
    emergency_autonomy_h: float,
    battery_efficiency: float,
    battery_capacity_kwh: float,
) -> dict[str, float]:
    _require_positive(
        required_illuminance_lux=required_illuminance_lux,
        required_emergency_illuminance_lux=required_emergency_illuminance_lux,
        luminaire_count=luminaire_count,
        normal_luminaire_power_w=normal_luminaire_power_w,
        control_factor=control_factor,
        annual_operating_hours=annual_operating_hours,
        area_m2=area_m2,
        target_leni_kwh_m2_year=target_leni_kwh_m2_year,
        emergency_luminaire_power_w=emergency_luminaire_power_w,
        exit_sign_count=exit_sign_count,
        exit_sign_power_w=exit_sign_power_w,
        emergency_autonomy_h=emergency_autonomy_h,
        battery_efficiency=battery_efficiency,
        battery_capacity_kwh=battery_capacity_kwh,
    )

    lux_values = [grid_lux_01, grid_lux_02, grid_lux_03, grid_lux_04, grid_lux_05, grid_lux_06]
    average_illuminance_lux = sum(lux_values) / len(lux_values)
    minimum_illuminance_lux = min(lux_values)
    uniformity_ratio = minimum_illuminance_lux / average_illuminance_lux
    illuminance_margin_lux = average_illuminance_lux - required_illuminance_lux
    emergency_illuminance_margin_lux = emergency_illuminance_lux - required_emergency_illuminance_lux
    annual_lighting_energy_kwh = (
        luminaire_count * normal_luminaire_power_w * control_factor * annual_operating_hours / 1000.0
    )
    leni_kwh_m2_year = annual_lighting_energy_kwh / area_m2
    leni_margin_kwh_m2_year = target_leni_kwh_m2_year - leni_kwh_m2_year
    emergency_load_w = luminaire_count * emergency_luminaire_power_w + exit_sign_count * exit_sign_power_w
    emergency_battery_required_kwh = emergency_load_w * emergency_autonomy_h / battery_efficiency / 1000.0
    emergency_battery_margin_kwh = battery_capacity_kwh - emergency_battery_required_kwh
    overall_pass_score = (
        1.0
        if (
            illuminance_margin_lux >= 0.0
            and emergency_illuminance_margin_lux >= 0.0
            and leni_margin_kwh_m2_year >= 0.0
            and emergency_battery_margin_kwh >= 0.0
        )
        else 0.0
    )

    return {
        "average_illuminance_lux": round(average_illuminance_lux, 3),
        "minimum_illuminance_lux": round(minimum_illuminance_lux, 3),
        "uniformity_ratio": round(uniformity_ratio, 3),
        "illuminance_margin_lux": round(illuminance_margin_lux, 3),
        "emergency_illuminance_margin_lux": round(emergency_illuminance_margin_lux, 3),
        "annual_lighting_energy_kwh": round(annual_lighting_energy_kwh, 3),
        "leni_kwh_m2_year": round(leni_kwh_m2_year, 3),
        "leni_margin_kwh_m2_year": round(leni_margin_kwh_m2_year, 3),
        "emergency_battery_required_kwh": round(emergency_battery_required_kwh, 3),
        "emergency_battery_margin_kwh": round(emergency_battery_margin_kwh, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
