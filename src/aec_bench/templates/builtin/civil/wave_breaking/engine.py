# ABOUTME: Wave breaking criteria computation engine based on USACE Coastal Engineering Manual.
# ABOUTME: Calculates breaking wave height, breaking depth, breaker type, and Iribarren number.

import math

# Gravity constant (m/s^2)
_G = 9.81

# Breaker type encoding for numeric output
_BREAKER_TYPE_SPILLING = 1.0
_BREAKER_TYPE_PLUNGING = 2.0
_BREAKER_TYPE_SURGING = 3.0


def _breaker_depth_index(bottom_slope: float) -> float:
    """Calculate breaker depth index gamma_b using Weggel (1972) simplified relation.

    gamma_b = 1.56 / (1 + exp(-19.5 * m))

    where m is the bottom slope. On a flat bottom (m -> 0), gamma_b -> 0.78,
    recovering McCowan's solitary wave limit. On steep slopes gamma_b increases
    toward 1.56.
    """
    return 1.56 / (1.0 + math.exp(-19.5 * bottom_slope))


def _deep_water_wavelength(wave_period_s: float) -> float:
    """Calculate deep-water wavelength L_0 = g * T^2 / (2 * pi)."""
    return _G * wave_period_s**2 / (2.0 * math.pi)


def _iribarren_number(
    bottom_slope: float,
    wave_height_m: float,
    deep_water_wavelength_m: float,
) -> float:
    """Calculate Iribarren number (surf similarity parameter).

    xi = m / sqrt(H_0 / L_0)

    where m is the bottom slope, H_0 is the incident (deep-water) wave height,
    and L_0 is the deep-water wavelength.
    """
    steepness = wave_height_m / deep_water_wavelength_m
    return bottom_slope / math.sqrt(steepness)


def _classify_breaker(iribarren: float) -> float:
    """Classify breaker type from Iribarren number.

    Returns encoded float:
      1.0 = spilling  (xi < 0.5)
      2.0 = plunging  (0.5 <= xi < 3.3)
      3.0 = surging   (xi >= 3.3)
    """
    if iribarren < 0.5:
        return _BREAKER_TYPE_SPILLING
    if iribarren < 3.3:
        return _BREAKER_TYPE_PLUNGING
    return _BREAKER_TYPE_SURGING


def _validate_inputs(
    wave_height_m: float,
    wave_period_s: float,
    water_depth_m: float,
    bottom_slope: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if wave_height_m <= 0:
        msg = "wave_height_m must be > 0"
        raise ValueError(msg)
    if wave_period_s <= 0:
        msg = "wave_period_s must be > 0"
        raise ValueError(msg)
    if water_depth_m <= 0:
        msg = "water_depth_m must be > 0"
        raise ValueError(msg)
    if bottom_slope <= 0:
        msg = "bottom_slope must be > 0"
        raise ValueError(msg)
    if bottom_slope >= 1.0:
        msg = "bottom_slope must be < 1.0 (rise/run ratio)"
        raise ValueError(msg)


def compute(
    wave_height_m: float,
    wave_period_s: float,
    water_depth_m: float,
    bottom_slope: float,
) -> dict[str, float]:
    """Compute wave breaking parameters using USACE CEM methods.

    Approach:
    1. Calculate breaker depth index gamma_b from bottom slope (Weggel 1972).
    2. Determine depth-limited breaking wave height H_b = gamma_b * d
       where d is the given water depth (the wave breaks when depth limits it).
    3. Calculate breaking depth d_b = H_b / gamma_b.
    4. Calculate Iribarren number from incident wave height and deep-water wavelength.
    5. Classify breaker type (spilling / plunging / surging).

    Returns a dict with keys: breaking_wave_height_m, breaking_depth_m,
    breaker_type, iribarren_number.
    """
    _validate_inputs(wave_height_m, wave_period_s, water_depth_m, bottom_slope)

    # Breaker depth index depends on bottom slope
    gamma_b = _breaker_depth_index(bottom_slope)

    # Depth-limited breaking wave height at the given water depth
    h_b = gamma_b * water_depth_m

    # Breaking depth (consistent with gamma_b definition: d_b = H_b / gamma_b)
    d_b = h_b / gamma_b

    # Deep-water wavelength for Iribarren number calculation
    l_0 = _deep_water_wavelength(wave_period_s)

    # Iribarren number uses incident wave height and deep-water wavelength
    xi = _iribarren_number(bottom_slope, wave_height_m, l_0)

    # Classify breaker type from Iribarren number
    breaker_type = _classify_breaker(xi)

    return {
        "breaking_wave_height_m": round(h_b, 2),
        "breaking_depth_m": round(d_b, 2),
        "breaker_type": round(breaker_type, 2),
        "iribarren_number": round(xi, 2),
    }
