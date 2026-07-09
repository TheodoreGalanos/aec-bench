# ABOUTME: Computes SSC-05 fire/life-safety and communications load metrics.
# ABOUTME: Combines device load rollups, UPS autonomy, NAC current, and feeder capacity checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _require_fraction(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        msg = f"{name} must be between 0 and 1"
        raise ValueError(msg)


def compute(
    nac_device_count: float,
    nac_device_current_a: float,
    nac_voltage_v: float,
    fire_panel_load_kw: float,
    emergency_lighting_load_kw: float,
    access_controller_count: float,
    access_controller_w: float,
    cctv_camera_count: float,
    cctv_camera_w: float,
    network_core_w: float,
    emergency_runtime_h: float,
    ups_nominal_kwh: float,
    ups_usable_fraction: float,
    nac_circuit_limit_a: float,
    feeder_voltage_v: float,
    feeder_allowable_current_a: float,
) -> dict[str, float]:
    """Compute source-bound life-safety, communications, battery, and feeder metrics."""
    _require_positive(
        nac_device_count=nac_device_count,
        nac_device_current_a=nac_device_current_a,
        nac_voltage_v=nac_voltage_v,
        fire_panel_load_kw=fire_panel_load_kw,
        emergency_lighting_load_kw=emergency_lighting_load_kw,
        access_controller_count=access_controller_count,
        access_controller_w=access_controller_w,
        cctv_camera_count=cctv_camera_count,
        cctv_camera_w=cctv_camera_w,
        network_core_w=network_core_w,
        emergency_runtime_h=emergency_runtime_h,
        ups_nominal_kwh=ups_nominal_kwh,
        nac_circuit_limit_a=nac_circuit_limit_a,
        feeder_voltage_v=feeder_voltage_v,
        feeder_allowable_current_a=feeder_allowable_current_a,
    )
    _require_fraction("ups_usable_fraction", ups_usable_fraction)

    nac_current_a = nac_device_count * nac_device_current_a
    nac_load_kw = nac_current_a * nac_voltage_v / 1000.0
    life_safety_load_kw = nac_load_kw + fire_panel_load_kw + emergency_lighting_load_kw
    communications_load_kw = (
        access_controller_count * access_controller_w + cctv_camera_count * cctv_camera_w + network_core_w
    ) / 1000.0
    total_essential_load_kw = life_safety_load_kw + communications_load_kw
    battery_required_kwh = total_essential_load_kw * emergency_runtime_h
    usable_battery_kwh = ups_nominal_kwh * ups_usable_fraction
    battery_margin_kwh = usable_battery_kwh - battery_required_kwh
    nac_margin_a = nac_circuit_limit_a - nac_current_a
    feeder_current_a = total_essential_load_kw * 1000.0 / feeder_voltage_v
    feeder_margin_a = feeder_allowable_current_a - feeder_current_a

    overall_pass_score = 1.0 if min(battery_margin_kwh, nac_margin_a, feeder_margin_a) >= 0.0 else 0.0

    return {
        "life_safety_load_kw": round(life_safety_load_kw, 3),
        "communications_load_kw": round(communications_load_kw, 3),
        "total_essential_load_kw": round(total_essential_load_kw, 3),
        "battery_required_kwh": round(battery_required_kwh, 3),
        "usable_battery_kwh": round(usable_battery_kwh, 3),
        "battery_margin_kwh": round(battery_margin_kwh, 3),
        "nac_current_a": round(nac_current_a, 3),
        "nac_margin_a": round(nac_margin_a, 3),
        "feeder_current_a": round(feeder_current_a, 3),
        "feeder_margin_a": round(feeder_margin_a, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
