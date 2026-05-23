# ABOUTME: Computes connected load, maximum demand, and supply kVA.
# ABOUTME: Applies diversity, future allowance, and power factor to equipment load.


def _validate_inputs(
    equipment_power_w: float,
    equipment_quantity: float,
    diversity_factor: float,
    future_expansion_pct: float,
    supply_power_factor: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if equipment_power_w <= 0:
        msg = "equipment_power_w must be > 0"
        raise ValueError(msg)
    if equipment_quantity <= 0:
        msg = "equipment_quantity must be > 0"
        raise ValueError(msg)
    if diversity_factor <= 0 or diversity_factor > 1:
        msg = "diversity_factor must be > 0 and <= 1"
        raise ValueError(msg)
    if future_expansion_pct < 0:
        msg = "future_expansion_pct must be >= 0"
        raise ValueError(msg)
    if supply_power_factor <= 0 or supply_power_factor > 1:
        msg = "supply_power_factor must be > 0 and <= 1"
        raise ValueError(msg)


def compute(
    equipment_power_w: float,
    equipment_quantity: float,
    diversity_factor: float,
    future_expansion_pct: float,
    supply_power_factor: float,
) -> dict[str, float]:
    """Compute signalling power connected load and recommended supply size."""
    _validate_inputs(
        equipment_power_w,
        equipment_quantity,
        diversity_factor,
        future_expansion_pct,
        supply_power_factor,
    )

    total_connected_load_w = equipment_power_w * equipment_quantity
    maximum_demand_w = total_connected_load_w * diversity_factor
    future_allowance_w = maximum_demand_w * future_expansion_pct / 100.0
    recommended_supply_size_kva = (maximum_demand_w + future_allowance_w) / supply_power_factor / 1000.0

    return {
        "total_connected_load_w": round(total_connected_load_w, 2),
        "maximum_demand_w": round(maximum_demand_w, 2),
        "future_allowance_w": round(future_allowance_w, 2),
        "recommended_supply_size_kva": round(recommended_supply_size_kva, 2),
    }
