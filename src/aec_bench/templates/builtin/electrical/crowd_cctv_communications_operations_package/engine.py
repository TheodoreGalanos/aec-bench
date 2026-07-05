# ABOUTME: Computes SSC-08 crowd, CCTV, communications, PoE, and access-state metrics.
# ABOUTME: Combines queue population, PPM coverage, storage, network load, PoE, and state checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    queue_length_m: float,
    queue_width_m: float,
    queue_density_person_m2: float,
    horizontal_pixels: float,
    camera_horizontal_field_m: float,
    required_ppm: float,
    camera_count: float,
    camera_bitrate_mbps: float,
    retention_days: float,
    storage_overhead_factor: float,
    access_network_mbps: float,
    intercom_network_mbps: float,
    network_overhead_percent: float,
    uplink_capacity_mbps: float,
    camera_poe_w: float,
    access_controller_count: float,
    access_controller_poe_w: float,
    intercom_count: float,
    intercom_poe_w: float,
    poe_budget_w: float,
    matching_access_states: float,
    required_access_states: float,
) -> dict[str, float]:
    """Compute deterministic security and communications metrics."""
    _require_positive(
        queue_length_m=queue_length_m,
        queue_width_m=queue_width_m,
        queue_density_person_m2=queue_density_person_m2,
        horizontal_pixels=horizontal_pixels,
        camera_horizontal_field_m=camera_horizontal_field_m,
        required_ppm=required_ppm,
        camera_count=camera_count,
        camera_bitrate_mbps=camera_bitrate_mbps,
        retention_days=retention_days,
        storage_overhead_factor=storage_overhead_factor,
        network_overhead_percent=network_overhead_percent,
        uplink_capacity_mbps=uplink_capacity_mbps,
        camera_poe_w=camera_poe_w,
        access_controller_count=access_controller_count,
        access_controller_poe_w=access_controller_poe_w,
        intercom_count=intercom_count,
        intercom_poe_w=intercom_poe_w,
        poe_budget_w=poe_budget_w,
        required_access_states=required_access_states,
    )

    queue_population_persons = queue_length_m * queue_width_m * queue_density_person_m2
    cctv_pixels_per_m = horizontal_pixels / camera_horizontal_field_m
    ppm_margin = cctv_pixels_per_m - required_ppm
    cctv_total_bitrate_mbps = camera_count * camera_bitrate_mbps
    cctv_storage_tb = cctv_total_bitrate_mbps * retention_days * 86400.0 / (8.0 * 1_000_000.0)
    cctv_storage_tb *= storage_overhead_factor
    network_load_mbps = cctv_total_bitrate_mbps + access_network_mbps + intercom_network_mbps
    network_load_mbps *= 1.0 + network_overhead_percent / 100.0
    network_headroom_mbps = uplink_capacity_mbps - network_load_mbps
    poe_load_w = (
        camera_count * camera_poe_w
        + access_controller_count * access_controller_poe_w
        + intercom_count * intercom_poe_w
    )
    poe_headroom_w = poe_budget_w - poe_load_w
    access_state_match_fraction = matching_access_states / required_access_states

    pass_checks = [
        ppm_margin >= 0.0,
        network_headroom_mbps >= 0.0,
        poe_headroom_w >= 0.0,
        access_state_match_fraction >= 1.0,
    ]

    return {
        "queue_population_persons": round(queue_population_persons, 3),
        "cctv_pixels_per_m": round(cctv_pixels_per_m, 3),
        "ppm_margin": round(ppm_margin, 3),
        "cctv_storage_tb": round(cctv_storage_tb, 3),
        "network_load_mbps": round(network_load_mbps, 3),
        "network_headroom_mbps": round(network_headroom_mbps, 3),
        "poe_load_w": round(poe_load_w, 3),
        "poe_headroom_w": round(poe_headroom_w, 3),
        "access_state_match_fraction": round(access_state_match_fraction, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
