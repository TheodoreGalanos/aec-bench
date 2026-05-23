# ABOUTME: Available flow computation engine for hydrant flow tests.
# ABOUTME: Extrapolates available flow at a target residual pressure.

_FLOW_EXPONENT = 0.54


def _validate_inputs(
    static_pressure_kpa: float,
    residual_pressure_kpa: float,
    test_flow_l_s: float,
    target_residual_pressure_kpa: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if test_flow_l_s < 0:
        msg = "test_flow_l_s must be >= 0"
        raise ValueError(msg)
    if static_pressure_kpa <= residual_pressure_kpa:
        msg = "static_pressure_kpa must be > residual_pressure_kpa"
        raise ValueError(msg)
    if static_pressure_kpa <= target_residual_pressure_kpa:
        msg = "static_pressure_kpa must be > target_residual_pressure_kpa"
        raise ValueError(msg)


def compute(
    static_pressure_kpa: float,
    residual_pressure_kpa: float,
    test_flow_l_s: float,
    target_residual_pressure_kpa: float,
) -> dict[str, float]:
    """Compute available flow from a hydrant flow test.

    Returns a dict with keys: pressure_drop_test_kpa, pressure_drop_target_kpa,
    available_flow_l_s, available_flow_m3_h.
    """
    _validate_inputs(
        static_pressure_kpa,
        residual_pressure_kpa,
        test_flow_l_s,
        target_residual_pressure_kpa,
    )

    pressure_drop_test = static_pressure_kpa - residual_pressure_kpa
    pressure_drop_target = static_pressure_kpa - target_residual_pressure_kpa
    available_flow = test_flow_l_s * (pressure_drop_target / pressure_drop_test) ** _FLOW_EXPONENT

    return {
        "pressure_drop_test_kpa": round(pressure_drop_test, 2),
        "pressure_drop_target_kpa": round(pressure_drop_target, 2),
        "available_flow_l_s": round(available_flow, 2),
        "available_flow_m3_h": round(available_flow * 3.6, 2),
    }
