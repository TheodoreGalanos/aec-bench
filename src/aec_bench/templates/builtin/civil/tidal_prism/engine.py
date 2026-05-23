# ABOUTME: Computes tidal prism and inlet flow metrics for a coastal basin.
# ABOUTME: Implements the reduced tidal prism relation P = basin area x tidal range.


def _validate_inputs(
    basin_surface_area_m2: float,
    tidal_range_m: float,
    inlet_width_m: float,
    inlet_average_depth_m: float,
    exchange_duration_h: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if basin_surface_area_m2 <= 0:
        msg = "basin_surface_area_m2 must be > 0"
        raise ValueError(msg)
    if tidal_range_m <= 0:
        msg = "tidal_range_m must be > 0"
        raise ValueError(msg)
    if inlet_width_m <= 0:
        msg = "inlet_width_m must be > 0"
        raise ValueError(msg)
    if inlet_average_depth_m <= 0:
        msg = "inlet_average_depth_m must be > 0"
        raise ValueError(msg)
    if exchange_duration_h <= 0:
        msg = "exchange_duration_h must be > 0"
        raise ValueError(msg)


def compute(
    basin_surface_area_m2: float,
    tidal_range_m: float,
    inlet_width_m: float,
    inlet_average_depth_m: float,
    exchange_duration_h: float,
) -> dict[str, float]:
    """Compute tidal prism, mean flow, and mean inlet velocity."""
    _validate_inputs(
        basin_surface_area_m2,
        tidal_range_m,
        inlet_width_m,
        inlet_average_depth_m,
        exchange_duration_h,
    )

    tidal_prism_m3 = basin_surface_area_m2 * tidal_range_m
    inlet_flow_area_m2 = inlet_width_m * inlet_average_depth_m
    exchange_duration_s = exchange_duration_h * 3600.0
    mean_tidal_flow_m3_s = tidal_prism_m3 / exchange_duration_s
    mean_tidal_velocity_m_s = mean_tidal_flow_m3_s / inlet_flow_area_m2

    return {
        "tidal_prism_m3": round(tidal_prism_m3, 2),
        "inlet_flow_area_m2": round(inlet_flow_area_m2, 2),
        "mean_tidal_flow_m3_s": round(mean_tidal_flow_m3_s, 2),
        "mean_tidal_velocity_m_s": round(mean_tidal_velocity_m_s, 2),
    }
