# ABOUTME: Computes SSC-13 station/building security lighting metrics.
# ABOUTME: Combines lighting, CCTV, network, PoE, and coverage checks.

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
    cctv_horizontal_pixels: float,
    cctv_target_width_m: float,
    required_ppm: float,
    camera_count: float,
    camera_network_mbps: float,
    access_network_mbps: float,
    lighting_control_network_mbps: float,
    network_overhead_factor: float,
    uplink_capacity_mbps: float,
    camera_poe_w: float,
    access_controller_count: float,
    access_controller_poe_w: float,
    poe_budget_w: float,
    matched_coverage_zones: float,
    required_coverage_zones: float,
) -> dict[str, float]:
    _require_positive(
        required_illuminance_lux=required_illuminance_lux,
        cctv_horizontal_pixels=cctv_horizontal_pixels,
        cctv_target_width_m=cctv_target_width_m,
        required_ppm=required_ppm,
        camera_count=camera_count,
        network_overhead_factor=network_overhead_factor,
        uplink_capacity_mbps=uplink_capacity_mbps,
        poe_budget_w=poe_budget_w,
        required_coverage_zones=required_coverage_zones,
    )

    lux_values = [grid_lux_01, grid_lux_02, grid_lux_03, grid_lux_04, grid_lux_05, grid_lux_06]
    average_illuminance_lux = sum(lux_values) / len(lux_values)
    minimum_illuminance_lux = min(lux_values)
    uniformity_ratio = minimum_illuminance_lux / average_illuminance_lux
    illuminance_margin_lux = average_illuminance_lux - required_illuminance_lux
    cctv_pixels_per_m = cctv_horizontal_pixels / cctv_target_width_m
    cctv_ppm_margin = cctv_pixels_per_m - required_ppm
    network_load_mbps = (
        camera_count * camera_network_mbps + access_network_mbps + lighting_control_network_mbps
    ) * network_overhead_factor
    network_headroom_mbps = uplink_capacity_mbps - network_load_mbps
    poe_load_w = camera_count * camera_poe_w + access_controller_count * access_controller_poe_w
    poe_headroom_w = poe_budget_w - poe_load_w
    coverage_match_fraction = matched_coverage_zones / required_coverage_zones
    overall_pass_score = (
        1.0
        if (
            illuminance_margin_lux >= 0.0
            and cctv_ppm_margin >= 0.0
            and network_headroom_mbps >= 0.0
            and poe_headroom_w >= 0.0
            and coverage_match_fraction >= 1.0
        )
        else 0.0
    )

    return {
        "average_illuminance_lux": round(average_illuminance_lux, 3),
        "minimum_illuminance_lux": round(minimum_illuminance_lux, 3),
        "uniformity_ratio": round(uniformity_ratio, 3),
        "illuminance_margin_lux": round(illuminance_margin_lux, 3),
        "cctv_pixels_per_m": round(cctv_pixels_per_m, 3),
        "cctv_ppm_margin": round(cctv_ppm_margin, 3),
        "network_load_mbps": round(network_load_mbps, 3),
        "network_headroom_mbps": round(network_headroom_mbps, 3),
        "poe_load_w": round(poe_load_w, 3),
        "poe_headroom_w": round(poe_headroom_w, 3),
        "coverage_match_fraction": round(coverage_match_fraction, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
