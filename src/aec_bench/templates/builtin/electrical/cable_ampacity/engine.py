# ABOUTME: Cable ampacity derating computation engine per AS/NZS 3008.1.1.
# ABOUTME: Calculates derated current-carrying capacity using temperature and grouping factors.

import math
from typing import Literal

# Base current-carrying capacity (A) for copper multicore cables at 30 deg C ambient.
# Organised by insulation type, then installation method, then conductor size (mm2 as str).
# Values are representative of AS/NZS 3008.1.1 Tables 4-15 for common installation methods.
# PVC insulation: max conductor temperature 75 deg C.
# XLPE insulation: max conductor temperature 90 deg C.
_BASE_AMPACITY: dict[str, dict[str, dict[str, float]]] = {
    "XLPE": {
        "in-air": {
            "1.5": 23.0,
            "2.5": 31.0,
            "4": 42.0,
            "6": 54.0,
            "10": 73.0,
            "16": 98.0,
            "25": 129.0,
            "35": 158.0,
            "50": 190.0,
            "70": 242.0,
            "95": 292.0,
            "120": 336.0,
            "150": 381.0,
            "185": 434.0,
            "240": 510.0,
        },
        "in-tray": {
            "1.5": 21.0,
            "2.5": 28.0,
            "4": 38.0,
            "6": 49.0,
            "10": 66.0,
            "16": 88.0,
            "25": 117.0,
            "35": 143.0,
            "50": 172.0,
            "70": 219.0,
            "95": 265.0,
            "120": 305.0,
            "150": 346.0,
            "185": 394.0,
            "240": 463.0,
        },
        "in-conduit": {
            "1.5": 19.0,
            "2.5": 26.0,
            "4": 35.0,
            "6": 45.0,
            "10": 61.0,
            "16": 81.0,
            "25": 107.0,
            "35": 131.0,
            "50": 158.0,
            "70": 200.0,
            "95": 242.0,
            "120": 278.0,
            "150": 316.0,
            "185": 360.0,
            "240": 423.0,
        },
        "buried": {
            "1.5": 26.0,
            "2.5": 35.0,
            "4": 46.0,
            "6": 58.0,
            "10": 79.0,
            "16": 104.0,
            "25": 137.0,
            "35": 167.0,
            "50": 200.0,
            "70": 253.0,
            "95": 304.0,
            "120": 348.0,
            "150": 393.0,
            "185": 446.0,
            "240": 521.0,
        },
    },
    "PVC": {
        "in-air": {
            "1.5": 19.5,
            "2.5": 27.0,
            "4": 36.0,
            "6": 46.0,
            "10": 63.0,
            "16": 85.0,
            "25": 112.0,
            "35": 137.0,
            "50": 165.0,
            "70": 210.0,
            "95": 254.0,
            "120": 292.0,
            "150": 330.0,
            "185": 376.0,
            "240": 442.0,
        },
        "in-tray": {
            "1.5": 17.5,
            "2.5": 24.0,
            "4": 32.0,
            "6": 41.0,
            "10": 56.0,
            "16": 75.0,
            "25": 99.0,
            "35": 122.0,
            "50": 147.0,
            "70": 187.0,
            "95": 226.0,
            "120": 260.0,
            "150": 294.0,
            "185": 335.0,
            "240": 393.0,
        },
        "in-conduit": {
            "1.5": 16.0,
            "2.5": 22.0,
            "4": 30.0,
            "6": 38.0,
            "10": 52.0,
            "16": 70.0,
            "25": 92.0,
            "35": 113.0,
            "50": 136.0,
            "70": 173.0,
            "95": 210.0,
            "120": 242.0,
            "150": 273.0,
            "185": 311.0,
            "240": 366.0,
        },
        "buried": {
            "1.5": 22.0,
            "2.5": 30.0,
            "4": 39.0,
            "6": 50.0,
            "10": 67.0,
            "16": 89.0,
            "25": 117.0,
            "35": 143.0,
            "50": 171.0,
            "70": 216.0,
            "95": 259.0,
            "120": 297.0,
            "150": 336.0,
            "185": 381.0,
            "240": 445.0,
        },
    },
}

# Maximum conductor temperature (deg C) by insulation type.
# Used in the temperature derating formula.
_MAX_CONDUCTOR_TEMP: dict[str, float] = {
    "XLPE": 90.0,
    "PVC": 75.0,
}

# Reference ambient temperature (deg C) used for the base ampacity tables.
_REFERENCE_AMBIENT_TEMP = 30.0

# Grouping derating factors for bunched multicore cables.
# Based on AS/NZS 3008.1.1 Table 22 (simplified for common groupings).
# Key is number of circuits; value is the derating factor.
_GROUPING_FACTORS: dict[int, float] = {
    1: 1.00,
    2: 0.80,
    3: 0.70,
    4: 0.65,
    5: 0.60,
    6: 0.57,
    7: 0.54,
    8: 0.52,
    9: 0.50,
    10: 0.48,
    11: 0.46,
    12: 0.45,
}

