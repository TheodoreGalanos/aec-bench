# ABOUTME: Pump power computation engine for hydraulic duty checks.
# ABOUTME: Calculates hydraulic power, shaft power, and efficiency margin.

_G = 9.81


def _validate_inputs(
    flow_rate_l_s: float,
    total_dynamic_head_m: float,
    fluid_density_kg_m3: float,
    pump_efficiency_pct: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if flow_rate_l_s <= 0:
        msg = "flow_rate_l_s must be > 0"
        raise ValueError(msg)
    if total_dynamic_head_m <= 0:
        msg = "total_dynamic_head_m must be > 0"
        raise ValueError(msg)
    if fluid_density_kg_m3 <= 0:
        msg = "fluid_density_kg_m3 must be > 0"
        raise ValueError(msg)
    if not 0 < pump_efficiency_pct <= 100:
        msg = "pump_efficiency_pct must be > 0 and <= 100"
        raise ValueError(msg)


def compute(
    flow_rate_l_s: float,
    total_dynamic_head_m: float,
    fluid_density_kg_m3: float,
    pump_efficiency_pct: float,
) -> dict[str, float]:
    """Compute hydraulic and shaft pump power.

    Returns a dict with keys: flow_rate_m3_s, hydraulic_power_kw,
    shaft_power_kw, efficiency_fraction.
    """
    _validate_inputs(
        flow_rate_l_s,
        total_dynamic_head_m,
        fluid_density_kg_m3,
        pump_efficiency_pct,
    )

    flow_rate_m3_s = flow_rate_l_s / 1000.0
    efficiency_fraction = pump_efficiency_pct / 100.0
    hydraulic_power = fluid_density_kg_m3 * _G * flow_rate_m3_s * total_dynamic_head_m / 1000.0
    shaft_power = hydraulic_power / efficiency_fraction

    return {
        "flow_rate_m3_s": round(flow_rate_m3_s, 3),
        "hydraulic_power_kw": round(hydraulic_power, 2),
        "shaft_power_kw": round(shaft_power, 2),
        "efficiency_fraction": round(efficiency_fraction, 3),
    }
