# ABOUTME: Heat exchanger LMTD computation engine for thermal process checks.
# ABOUTME: Calculates LMTD, corrected MTD, heat duty, and terminal approach.

import math
from typing import Literal


def _validate_inputs(
    hot_inlet_c: float,
    hot_outlet_c: float,
    cold_inlet_c: float,
    cold_outlet_c: float,
    overall_u_kw_m2_c: float,
    heat_transfer_area_m2: float,
    correction_factor: float,
    flow_arrangement: str,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if hot_inlet_c <= hot_outlet_c:
        msg = "hot_inlet_c must be > hot_outlet_c"
        raise ValueError(msg)
    if cold_outlet_c <= cold_inlet_c:
        msg = "cold_outlet_c must be > cold_inlet_c"
        raise ValueError(msg)
    if hot_inlet_c <= cold_outlet_c:
        msg = "hot_inlet_c must be > cold_outlet_c"
        raise ValueError(msg)
    if hot_outlet_c <= cold_inlet_c:
        msg = "hot_outlet_c must be > cold_inlet_c"
        raise ValueError(msg)
    if overall_u_kw_m2_c <= 0:
        msg = "overall_u_kw_m2_c must be > 0"
        raise ValueError(msg)
    if heat_transfer_area_m2 <= 0:
        msg = "heat_transfer_area_m2 must be > 0"
        raise ValueError(msg)
    if correction_factor <= 0 or correction_factor > 1:
        msg = "correction_factor must be > 0 and <= 1"
        raise ValueError(msg)
    if flow_arrangement not in {"counterflow", "parallel"}:
        msg = "flow_arrangement must be one of ['counterflow', 'parallel']"
        raise ValueError(msg)


def _lmtd(delta_t1: float, delta_t2: float) -> float:
    """Return log mean temperature difference."""
    if abs(delta_t1 - delta_t2) < 1.0e-9:
        return delta_t1
    return (delta_t1 - delta_t2) / math.log(delta_t1 / delta_t2)


def compute(
    hot_inlet_c: float,
    hot_outlet_c: float,
    cold_inlet_c: float,
    cold_outlet_c: float,
    overall_u_kw_m2_c: float,
    heat_transfer_area_m2: float,
    correction_factor: float,
    flow_arrangement: Literal["counterflow", "parallel"],
) -> dict[str, float]:
    """Compute LMTD and heat duty from terminal temperatures and UA.

    Returns a dict with keys: delta_t1_c, delta_t2_c, lmtd_c,
    corrected_mtd_c, heat_duty_kw, minimum_approach_c.
    """
    _validate_inputs(
        hot_inlet_c,
        hot_outlet_c,
        cold_inlet_c,
        cold_outlet_c,
        overall_u_kw_m2_c,
        heat_transfer_area_m2,
        correction_factor,
        flow_arrangement,
    )

    if flow_arrangement == "counterflow":
        delta_t1 = hot_inlet_c - cold_outlet_c
        delta_t2 = hot_outlet_c - cold_inlet_c
    else:
        delta_t1 = hot_inlet_c - cold_inlet_c
        delta_t2 = hot_outlet_c - cold_outlet_c

    if delta_t1 <= 0 or delta_t2 <= 0:
        msg = "terminal temperature differences must be > 0 for LMTD"
        raise ValueError(msg)

    lmtd = _lmtd(delta_t1, delta_t2)
    corrected_mtd = lmtd * correction_factor
    heat_duty = overall_u_kw_m2_c * heat_transfer_area_m2 * corrected_mtd
    minimum_approach = min(hot_inlet_c - cold_outlet_c, hot_outlet_c - cold_inlet_c)

    return {
        "delta_t1_c": round(delta_t1, 2),
        "delta_t2_c": round(delta_t2, 2),
        "lmtd_c": round(lmtd, 2),
        "corrected_mtd_c": round(corrected_mtd, 2),
        "heat_duty_kw": round(heat_duty, 2),
        "minimum_approach_c": round(minimum_approach, 2),
    }
