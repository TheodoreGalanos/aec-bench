# ABOUTME: Vibration transmissibility computation engine for isolation checks.
# ABOUTME: Calculates frequency ratio, transmissibility, and isolation efficiency.

import math


def _validate_inputs(
    forcing_frequency_hz: float,
    natural_frequency_hz: float,
    damping_ratio: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if forcing_frequency_hz <= 0:
        msg = "forcing_frequency_hz must be > 0"
        raise ValueError(msg)
    if natural_frequency_hz <= 0:
        msg = "natural_frequency_hz must be > 0"
        raise ValueError(msg)
    if damping_ratio < 0:
        msg = "damping_ratio must be >= 0"
        raise ValueError(msg)


def compute(
    forcing_frequency_hz: float,
    natural_frequency_hz: float,
    damping_ratio: float,
) -> dict[str, float]:
    """Compute force transmissibility for a damped single-degree isolator.

    Returns a dict with keys: frequency_ratio, transmissibility,
    isolation_efficiency_pct.
    """
    _validate_inputs(forcing_frequency_hz, natural_frequency_hz, damping_ratio)

    frequency_ratio = forcing_frequency_hz / natural_frequency_hz
    damping_term = 2.0 * damping_ratio * frequency_ratio
    numerator = math.sqrt(1.0 + damping_term**2)
    denominator = math.sqrt((1.0 - frequency_ratio**2) ** 2 + damping_term**2)
    transmissibility = numerator / denominator
    isolation_efficiency = (1.0 - transmissibility) * 100.0

    return {
        "frequency_ratio": round(frequency_ratio, 2),
        "transmissibility": round(transmissibility, 3),
        "isolation_efficiency_pct": round(isolation_efficiency, 2),
    }
