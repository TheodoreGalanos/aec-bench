# ABOUTME: Control valve Cv sizing engine for incompressible liquid service per ISA-75.01.01.
# ABOUTME: Calculates required Cv, checks for choked (cavitating) flow using FL recovery factor.

import math


def _validate_inputs(
    flow_rate_m3_h: float,
    upstream_pressure_bar: float,
    downstream_pressure_bar: float,
    fluid_specific_gravity: float,
    fluid_vapor_pressure_bar: float,
    fluid_critical_pressure_bar: float,
    fl_recovery_factor: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if flow_rate_m3_h <= 0:
        msg = "flow_rate_m3_h must be > 0"
        raise ValueError(msg)
    if upstream_pressure_bar <= 0:
        msg = "upstream_pressure_bar must be > 0"
        raise ValueError(msg)
    if downstream_pressure_bar < 0:
        msg = "downstream_pressure_bar must be >= 0"
        raise ValueError(msg)
    if fluid_specific_gravity <= 0:
        msg = "fluid_specific_gravity must be > 0"
        raise ValueError(msg)
    if fluid_vapor_pressure_bar < 0:
        msg = "fluid_vapor_pressure_bar must be >= 0"
        raise ValueError(msg)
    if fluid_critical_pressure_bar <= 0:
        msg = "fluid_critical_pressure_bar must be > 0"
        raise ValueError(msg)
    if fl_recovery_factor <= 0 or fl_recovery_factor > 1.0:
        msg = "fl_recovery_factor must be > 0 and <= 1.0"
        raise ValueError(msg)


def _critical_pressure_ratio_factor(
    vapor_pressure_bar: float,
    critical_pressure_bar: float,
) -> float:
    """Calculate FF, the liquid critical pressure ratio factor.

    FF = 0.96 - 0.28 * sqrt(Pv / Pc) per ISA-75.01.01 Equation 3.
    FF represents the ratio of apparent vena contracta pressure at choked
    flow to the vapor pressure of the liquid.
    """
    return 0.96 - 0.28 * math.sqrt(vapor_pressure_bar / critical_pressure_bar)


def _choked_pressure_drop(
    upstream_pressure_bar: float,
    vapor_pressure_bar: float,
    critical_pressure_bar: float,
    fl_recovery_factor: float,
) -> float:
    """Calculate the choked (maximum effective) pressure drop in bar.

    deltaP_choked = FL^2 * (P1 - FF * Pv) per ISA-75.01.01 Equation 2.
    When the actual pressure drop exceeds this value, flow is choked and
    the effective pressure drop is limited to deltaP_choked.
    """
    ff = _critical_pressure_ratio_factor(vapor_pressure_bar, critical_pressure_bar)
    return fl_recovery_factor**2 * (upstream_pressure_bar - ff * vapor_pressure_bar)


def compute(
    flow_rate_m3_h: float,
    upstream_pressure_bar: float,
    downstream_pressure_bar: float,
    fluid_specific_gravity: float,
    fluid_vapor_pressure_bar: float,
    fluid_critical_pressure_bar: float,
    fl_recovery_factor: float,
) -> dict[str, float]:
    """Compute required Cv for a control valve in incompressible liquid service.

    Uses ISA-75.01.01 / IEC 60534-2-1 sizing equations for liquids without
    attached fittings (Fp = 1). Checks for choked flow and uses the limiting
    pressure drop when the actual drop exceeds the choked threshold.

    The Kv equation for SI units is:
        Kv = Q * sqrt(SG / deltaP_eff)
    where Q is in m3/h, deltaP_eff in bar, SG is dimensionless.
    Cv = 1.156 * Kv (conversion from metric to US flow coefficient).

    Returns a dict with keys: pressure_drop_bar, cv_required,
    choked_pressure_drop_bar, is_choked.
    """
    _validate_inputs(
        flow_rate_m3_h,
        upstream_pressure_bar,
        downstream_pressure_bar,
        fluid_specific_gravity,
        fluid_vapor_pressure_bar,
        fluid_critical_pressure_bar,
        fl_recovery_factor,
    )

    # Actual pressure drop across the valve
    delta_p_actual = upstream_pressure_bar - downstream_pressure_bar

    # Guard: if no positive pressure drop, valve is fully open / no restriction
    if delta_p_actual <= 0:
        return {
            "pressure_drop_bar": round(delta_p_actual, 2),
            "cv_required": round(0.0, 2),
            "choked_pressure_drop_bar": round(0.0, 2),
            "is_choked": round(0.0, 2),
        }

    # Choked pressure drop per ISA-75.01.01
    delta_p_choked = _choked_pressure_drop(
        upstream_pressure_bar,
        fluid_vapor_pressure_bar,
        fluid_critical_pressure_bar,
        fl_recovery_factor,
    )

    # Guard: if choked pressure drop is non-positive, use actual pressure drop
    if delta_p_choked <= 0:
        delta_p_choked = delta_p_actual

    # Determine effective pressure drop: use the smaller of actual and choked
    is_choked = 1.0 if delta_p_actual >= delta_p_choked else 0.0
    delta_p_eff = min(delta_p_actual, delta_p_choked)

    # Kv (metric flow coefficient) per ISA-75.01.01 Equation 1
    # Kv = Q * sqrt(SG / deltaP_eff)
    kv = flow_rate_m3_h * math.sqrt(fluid_specific_gravity / delta_p_eff)

    # Convert Kv to Cv (US flow coefficient)
    # Cv = 1.156 * Kv per ISA-75.01.01 conversion
    cv = 1.156 * kv

    return {
        "pressure_drop_bar": round(delta_p_actual, 2),
        "cv_required": round(cv, 2),
        "choked_pressure_drop_bar": round(delta_p_choked, 2),
        "is_choked": round(is_choked, 2),
    }
