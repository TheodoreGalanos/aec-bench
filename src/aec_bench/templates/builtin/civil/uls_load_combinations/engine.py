# ABOUTME: ULS load combination computation engine per AS/NZS 1170.0 Table 4.1.
# ABOUTME: Calculates all ultimate limit state combinations and identifies the governing case.

from typing import Literal

# Combination factors from AS/NZS 1170.0 Table 4.1.
# psi_c: combination factor for imposed actions when wind is dominant.
# psi_E: combination factor for imposed actions when earthquake is dominant.
_PSI_C: dict[str, float] = {
    "A": 0.4,
    "B": 0.4,
    "C": 0.4,
    "D": 0.4,
    "E": 0.6,
}

_PSI_E: dict[str, float] = {
    "A": 0.3,
    "B": 0.3,
    "C": 0.3,
    "D": 0.3,
    "E": 0.6,
}

_VALID_CATEGORIES: set[str] = set(_PSI_C.keys())


def _validate_inputs(
    dead_load_kn: float,
    live_load_kn: float,
    wind_ultimate_kn: float,
    earthquake_load_kn: float,
    load_category: str,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if dead_load_kn < 0:
        msg = "dead_load_kn must be >= 0"
        raise ValueError(msg)
    if live_load_kn < 0:
        msg = "live_load_kn must be >= 0"
        raise ValueError(msg)
    if wind_ultimate_kn < 0:
        msg = "wind_ultimate_kn must be >= 0"
        raise ValueError(msg)
    if earthquake_load_kn < 0:
        msg = "earthquake_load_kn must be >= 0"
        raise ValueError(msg)
    if load_category not in _VALID_CATEGORIES:
        msg = f"load_category must be one of {sorted(_VALID_CATEGORIES)}, got '{load_category}'"
        raise ValueError(msg)


def _uls_permanent(dead_load_kn: float) -> float:
    """Combination 1: Permanent action only.

    Ed = 1.35 * G
    """
    return 1.35 * dead_load_kn


def _uls_imposed(dead_load_kn: float, live_load_kn: float) -> float:
    """Combination 2: Permanent + imposed actions.

    Ed = 1.2 * G + 1.5 * Q
    """
    return 1.2 * dead_load_kn + 1.5 * live_load_kn


def _uls_wind(
    dead_load_kn: float,
    live_load_kn: float,
    wind_ultimate_kn: float,
    psi_c: float,
) -> float:
    """Combination 3: Permanent + imposed (companion) + wind.

    Ed = 1.2 * G + psi_c * Q + W_u
    """
    return 1.2 * dead_load_kn + psi_c * live_load_kn + wind_ultimate_kn


def _uls_wind_uplift(
    dead_load_kn: float,
    wind_ultimate_kn: float,
) -> float:
    """Combination 4: Permanent + wind (favourable dead load for uplift/overturning).

    Ed = 0.9 * G + W_u
    """
    return 0.9 * dead_load_kn + wind_ultimate_kn


def _uls_earthquake(
    dead_load_kn: float,
    live_load_kn: float,
    earthquake_load_kn: float,
    psi_e: float,
) -> float:
    """Combination 5: Permanent + imposed (earthquake companion) + earthquake.

    Ed = 1.0 * G + psi_E * Q + E
    """
    return 1.0 * dead_load_kn + psi_e * live_load_kn + earthquake_load_kn


def compute(
    dead_load_kn: float,
    live_load_kn: float,
    wind_ultimate_kn: float = 0.0,
    earthquake_load_kn: float = 0.0,
    load_category: Literal["A", "B", "C", "D", "E"] = "A",
) -> dict[str, float]:
    """Compute all ULS load combinations per AS/NZS 1170.0 Table 4.1.

    Parameters
    ----------
    dead_load_kn : float
        Permanent (dead) load G in kN.
    live_load_kn : float
        Imposed (live) load Q in kN.
    wind_ultimate_kn : float
        Ultimate wind action W_u in kN (0 if no wind).
    earthquake_load_kn : float
        Earthquake action E in kN (0 if no earthquake).
    load_category : str
        Imposed action category per AS/NZS 1170.0: A-D (general) or E (storage).

    Returns
    -------
    dict with keys: uls_permanent_kn, uls_imposed_kn, uls_wind_kn,
    uls_wind_uplift_kn, uls_earthquake_kn, governing_uls_kn.
    """
    _validate_inputs(
        dead_load_kn,
        live_load_kn,
        wind_ultimate_kn,
        earthquake_load_kn,
        load_category,
    )

    psi_c = _PSI_C[load_category]
    psi_e = _PSI_E[load_category]

    permanent = _uls_permanent(dead_load_kn)
    imposed = _uls_imposed(dead_load_kn, live_load_kn)
    wind = _uls_wind(dead_load_kn, live_load_kn, wind_ultimate_kn, psi_c)
    wind_uplift = _uls_wind_uplift(dead_load_kn, wind_ultimate_kn)
    earthquake = _uls_earthquake(dead_load_kn, live_load_kn, earthquake_load_kn, psi_e)

    governing = max(permanent, imposed, wind, wind_uplift, earthquake)

    return {
        "uls_permanent_kn": round(permanent, 2),
        "uls_imposed_kn": round(imposed, 2),
        "uls_wind_kn": round(wind, 2),
        "uls_wind_uplift_kn": round(wind_uplift, 2),
        "uls_earthquake_kn": round(earthquake, 2),
        "governing_uls_kn": round(governing, 2),
    }
