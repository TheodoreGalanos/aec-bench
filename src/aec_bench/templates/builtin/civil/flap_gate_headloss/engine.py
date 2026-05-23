# ABOUTME: Flap gate headloss computation engine for stormwater outfalls.
# ABOUTME: Calculates energy loss, unseating head, and capacity reduction using orifice-based Cd approach.

from typing import Literal

# Gravitational acceleration (m/s^2).
_G = 9.81

# Specific weight of water (N/m^3).
_GAMMA_W = 9810.0

# Discharge coefficients by gate type.
# Values from hydraulic references and manufacturer data (Waterman, Hydro Gate, Mosbaek).
_CD_TABLE: dict[str, tuple[float, float]] = {
    "side_hinged": (0.60, 0.65),
    "top_hinged": (0.55, 0.60),
    "duckbill": (0.50, 0.55),
}

# Unseating head lookup by pipe diameter (mm).
# Represents the minimum differential head (m) to open the gate against its weight.
# Derived from manufacturer data for cast-iron and fabricated steel flap gates.
_UNSEATING_HEAD_M: dict[str, float] = {
    "150": 0.010,
    "225": 0.012,
    "300": 0.015,
    "375": 0.020,
    "450": 0.025,
    "600": 0.030,
    "750": 0.035,
    "900": 0.040,
    "1200": 0.050,
}

# Gate weight lookup by pipe diameter (kg).
# Representative weights for standard cast-iron flap gates.
_GATE_WEIGHT_KG: dict[str, float] = {
    "150": 8.0,
    "225": 14.0,
    "300": 22.0,
    "375": 32.0,
    "450": 45.0,
    "600": 75.0,
    "750": 110.0,
    "900": 155.0,
    "1200": 280.0,
}


def _validate_inputs(
    pipe_diameter_mm: str,
    flow_velocity_m_per_s: float,
    gate_type: str,
    upstream_head_m: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    valid_diameters = list(_UNSEATING_HEAD_M.keys())
    if pipe_diameter_mm not in valid_diameters:
        msg = f"pipe_diameter_mm must be one of {valid_diameters}, got '{pipe_diameter_mm}'"
        raise ValueError(msg)

    if flow_velocity_m_per_s <= 0:
        msg = "flow_velocity_m_per_s must be > 0"
        raise ValueError(msg)

    valid_gate_types = list(_CD_TABLE.keys())
    if gate_type not in valid_gate_types:
        msg = f"gate_type must be one of {valid_gate_types}, got '{gate_type}'"
        raise ValueError(msg)

    if upstream_head_m <= 0:
        msg = "upstream_head_m must be > 0"
        raise ValueError(msg)


def _mid_cd(gate_type: str) -> float:
    """Return the midpoint discharge coefficient for a gate type."""
    cd_low, cd_high = _CD_TABLE[gate_type]
    return (cd_low + cd_high) / 2.0


def compute(
    pipe_diameter_mm: Literal[
        "150",
        "225",
        "300",
        "375",
        "450",
        "600",
        "750",
        "900",
        "1200",
    ],
    flow_velocity_m_per_s: float,
    gate_type: Literal["side_hinged", "top_hinged", "duckbill"],
    upstream_head_m: float,
) -> dict[str, float]:
    """Compute flap gate headloss, unseating head, and capacity reduction.

    Steps:
      1. Look up midpoint discharge coefficient Cd for the gate type.
      2. Calculate headloss: h_loss = V^2 / (2 * g * Cd^2).
      3. Look up unseating head from the diameter-based table.
      4. Calculate capacity reduction: (1 - Cd) * 100.

    Returns a dict with keys: headloss_m, unseating_head_m,
    capacity_reduction_percent, discharge_coefficient.
    """
    _validate_inputs(pipe_diameter_mm, flow_velocity_m_per_s, gate_type, upstream_head_m)

    cd = _mid_cd(gate_type)

    # Headloss through the flap gate using orifice equation rearranged:
    # h_loss = V^2 / (2 * g * Cd^2)
    v = flow_velocity_m_per_s
    headloss = v**2 / (2.0 * _G * cd**2)

    # Unseating head from lookup table
    unseating_head = _UNSEATING_HEAD_M[pipe_diameter_mm]

    # Capacity reduction compared to open pipe
    capacity_reduction = (1.0 - cd) * 100.0

    return {
        "headloss_m": round(headloss, 2),
        "unseating_head_m": round(unseating_head, 2),
        "capacity_reduction_percent": round(capacity_reduction, 2),
        "discharge_coefficient": round(cd, 2),
    }