# Valid installation methods matching the enum values in params.toml.
_VALID_INSTALLATION_METHODS = {"buried", "in-tray", "in-conduit", "in-air"}

# Valid insulation types matching the enum values in params.toml.
_VALID_INSULATION_TYPES = {"XLPE", "PVC"}


def _get_grouping_factor(num_circuits: int) -> float:
    """Look up the grouping derating factor for a given number of circuits.

    For circuit counts beyond the table, extrapolate using the inverse square
    root relationship: factor = 1 / sqrt(n), which is the standard engineering
    approximation for large cable groups.
    """
    if num_circuits in _GROUPING_FACTORS:
        return _GROUPING_FACTORS[num_circuits]
    # Extrapolate for counts above 12 using 1/sqrt(n)
    return round(1.0 / math.sqrt(num_circuits), 2)


def _calc_temp_derating(
    ambient_temp_c: float,
    max_conductor_temp_c: float,
) -> float:
    """Calculate temperature derating factor per IEC 60287 / AS/NZS 3008.

    Ct = sqrt((Tmax - Tamb) / (Tmax - Tref))
    where Tref is the reference ambient temperature (30 deg C for air tables).
    """
    numerator = max_conductor_temp_c - ambient_temp_c
    denominator = max_conductor_temp_c - _REFERENCE_AMBIENT_TEMP
    return math.sqrt(numerator / denominator)


def _validate_inputs(
    conductor_size_mm2: str,
    insulation_type: str,
    installation_method: str,
    ambient_temp_c: float,
    max_conductor_temp_c: float,
    grouping_circuits: int,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if insulation_type not in _VALID_INSULATION_TYPES:
        msg = f"insulation_type must be one of {sorted(_VALID_INSULATION_TYPES)}, got '{insulation_type}'"
        raise ValueError(msg)
    if installation_method not in _VALID_INSTALLATION_METHODS:
        msg = f"installation_method must be one of {sorted(_VALID_INSTALLATION_METHODS)}, got '{installation_method}'"
        raise ValueError(msg)
    valid_sizes = _BASE_AMPACITY[insulation_type][installation_method]
    if conductor_size_mm2 not in valid_sizes:
        msg = (
            f"conductor_size_mm2 '{conductor_size_mm2}' not available for "
            f"{insulation_type}/{installation_method}. "
            f"Valid sizes: {sorted(valid_sizes.keys(), key=lambda s: float(s))}"
        )
        raise ValueError(msg)
    if ambient_temp_c < 0:
        msg = "ambient_temp_c must be >= 0"
        raise ValueError(msg)
    if ambient_temp_c >= max_conductor_temp_c:
        msg = f"ambient_temp_c ({ambient_temp_c}) must be less than max_conductor_temp_c ({max_conductor_temp_c})"
        raise ValueError(msg)
    if max_conductor_temp_c <= _REFERENCE_AMBIENT_TEMP:
        msg = f"max_conductor_temp_c must be > reference ambient ({_REFERENCE_AMBIENT_TEMP} deg C)"
        raise ValueError(msg)
    if grouping_circuits < 1:
        msg = "grouping_circuits must be >= 1"
        raise ValueError(msg)


def compute(
    conductor_size_mm2: str,
    insulation_type: Literal["XLPE", "PVC"],
    installation_method: Literal["buried", "in-tray", "in-conduit", "in-air"],
    ambient_temp_c: float,
    max_conductor_temp_c: float = 90.0,
    grouping_circuits: int = 1,
) -> dict[str, float]:
    """Compute derated cable ampacity per AS/NZS 3008.1.1.

    The method applies temperature and grouping derating factors to the base
    current-carrying capacity:
        derated_ampacity = base_ampacity * Ct * Cg

    Returns a dict with keys: base_ampacity_a, temp_derating_factor,
    grouping_derating_factor, derated_ampacity_a.
    """
    _validate_inputs(
        conductor_size_mm2,
        insulation_type,
        installation_method,
        ambient_temp_c,
        max_conductor_temp_c,
        grouping_circuits,
    )

    # Step 1: Look up base ampacity from tables
    base_ampacity = _BASE_AMPACITY[insulation_type][installation_method][conductor_size_mm2]

    # Step 2: Temperature derating factor
    # Ct = sqrt((Tmax - Tamb) / (Tmax - Tref))
    ct = _calc_temp_derating(ambient_temp_c, max_conductor_temp_c)

    # Step 3: Grouping derating factor from table or extrapolation
    cg = _get_grouping_factor(grouping_circuits)

    # Step 4: Final derated ampacity
    derated_ampacity = base_ampacity * ct * cg

    return {
        "base_ampacity_a": round(base_ampacity, 2),
        "temp_derating_factor": round(ct, 2),
        "grouping_derating_factor": round(cg, 2),
        "derated_ampacity_a": round(derated_ampacity, 2),
    }
