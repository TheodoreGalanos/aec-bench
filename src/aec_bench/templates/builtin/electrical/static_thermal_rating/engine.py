# ABOUTME: IEEE 738 steady-state thermal rating computation engine for bare overhead conductors.
# ABOUTME: Calculates ampacity via heat balance: convective + radiative cooling = solar gain + ohmic heating.

import math

# Stefan-Boltzmann constant (W/m^2·K^4).
_STEFAN_BOLTZMANN = 5.6704e-8

# Sea-level atmospheric pressure (Pa).
_ATM_PRESSURE_PA = 101325.0

# Molar mass of dry air (kg/mol).
_MOLAR_MASS_AIR = 0.0289644

# Universal gas constant (J/(mol·K)).
_GAS_CONSTANT = 8.31447


def _film_temperature(conductor_temp_c: float, ambient_temp_c: float) -> float:
    """Average of conductor and ambient temperatures used for air property evaluation."""
    return (conductor_temp_c + ambient_temp_c) / 2.0


def _air_density_kg_m3(film_temp_c: float) -> float:
    """Air density at sea level using ideal gas law.

    Returns density in kg/m^3.
    """
    t_kelvin = film_temp_c + 273.15
    return _ATM_PRESSURE_PA * _MOLAR_MASS_AIR / (_GAS_CONSTANT * t_kelvin)


def _air_dynamic_viscosity_pa_s(film_temp_c: float) -> float:
    """Dynamic viscosity of air using Sutherland's formula.

    Returns viscosity in Pa·s (kg/(m·s)).
    """
    t_kelvin = film_temp_c + 273.15
    # Sutherland's law: mu = C1 * T^1.5 / (T + S)
    # C1 = 1.458e-6 kg/(m·s·K^0.5), S = 110.4 K
    return 1.458e-6 * t_kelvin**1.5 / (t_kelvin + 110.4)


def _air_thermal_conductivity_w_m_k(film_temp_c: float) -> float:
    """Thermal conductivity of air as a polynomial of film temperature.

    IEEE 738 polynomial fit (SI): kf = 2.424e-2 + 7.477e-5*Tf - 4.407e-9*Tf^2
    where Tf is in degrees Celsius and kf is in W/(m·°C).
    """
    tf = film_temp_c
    return 2.424e-2 + 7.477e-5 * tf - 4.407e-9 * tf * tf


def _reynolds_number(
    diameter_m: float,
    air_density: float,
    wind_speed_m_s: float,
    air_viscosity: float,
) -> float:
    """Reynolds number for flow over a cylinder: Re = D * rho * V / mu."""
    return diameter_m * air_density * wind_speed_m_s / air_viscosity


def _wind_angle_factor(wind_angle_deg: float) -> float:
    """Wind direction factor Kangle per IEEE 738.

    Kangle = 1.194 - cos(phi) + 0.194*cos(2*phi) + 0.368*sin(2*phi)
    where phi is the angle between wind direction and conductor axis (0-90 deg).
    """
    # Clamp to [0, 90] range
    phi_deg = max(0.0, min(90.0, wind_angle_deg))
    phi_rad = math.radians(phi_deg)
    return 1.194 - math.cos(phi_rad) + 0.194 * math.cos(2.0 * phi_rad) + 0.368 * math.sin(2.0 * phi_rad)


def _forced_convection_low_re(
    k_angle: float,
    reynolds: float,
    kf: float,
    temp_diff: float,
) -> float:
    """Forced convection heat loss for low Reynolds numbers (IEEE 738 Eq. 3a SI).

    qc1 = Kangle * [1.01 + 1.35 * NRe^0.52] * kf * (Tc - Ta)  [W/m]
    """
    return k_angle * (1.01 + 1.35 * reynolds**0.52) * kf * temp_diff


