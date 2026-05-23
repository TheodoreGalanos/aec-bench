# ABOUTME: Design wind pressure computation engine per AS/NZS 1170.2 Section 2.4.
# ABOUTME: Calculates pressure and total surface force from wind speed and aerodynamic factors.


def _validate_inputs(
    design_wind_speed_m_per_s: float,
    cfig: float,
    cdyn: float,
    air_density_kg_per_m3: float,
    tributary_area_m2: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if design_wind_speed_m_per_s <= 0:
        msg = "design_wind_speed_m_per_s must be > 0"
        raise ValueError(msg)
    if cdyn <= 0:
        msg = "cdyn must be > 0"
        raise ValueError(msg)
    if air_density_kg_per_m3 <= 0:
        msg = "air_density_kg_per_m3 must be > 0"
        raise ValueError(msg)
    if tributary_area_m2 <= 0:
        msg = "tributary_area_m2 must be > 0"
        raise ValueError(msg)
    # cfig can be negative (suction) or positive (pressure), but not zero
    # for a meaningful load calculation; however zero is physically valid
    # (e.g., balanced internal/external pressures) so we allow it.


def _dynamic_pressure_pa(
    air_density_kg_per_m3: float,
    design_wind_speed_m_per_s: float,
) -> float:
    """Compute the basic dynamic wind pressure q = 0.5 * rho * V^2.

    Returns pressure in Pascals (Pa).
    """
    return 0.5 * air_density_kg_per_m3 * design_wind_speed_m_per_s**2


def _design_pressure_pa(
    dynamic_pressure_pa: float,
    cfig: float,
    cdyn: float,
) -> float:
    """Compute design wind pressure p = q * C_fig * C_dyn.

    Per AS/NZS 1170.2 Clause 2.4.1:
      p = 0.5 * rho_air * V_des^2 * C_fig * C_dyn

    Returns pressure in Pascals (Pa). Sign follows C_fig convention:
    positive = pressure towards surface, negative = suction away from surface.
    """
    return dynamic_pressure_pa * cfig * cdyn


def _total_force_kn(
    design_pressure_pa: float,
    tributary_area_m2: float,
) -> float:
    """Compute total wind force on the tributary area.

    F = p * A, converted from N to kN (divide by 1000).
    Sign follows design pressure convention.
    """
    return design_pressure_pa * tributary_area_m2 / 1000.0


def compute(
    design_wind_speed_m_per_s: float,
    cfig: float,
    cdyn: float = 1.0,
    air_density_kg_per_m3: float = 1.2,
    tributary_area_m2: float = 1.0,
) -> dict[str, float]:
    """Compute design wind pressure and surface force per AS/NZS 1170.2.

    Uses the formula: p = 0.5 * rho_air * V_des^2 * C_fig * C_dyn

    Where:
    - rho_air = air density (standard 1.2 kg/m3)
    - V_des = design wind speed (m/s)
    - C_fig = aerodynamic shape factor (positive = pressure, negative = suction)
    - C_dyn = dynamic response factor (1.0 for most low-rise structures)

    Returns a dict with keys: dynamic_pressure_kpa, design_pressure_kpa, total_force_kn.
    """
    _validate_inputs(
        design_wind_speed_m_per_s,
        cfig,
        cdyn,
        air_density_kg_per_m3,
        tributary_area_m2,
    )

    q_pa = _dynamic_pressure_pa(air_density_kg_per_m3, design_wind_speed_m_per_s)
    p_pa = _design_pressure_pa(q_pa, cfig, cdyn)
    f_kn = _total_force_kn(p_pa, tributary_area_m2)

    # Convert Pa to kPa for output (1 kPa = 1000 Pa)
    q_kpa = q_pa / 1000.0
    p_kpa = p_pa / 1000.0

    return {
        "dynamic_pressure_kpa": round(q_kpa, 2),
        "design_pressure_kpa": round(p_kpa, 2),
        "total_force_kn": round(f_kn, 2),
    }
