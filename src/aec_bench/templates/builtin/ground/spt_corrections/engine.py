# ABOUTME: SPT N-value correction computation engine (Liao & Whitman 1986).
# ABOUTME: Applies energy, borehole, sampler, rod length, and overburden corrections.

import math

# Energy correction factors (CE) by hammer type.
# Midpoints from Liao & Whitman (1986) via Das, "Principles of Geotechnical Engineering".
_CE_TABLE: dict[str, float] = {
    "auto": 1.33,
    "safety": 0.96,
    "donut": 0.79,
}

# Borehole diameter correction factors (CB).
# Keys are strings because the sampler produces string values for enum params.
_CB_TABLE: dict[str, float] = {
    "65": 1.00,
    "115": 1.00,
    "150": 1.05,
    "200": 1.15,
}

# Sampler correction factors (CS).
_CS_TABLE: dict[str, float] = {
    "with_liner": 1.00,
    "without_liner": 1.20,
}

# Rod length correction factor (CR) boundaries.
# Uses half-open intervals: [3, 4) = 0.75, [4, 6) = 0.85, [6, 10) = 0.95, >= 10 = 1.00.
_CR_BOUNDARIES: list[tuple[float, float]] = [
    (4.0, 0.75),
    (6.0, 0.85),
    (10.0, 0.95),
]
_CR_DEFAULT = 1.00

# Reference atmospheric pressure for overburden correction (kPa).
_PA = 100.0

# Maximum overburden correction factor.
_CN_MAX = 2.0


def _get_cr(rod_length_m: float) -> float:
    """Look up rod length correction factor using half-open intervals."""
    for boundary, factor in _CR_BOUNDARIES:
        if rod_length_m < boundary:
            return factor
    return _CR_DEFAULT


def _validate_inputs(
    raw_n_value: int,
    effective_overburden_kpa: float,
    hammer_type: str,
    borehole_diameter_mm: str,
    sampler_type: str,
    rod_length_m: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if raw_n_value <= 0:
        msg = "raw_n_value must be > 0"
        raise ValueError(msg)
    if effective_overburden_kpa <= 0:
        msg = "effective_overburden_kpa must be > 0"
        raise ValueError(msg)
    if hammer_type not in _CE_TABLE:
        msg = f"hammer_type must be one of {list(_CE_TABLE.keys())}, got '{hammer_type}'"
        raise ValueError(msg)
    if borehole_diameter_mm not in _CB_TABLE:
        msg = f"borehole_diameter_mm must be one of {list(_CB_TABLE.keys())}, got {borehole_diameter_mm}"
        raise ValueError(msg)
    if sampler_type not in _CS_TABLE:
        msg = f"sampler_type must be one of {list(_CS_TABLE.keys())}, got '{sampler_type}'"
        raise ValueError(msg)
    if rod_length_m <= 0:
        msg = "rod_length_m must be > 0"
        raise ValueError(msg)


def compute(
    raw_n_value: int,
    effective_overburden_kpa: float,
    hammer_type: str,
    borehole_diameter_mm: str,
    sampler_type: str,
    rod_length_m: float,
) -> dict[str, float]:
    """Compute corrected SPT N-values using Liao & Whitman (1986) procedure.

    Returns a dict with keys: ce, cb, cs, cr, n60, cn, n1_60.
    borehole_diameter_mm is a string because the sampler produces string values for enum params.
    """
    _validate_inputs(
        raw_n_value,
        effective_overburden_kpa,
        hammer_type,
        borehole_diameter_mm,
        sampler_type,
        rod_length_m,
    )

    ce = _CE_TABLE[hammer_type]
    cb = _CB_TABLE[borehole_diameter_mm]
    cs = _CS_TABLE[sampler_type]
    cr = _get_cr(rod_length_m)

    n60 = raw_n_value * ce * cb * cs * cr
    cn = min(math.sqrt(_PA / effective_overburden_kpa), _CN_MAX)
    n1_60 = cn * n60

    return {
        "ce": round(ce, 2),
        "cb": round(cb, 2),
        "cs": round(cs, 2),
        "cr": round(cr, 2),
        "n60": round(n60, 2),
        "cn": round(cn, 2),
        "n1_60": round(n1_60, 2),
    }
