# ABOUTME: Computes optical fibre link loss and power margin.
# ABOUTME: Sums fibre attenuation, connector losses, and splice losses.


def _validate_inputs(
    fiber_length_km: float,
    fiber_attenuation_db_per_km: float,
    connector_count: float,
    connector_loss_db: float,
    splice_count: float,
    splice_loss_db: float,
    system_loss_budget_db: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "fiber_length_km": fiber_length_km,
        "fiber_attenuation_db_per_km": fiber_attenuation_db_per_km,
        "connector_loss_db": connector_loss_db,
        "splice_loss_db": splice_loss_db,
        "system_loss_budget_db": system_loss_budget_db,
    }.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)
    for name, value in {"connector_count": connector_count, "splice_count": splice_count}.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)


def compute(
    fiber_length_km: float,
    fiber_attenuation_db_per_km: float,
    connector_count: float,
    connector_loss_db: float,
    splice_count: float,
    splice_loss_db: float,
    system_loss_budget_db: float,
) -> dict[str, float]:
    """Compute fibre link loss and remaining optical power margin."""
    _validate_inputs(
        fiber_length_km,
        fiber_attenuation_db_per_km,
        connector_count,
        connector_loss_db,
        splice_count,
        splice_loss_db,
        system_loss_budget_db,
    )

    fiber_loss_db = fiber_length_km * fiber_attenuation_db_per_km
    connector_loss_total_db = connector_count * connector_loss_db
    splice_loss_total_db = splice_count * splice_loss_db
    total_link_loss_db = fiber_loss_db + connector_loss_total_db + splice_loss_total_db
    power_margin_db = system_loss_budget_db - total_link_loss_db

    return {
        "fiber_loss_db": round(fiber_loss_db, 2),
        "connector_loss_total_db": round(connector_loss_total_db, 2),
        "splice_loss_total_db": round(splice_loss_total_db, 2),
        "total_link_loss_db": round(total_link_loss_db, 2),
        "power_margin_db": round(power_margin_db, 2),
    }