def _forced_convection_high_re(
    k_angle: float,
    reynolds: float,
    kf: float,
    temp_diff: float,
) -> float:
    """Forced convection heat loss for high Reynolds numbers (IEEE 738 Eq. 3b SI).

    qc2 = Kangle * 0.0754 * NRe^0.6 * kf * (Tc - Ta)  [W/m]
    """
    return k_angle * 0.0754 * reynolds**0.6 * kf * temp_diff


def _natural_convection(
    air_density: float,
    diameter_m: float,
    temp_diff: float,
) -> float:
    """Natural convection heat loss (IEEE 738 SI).

    qcn = 3.645 * rho_f^0.5 * D0^0.75 * (Tc - Ta)^1.25  [W/m]
    """
    if temp_diff <= 0.0:
        return 0.0
    return 3.645 * air_density**0.5 * diameter_m**0.75 * temp_diff**1.25


def _convective_cooling_w_m(
    diameter_m: float,
    conductor_temp_c: float,
    ambient_temp_c: float,
    wind_speed_m_s: float,
    wind_angle_deg: float,
    air_density: float,
    air_viscosity: float,
    air_kf: float,
) -> float:
    """Total convective cooling: max of natural and forced convection."""
    temp_diff = conductor_temp_c - ambient_temp_c
    if temp_diff <= 0.0:
        return 0.0

    qcn = _natural_convection(air_density, diameter_m, temp_diff)

    if wind_speed_m_s <= 0.0:
        return qcn

    k_angle = _wind_angle_factor(wind_angle_deg)
    reynolds = _reynolds_number(diameter_m, air_density, wind_speed_m_s, air_viscosity)

    qc1 = _forced_convection_low_re(k_angle, reynolds, air_kf, temp_diff)
    qc2 = _forced_convection_high_re(k_angle, reynolds, air_kf, temp_diff)

    return max(qcn, qc1, qc2)


def _radiative_cooling_w_m(
    diameter_m: float,
    emissivity: float,
    conductor_temp_c: float,
    ambient_temp_c: float,
) -> float:
    """Radiative heat loss per IEEE 738 (SI).

    qr = pi * D * sigma * epsilon * (Tc_K^4 - Ta_K^4)  [W/m]

    Using the Stefan-Boltzmann constant directly with temperatures in Kelvin.
    """
    tc_k = conductor_temp_c + 273.15
    ta_k = ambient_temp_c + 273.15
    return math.pi * diameter_m * _STEFAN_BOLTZMANN * emissivity * (tc_k**4 - ta_k**4)


def _solar_heat_gain_w_m(
    absorptivity: float,
    solar_radiation_w_m2: float,
    diameter_m: float,
) -> float:
    """Solar heat gain per unit length (simplified, assuming perpendicular incidence).

    qs = alpha * Qse * D  [W/m]

    Solar incidence angle theta is assumed 90 deg (sin(theta) = 1.0) for
    conservative (maximum solar gain) rating. The solar_radiation_w_m2 input
    represents the total solar flux on a surface normal to the conductor.
    """
    return absorptivity * solar_radiation_w_m2 * diameter_m


def _resistance_at_temp(
    resistance_ohm_per_km_25c: float,
    conductor_temp_c: float,
) -> float:
    """AC resistance at conductor temperature using linear interpolation.

    R(T) = R(25) * [1 + alpha * (T - 25)]
    where alpha = 0.00403 /°C for aluminium (typical ACSR conductors).
    Returns ohm/m.
    """
    # Temperature coefficient of resistance for aluminium
    alpha_r = 0.00403
    r_per_m_25c = resistance_ohm_per_km_25c / 1000.0
    return r_per_m_25c * (1.0 + alpha_r * (conductor_temp_c - 25.0))


