# ABOUTME: Mooring line capacity computation engine for marine structural checks.
# ABOUTME: Calculates design tension, reserve capacity, utilisation, and pass status.


def _validate_inputs(
    line_tension_kn: float,
    dynamic_factor: float,
    consequence_factor: float,
    mbl_kn: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if line_tension_kn <= 0:
        msg = "line_tension_kn must be > 0"
        raise ValueError(msg)
    if dynamic_factor <= 0:
        msg = "dynamic_factor must be > 0"
        raise ValueError(msg)
    if consequence_factor <= 0:
        msg = "consequence_factor must be > 0"
        raise ValueError(msg)
    if mbl_kn <= 0:
        msg = "mbl_kn must be > 0"
        raise ValueError(msg)


def compute(
    line_tension_kn: float,
    dynamic_factor: float,
    consequence_factor: float,
    mbl_kn: float,
) -> dict[str, float]:
    """Compute mooring line design tension and capacity check outputs.

    Returns a dict with keys: design_tension_kn, capacity_margin_ratio,
    reserve_capacity_kn, utilisation_ratio, passes_capacity_check.
    """
    _validate_inputs(line_tension_kn, dynamic_factor, consequence_factor, mbl_kn)

    design_tension = line_tension_kn * dynamic_factor * consequence_factor
    capacity_margin_ratio = mbl_kn / design_tension
    reserve_capacity = mbl_kn - design_tension
    utilisation_ratio = design_tension / mbl_kn
    passes_capacity_check = 1.0 if design_tension <= mbl_kn else 0.0

    return {
        "design_tension_kn": round(design_tension, 2),
        "capacity_margin_ratio": round(capacity_margin_ratio, 3),
        "reserve_capacity_kn": round(reserve_capacity, 2),
        "utilisation_ratio": round(utilisation_ratio, 3),
        "passes_capacity_check": round(passes_capacity_check, 2),
    }
