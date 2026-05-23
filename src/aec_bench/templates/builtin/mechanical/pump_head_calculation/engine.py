# ABOUTME: Total dynamic head computation engine for pump hydraulic checks.
# ABOUTME: Converts pressure and loss terms to fluid head and computes hydraulic power.

_G = 9.81


def _validate_inputs(
    flow_rate_m3_h: float,
    suction_pressure_kpa: float,
    discharge_pressure_kpa: float,
    elevation_difference_m: float,
    pipe_friction_losses_kpa: float,
    fluid_density_kg_m3: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if flow_rate_m3_h <= 0:
        msg = "flow_rate_m3_h must be > 0"
        raise ValueError(msg)
    if discharge_pressure_kpa < suction_pressure_kpa:
        msg = "discharge_pressure_kpa must be >= suction_pressure_kpa"
        raise ValueError(msg)
    if pipe_friction_losses_kpa < 0:
        msg = "pipe_friction_losses_kpa must be >= 0"
        raise ValueError(msg)
    if fluid_density_kg_m3 <= 0:
        msg = "fluid_density_kg_m3 must be > 0"
        raise ValueError(msg)


def compute(
    flow_rate_m3_h: float,
    suction_pressure_kpa: float,
    discharge_pressure_kpa: float,
    elevation_difference_m: float,
    pipe_friction_losses_kpa: float,
    fluid_density_kg_m3: float,
) -> dict[str, float]:
    """Compute total dynamic head and hydraulic power.

    Returns a dict with keys: static_head_m, pressure_head_differential_m,
    friction_head_m, total_dynamic_head_m, hydraulic_power_kw.
    """
    _validate_inputs(
        flow_rate_m3_h,
        suction_pressure_kpa,
        discharge_pressure_kpa,
        elevation_difference_m,
        pipe_friction_losses_kpa,
        fluid_density_kg_m3,
    )

    flow_rate_m3_s = flow_rate_m3_h / 3600.0
    pressure_head = (discharge_pressure_kpa - suction_pressure_kpa) * 1000.0 / (fluid_density_kg_m3 * _G)
    friction_head = pipe_friction_losses_kpa * 1000.0 / (fluid_density_kg_m3 * _G)
    static_head = elevation_difference_m
    total_dynamic_head = static_head + pressure_head + friction_head
    hydraulic_power = fluid_density_kg_m3 * _G * flow_rate_m3_s * total_dynamic_head / 1000.0

    return {
        "static_head_m": round(static_head, 2),
        "pressure_head_differential_m": round(pressure_head, 2),
        "friction_head_m": round(friction_head, 2),
        "total_dynamic_head_m": round(total_dynamic_head, 2),
        "hydraulic_power_kw": round(hydraulic_power, 2),
    }
