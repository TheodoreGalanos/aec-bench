# ABOUTME: Superelevation rate and development length computation engine for horizontal curves.
# ABOUTME: Implements e + f = V^2 / (127 * R) per AASHTO / Austroads AGRD Part 3 Section 7.5.


def _validate_inputs(
    design_speed_km_h: float,
    curve_radius_m: float,
    side_friction_factor: float,
    lane_width_m: float,
    rotation_rate: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if design_speed_km_h <= 0:
        msg = "design_speed_km_h must be > 0"
        raise ValueError(msg)
    if curve_radius_m <= 0:
        msg = "curve_radius_m must be > 0"
        raise ValueError(msg)
    if side_friction_factor < 0:
        msg = "side_friction_factor must be >= 0"
        raise ValueError(msg)
    if side_friction_factor > 0.4:
        msg = "side_friction_factor must be <= 0.4"
        raise ValueError(msg)
    if lane_width_m <= 0:
        msg = "lane_width_m must be > 0"
        raise ValueError(msg)
    if rotation_rate <= 0:
        msg = "rotation_rate must be > 0"
        raise ValueError(msg)


def _superelevation_rate(
    design_speed_km_h: float,
    curve_radius_m: float,
    side_friction_factor: float,
) -> float:
    """Calculate the required superelevation rate as a percentage.

    Uses the AASHTO / Austroads point-mass equilibrium equation:
        e + f = V^2 / (127 * R)
    Rearranged:
        e = V^2 / (127 * R) - f

    The result is expressed as a percentage (e.g. 0.04 -> 4.0%).
    Negative results are clamped to zero (curve is gentle enough that
    normal crown or adverse crown is sufficient).
    """
    e_fraction = (design_speed_km_h**2) / (127.0 * curve_radius_m) - side_friction_factor
    # Clamp to zero — no negative superelevation from this formula
    e_fraction = max(0.0, e_fraction)
    return e_fraction * 100.0


def _development_length(
    superelevation_rate_pct: float,
    lane_width_m: float,
    rotation_rate: float,
) -> float:
    """Calculate the superelevation development (runoff) length.

    Ls = (e / 100) * w / rotation_rate

    where:
        e   = superelevation rate (%)
        w   = lane width (m)
        rotation_rate = maximum rate of pavement rotation (m/m),
                        typically 1/200 = 0.005 for design speeds ~80 km/h
    """
    e_fraction = superelevation_rate_pct / 100.0
    return e_fraction * lane_width_m / rotation_rate


def compute(
    design_speed_km_h: float,
    curve_radius_m: float,
    side_friction_factor: float,
    lane_width_m: float,
    rotation_rate: float = 0.005,
) -> dict[str, float]:
    """Compute superelevation rate and development length for a horizontal curve.

    Returns a dict with keys: superelevation_rate_pct, development_length_m.
    """
    _validate_inputs(
        design_speed_km_h,
        curve_radius_m,
        side_friction_factor,
        lane_width_m,
        rotation_rate,
    )

    e_pct = _superelevation_rate(design_speed_km_h, curve_radius_m, side_friction_factor)
    ls = _development_length(e_pct, lane_width_m, rotation_rate)

    return {
        "superelevation_rate_pct": round(e_pct, 2),
        "development_length_m": round(ls, 2),
    }
