# ABOUTME: A-weighting computation engine for octave-band sound spectra.
# ABOUTME: Calculates linear and A-weighted total sound pressure levels.

import math

_A_WEIGHTING_DB: tuple[float, ...] = (
    -39.4,
    -26.2,
    -16.1,
    -8.6,
    -3.2,
    0.0,
    1.2,
    1.0,
)


def _validate_inputs(
    level_31_5_hz_db: float,
    level_63_hz_db: float,
    level_125_hz_db: float,
    level_250_hz_db: float,
    level_500_hz_db: float,
    level_1000_hz_db: float,
    level_2000_hz_db: float,
    level_4000_hz_db: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    levels = (
        level_31_5_hz_db,
        level_63_hz_db,
        level_125_hz_db,
        level_250_hz_db,
        level_500_hz_db,
        level_1000_hz_db,
        level_2000_hz_db,
        level_4000_hz_db,
    )
    for level in levels:
        if level < 0:
            msg = "octave band sound levels must be >= 0"
            raise ValueError(msg)


def _log_sum(levels: tuple[float, ...]) -> float:
    """Return the logarithmic sum of sound pressure levels in decibels."""
    return 10.0 * math.log10(sum(10.0 ** (level / 10.0) for level in levels))


def compute(
    level_31_5_hz_db: float,
    level_63_hz_db: float,
    level_125_hz_db: float,
    level_250_hz_db: float,
    level_500_hz_db: float,
    level_1000_hz_db: float,
    level_2000_hz_db: float,
    level_4000_hz_db: float,
) -> dict[str, float]:
    """Compute A-weighted total level from octave-band sound levels.

    Returns a dict with keys: total_linear_level_db, a_weighted_total_dba,
    a_weighting_adjustment_db.
    """
    _validate_inputs(
        level_31_5_hz_db,
        level_63_hz_db,
        level_125_hz_db,
        level_250_hz_db,
        level_500_hz_db,
        level_1000_hz_db,
        level_2000_hz_db,
        level_4000_hz_db,
    )

    levels = (
        level_31_5_hz_db,
        level_63_hz_db,
        level_125_hz_db,
        level_250_hz_db,
        level_500_hz_db,
        level_1000_hz_db,
        level_2000_hz_db,
        level_4000_hz_db,
    )
    weighted_levels = tuple(
        level + correction
        for level, correction in zip(
            levels,
            _A_WEIGHTING_DB,
            strict=True,
        )
    )
    total_linear = _log_sum(levels)
    total_weighted = _log_sum(weighted_levels)

    return {
        "total_linear_level_db": round(total_linear, 2),
        "a_weighted_total_dba": round(total_weighted, 2),
        "a_weighting_adjustment_db": round(total_weighted - total_linear, 2),
    }
