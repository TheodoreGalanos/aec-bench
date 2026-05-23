# ABOUTME: Steel critical temperature computation engine for structural fire checks.
# ABOUTME: Calculates critical steel temperature from explicit load ratio inputs.

import math


def _validate_inputs(
    load_ratio: float,
    protection_trigger_c: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if load_ratio <= 0:
        msg = "load_ratio must be > 0"
        raise ValueError(msg)
    if load_ratio >= 1.0:
        msg = "load_ratio must be < 1.0"
        raise ValueError(msg)
    if protection_trigger_c <= 0:
        msg = "protection_trigger_c must be > 0"
        raise ValueError(msg)


def compute(
    load_ratio: float,
    protection_trigger_c: float,
) -> dict[str, float]:
    """Compute critical steel temperature from member load ratio.

    Returns a dict with keys: critical_temperature_c, protection_margin_c,
    protection_required.
    """
    _validate_inputs(load_ratio, protection_trigger_c)

    denominator = 0.9674 * load_ratio**3.833
    critical_temperature = 39.19 * math.log((1.0 / denominator) - 1.0) + 482.0
    protection_margin = critical_temperature - protection_trigger_c
    protection_required = 1.0 if critical_temperature < protection_trigger_c else 0.0

    return {
        "critical_temperature_c": round(critical_temperature, 2),
        "protection_margin_c": round(protection_margin, 2),
        "protection_required": round(protection_required, 2),
    }
