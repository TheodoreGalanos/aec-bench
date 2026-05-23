# ABOUTME: Net positive suction head computation engine for pump inlet checks.
# ABOUTME: Calculates NPSH available and cavitation margin from suction-side inputs.

_G = 9.81


def _validate_inputs(
    suction_vessel_pressure_kpa_abs: float,
    liquid_level_above_pump_m: float,
    suction_pipe_losses_kpa: float,
    vapor_pressure_kpa_abs: float,
    fluid_density_kg_m3: float,
    npsh_required_m: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if suction_vessel_pressure_kpa_abs <= 0:
        msg = "suction_vessel_pressure_kpa_abs must be > 0"
        raise ValueError(msg)
    if suction_pipe_losses_kpa < 0:
        msg = "suction_pipe_losses_kpa must be >= 0"
        raise ValueError(msg)
    if vapor_pressure_kpa_abs < 0:
        msg = "vapor_pressure_kpa_abs must be >= 0"
        raise ValueError(msg)
    if fluid_density_kg_m3 <= 0:
        msg = "fluid_density_kg_m3 must be > 0"
        raise ValueError(msg)
    if npsh_required_m < 0:
        msg = "npsh_required_m must be >= 0"
        raise ValueError(msg)


def compute(
    suction_vessel_pressure_kpa_abs: float,
    liquid_level_above_pump_m: float,
    suction_pipe_losses_kpa: float,
    vapor_pressure_kpa_abs: float,
    fluid_density_kg_m3: float,
    npsh_required_m: float,
) -> dict[str, float]:
    """Compute NPSH available and margin over required NPSH.

    Returns a dict with keys: pressure_head_m, vapor_pressure_head_m,
    loss_head_m, npsh_available_m, cavitation_margin_m, margin_ratio.
    """
    _validate_inputs(
        suction_vessel_pressure_kpa_abs,
        liquid_level_above_pump_m,
        suction_pipe_losses_kpa,
        vapor_pressure_kpa_abs,
        fluid_density_kg_m3,
        npsh_required_m,
    )

    pressure_head = suction_vessel_pressure_kpa_abs * 1000.0 / (fluid_density_kg_m3 * _G)
    vapor_head = vapor_pressure_kpa_abs * 1000.0 / (fluid_density_kg_m3 * _G)
    loss_head = suction_pipe_losses_kpa * 1000.0 / (fluid_density_kg_m3 * _G)
    npsha = pressure_head + liquid_level_above_pump_m - vapor_head - loss_head
    margin = npsha - npsh_required_m
    margin_ratio = npsha / npsh_required_m if npsh_required_m > 0 else 99.99

    return {
        "pressure_head_m": round(pressure_head, 2),
        "vapor_pressure_head_m": round(vapor_head, 2),
        "loss_head_m": round(loss_head, 2),
        "npsh_available_m": round(npsha, 2),
        "cavitation_margin_m": round(margin, 2),
        "margin_ratio": round(margin_ratio, 2),
    }
