# ABOUTME: Computes ITS network bandwidth from device counts and data rates.
# ABOUTME: Applies overhead and future-capacity buffers to base demand.


def _validate_inputs(
    camera_count: float,
    camera_data_rate_mbps: float,
    controller_count: float,
    controller_data_rate_mbps: float,
    sensor_count: float,
    sensor_data_rate_mbps: float,
    network_overhead_pct: float,
    future_capacity_buffer_pct: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "camera_count": camera_count,
        "controller_count": controller_count,
        "sensor_count": sensor_count,
    }.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)
    for name, value in {
        "camera_data_rate_mbps": camera_data_rate_mbps,
        "controller_data_rate_mbps": controller_data_rate_mbps,
        "sensor_data_rate_mbps": sensor_data_rate_mbps,
    }.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)
    if network_overhead_pct < 0:
        msg = "network_overhead_pct must be >= 0"
        raise ValueError(msg)
    if future_capacity_buffer_pct < 0:
        msg = "future_capacity_buffer_pct must be >= 0"
        raise ValueError(msg)


def compute(
    camera_count: float,
    camera_data_rate_mbps: float,
    controller_count: float,
    controller_data_rate_mbps: float,
    sensor_count: float,
    sensor_data_rate_mbps: float,
    network_overhead_pct: float,
    future_capacity_buffer_pct: float,
) -> dict[str, float]:
    """Compute base, peak, and buffered ITS bandwidth demand."""
    _validate_inputs(
        camera_count,
        camera_data_rate_mbps,
        controller_count,
        controller_data_rate_mbps,
        sensor_count,
        sensor_data_rate_mbps,
        network_overhead_pct,
        future_capacity_buffer_pct,
    )

    base_bandwidth_mbps = (
        camera_count * camera_data_rate_mbps
        + controller_count * controller_data_rate_mbps
        + sensor_count * sensor_data_rate_mbps
    )
    peak_demand_mbps = base_bandwidth_mbps * (1.0 + network_overhead_pct / 100.0)
    required_bandwidth_mbps = peak_demand_mbps * (1.0 + future_capacity_buffer_pct / 100.0)

    return {
        "base_bandwidth_mbps": round(base_bandwidth_mbps, 2),
        "peak_demand_mbps": round(peak_demand_mbps, 2),
        "required_bandwidth_mbps": round(required_bandwidth_mbps, 2),
    }
