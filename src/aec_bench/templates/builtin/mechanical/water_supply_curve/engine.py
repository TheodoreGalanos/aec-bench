# ABOUTME: Water supply curve computation engine for hydrant flow tests.
# ABOUTME: Calculates curve coefficient and available flows from pressure data.

_HYDRANT_EXPONENT = 0.54


def _validate_inputs(
    static_pressure_psi: float,
    residual_pressure_psi: float,
    test_flow_gpm: float,
    target_residual_pressure_psi: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if static_pressure_psi <= 0:
        msg = "static_pressure_psi must be > 0"
        raise ValueError(msg)
    if residual_pressure_psi < 0:
        msg = "residual_pressure_psi must be >= 0"
        raise ValueError(msg)
    if target_residual_pressure_psi < 0:
        msg = "target_residual_pressure_psi must be >= 0"
        raise ValueError(msg)
    if residual_pressure_psi >= static_pressure_psi:
        msg = "residual_pressure_psi must be < static_pressure_psi"
        raise ValueError(msg)
    if target_residual_pressure_psi >= static_pressure_psi:
        msg = "target_residual_pressure_psi must be < static_pressure_psi"
        raise ValueError(msg)
    if test_flow_gpm <= 0:
        msg = "test_flow_gpm must be > 0"
        raise ValueError(msg)


def compute(
    static_pressure_psi: float,
    residual_pressure_psi: float,
    test_flow_gpm: float,
    target_residual_pressure_psi: float,
) -> dict[str, float]:
    """Compute hydrant water supply curve coefficient and target flows.

    Returns a dict with keys: pressure_drop_test_psi, curve_coefficient,
    flow_at_target_residual_gpm, available_flow_20psi_gpm.
    """
    _validate_inputs(
        static_pressure_psi,
        residual_pressure_psi,
        test_flow_gpm,
        target_residual_pressure_psi,
    )

    pressure_drop_test = static_pressure_psi - residual_pressure_psi
    target_drop = static_pressure_psi - target_residual_pressure_psi
    drop_to_20psi = static_pressure_psi - 20.0
    curve_coefficient = test_flow_gpm / pressure_drop_test**_HYDRANT_EXPONENT
    flow_at_target = curve_coefficient * target_drop**_HYDRANT_EXPONENT
    available_flow_20psi = curve_coefficient * drop_to_20psi**_HYDRANT_EXPONENT

    return {
        "pressure_drop_test_psi": round(pressure_drop_test, 2),
        "curve_coefficient": round(curve_coefficient, 3),
        "flow_at_target_residual_gpm": round(flow_at_target, 2),
        "available_flow_20psi_gpm": round(available_flow_20psi, 2),
    }
