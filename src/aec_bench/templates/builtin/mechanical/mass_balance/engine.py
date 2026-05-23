# ABOUTME: Global mass balance computation engine for process convergence checks.
# ABOUTME: Calculates imbalance, closure error, and an explicit tolerance flag.


def _validate_inputs(
    inlet_1_kg_h: float,
    inlet_2_kg_h: float,
    outlet_1_kg_h: float,
    outlet_2_kg_h: float,
    closure_tolerance_pct: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "inlet_1_kg_h": inlet_1_kg_h,
        "inlet_2_kg_h": inlet_2_kg_h,
        "outlet_1_kg_h": outlet_1_kg_h,
        "outlet_2_kg_h": outlet_2_kg_h,
    }.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)
    if inlet_1_kg_h + inlet_2_kg_h <= 0:
        msg = "total inlet mass flow must be > 0"
        raise ValueError(msg)
    if closure_tolerance_pct < 0:
        msg = "closure_tolerance_pct must be >= 0"
        raise ValueError(msg)


def compute(
    inlet_1_kg_h: float,
    inlet_2_kg_h: float,
    outlet_1_kg_h: float,
    outlet_2_kg_h: float,
    closure_tolerance_pct: float,
) -> dict[str, float]:
    """Compute global process mass balance closure.

    Returns a dict with keys: total_inlet_kg_h, total_outlet_kg_h,
    imbalance_kg_h, closure_error_pct, closure_satisfied.
    """
    _validate_inputs(
        inlet_1_kg_h,
        inlet_2_kg_h,
        outlet_1_kg_h,
        outlet_2_kg_h,
        closure_tolerance_pct,
    )

    total_inlet = inlet_1_kg_h + inlet_2_kg_h
    total_outlet = outlet_1_kg_h + outlet_2_kg_h
    imbalance = total_inlet - total_outlet
    closure_error = abs(imbalance) / total_inlet * 100.0
    closure_satisfied = 1.0 if closure_error <= closure_tolerance_pct else 0.0

    return {
        "total_inlet_kg_h": round(total_inlet, 2),
        "total_outlet_kg_h": round(total_outlet, 2),
        "imbalance_kg_h": round(imbalance, 2),
        "closure_error_pct": round(closure_error, 3),
        "closure_satisfied": round(closure_satisfied, 2),
    }
