# ABOUTME: MLSS inventory computation engine for activated sludge basins.
# ABOUTME: Calculates suspended and volatile suspended solids mass from volume and concentration.


def _validate_inputs(
    aeration_volume_m3: float,
    mlss_concentration_mg_l: float,
    mlvss_fraction: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if aeration_volume_m3 <= 0:
        msg = "aeration_volume_m3 must be > 0"
        raise ValueError(msg)
    if mlss_concentration_mg_l <= 0:
        msg = "mlss_concentration_mg_l must be > 0"
        raise ValueError(msg)
    if mlvss_fraction < 0 or mlvss_fraction > 1:
        msg = "mlvss_fraction must be between 0 and 1"
        raise ValueError(msg)


def compute(
    aeration_volume_m3: float,
    mlss_concentration_mg_l: float,
    mlvss_fraction: float,
) -> dict[str, float]:
    """Compute MLSS and MLVSS inventory.

    Returns a dict with keys: mlss_inventory_kg, mlvss_inventory_kg,
    inert_solids_inventory_kg.
    """
    _validate_inputs(aeration_volume_m3, mlss_concentration_mg_l, mlvss_fraction)

    mlss_inventory = aeration_volume_m3 * mlss_concentration_mg_l / 1000.0
    mlvss_inventory = mlss_inventory * mlvss_fraction
    inert_inventory = mlss_inventory - mlvss_inventory

    return {
        "mlss_inventory_kg": round(mlss_inventory, 2),
        "mlvss_inventory_kg": round(mlvss_inventory, 2),
        "inert_solids_inventory_kg": round(inert_inventory, 2),
    }
