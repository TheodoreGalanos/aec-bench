# ABOUTME: Wave shoaling and refraction computation engine based on USACE Coastal Engineering Manual.
# ABOUTME: Calculates shoaling, refraction, and nearshore wave height with an explicit wavelength method.

import math

# Gravity constant (m/s^2)
_G = 9.81


def _deep_water_wavelength(wave_period_s: float) -> float:
    """Calculate deep-water wavelength L_0 = g * T^2 / (2 * pi)."""
    return _G * wave_period_s**2 / (2.0 * math.pi)


def _fenton_mckee_kd(sigma: float, depth_m: float) -> float:
    """Calculate kd using the Fenton & McKee (1990) explicit approximation.

    kd = (sigma^2 * d / g) * [coth((sigma^2 * d / g)^(3/4))]^(2/3)

    This avoids iterative solution of the dispersion relation and gives
    less than 1.5% error compared to the full implicit solution.
    """
    sigma2_d_over_g = sigma**2 * depth_m / _G
    # coth(x) = cosh(x) / sinh(x) = 1 / tanh(x)
    coth_term = 1.0 / math.tanh(sigma2_d_over_g**0.75)
    return sigma2_d_over_g * coth_term ** (2.0 / 3.0)


def _group_velocity_ratio(kd: float) -> float:
    """Calculate n = 0.5 * (1 + 2*kd / sinh(2*kd)).

    The ratio of group velocity to phase velocity in intermediate water.
    """
    return 0.5 * (1.0 + 2.0 * kd / math.sinh(2.0 * kd))


def _shoaling_coefficient(
    deep_water_group_velocity: float,
    local_group_velocity: float,
) -> float:
    """Calculate shoaling coefficient K_s = sqrt(C_g0 / C_g)."""
    return math.sqrt(deep_water_group_velocity / local_group_velocity)


def _refraction_coefficient(
    deep_water_angle_rad: float,
    local_angle_rad: float,
) -> float:
    """Calculate refraction coefficient K_r = sqrt(cos(theta_0) / cos(theta))."""
    return math.sqrt(math.cos(deep_water_angle_rad) / math.cos(local_angle_rad))


def _snells_law_local_angle(
    deep_water_angle_rad: float,
    deep_water_celerity: float,
    local_celerity: float,
) -> float:
    """Apply Snell's law to find local wave angle.

    sin(theta) / C = sin(theta_0) / C_0
    => sin(theta) = sin(theta_0) * C / C_0
    """
    sin_theta = math.sin(deep_water_angle_rad) * local_celerity / deep_water_celerity
    # Clamp to [-1, 1] to avoid domain errors from floating point
    sin_theta = max(-1.0, min(1.0, sin_theta))
    return math.asin(sin_theta)


def _validate_inputs(
    deep_water_wave_height_m: float,
    wave_period_s: float,
    nearshore_depth_m: float,
    deep_water_wave_angle_deg: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if deep_water_wave_height_m <= 0:
        msg = "deep_water_wave_height_m must be > 0"
        raise ValueError(msg)
    if wave_period_s <= 0:
        msg = "wave_period_s must be > 0"
        raise ValueError(msg)
    if nearshore_depth_m <= 0:
        msg = "nearshore_depth_m must be > 0"
        raise ValueError(msg)
    if deep_water_wave_angle_deg < 0:
        msg = "deep_water_wave_angle_deg must be >= 0"
        raise ValueError(msg)
    if deep_water_wave_angle_deg >= 90:
        msg = "deep_water_wave_angle_deg must be < 90"
        raise ValueError(msg)


def compute(
    deep_water_wave_height_m: float,
    wave_period_s: float,
    nearshore_depth_m: float,
    deep_water_wave_angle_deg: float,
) -> dict[str, float]:
    """Compute wave shoaling and refraction using USACE CEM methods.

    Approach:
    1. Calculate deep-water wavelength L_0 and deep-water phase celerity C_0.
    2. Use Fenton & McKee (1990) explicit approximation to solve for kd
       without iteration.
    3. Derive local wavelength L, wavenumber k, phase celerity C, and
       group velocity C_g from kd.
    4. Calculate deep-water group velocity C_g0 = g*T/(4*pi).
    5. Shoaling coefficient K_s = sqrt(C_g0 / C_g).
    6. Apply Snell's law for refraction angle, then K_r = sqrt(cos(theta_0)/cos(theta)).
    7. Nearshore wave height H = H_0 * K_s * K_r.

    Returns a dict with keys: shoaling_coefficient, refraction_coefficient,
    nearshore_wave_height_m.
    """
    _validate_inputs(
        deep_water_wave_height_m,
        wave_period_s,
        nearshore_depth_m,
        deep_water_wave_angle_deg,
    )

    # Angular frequency
    sigma = 2.0 * math.pi / wave_period_s

    # Deep-water wavelength and celerity
    l_0 = _deep_water_wavelength(wave_period_s)
    c_0 = l_0 / wave_period_s  # deep-water phase celerity

    # Deep-water group velocity
    c_g0 = _G * wave_period_s / (4.0 * math.pi)

    # Local wave parameters via Fenton & McKee approximation
    kd = _fenton_mckee_kd(sigma, nearshore_depth_m)
    k = kd / nearshore_depth_m
    local_wavelength = 2.0 * math.pi / k
    c = local_wavelength / wave_period_s  # local phase celerity

    # Group velocity ratio and local group velocity
    n = _group_velocity_ratio(kd)
    c_g = n * c

    # Shoaling coefficient
    k_s = _shoaling_coefficient(c_g0, c_g)

    # Refraction via Snell's law
    theta_0_rad = math.radians(deep_water_wave_angle_deg)
    theta_rad = _snells_law_local_angle(theta_0_rad, c_0, c)
    k_r = _refraction_coefficient(theta_0_rad, theta_rad)

    # Nearshore wave height
    h_nearshore = deep_water_wave_height_m * k_s * k_r

    return {
        "shoaling_coefficient": round(k_s, 2),
        "refraction_coefficient": round(k_r, 2),
        "nearshore_wave_height_m": round(h_nearshore, 2),
    }
