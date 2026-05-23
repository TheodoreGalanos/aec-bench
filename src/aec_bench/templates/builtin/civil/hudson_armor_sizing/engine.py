# ABOUTME: Hudson (1959) armor stone sizing computation engine.
# ABOUTME: Calculates required median armor weight and nominal diameter for breakwater stability.

import math


def _validate_inputs(
    design_wave_height_m: float,
    rock_density_kg_m3: float,
    water_density_kg_m3: float,
    slope_angle_deg: float,
    stability_coefficient_kd: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if design_wave_height_m <= 0:
        msg = "design_wave_height_m must be > 0"
        raise ValueError(msg)
    if rock_density_kg_m3 <= 0:
        msg = "rock_density_kg_m3 must be > 0"
        raise ValueError(msg)
    if water_density_kg_m3 <= 0:
        msg = "water_density_kg_m3 must be > 0"
        raise ValueError(msg)
    if rock_density_kg_m3 <= water_density_kg_m3:
        msg = "rock_density_kg_m3 must be > water_density_kg_m3 (armor must be denser than water)"
        raise ValueError(msg)
    if slope_angle_deg <= 0:
        msg = "slope_angle_deg must be > 0"
        raise ValueError(msg)
    if slope_angle_deg >= 90:
        msg = "slope_angle_deg must be < 90"
        raise ValueError(msg)
    if stability_coefficient_kd <= 0:
        msg = "stability_coefficient_kd must be > 0"
        raise ValueError(msg)


def compute(
    design_wave_height_m: float,
    rock_density_kg_m3: float,
    water_density_kg_m3: float,
    slope_angle_deg: float,
    stability_coefficient_kd: float,
) -> dict[str, float]:
    """Compute armor stone weight and nominal diameter using Hudson's equation.

    Hudson's formula (USACE CEM / CIRIA C683):
        W = (rho_r * H^3) / (KD * (Sr - 1)^3 * cot(alpha))

    where:
        W     = median armor unit weight (kg)
        rho_r = rock density (kg/m^3)
        H     = design wave height (m)
        KD    = stability coefficient (dimensionless)
        Sr    = rho_r / rho_w (specific gravity of rock)
        alpha = slope angle from horizontal (degrees)

    Nominal diameter:
        Dn50 = (W / rho_r)^(1/3)

    Returns a dict with keys: specific_gravity_sr, armor_weight_tonnes,
    nominal_diameter_m.
    """
    _validate_inputs(
        design_wave_height_m,
        rock_density_kg_m3,
        water_density_kg_m3,
        slope_angle_deg,
        stability_coefficient_kd,
    )

    # Specific gravity of rock relative to water
    sr = rock_density_kg_m3 / water_density_kg_m3

    # Slope angle in radians for cot(alpha) calculation
    alpha_rad = math.radians(slope_angle_deg)
    cot_alpha = math.cos(alpha_rad) / math.sin(alpha_rad)

    # Hudson's equation: W = rho_r * H^3 / (KD * (Sr - 1)^3 * cot(alpha))
    # Result in kg
    w_kg = (rock_density_kg_m3 * design_wave_height_m**3) / (stability_coefficient_kd * (sr - 1.0) ** 3 * cot_alpha)

    # Convert to tonnes (1 tonne = 1000 kg)
    w_tonnes = w_kg / 1000.0

    # Nominal diameter: Dn50 = (W / rho_r)^(1/3)
    dn50_m = (w_kg / rock_density_kg_m3) ** (1.0 / 3.0)

    return {
        "specific_gravity_sr": round(sr, 2),
        "armor_weight_tonnes": round(w_tonnes, 2),
        "nominal_diameter_m": round(dn50_m, 2),
    }
