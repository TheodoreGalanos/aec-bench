# ABOUTME: Bracket load computation engine for reduced structural checks.
# ABOUTME: Applies explicit factors to vertical and lateral bracket actions.

import math


def _validate_inputs(*values: float) -> None:
    """Raise ValueError for invalid input parameters."""
    for value in values:
        if value < 0:
            msg = "loads and factors must be >= 0"
            raise ValueError(msg)


def compute(
    dead_load_kn: float,
    live_load_kn: float,
    wind_load_kn: float,
    dead_load_factor: float,
    live_load_factor: float,
    wind_load_factor: float,
) -> dict[str, float]:
    """Compute reduced factored bracket load resultants.

    Returns a dict with keys: service_vertical_load_kn, factored_vertical_load_kn,
    factored_lateral_load_kn, factored_resultant_load_kn.
    """
    _validate_inputs(
        dead_load_kn,
        live_load_kn,
        wind_load_kn,
        dead_load_factor,
        live_load_factor,
        wind_load_factor,
    )

    service_vertical = dead_load_kn + live_load_kn
    factored_vertical = dead_load_factor * dead_load_kn + live_load_factor * live_load_kn
    factored_lateral = wind_load_factor * wind_load_kn
    resultant = math.hypot(factored_vertical, factored_lateral)

    return {
        "service_vertical_load_kn": round(service_vertical, 2),
        "factored_vertical_load_kn": round(factored_vertical, 2),
        "factored_lateral_load_kn": round(factored_lateral, 2),
        "factored_resultant_load_kn": round(resultant, 2),
    }
