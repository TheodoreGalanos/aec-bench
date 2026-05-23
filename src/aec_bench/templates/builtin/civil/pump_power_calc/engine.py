# ABOUTME: Pump power computation engine for water/wastewater pump stations.
# ABOUTME: Calculates hydraulic power, brake (shaft) power, and motor input power from duty point parameters.


# Density of water at ~15-20 degrees C in kg/m^3.
_RHO = 998.0

# Gravitational acceleration in m/s^2.
_G = 9.81


def _validate_inputs(
    flow_rate_l_s: float,
    total_dynamic_head_m: float,
    pump_efficiency_pct: float,
    motor_efficiency_pct: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if flow_rate_l_s <= 0:
        msg = "flow_rate_l_s must be > 0"
        raise ValueError(msg)
    if total_dynamic_head_m <= 0:
        msg = "total_dynamic_head_m must be > 0"
        raise ValueError(msg)
    if pump_efficiency_pct <= 0 or pump_efficiency_pct > 100:
        msg = "pump_efficiency_pct must be > 0 and <= 100"
        raise ValueError(msg)
    if motor_efficiency_pct <= 0 or motor_efficiency_pct > 100:
        msg = "motor_efficiency_pct must be > 0 and <= 100"
        raise ValueError(msg)


def compute(
    flow_rate_l_s: float,
    total_dynamic_head_m: float,
    pump_efficiency_pct: float,
    motor_efficiency_pct: float,
) -> dict[str, float]:
    """Compute pump power requirements at a given duty point.

    Steps:
      1. Convert flow rate from L/s to m^3/s: Q_m3s = Q_ls / 1000
      2. Calculate hydraulic power: P_h = rho * g * Q * H / 1000 (kW)
      3. Calculate brake (shaft) power: P_b = P_h / eta_pump
      4. Calculate motor input power: P_m = P_b / eta_motor

    Returns a dict with keys: hydraulic_power_kw, brake_power_kw,
    motor_input_power_kw.
    """
    _validate_inputs(
        flow_rate_l_s,
        total_dynamic_head_m,
        pump_efficiency_pct,
        motor_efficiency_pct,
    )

    # Convert flow rate from L/s to m^3/s
    flow_rate_m3_s = flow_rate_l_s / 1000.0

    # Convert efficiencies from percentage to decimal
    eta_pump = pump_efficiency_pct / 100.0
    eta_motor = motor_efficiency_pct / 100.0

    # Hydraulic power (water power): P_h = rho * g * Q * H / 1000
    # Dividing by 1000 converts W to kW
    hydraulic_power_kw = _RHO * _G * flow_rate_m3_s * total_dynamic_head_m / 1000.0

    # Brake (shaft) power: power delivered to the pump shaft
    brake_power_kw = hydraulic_power_kw / eta_pump

    # Motor input power: electrical power drawn by the motor
    motor_input_power_kw = brake_power_kw / eta_motor

    return {
        "hydraulic_power_kw": round(hydraulic_power_kw, 2),
        "brake_power_kw": round(brake_power_kw, 2),
        "motor_input_power_kw": round(motor_input_power_kw, 2),
    }
