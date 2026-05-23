# ABOUTME: SCM substitution computation engine for concrete binder mixes.
# ABOUTME: Calculates cement and supplementary cementitious material quantities.


def _validate_inputs(
    total_binder_kg_m3: float,
    scm_replacement_pct: float,
    water_content_kg_m3: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if total_binder_kg_m3 <= 0:
        msg = "total_binder_kg_m3 must be > 0"
        raise ValueError(msg)
    if not 0 <= scm_replacement_pct <= 100:
        msg = "scm_replacement_pct must be between 0 and 100"
        raise ValueError(msg)
    if water_content_kg_m3 < 0:
        msg = "water_content_kg_m3 must be >= 0"
        raise ValueError(msg)


def compute(
    total_binder_kg_m3: float,
    scm_replacement_pct: float,
    water_content_kg_m3: float,
) -> dict[str, float]:
    """Compute cement and SCM quantities from binder replacement percentage.

    Returns a dict with keys: cement_content_kg_m3, scm_content_kg_m3,
    cement_reduction_kg_m3, water_binder_ratio.
    """
    _validate_inputs(total_binder_kg_m3, scm_replacement_pct, water_content_kg_m3)

    replacement_fraction = scm_replacement_pct / 100.0
    scm_content = total_binder_kg_m3 * replacement_fraction
    cement_content = total_binder_kg_m3 - scm_content
    water_binder_ratio = water_content_kg_m3 / total_binder_kg_m3

    return {
        "cement_content_kg_m3": round(cement_content, 2),
        "scm_content_kg_m3": round(scm_content, 2),
        "cement_reduction_kg_m3": round(scm_content, 2),
        "water_binder_ratio": round(water_binder_ratio, 3),
    }
