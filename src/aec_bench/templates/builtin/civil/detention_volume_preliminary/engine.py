# ABOUTME: Detention volume computation engine using simplified triangular hydrograph method.
# ABOUTME: Calculates required storage volume and approximate surface area for stormwater detention.


def _validate_inputs(
    post_dev_peak_flow_m3_s: float,
    allowable_release_rate_m3_s: float,
    storm_duration_hr: float,
    design_depth_m: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if post_dev_peak_flow_m3_s <= 0:
        msg = "post_dev_peak_flow_m3_s must be > 0"
        raise ValueError(msg)
    if allowable_release_rate_m3_s <= 0:
        msg = "allowable_release_rate_m3_s must be > 0"
        raise ValueError(msg)
    if storm_duration_hr <= 0:
        msg = "storm_duration_hr must be > 0"
        raise ValueError(msg)
    if storm_duration_hr > 72:
        msg = "storm_duration_hr must be <= 72 (practical limit for detention sizing)"
        raise ValueError(msg)
    if design_depth_m <= 0:
        msg = "design_depth_m must be > 0"
        raise ValueError(msg)
    if design_depth_m > 3.0:
        msg = "design_depth_m must be <= 3.0 (practical limit for detention basins)"
        raise ValueError(msg)


def compute(
    post_dev_peak_flow_m3_s: float,
    allowable_release_rate_m3_s: float,
    storm_duration_hr: float,
    design_depth_m: float,
) -> dict[str, float]:
    """Estimate detention volume via simplified triangular hydrograph method.

    Assumes a triangular inflow hydrograph with peak Q_post and duration
    t_storm, and constant outflow at Q_allow during the storm.

    Two cases for required storage volume:
      Case 1 (Q_allow < Q_post/2):
        V = t_storm * 3600 * (Q_post/2 - Q_allow)
      Case 2 (Q_allow >= Q_post/2):
        V = (Q_post - Q_allow)^2 * t_storm * 3600 / (2 * Q_post)

    If Q_allow >= Q_post (no detention needed), V = 0.

    Approximate surface area:
      A_surface = V / design_depth

    Returns a dict with keys: required_storage_volume_m3,
    approximate_surface_area_m2.
    """
    _validate_inputs(
        post_dev_peak_flow_m3_s,
        allowable_release_rate_m3_s,
        storm_duration_hr,
        design_depth_m,
    )

    # Clamp allowable release rate below post-development peak flow.
    # If Q_allow >= Q_post, no detention is needed; compute valid result with V=0.
    q_post = post_dev_peak_flow_m3_s
    q_allow = min(allowable_release_rate_m3_s, q_post)

    t_seconds = storm_duration_hr * 3600.0

    if q_allow >= q_post:
        # No detention required
        required_storage_volume_m3 = 0.0
    elif q_allow < q_post / 2.0:
        # Case 1: outflow is less than half the triangular peak
        # Volume = inflow triangle area minus outflow rectangle
        required_storage_volume_m3 = t_seconds * (q_post / 2.0 - q_allow)
    else:
        # Case 2: outflow intersects the rising limb of the triangle
        # Volume = (Q_post - Q_allow)^2 * t_storm * 3600 / (2 * Q_post)
        required_storage_volume_m3 = (q_post - q_allow) ** 2 * t_seconds / (2.0 * q_post)

    # Approximate surface area from volume and design depth
    approximate_surface_area_m2 = required_storage_volume_m3 / design_depth_m if required_storage_volume_m3 > 0 else 0.0

    return {
        "required_storage_volume_m3": round(required_storage_volume_m3, 2),
        "approximate_surface_area_m2": round(approximate_surface_area_m2, 2),
    }
