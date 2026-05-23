# ABOUTME: CSTR sizing engine for first-order liquid reactions.
# ABOUTME: Calculates outlet concentration, reaction rate, space time, and volume.


def _validate_inputs(
    volumetric_flow_m3_h: float,
    inlet_concentration_kmol_m3: float,
    required_conversion_pct: float,
    rate_constant_h_inv: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if volumetric_flow_m3_h <= 0:
        msg = "volumetric_flow_m3_h must be > 0"
        raise ValueError(msg)
    if inlet_concentration_kmol_m3 <= 0:
        msg = "inlet_concentration_kmol_m3 must be > 0"
        raise ValueError(msg)
    if required_conversion_pct <= 0 or required_conversion_pct >= 100:
        msg = "required_conversion_pct must be > 0 and < 100"
        raise ValueError(msg)
    if rate_constant_h_inv <= 0:
        msg = "rate_constant_h_inv must be > 0"
        raise ValueError(msg)


def compute(
    volumetric_flow_m3_h: float,
    inlet_concentration_kmol_m3: float,
    required_conversion_pct: float,
    rate_constant_h_inv: float,
) -> dict[str, float]:
    """Compute CSTR volume for an isothermal first-order reaction.

    Returns a dict with keys: outlet_concentration_kmol_m3,
    outlet_reaction_rate_kmol_m3_h, space_time_h, required_volume_m3.
    """
    _validate_inputs(
        volumetric_flow_m3_h,
        inlet_concentration_kmol_m3,
        required_conversion_pct,
        rate_constant_h_inv,
    )

    conversion = required_conversion_pct / 100.0
    outlet_concentration = inlet_concentration_kmol_m3 * (1.0 - conversion)
    outlet_rate = rate_constant_h_inv * outlet_concentration
    space_time = conversion / (rate_constant_h_inv * (1.0 - conversion))
    volume = volumetric_flow_m3_h * space_time

    return {
        "outlet_concentration_kmol_m3": round(outlet_concentration, 2),
        "outlet_reaction_rate_kmol_m3_h": round(outlet_rate, 2),
        "space_time_h": round(space_time, 2),
        "required_volume_m3": round(volume, 2),
    }
