# ABOUTME: Computes SSC-13 CCTV coverage, pixel-density, and storage metrics.
# ABOUTME: Combines PPM, coverage, retention, network, PoE, and fibre checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _storage_tb(total_bitrate_mbps: float, retention_days: float, storage_overhead_factor: float) -> float:
    daily_storage_gb = total_bitrate_mbps * 24.0 * 3600.0 / 8.0 / 1000.0
    return daily_storage_gb * retention_days * storage_overhead_factor / 1000.0


def compute(
    camera_01_horizontal_pixels: float,
    camera_01_target_width_m: float,
    camera_02_horizontal_pixels: float,
    camera_02_target_width_m: float,
    camera_03_horizontal_pixels: float,
    camera_03_target_width_m: float,
    required_ppm: float,
    covered_targets: float,
    required_targets: float,
    camera_01_bitrate_mbps: float,
    camera_02_bitrate_mbps: float,
    camera_03_bitrate_mbps: float,
    retention_days: float,
    storage_overhead_factor: float,
    network_overhead_factor: float,
    uplink_capacity_mbps: float,
    camera_count: float,
    camera_poe_w: float,
    recorder_aux_poe_w: float,
    poe_budget_w: float,
    fibre_length_km: float,
    fibre_loss_db_per_km: float,
    connector_loss_db: float,
    splice_loss_db: float,
    reserve_loss_db: float,
    fibre_budget_db: float,
) -> dict[str, float]:
    _require_positive(
        camera_01_horizontal_pixels=camera_01_horizontal_pixels,
        camera_01_target_width_m=camera_01_target_width_m,
        camera_02_horizontal_pixels=camera_02_horizontal_pixels,
        camera_02_target_width_m=camera_02_target_width_m,
        camera_03_horizontal_pixels=camera_03_horizontal_pixels,
        camera_03_target_width_m=camera_03_target_width_m,
        required_ppm=required_ppm,
        required_targets=required_targets,
        retention_days=retention_days,
        storage_overhead_factor=storage_overhead_factor,
        network_overhead_factor=network_overhead_factor,
        uplink_capacity_mbps=uplink_capacity_mbps,
        camera_count=camera_count,
        poe_budget_w=poe_budget_w,
        fibre_length_km=fibre_length_km,
        fibre_loss_db_per_km=fibre_loss_db_per_km,
        fibre_budget_db=fibre_budget_db,
    )

    camera_01_pixels_per_m = camera_01_horizontal_pixels / camera_01_target_width_m
    camera_02_pixels_per_m = camera_02_horizontal_pixels / camera_02_target_width_m
    camera_03_pixels_per_m = camera_03_horizontal_pixels / camera_03_target_width_m
    minimum_pixels_per_m = min(camera_01_pixels_per_m, camera_02_pixels_per_m, camera_03_pixels_per_m)
    ppm_margin = minimum_pixels_per_m - required_ppm
    coverage_match_fraction = covered_targets / required_targets
    total_bitrate_mbps = camera_01_bitrate_mbps + camera_02_bitrate_mbps + camera_03_bitrate_mbps
    storage_required_tb = _storage_tb(total_bitrate_mbps, retention_days, storage_overhead_factor)
    network_load_mbps = total_bitrate_mbps * network_overhead_factor
    network_headroom_mbps = uplink_capacity_mbps - network_load_mbps
    poe_load_w = camera_count * camera_poe_w + recorder_aux_poe_w
    poe_headroom_w = poe_budget_w - poe_load_w
    fibre_loss_db = fibre_length_km * fibre_loss_db_per_km + connector_loss_db + splice_loss_db + reserve_loss_db
    fibre_margin_db = fibre_budget_db - fibre_loss_db
    overall_pass_score = (
        1.0
        if (
            ppm_margin >= 0.0
            and coverage_match_fraction >= 1.0
            and network_headroom_mbps >= 0.0
            and poe_headroom_w >= 0.0
            and fibre_margin_db >= 0.0
        )
        else 0.0
    )

    return {
        "camera_01_pixels_per_m": round(camera_01_pixels_per_m, 3),
        "camera_02_pixels_per_m": round(camera_02_pixels_per_m, 3),
        "camera_03_pixels_per_m": round(camera_03_pixels_per_m, 3),
        "minimum_pixels_per_m": round(minimum_pixels_per_m, 3),
        "ppm_margin": round(ppm_margin, 3),
        "coverage_match_fraction": round(coverage_match_fraction, 3),
        "storage_required_tb": round(storage_required_tb, 3),
        "network_load_mbps": round(network_load_mbps, 3),
        "network_headroom_mbps": round(network_headroom_mbps, 3),
        "poe_load_w": round(poe_load_w, 3),
        "poe_headroom_w": round(poe_headroom_w, 3),
        "fibre_margin_db": round(fibre_margin_db, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
