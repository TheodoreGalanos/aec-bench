# ABOUTME: Computes CCTV video storage from bitrate, recording duration, and retention.
# ABOUTME: Converts Mbps video rates into daily GB and retained TB capacity.


def _validate_inputs(
    camera_count: float,
    average_bitrate_mbps: float,
    recording_hours_per_day: float,
    retention_days: float,
    storage_overhead_pct: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if camera_count <= 0:
        msg = "camera_count must be > 0"
        raise ValueError(msg)
    for name, value in {
        "average_bitrate_mbps": average_bitrate_mbps,
        "recording_hours_per_day": recording_hours_per_day,
        "retention_days": retention_days,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)
    if recording_hours_per_day > 24:
        msg = "recording_hours_per_day must be <= 24"
        raise ValueError(msg)
    if storage_overhead_pct < 0:
        msg = "storage_overhead_pct must be >= 0"
        raise ValueError(msg)


def compute(
    camera_count: float,
    average_bitrate_mbps: float,
    recording_hours_per_day: float,
    retention_days: float,
    storage_overhead_pct: float,
) -> dict[str, float]:
    """Compute CCTV daily and retained storage capacity."""
    _validate_inputs(
        camera_count,
        average_bitrate_mbps,
        recording_hours_per_day,
        retention_days,
        storage_overhead_pct,
    )

    daily_storage_per_camera_gb = average_bitrate_mbps * recording_hours_per_day * 3600.0 / 8.0 / 1000.0
    usable_storage_required_tb = daily_storage_per_camera_gb * camera_count * retention_days / 1000.0
    raw_storage_with_overhead_tb = usable_storage_required_tb * (1.0 + storage_overhead_pct / 100.0)

    return {
        "daily_storage_per_camera_gb": round(daily_storage_per_camera_gb, 2),
        "usable_storage_required_tb": round(usable_storage_required_tb, 2),
        "raw_storage_with_overhead_tb": round(raw_storage_with_overhead_tb, 2),
    }
