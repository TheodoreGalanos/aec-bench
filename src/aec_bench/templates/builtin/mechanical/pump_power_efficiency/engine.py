# ABOUTME: Pump power and efficiency computation engine.
# ABOUTME: Calculates hydraulic, shaft, motor input, and recommended motor power.

_G = 9.81


def _validate_inputs(
    flow_rate_m3_h: float,
    total_dynamic_head_m: float,
    fluid_density_kg_m3: float,
    pump_efficiency_pct: float,
    motor_efficiency_pct: float,
    motor_sizing_factor: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if flow_rate_m3_h <= 0:
        msg = "flow_rate_m3_h must be > 0"
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
    if not 0 < motor_efficiency_pct <= 100:
        msg = "motor_efficiency_pct must be > 0 and <= 100"
        raise ValueError(msg)
    if motor_sizing_factor < 1:
        msg = "motor_sizing_factor must be >= 1"
        raise ValueError(msg)


def compute(
    flow_rate_m3_h: float,
    total_dynamic_head_m: float,
    fluid_density_kg_m3: float,
    pump_efficiency_pct: float,
    motor_efficiency_pct: float,
    motor_sizing_factor: float,
) -> dict[str, float]:
    """Compute pump shaft power and motor power allowance.

    Returns a dict with keys: hydraulic_power_kw, shaft_power_kw,
    motor_input_power_kw, recommended_motor_size_kw.
    """
    _validate_inputs(
        flow_rate_m3_h,
        total_dynamic_head_m,
        fluid_density_kg_m3,
        pump_efficiency_pct,
        motor_efficiency_pct,
        motor_sizing_factor,
    )

    flow_rate_m3_s = flow_rate_m3_h / 3600.0
    pump_efficiency = pump_efficiency_pct / 100.0
    motor_efficiency = motor_efficiency_pct / 100.0
    hydraulic_power_kw = fluid_density_kg_m3 * _G * flow_rate_m3_s * total_dynamic_head_m / 1000.0
    shaft_power_kw = hydraulic_power_kw / pump_efficiency
    motor_input_power_kw = shaft_power_kw / motor_efficiency
    recommended_motor_size_kw = motor_input_power_kw * motor_sizing_factor

    return {
        "hydraulic_power_kw": round(hydraulic_power_kw, 2),
        "shaft_power_kw": round(shaft_power_kw, 2),
        "motor_input_power_kw": round(motor_input_power_kw, 2),
        "recommended_motor_size_kw": round(recommended_motor_size_kw, 2),
    }
