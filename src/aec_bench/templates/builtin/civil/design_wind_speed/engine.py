# ABOUTME: Design wind speed computation engine per AS/NZS 1170.2 Section 2.2.
# ABOUTME: Calculates site wind speed V_sit,beta from regional speed and multipliers.

from typing import Literal

# Table 4.1(A) from AS/NZS 1170.2 — terrain/height multiplier M_z,cat.
# Heights in metres; values for terrain categories 1, 2, 2.5, 3, 4.
# Heights below 3 m use the 3 m row (standard minimum).
# TC 2.5 values from the 2021 edition interpolate between TC2 and TC3.
_MZCAT_TABLE: list[tuple[float, float, float, float, float, float]] = [
    # (height_m, TC1,  TC2,  TC2.5, TC3,  TC4)
    (3, 0.99, 0.91, 0.87, 0.83, 0.75),
    (5, 1.05, 0.91, 0.87, 0.83, 0.75),
    (10, 1.12, 1.00, 0.92, 0.83, 0.75),
    (15, 1.16, 1.05, 0.97, 0.89, 0.75),
    (20, 1.19, 1.08, 1.01, 0.94, 0.75),
    (25, 1.22, 1.10, 1.04, 0.98, 0.75),
    (30, 1.24, 1.12, 1.06, 1.00, 0.80),
    (40, 1.24, 1.16, 1.10, 1.04, 0.85),
    (50, 1.25, 1.18, 1.13, 1.07, 0.90),
    (75, 1.27, 1.22, 1.17, 1.12, 0.98),
    (100, 1.29, 1.24, 1.20, 1.16, 1.03),
    (150, 1.31, 1.27, 1.24, 1.21, 1.11),
    (200, 1.32, 1.29, 1.27, 1.24, 1.16),
]

# Map terrain category string to column index in the table.
_TC_COLUMN: dict[str, int] = {
    "1": 1,
    "2": 2,
    "2.5": 3,
    "3": 4,
    "4": 5,
}


def _interpolate_mzcat(height_m: float, terrain_category: str) -> float:
    """Linearly interpolate M_z,cat from Table 4.1(A).

    For heights below 3 m the 3 m row is used (standard minimum).
    For heights above 200 m the 200 m row is used (standard maximum).
    """
    col = _TC_COLUMN[terrain_category]

    # Clamp height to table bounds
    clamped_h = max(3.0, min(200.0, height_m))

    # Find bracketing rows
    for i in range(len(_MZCAT_TABLE) - 1):
        h_lo, *_ = _MZCAT_TABLE[i]
        h_hi, *_ = _MZCAT_TABLE[i + 1]
        if h_lo <= clamped_h <= h_hi:
            val_lo = _MZCAT_TABLE[i][col]
            val_hi = _MZCAT_TABLE[i + 1][col]
            if h_hi == h_lo:
                return val_lo
            fraction = (clamped_h - h_lo) / (h_hi - h_lo)
            return val_lo + fraction * (val_hi - val_lo)

    # Exact match at last row
    return _MZCAT_TABLE[-1][col]


def _validate_inputs(
    regional_wind_speed_m_per_s: float,
    terrain_category: str,
    building_height_m: float,
    topographic_multiplier: float,
    shielding_multiplier: float,
    wind_direction_multiplier: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if regional_wind_speed_m_per_s <= 0:
        msg = "regional_wind_speed_m_per_s must be > 0"
        raise ValueError(msg)
    if terrain_category not in _TC_COLUMN:
        msg = f"terrain_category must be one of {list(_TC_COLUMN.keys())}, got '{terrain_category}'"
        raise ValueError(msg)
    if building_height_m <= 0:
        msg = "building_height_m must be > 0"
        raise ValueError(msg)
    if topographic_multiplier < 0.5:
        msg = "topographic_multiplier must be >= 0.5"
        raise ValueError(msg)
    if topographic_multiplier > 2.0:
        msg = "topographic_multiplier must be <= 2.0"
        raise ValueError(msg)
    if shielding_multiplier < 0.5:
        msg = "shielding_multiplier must be >= 0.5"
        raise ValueError(msg)
    if shielding_multiplier > 1.0:
        msg = "shielding_multiplier must be <= 1.0"
        raise ValueError(msg)
    if wind_direction_multiplier < 0.5:
        msg = "wind_direction_multiplier must be >= 0.5"
        raise ValueError(msg)
    if wind_direction_multiplier > 1.0:
        msg = "wind_direction_multiplier must be <= 1.0"
        raise ValueError(msg)


def compute(
    regional_wind_speed_m_per_s: float,
    terrain_category: Literal["1", "2", "2.5", "3", "4"],
    building_height_m: float,
    topographic_multiplier: float,
    shielding_multiplier: float,
    wind_direction_multiplier: float = 1.0,
) -> dict[str, float]:
    """Compute site wind speed per AS/NZS 1170.2 Section 2.2.

    V_sit,beta = V_R * M_d * M_z,cat * M_s * M_t

    Returns a dict with keys: mz_cat, site_wind_speed_m_per_s.
    """
    _validate_inputs(
        regional_wind_speed_m_per_s,
        terrain_category,
        building_height_m,
        topographic_multiplier,
        shielding_multiplier,
        wind_direction_multiplier,
    )

    mz_cat = _interpolate_mzcat(building_height_m, terrain_category)

    site_wind_speed = (
        regional_wind_speed_m_per_s * wind_direction_multiplier * mz_cat * shielding_multiplier * topographic_multiplier
    )

    return {
        "mz_cat": round(mz_cat, 2),
        "site_wind_speed_m_per_s": round(site_wind_speed, 2),
    }
