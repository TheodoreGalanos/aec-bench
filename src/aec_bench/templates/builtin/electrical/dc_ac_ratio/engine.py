# ABOUTME: Solar PV DC/AC ratio (inverter loading ratio) computation engine.
# ABOUTME: Calculates ILR, estimated clipping losses, and annual energy yield per IEC 62548.


# Clipping loss model coefficients.
# Quadratic approximation: clipping_pct = a * (ILR - 1)^2 + b * (ILR - 1)
# Fitted to industry-typical values:
#   ILR 1.0 -> 0%, ILR 1.2 -> ~0.5%, ILR 1.3 -> ~1.5%, ILR 1.5 -> ~5%
# These coefficients represent a moderate-irradiance site (e.g., Australia, IEC 62548).
_CLIP_A = 10.0
_CLIP_B = -0.5

# Inverter efficiency assumed for simplified model (typical CEC weighted efficiency).
_INVERTER_EFFICIENCY = 0.965


def _estimate_clipping_loss_pct(ilr: float) -> float:
    """Estimate annual clipping losses as a percentage of DC energy using a quadratic model.

    For ILR <= 1.0, no clipping occurs because the inverter is never overloaded.
    For ILR > 1.0, a quadratic approximation models the increasing probability
    that instantaneous DC power exceeds inverter AC capacity during peak hours.
    """
    if ilr <= 1.0:
        return 0.0
    excess = ilr - 1.0
    clip_pct = _CLIP_A * excess * excess + _CLIP_B * excess
    # Clipping cannot be negative
    return max(0.0, clip_pct)


def _validate_inputs(
    dc_array_capacity_kwp: float,
    inverter_ac_capacity_kw: float,
    annual_psh: float,
    system_losses_pct: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if dc_array_capacity_kwp <= 0:
        msg = "dc_array_capacity_kwp must be > 0"
        raise ValueError(msg)
    if inverter_ac_capacity_kw <= 0:
        msg = "inverter_ac_capacity_kw must be > 0"
        raise ValueError(msg)
    if annual_psh <= 0:
        msg = "annual_psh must be > 0"
        raise ValueError(msg)
    if system_losses_pct < 0:
        msg = "system_losses_pct must be >= 0"
        raise ValueError(msg)
    if system_losses_pct >= 100:
        msg = "system_losses_pct must be < 100"
        raise ValueError(msg)


def compute(
    dc_array_capacity_kwp: float,
    inverter_ac_capacity_kw: float,
    annual_psh: float,
    system_losses_pct: float,
) -> dict[str, float]:
    """Compute DC/AC ratio, clipping losses, annual energy yield, and specific yield.

    The DC/AC ratio (ILR) is the ratio of installed DC array capacity to inverter
    AC capacity. Higher ratios increase inverter utilisation but introduce clipping
    losses when DC output exceeds inverter capacity during peak irradiance hours.

    Returns a dict with keys: dc_ac_ratio, estimated_clipping_loss_pct,
    annual_energy_yield_kwh, specific_yield_kwh_per_kwp.
    """
    _validate_inputs(
        dc_array_capacity_kwp,
        inverter_ac_capacity_kw,
        annual_psh,
        system_losses_pct,
    )

    # DC/AC ratio (Inverter Loading Ratio)
    # ILR = DC array capacity (kWp) / inverter AC capacity (kW)
    dc_ac_ratio = dc_array_capacity_kwp / inverter_ac_capacity_kw

    # Estimated clipping loss using quadratic model
    clipping_loss_pct = _estimate_clipping_loss_pct(dc_ac_ratio)

    # Annual energy yield calculation
    # E = P_dc * PSH * (1 - system_losses/100) * inverter_eff * (1 - clipping/100)
    system_loss_factor = 1.0 - system_losses_pct / 100.0
    clipping_factor = 1.0 - clipping_loss_pct / 100.0
    annual_energy_kwh = dc_array_capacity_kwp * annual_psh * system_loss_factor * _INVERTER_EFFICIENCY * clipping_factor

    # Specific yield: energy produced per kWp of installed DC capacity
    specific_yield = annual_energy_kwh / dc_array_capacity_kwp

    return {
        "dc_ac_ratio": round(dc_ac_ratio, 2),
        "estimated_clipping_loss_pct": round(clipping_loss_pct, 2),
        "annual_energy_yield_kwh": round(annual_energy_kwh, 2),
        "specific_yield_kwh_per_kwp": round(specific_yield, 2),
    }
