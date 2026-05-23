# ABOUTME: CERC longshore sediment transport computation engine.
# ABOUTME: Calculates volumetric transport rate Q_l using the CERC formula from USACE CEM / Shore Protection Manual.

import math

# Gravitational acceleration (m/s^2).
_G = 9.81

# Seconds per year (365.25 days).
_SECONDS_PER_YEAR = 365.25 * 24.0 * 3600.0

# Default breaker index gamma_b (ratio H_b / d_b).
_GAMMA_B = 0.78


def _validate_inputs(
    breaking_wave_height_m: float,
    wave_angle_at_breaking_deg: float,
    k_coefficient: float,
    sediment_density_kg_m3: float,
    water_density_kg_m3: float,
    porosity: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if breaking_wave_height_m <= 0:
        msg = "breaking_wave_height_m must be > 0"
        raise ValueError(msg)
    if wave_angle_at_breaking_deg < -90 or wave_angle_at_breaking_deg > 90:
        msg = "wave_angle_at_breaking_deg must be between -90 and 90"
        raise ValueError(msg)
    if wave_angle_at_breaking_deg == 0:
        msg = "wave_angle_at_breaking_deg must be non-zero (zero angle produces zero transport)"
        raise ValueError(msg)
    if k_coefficient <= 0:
        msg = "k_coefficient must be > 0"
        raise ValueError(msg)
    if sediment_density_kg_m3 <= 0:
        msg = "sediment_density_kg_m3 must be > 0"
        raise ValueError(msg)
    if water_density_kg_m3 <= 0:
        msg = "water_density_kg_m3 must be > 0"
        raise ValueError(msg)
    if sediment_density_kg_m3 <= water_density_kg_m3:
        msg = "sediment_density_kg_m3 must be > water_density_kg_m3"
        raise ValueError(msg)
    if porosity < 0 or porosity >= 1:
        msg = "porosity must be >= 0 and < 1"
        raise ValueError(msg)


def compute(
    breaking_wave_height_m: float,
    wave_angle_at_breaking_deg: float,
    k_coefficient: float,
    sediment_density_kg_m3: float = 2650.0,
    water_density_kg_m3: float = 1025.0,
    porosity: float = 0.4,
) -> dict[str, float]:
    """Compute longshore sediment transport rate using the CERC formula.

    CERC formula (USACE CEM / Shore Protection Manual):
        I_l = K * (E * C_g)_b * sin(2 * alpha_b) / 2
        Q_l = I_l / ((rho_s - rho_w) * g * (1 - p))

    where:
        (E * C_g)_b = rho_w * g * H_b^2 * C_gb / 8    (wave energy flux at breaking)
        C_gb = sqrt(g * d_b)                             (shallow water group velocity)
        d_b = H_b / gamma_b                              (breaking depth, gamma_b ~ 0.78)

    Returns a dict with keys: energy_flux_w_m, transport_rate_m3_yr,
    transport_direction.
    """
    _validate_inputs(
        breaking_wave_height_m,
        wave_angle_at_breaking_deg,
        k_coefficient,
        sediment_density_kg_m3,
        water_density_kg_m3,
        porosity,
    )

    h_b = breaking_wave_height_m
    alpha_b_rad = math.radians(wave_angle_at_breaking_deg)

    # Breaking depth from breaker index: d_b = H_b / gamma_b
    d_b = h_b / _GAMMA_B

    # Shallow water group velocity at breaking: C_gb = sqrt(g * d_b)
    c_gb = math.sqrt(_G * d_b)

    # Wave energy flux at breaking: (E * C_g)_b = rho_w * g * H_b^2 * C_gb / 8
    energy_flux = water_density_kg_m3 * _G * h_b**2 * c_gb / 8.0

    # Immersed weight transport rate: I_l = K * P_ls
    # where P_ls = (E * C_g)_b * sin(2 * alpha_b) / 2
    p_ls = energy_flux * math.sin(2.0 * alpha_b_rad) / 2.0
    i_l = k_coefficient * p_ls

    # Volumetric transport rate: Q_l = I_l / ((rho_s - rho_w) * g * (1 - p))
    q_l_m3_s = i_l / ((sediment_density_kg_m3 - water_density_kg_m3) * _G * (1.0 - porosity))

    # Convert from m^3/s to m^3/year
    q_l_m3_yr = q_l_m3_s * _SECONDS_PER_YEAR

    # Transport direction: positive alpha_b = left-to-right looking shoreward
    direction = 1.0 if wave_angle_at_breaking_deg > 0 else -1.0

    return {
        "energy_flux_w_m": round(energy_flux, 2),
        "transport_rate_m3_yr": round(abs(q_l_m3_yr), 2),
        "transport_direction": round(direction, 2),
    }
