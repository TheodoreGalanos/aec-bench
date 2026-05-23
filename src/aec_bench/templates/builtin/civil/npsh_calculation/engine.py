# ABOUTME: Net Positive Suction Head Available (NPSHa) computation engine.
# ABOUTME: Calculates NPSHa, NPSH margin, and margin ratio per Hydraulics Institute methodology.


# Gravitational acceleration in m/s^2.
_G = 9.81

# Reference water density at ~15-20 degrees C in kg/m^3.
_RHO_WATER = 998.0


def _validate_inputs(
    atmospheric_pressure_kpa: float,
    vapour_pressure_kpa: float,
    specific_gravity: float,
    static_suction_head_m: float,
    friction_loss_m: float,
    npsh_required_m: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if atmospheric_pressure_kpa <= 0:
        msg = "atmospheric_pressure_kpa must be > 0"
        raise ValueError(msg)
    if vapour_pressure_kpa < 0:
        msg = "vapour_pressure_kpa must be >= 0"
        raise ValueError(msg)
    if vapour_pressure_kpa >= atmospheric_pressure_kpa:
        msg = "vapour_pressure_kpa must be < atmospheric_pressure_kpa"
        raise ValueError(msg)
    if specific_gravity <= 0:
        msg = "specific_gravity must be > 0"
        raise ValueError(msg)
    if friction_loss_m < 0:
        msg = "friction_loss_m must be >= 0"
        raise ValueError(msg)
    if npsh_required_m <= 0:
        msg = "npsh_required_m must be > 0"
        raise ValueError(msg)


def compute(
    atmospheric_pressure_kpa: float,
    vapour_pressure_kpa: float,
    specific_gravity: float,
    static_suction_head_m: float,
    friction_loss_m: float,
    npsh_required_m: float,
) -> dict[str, float]:
    """Compute NPSHa, NPSH margin, and margin ratio for a pump suction system.

    The Hydraulics Institute formula for NPSHa:
      NPSHa = (P_atm - P_vap) / (rho * g) + h_s - h_f

    where:
      P_atm = atmospheric pressure (kPa, converted to Pa)
      P_vap = fluid vapour pressure (kPa, converted to Pa)
      rho   = fluid density = _RHO_WATER * specific_gravity (kg/m^3)
      g     = 9.81 m/s^2
      h_s   = static suction head (m), positive if pump below liquid, negative if above
      h_f   = suction pipe friction losses (m)

    NPSH margin = NPSHa - NPSHr
    Margin ratio = NPSHa / NPSHr (should exceed 1.35 per ANSI/HI 9.6.1)

    Returns a dict with keys: pressure_head_m, npsh_available_m,
    npsh_margin_m, npsh_margin_ratio.
    """
    _validate_inputs(
        atmospheric_pressure_kpa,
        vapour_pressure_kpa,
        specific_gravity,
        static_suction_head_m,
        friction_loss_m,
        npsh_required_m,
    )

    # Fluid density based on specific gravity relative to water
    rho = _RHO_WATER * specific_gravity

    # Convert pressures from kPa to Pa for consistent units
    p_atm_pa = atmospheric_pressure_kpa * 1000.0
    p_vap_pa = vapour_pressure_kpa * 1000.0

    # Pressure head: net pressure contribution converted to metres of fluid
    pressure_head_m = (p_atm_pa - p_vap_pa) / (rho * _G)

    # NPSHa per Hydraulics Institute: pressure head + static head - friction losses
    npsh_available_m = pressure_head_m + static_suction_head_m - friction_loss_m

    # NPSH margin: how much available exceeds required
    npsh_margin_m = npsh_available_m - npsh_required_m

    # Margin ratio: NPSHa / NPSHr (ANSI/HI 9.6.1 recommends > 1.35)
    npsh_margin_ratio = npsh_available_m / npsh_required_m

    return {
        "pressure_head_m": round(pressure_head_m, 2),
        "npsh_available_m": round(npsh_available_m, 2),
        "npsh_margin_m": round(npsh_margin_m, 2),
        "npsh_margin_ratio": round(npsh_margin_ratio, 2),
    }
