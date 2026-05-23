# ABOUTME: Minimum horizontal curve radius computation engine for road geometry design.
# ABOUTME: Implements R_min = V^2 / (127 * (e_max + f)) per AGRD Part 3 Section 7.


def _validate_inputs(
    design_speed_km_h: float,
    max_superelevation_pct: float,
    side_friction_factor: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if design_speed_km_h <= 0:
        msg = "design_speed_km_h must be > 0"
        raise ValueError(msg)
    if max_superelevation_pct < 0:
        msg = "max_superelevation_pct must be >= 0"
        raise ValueError(msg)
    if max_superelevation_pct > 12.0:
        msg = "max_superelevation_pct must be <= 12"
        raise ValueError(msg)
    if side_friction_factor < 0:
        msg = "side_friction_factor must be >= 0"
        raise ValueError(msg)
    if side_friction_factor > 0.40:
        msg = "side_friction_factor must be <= 0.40"
        raise ValueError(msg)
    # Ensure the denominator is positive
    e_max = max_superelevation_pct / 100.0
    if (e_max + side_friction_factor) <= 0:
        msg = "e_max + side_friction_factor must be > 0"
        raise ValueError(msg)


def _min_radius(
    design_speed_km_h: float,
    e_max: float,
    side_friction_factor: float,
) -> float:
    """Calculate absolute minimum horizontal curve radius in metres.

    R_min = V^2 / (127 * (e_max + f))

    where:
        V     = design speed (km/h)
        e_max = maximum superelevation rate as a decimal (e.g. 0.06 for 6%)
        f     = side friction factor (speed-dependent, from AGRD Table 7.5)
    """
    return (design_speed_km_h**2) / (127.0 * (e_max + side_friction_factor))


def _desirable_min_radius(
    design_speed_km_h: float,
    e_max: float,
    side_friction_factor: float,
) -> float:
    """Calculate desirable minimum horizontal curve radius in metres.

    Uses a reduced friction factor (0.7 * f) for a larger margin of safety:
        R_desirable = V^2 / (127 * (e_max + 0.7 * f))
    """
    f_reduced = 0.7 * side_friction_factor
    return (design_speed_km_h**2) / (127.0 * (e_max + f_reduced))


def compute(
    design_speed_km_h: float,
    max_superelevation_pct: float,
    side_friction_factor: float,
) -> dict[str, float]:
    """Compute minimum and desirable minimum horizontal curve radius.

    Returns a dict with keys: min_radius_m, desirable_min_radius_m.
    """
    _validate_inputs(design_speed_km_h, max_superelevation_pct, side_friction_factor)

    e_max = max_superelevation_pct / 100.0

    r_min = _min_radius(design_speed_km_h, e_max, side_friction_factor)
    r_desirable = _desirable_min_radius(design_speed_km_h, e_max, side_friction_factor)

    return {
        "min_radius_m": round(r_min, 2),
        "desirable_min_radius_m": round(r_desirable, 2),
    }