def _validate_inputs(
    conductor_diameter_mm: float,
    conductor_resistance_ohm_per_km: float,
    max_conductor_temp_c: float,
    ambient_temp_c: float,
    wind_speed_m_s: float,
    wind_angle_deg: float,
    solar_radiation_w_m2: float,
    emissivity: float,
    absorptivity: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if conductor_diameter_mm <= 0:
        msg = "conductor_diameter_mm must be > 0"
        raise ValueError(msg)
    if conductor_resistance_ohm_per_km <= 0:
        msg = "conductor_resistance_ohm_per_km must be > 0"
        raise ValueError(msg)
    if max_conductor_temp_c <= ambient_temp_c:
        msg = "max_conductor_temp_c must be > ambient_temp_c"
        raise ValueError(msg)
    if ambient_temp_c < -50 or ambient_temp_c > 60:
        msg = "ambient_temp_c must be between -50 and 60"
        raise ValueError(msg)
    if wind_speed_m_s < 0:
        msg = "wind_speed_m_s must be >= 0"
        raise ValueError(msg)
    if wind_angle_deg < 0 or wind_angle_deg > 90:
        msg = "wind_angle_deg must be between 0 and 90"
        raise ValueError(msg)
    if solar_radiation_w_m2 < 0:
        msg = "solar_radiation_w_m2 must be >= 0"
        raise ValueError(msg)
    if emissivity < 0 or emissivity > 1:
        msg = "emissivity must be between 0 and 1"
        raise ValueError(msg)
    if absorptivity < 0 or absorptivity > 1:
        msg = "absorptivity must be between 0 and 1"
        raise ValueError(msg)


def compute(
    conductor_diameter_mm: float,
    conductor_resistance_ohm_per_km: float,
    max_conductor_temp_c: float,
    ambient_temp_c: float,
    wind_speed_m_s: float,
    wind_angle_deg: float,
    solar_radiation_w_m2: float,
    emissivity: float = 0.5,
    absorptivity: float = 0.5,
) -> dict[str, float]:
    """Compute steady-state thermal rating (ampacity) per IEEE 738 heat balance.

    The heat balance at steady state is: qc + qr = qs + I^2*R
    Solving for current: I = sqrt((qc + qr - qs) / R)

    Returns a dict with keys: convective_cooling_w_m, radiative_cooling_w_m,
    solar_heat_gain_w_m, ampacity_a.
    """
    _validate_inputs(
        conductor_diameter_mm,
        conductor_resistance_ohm_per_km,
        max_conductor_temp_c,
        ambient_temp_c,
        wind_speed_m_s,
        wind_angle_deg,
        solar_radiation_w_m2,
        emissivity,
        absorptivity,
    )

    diameter_m = conductor_diameter_mm / 1000.0
    t_film = _film_temperature(max_conductor_temp_c, ambient_temp_c)

    # Air properties at film temperature
    rho_f = _air_density_kg_m3(t_film)
    mu_f = _air_dynamic_viscosity_pa_s(t_film)
    kf = _air_thermal_conductivity_w_m_k(t_film)

    # Heat balance components
    qc = _convective_cooling_w_m(
        diameter_m,
        max_conductor_temp_c,
        ambient_temp_c,
        wind_speed_m_s,
        wind_angle_deg,
        rho_f,
        mu_f,
        kf,
    )

    qr = _radiative_cooling_w_m(
        diameter_m,
        emissivity,
        max_conductor_temp_c,
        ambient_temp_c,
    )

    qs = _solar_heat_gain_w_m(
        absorptivity,
        solar_radiation_w_m2,
        diameter_m,
    )

    # AC resistance at maximum conductor temperature (ohm/m)
    r_ohm_m = _resistance_at_temp(
        conductor_resistance_ohm_per_km,
        max_conductor_temp_c,
    )

    # Ampacity from heat balance: I = sqrt((qc + qr - qs) / R)
    net_cooling = qc + qr - qs
    if net_cooling <= 0.0:
        ampacity = 0.0
    else:
        ampacity = math.sqrt(net_cooling / r_ohm_m)

    return {
        "convective_cooling_w_m": round(qc, 2),
        "radiative_cooling_w_m": round(qr, 2),
        "solar_heat_gain_w_m": round(qs, 2),
        "ampacity_a": round(ampacity, 2),
    }
