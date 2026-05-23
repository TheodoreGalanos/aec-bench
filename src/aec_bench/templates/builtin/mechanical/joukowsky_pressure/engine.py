# ABOUTME: Joukowsky pressure computation engine for transient hydraulic checks.
# ABOUTME: Calculates pressure rise in pascals, kilopascals, and metres of head.

_G = 9.81


def _validate_inputs(
    fluid_density_kg_m3: float,
    wave_speed_m_s: float,
    velocity_change_m_s: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if fluid_density_kg_m3 <= 0:
        msg = "fluid_density_kg_m3 must be > 0"
        raise ValueError(msg)
    if wave_speed_m_s <= 0:
        msg = "wave_speed_m_s must be > 0"
        raise ValueError(msg)
    if velocity_change_m_s < 0:
        msg = "velocity_change_m_s must be >= 0"
        raise ValueError(msg)


def compute(
    fluid_density_kg_m3: float,
    wave_speed_m_s: float,
    velocity_change_m_s: float,
) -> dict[str, float]:
    """Compute Joukowsky pressure rise from a velocity change.

    Returns a dict with keys: pressure_rise_pa, pressure_rise_kpa,
    pressure_head_m.
    """
    _validate_inputs(fluid_density_kg_m3, wave_speed_m_s, velocity_change_m_s)

    pressure_rise_pa = fluid_density_kg_m3 * wave_speed_m_s * velocity_change_m_s
    pressure_rise_kpa = pressure_rise_pa / 1000.0
    pressure_head = pressure_rise_pa / (fluid_density_kg_m3 * _G)

    return {
        "pressure_rise_pa": round(pressure_rise_pa, 2),
        "pressure_rise_kpa": round(pressure_rise_kpa, 2),
        "pressure_head_m": round(pressure_head, 2),
    }
