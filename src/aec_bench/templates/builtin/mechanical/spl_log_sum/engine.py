# ABOUTME: Sound pressure level logarithmic summation engine.
# ABOUTME: Calculates combined SPL from three independent source levels.

import math


def _validate_inputs(source_1_spl_db: float, source_2_spl_db: float, source_3_spl_db: float) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "source_1_spl_db": source_1_spl_db,
        "source_2_spl_db": source_2_spl_db,
        "source_3_spl_db": source_3_spl_db,
    }.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)


def compute(
    source_1_spl_db: float,
    source_2_spl_db: float,
    source_3_spl_db: float,
) -> dict[str, float]:
    """Compute total SPL by logarithmic addition of three sources.

    Returns a dict with keys: total_linear_energy, combined_spl_db,
    dominant_source_spl_db.
    """
    _validate_inputs(source_1_spl_db, source_2_spl_db, source_3_spl_db)

    linear_energy = (
        10.0 ** (source_1_spl_db / 10.0) + 10.0 ** (source_2_spl_db / 10.0) + 10.0 ** (source_3_spl_db / 10.0)
    )
    combined_spl = 10.0 * math.log10(linear_energy)
    dominant_source = max(source_1_spl_db, source_2_spl_db, source_3_spl_db)

    return {
        "total_linear_energy": round(linear_energy, 2),
        "combined_spl_db": round(combined_spl, 2),
        "dominant_source_spl_db": round(dominant_source, 2),
    }
