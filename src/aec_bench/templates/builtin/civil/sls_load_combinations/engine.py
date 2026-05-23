# ABOUTME: SLS load combination engine per AS/NZS 1170.0 Table 4.1.
# ABOUTME: Computes short-term, long-term, and wind serviceability combinations from dead, live, and wind loads.

from typing import Literal

# Combination factors from AS/NZS 1170.0 Table 4.1.
# Keys are imposed-action categories per AS 1170.1.
#   A — domestic/residential floors
#   B — office floors
#   C — areas of public assembly (theatres, restaurants, etc.)
#   D — shops/retail areas
#   E — storage areas and trafficable roofs used for storage
_PSI_FACTORS: dict[str, tuple[float, float]] = {
    # (psi_s, psi_l)
    "A": (0.7, 0.4),
    "B": (0.7, 0.4),
    "C": (0.7, 0.6),
    "D": (0.7, 0.4),
    "E": (1.0, 0.6),
}


def _validate_inputs(
    dead_load_kn: float,
    live_load_kn: float,
    wind_serviceability_kn: float,
    load_category: str,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if dead_load_kn < 0:
        msg = "dead_load_kn must be >= 0"
        raise ValueError(msg)
    if live_load_kn < 0:
        msg = "live_load_kn must be >= 0"
        raise ValueError(msg)
    if wind_serviceability_kn < 0:
        msg = "wind_serviceability_kn must be >= 0"
        raise ValueError(msg)
    if load_category not in _PSI_FACTORS:
        msg = f"load_category must be one of {list(_PSI_FACTORS.keys())}, got '{load_category}'"
        raise ValueError(msg)


def compute(
    dead_load_kn: float,
    live_load_kn: float,
    load_category: Literal["A", "B", "C", "D", "E"],
    wind_serviceability_kn: float = 0.0,
) -> dict[str, float]:
    """Compute SLS load combinations per AS/NZS 1170.0 Table 4.1.

    Serviceability limit state combinations:
      Short-term:  G + psi_s * Q
      Long-term:   G + psi_l * Q
      Wind SLS:    G + psi_s * Q + W_s

    The governing SLS value is the maximum of all three combinations.

    Returns a dict with keys:
      psi_s, psi_l,
      sls_short_term_kn, sls_long_term_kn, sls_wind_kn,
      governing_sls_kn.
    """
    _validate_inputs(dead_load_kn, live_load_kn, wind_serviceability_kn, load_category)

    psi_s, psi_l = _PSI_FACTORS[load_category]

    sls_short_term = dead_load_kn + psi_s * live_load_kn
    sls_long_term = dead_load_kn + psi_l * live_load_kn
    sls_wind = dead_load_kn + psi_s * live_load_kn + wind_serviceability_kn

    governing = max(sls_short_term, sls_long_term, sls_wind)

    return {
        "psi_s": round(psi_s, 2),
        "psi_l": round(psi_l, 2),
        "sls_short_term_kn": round(sls_short_term, 2),
        "sls_long_term_kn": round(sls_long_term, 2),
        "sls_wind_kn": round(sls_wind, 2),
        "governing_sls_kn": round(governing, 2),
    }
