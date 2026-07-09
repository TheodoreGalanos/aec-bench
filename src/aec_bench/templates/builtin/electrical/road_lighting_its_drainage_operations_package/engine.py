# ABOUTME: Computes SSC-01 road lighting, ITS, and drainage operations metrics.
# ABOUTME: Aggregates illuminance, network, CCTV storage, PoE, storm sensor, and UPS checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    lighting_lux_01: float,
    lighting_lux_02: float,
    lighting_lux_03: float,
    lighting_lux_04: float,
    lighting_lux_05: float,
    lighting_lux_06: float,
    cctv_count: float,
    cctv_network_load_mbps: float,
    vms_network_load_mbps: float,
    sensor_network_load_mbps: float,
    controller_network_load_mbps: float,
    network_overhead_pct: float,
    uplink_capacity_mbps: float,
    cctv_total_bitrate_mbps: float,
    retention_days: float,
    storage_overhead_factor: float,
    cctv_poe_load_w: float,
    vms_poe_load_w: float,
    sensor_poe_load_w: float,
    poe_budget_w: float,
    storm_sensor_level_m: float,
    storm_alarm_threshold_m: float,
    luminaire_power_w: float,
    luminaire_count: float,
    device_ups_load_w: float,
    ups_autonomy_h: float,
    ups_efficiency: float,
    minimum_uniformity_ratio: float,
) -> dict[str, float]:
    """Compute deterministic SSC-01 lighting, ITS, and drainage operations metrics."""
    _require_positive(
        cctv_count=cctv_count,
        cctv_network_load_mbps=cctv_network_load_mbps,
        uplink_capacity_mbps=uplink_capacity_mbps,
        cctv_total_bitrate_mbps=cctv_total_bitrate_mbps,
        retention_days=retention_days,
        storage_overhead_factor=storage_overhead_factor,
        poe_budget_w=poe_budget_w,
        luminaire_power_w=luminaire_power_w,
        luminaire_count=luminaire_count,
        ups_autonomy_h=ups_autonomy_h,
        ups_efficiency=ups_efficiency,
        minimum_uniformity_ratio=minimum_uniformity_ratio,
    )
    lux_values = [
        lighting_lux_01,
        lighting_lux_02,
        lighting_lux_03,
        lighting_lux_04,
        lighting_lux_05,
        lighting_lux_06,
    ]
    average_illuminance_lux = sum(lux_values) / len(lux_values)
    minimum_illuminance_lux = min(lux_values)
    uniformity_ratio = minimum_illuminance_lux / average_illuminance_lux
    glare_variation_ratio = max(lux_values) / average_illuminance_lux

    base_network_load_mbps = (
        cctv_count * cctv_network_load_mbps
        + vms_network_load_mbps
        + sensor_network_load_mbps
        + controller_network_load_mbps
    )
    total_network_load_mbps = base_network_load_mbps * (1.0 + network_overhead_pct / 100.0)
    network_headroom_mbps = uplink_capacity_mbps - total_network_load_mbps
    total_cctv_storage_tb = (
        cctv_total_bitrate_mbps * 24.0 * 3600.0 / 8.0 / 1000.0 * retention_days * storage_overhead_factor / 1000.0
    )
    poe_load_w = cctv_count * cctv_poe_load_w + vms_poe_load_w + sensor_poe_load_w
    poe_headroom_w = poe_budget_w - poe_load_w
    water_level_margin_m = storm_alarm_threshold_m - storm_sensor_level_m
    ups_load_w = luminaire_power_w * luminaire_count + device_ups_load_w
    ups_energy_kwh = ups_load_w * ups_autonomy_h / ups_efficiency / 1000.0

    pass_checks = [
        uniformity_ratio >= minimum_uniformity_ratio,
        network_headroom_mbps >= 0.0,
        poe_headroom_w >= 0.0,
        water_level_margin_m >= 0.0,
        ups_energy_kwh > 0.0,
    ]

    return {
        "average_illuminance_lux": round(average_illuminance_lux, 3),
        "minimum_illuminance_lux": round(minimum_illuminance_lux, 3),
        "uniformity_ratio": round(uniformity_ratio, 3),
        "glare_variation_ratio": round(glare_variation_ratio, 3),
        "total_network_load_mbps": round(total_network_load_mbps, 3),
        "network_headroom_mbps": round(network_headroom_mbps, 3),
        "total_cctv_storage_tb": round(total_cctv_storage_tb, 3),
        "poe_load_w": round(poe_load_w, 3),
        "poe_headroom_w": round(poe_headroom_w, 3),
        "water_level_margin_m": round(water_level_margin_m, 3),
        "ups_energy_kwh": round(ups_energy_kwh, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
