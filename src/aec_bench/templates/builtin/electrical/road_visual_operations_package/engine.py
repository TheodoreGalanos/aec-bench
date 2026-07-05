# ABOUTME: Computes SSC-13 road visual operations metrics from task-owned source-pack values.
# ABOUTME: Aggregates lighting, CCTV, network, PoE, fibre, and UPS calculations for verifier ground truth.


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _storage_tb(
    *,
    bitrate_mbps: float,
    retention_days: float,
    storage_overhead_factor: float,
) -> float:
    """Return continuous CCTV storage in TB using decimal GB/TB units."""
    daily_storage_gb = bitrate_mbps * 24.0 * 3600.0 / 8.0 / 1000.0
    return daily_storage_gb * retention_days * storage_overhead_factor / 1000.0


def compute(
    lighting_grid_lg01_lux: float,
    lighting_grid_lg02_lux: float,
    lighting_grid_lg03_lux: float,
    lighting_grid_lg04_lux: float,
    lighting_grid_lg05_lux: float,
    lighting_grid_lg06_lux: float,
    lighting_grid_lg07_lux: float,
    lighting_grid_lg08_lux: float,
    cctv_01_target_width_m: float,
    cctv_01_horizontal_pixels: float,
    cctv_01_bitrate_mbps: float,
    cctv_02_target_width_m: float,
    cctv_02_horizontal_pixels: float,
    cctv_02_bitrate_mbps: float,
    retention_days: float,
    storage_overhead_factor: float,
    cctv_01_network_load_mbps: float,
    cctv_02_network_load_mbps: float,
    vms_network_load_mbps: float,
    environment_sensor_network_load_mbps: float,
    cabinet_aux_network_load_mbps: float,
    cctv_01_poe_load_w: float,
    cctv_02_poe_load_w: float,
    vms_poe_load_w: float,
    environment_sensor_poe_load_w: float,
    poe_budget_w: float,
    fibre_length_km: float,
    fibre_loss_db_per_km: float,
    connector_loss_db: float,
    splice_loss_db: float,
    fibre_reserve_loss_db: float,
    fibre_budget_db: float,
    luminaire_01_power_w: float,
    luminaire_02_power_w: float,
    luminaire_03_power_w: float,
    luminaire_04_power_w: float,
    vms_power_w: float,
    cabinet_aux_power_w: float,
    ups_autonomy_h: float,
    ups_efficiency: float,
) -> dict[str, float]:
    """Compute the road visual operations package metrics."""
    _require_positive(
        cctv_01_target_width_m=cctv_01_target_width_m,
        cctv_01_horizontal_pixels=cctv_01_horizontal_pixels,
        cctv_01_bitrate_mbps=cctv_01_bitrate_mbps,
        cctv_02_target_width_m=cctv_02_target_width_m,
        cctv_02_horizontal_pixels=cctv_02_horizontal_pixels,
        cctv_02_bitrate_mbps=cctv_02_bitrate_mbps,
        retention_days=retention_days,
        storage_overhead_factor=storage_overhead_factor,
        poe_budget_w=poe_budget_w,
        fibre_length_km=fibre_length_km,
        fibre_loss_db_per_km=fibre_loss_db_per_km,
        fibre_budget_db=fibre_budget_db,
        ups_autonomy_h=ups_autonomy_h,
        ups_efficiency=ups_efficiency,
    )

    lux_values = [
        lighting_grid_lg01_lux,
        lighting_grid_lg02_lux,
        lighting_grid_lg03_lux,
        lighting_grid_lg04_lux,
        lighting_grid_lg05_lux,
        lighting_grid_lg06_lux,
        lighting_grid_lg07_lux,
        lighting_grid_lg08_lux,
    ]
    average_illuminance_lux = sum(lux_values) / len(lux_values)
    minimum_illuminance_lux = min(lux_values)
    uniformity_ratio = minimum_illuminance_lux / average_illuminance_lux

    cctv_01_pixels_per_meter = cctv_01_horizontal_pixels / cctv_01_target_width_m
    cctv_02_pixels_per_meter = cctv_02_horizontal_pixels / cctv_02_target_width_m
    cctv_01_storage_tb = _storage_tb(
        bitrate_mbps=cctv_01_bitrate_mbps,
        retention_days=retention_days,
        storage_overhead_factor=storage_overhead_factor,
    )
    cctv_02_storage_tb = _storage_tb(
        bitrate_mbps=cctv_02_bitrate_mbps,
        retention_days=retention_days,
        storage_overhead_factor=storage_overhead_factor,
    )
    total_cctv_storage_tb = cctv_01_storage_tb + cctv_02_storage_tb

    total_network_load_mbps = (
        cctv_01_network_load_mbps
        + cctv_02_network_load_mbps
        + vms_network_load_mbps
        + environment_sensor_network_load_mbps
        + cabinet_aux_network_load_mbps
    )

    poe_load_w = cctv_01_poe_load_w + cctv_02_poe_load_w + vms_poe_load_w + environment_sensor_poe_load_w
    poe_headroom_w = poe_budget_w - poe_load_w

    fibre_loss_db = fibre_length_km * fibre_loss_db_per_km + connector_loss_db + splice_loss_db + fibre_reserve_loss_db
    fibre_margin_db = fibre_budget_db - fibre_loss_db

    selected_ups_load_w = (
        luminaire_01_power_w
        + luminaire_02_power_w
        + luminaire_03_power_w
        + luminaire_04_power_w
        + vms_power_w
        + cabinet_aux_power_w
    )
    ups_energy_kwh = selected_ups_load_w * ups_autonomy_h / ups_efficiency / 1000.0

    return {
        "average_illuminance_lux": round(average_illuminance_lux, 3),
        "minimum_illuminance_lux": round(minimum_illuminance_lux, 3),
        "uniformity_ratio": round(uniformity_ratio, 3),
        "cctv_01_pixels_per_meter": round(cctv_01_pixels_per_meter, 3),
        "cctv_02_pixels_per_meter": round(cctv_02_pixels_per_meter, 3),
        "cctv_01_storage_tb": round(cctv_01_storage_tb, 5),
        "cctv_02_storage_tb": round(cctv_02_storage_tb, 5),
        "total_cctv_storage_tb": round(total_cctv_storage_tb, 5),
        "total_network_load_mbps": round(total_network_load_mbps, 3),
        "poe_load_w": round(poe_load_w, 3),
        "poe_headroom_w": round(poe_headroom_w, 3),
        "fibre_loss_db": round(fibre_loss_db, 3),
        "fibre_margin_db": round(fibre_margin_db, 3),
        "ups_energy_kwh": round(ups_energy_kwh, 3),
    }
