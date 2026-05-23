# ABOUTME: EurOtop (2018) wave runup computation engine using the TAW formula.
# ABOUTME: Calculates breaker parameter, 2% exceedance runup height, and wave regime classification.

import math

# Gravitational acceleration (m/s^2)
_G = 9.81

# Wave regime encoding for numeric output
_REGIME_BREAKING = 1.0
_REGIME_SURGING = 2.0


def _spectral_wavelength(wave_period_s: float) -> float:
    """Calculate spectral deep-water wavelength L_m-1,0 = g * T_m-1,0^2 / (2 * pi)."""
    return _G * wave_period_s**2 / (2.0 * math.pi)


def _breaker_parameter(
    structure_slope: float,
    wave_height_m: float,
    wavelength_m: float,
) -> float:
    """Calculate Iribarren-type breaker parameter xi_m-1,0.

    xi_m-1,0 = tan(alpha) / sqrt(H_m0 / L_m-1,0)

    where tan(alpha) is the structure slope expressed as a ratio (e.g. 0.33 for 1:3)
    and H_m0 / L_m-1,0 is the fictitious wave steepness.
    """
    steepness = wave_height_m / wavelength_m
    return structure_slope / math.sqrt(steepness)


def _runup_breaking(
    xi: float,
    gamma_b: float,
    gamma_f: float,
) -> float:
    """Dimensionless runup for breaking (plunging) waves.

    Ru2% / H_m0 = 1.65 * gamma_b * gamma_f * gamma_beta * xi_m-1,0

    gamma_beta is taken as 1.0 (head-on wave attack).
    """
    gamma_beta = 1.0
    return 1.65 * gamma_b * gamma_f * gamma_beta * xi


def _runup_surging(
    xi: float,
    gamma_f: float,
) -> float:
    """Dimensionless runup maximum for surging (non-breaking) waves.

    Ru2% / H_m0 = 1.0 * gamma_f * gamma_beta * (4.0 - 1.5 / sqrt(xi_m-1,0))

    gamma_beta is taken as 1.0 (head-on wave attack).
    """
    gamma_beta = 1.0
    return 1.0 * gamma_f * gamma_beta * (4.0 - 1.5 / math.sqrt(xi))


def _validate_inputs(
    wave_height_m: float,
    wave_period_s: float,
    structure_slope: float,
    roughness_factor: float,
    berm_factor: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if wave_height_m <= 0:
        msg = "wave_height_m must be > 0"
        raise ValueError(msg)
    if wave_period_s <= 0:
        msg = "wave_period_s must be > 0"
        raise ValueError(msg)
    if structure_slope <= 0:
        msg = "structure_slope must be > 0"
        raise ValueError(msg)
    if structure_slope >= 1.0:
        msg = "structure_slope must be < 1.0 (tan alpha, e.g. 0.33 for 1:3)"
        raise ValueError(msg)
    if roughness_factor <= 0 or roughness_factor > 1.0:
        msg = "roughness_factor must be in (0, 1.0]"
        raise ValueError(msg)
    if berm_factor <= 0 or berm_factor > 1.0:
        msg = "berm_factor must be in (0, 1.0]"
        raise ValueError(msg)


def compute(
    wave_height_m: float,
    wave_period_s: float,
    structure_slope: float,
    roughness_factor: float,
    berm_factor: float,
) -> dict[str, float]:
    """Compute 2% exceedance wave runup using EurOtop (2018) TAW formula.

    Procedure:
    1. Calculate spectral wavelength L_m-1,0 = g * T^2 / (2*pi).
    2. Calculate breaker parameter xi_m-1,0 = tan(alpha) / sqrt(H_m0 / L_m-1,0).
    3. Evaluate both runup expressions and take the minimum:
       - Breaking:  Ru2%/H_m0 = 1.65 * gamma_b * gamma_f * gamma_beta * xi
       - Maximum:   Ru2%/H_m0 = gamma_f * gamma_beta * (4.0 - 1.5 / sqrt(xi))
    4. Ru2% = (Ru2%/H_m0) * H_m0.
    5. Classify regime: breaking (1.0) if the breaking expression governs,
       surging/non-breaking (2.0) if the maximum expression governs.

    Returns a dict with keys: breaker_parameter, runup_height_m, regime.
    """
    _validate_inputs(
        wave_height_m,
        wave_period_s,
        structure_slope,
        roughness_factor,
        berm_factor,
    )

    # Spectral deep-water wavelength
    l_m = _spectral_wavelength(wave_period_s)

    # Breaker parameter (Iribarren-type)
    xi = _breaker_parameter(structure_slope, wave_height_m, l_m)

    # Dimensionless runup from both expressions
    ru_breaking = _runup_breaking(xi, berm_factor, roughness_factor)
    ru_surging = _runup_surging(xi, roughness_factor)

    # EurOtop: take the minimum of the two expressions
    if ru_breaking <= ru_surging:
        ru_ratio = ru_breaking
        regime = _REGIME_BREAKING
    else:
        ru_ratio = ru_surging
        regime = _REGIME_SURGING

    # Dimensional runup height
    ru2_percent = ru_ratio * wave_height_m

    return {
        "breaker_parameter": round(xi, 2),
        "runup_height_m": round(ru2_percent, 2),
        "regime": round(regime, 2),
    }
