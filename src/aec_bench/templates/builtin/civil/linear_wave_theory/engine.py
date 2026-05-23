# ABOUTME: Linear (Airy) wave theory computation engine based on USACE CEM Part II Chapter 1.
# ABOUTME: Solves the dispersion relation via Newton-Raphson to compute wavelength, celerity, and group velocity.

import math

# Gravitational acceleration (m/s^2)
_G = 9.81


def _validate_inputs(
    wave_period_s: float,
    water_depth_m: float,
    wave_height_m: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if wave_period_s <= 0:
        msg = "wave_period_s must be > 0"
        raise ValueError(msg)
    if water_depth_m <= 0:
        msg = "water_depth_m must be > 0"
        raise ValueError(msg)
    if wave_height_m <= 0:
        msg = "wave_height_m must be > 0"
        raise ValueError(msg)


def _solve_dispersion(wave_period_s: float, water_depth_m: float) -> float:
    """Solve the linear wave dispersion relation for wavelength L.

    The dispersion relation is:
        L = (g * T^2 / (2 * pi)) * tanh(2 * pi * d / L)

    This is transcendental (L appears on both sides). We solve iteratively
    using Newton-Raphson on f(L) = L - (g*T^2/(2*pi)) * tanh(2*pi*d/L).

    The derivative is:
        f'(L) = 1 + (g*T^2*d / L^2) * (2*pi / cosh^2(2*pi*d/L))

    which simplifies to:
        f'(L) = 1 + (2*pi*d/L^2) * (g*T^2/(2*pi)) / cosh^2(2*pi*d/L)

    Starting from the deep-water wavelength L_0 = g*T^2 / (2*pi),
    this converges in 5-10 iterations for any water depth.
    """
    two_pi = 2.0 * math.pi

    # Deep-water wavelength as initial guess
    l_0 = _G * wave_period_s**2 / two_pi
    l_n = l_0

    for _ in range(50):
        kd = two_pi * water_depth_m / l_n
        tanh_kd = math.tanh(kd)
        cosh_kd = math.cosh(kd)

        # f(L) = L - L_0 * tanh(2*pi*d/L)
        f_val = l_n - l_0 * tanh_kd

        # f'(L) = 1 + L_0 * (2*pi*d / L^2) / cosh^2(2*pi*d/L)
        f_prime = 1.0 + l_0 * (two_pi * water_depth_m / (l_n**2)) / (cosh_kd**2)

        l_next = l_n - f_val / f_prime

        if abs(l_next - l_n) < 1e-10:
            return l_next

        l_n = l_next

    return l_n


def compute(
    wave_period_s: float,
    water_depth_m: float,
    wave_height_m: float,
) -> dict[str, float]:
    """Compute wave properties using linear (Airy) wave theory.

    Solves the dispersion relation via Newton-Raphson iteration, then derives
    wave celerity, group velocity, wave steepness, and relative depth.

    Dispersion relation (USACE CEM II-1-8):
        L = (g * T^2 / (2*pi)) * tanh(2*pi*d / L)

    Wave celerity:
        C = L / T

    Group velocity:
        C_g = n * C
        where n = 0.5 * (1 + 2*k*d / sinh(2*k*d))
        and k = 2*pi / L

    Wave steepness:
        S = H / L

    Relative depth (d/L) indicates the water depth regime:
        d/L > 0.5    -> deep water
        d/L < 0.05   -> shallow water
        0.05 <= d/L <= 0.5 -> intermediate

    Returns a dict with keys: wavelength_m, wave_celerity_m_per_s,
    group_velocity_m_per_s, wave_steepness, relative_depth.
    """
    _validate_inputs(wave_period_s, water_depth_m, wave_height_m)

    # Solve dispersion relation for wavelength
    wavelength = _solve_dispersion(wave_period_s, water_depth_m)

    # Wave celerity (phase velocity)
    celerity = wavelength / wave_period_s

    # Wavenumber
    k = 2.0 * math.pi / wavelength
    kd = k * water_depth_m

    # Group velocity ratio n = 0.5 * (1 + 2kd / sinh(2kd))
    n = 0.5 * (1.0 + 2.0 * kd / math.sinh(2.0 * kd))

    # Group velocity
    group_velocity = n * celerity

    # Wave steepness
    steepness = wave_height_m / wavelength

    # Relative depth
    relative_depth = water_depth_m / wavelength

    return {
        "wavelength_m": round(wavelength, 2),
        "wave_celerity_m_per_s": round(celerity, 2),
        "group_velocity_m_per_s": round(group_velocity, 2),
        "wave_steepness": round(steepness, 4),
        "relative_depth": round(relative_depth, 4),
    }
