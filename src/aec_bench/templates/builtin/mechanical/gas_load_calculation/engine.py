# ABOUTME: Gas load computation engine for building services checks.
# ABOUTME: Sums explicit appliance gas loads and converts energy units.

_MJ_H_PER_KW = 3.6


def _validate_inputs(
    appliance_1_load_mj_h: float,
    appliance_1_quantity: float,
    appliance_2_load_mj_h: float,
    appliance_2_quantity: float,
    appliance_3_load_mj_h: float,
    appliance_3_quantity: float,
    diversity_factor: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "appliance_1_load_mj_h": appliance_1_load_mj_h,
        "appliance_1_quantity": appliance_1_quantity,
        "appliance_2_load_mj_h": appliance_2_load_mj_h,
        "appliance_2_quantity": appliance_2_quantity,
        "appliance_3_load_mj_h": appliance_3_load_mj_h,
        "appliance_3_quantity": appliance_3_quantity,
    }.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)
    if not 0 < diversity_factor <= 1:
        msg = "diversity_factor must be > 0 and <= 1"
        raise ValueError(msg)


def compute(
    appliance_1_load_mj_h: float,
    appliance_1_quantity: float,
    appliance_2_load_mj_h: float,
    appliance_2_quantity: float,
    appliance_3_load_mj_h: float,
    appliance_3_quantity: float,
    diversity_factor: float,
) -> dict[str, float]:
    """Compute diversified total gas demand.

    Returns a dict with keys: connected_load_mj_h, diversified_load_mj_h,
    diversified_load_kw, connected_load_kw.
    """
    _validate_inputs(
        appliance_1_load_mj_h,
        appliance_1_quantity,
        appliance_2_load_mj_h,
        appliance_2_quantity,
        appliance_3_load_mj_h,
        appliance_3_quantity,
        diversity_factor,
    )

    connected_load = (
        appliance_1_load_mj_h * appliance_1_quantity
        + appliance_2_load_mj_h * appliance_2_quantity
        + appliance_3_load_mj_h * appliance_3_quantity
    )
    diversified_load = connected_load * diversity_factor

    return {
        "connected_load_mj_h": round(connected_load, 2),
        "diversified_load_mj_h": round(diversified_load, 2),
        "connected_load_kw": round(connected_load / _MJ_H_PER_KW, 2),
        "diversified_load_kw": round(diversified_load / _MJ_H_PER_KW, 2),
    }
