# ABOUTME: Chemical dosing computation engine for water and wastewater treatment.
# ABOUTME: Calculates active mass, product mass, volume feed rate, and annual consumption.


def _validate_inputs(
    flow_rate_m3_d: float,
    target_dose_mg_l: float,
    product_strength_pct: float,
    product_density_kg_l: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if flow_rate_m3_d <= 0:
        msg = "flow_rate_m3_d must be > 0"
        raise ValueError(msg)
    if target_dose_mg_l <= 0:
        msg = "target_dose_mg_l must be > 0"
        raise ValueError(msg)
    if product_strength_pct <= 0 or product_strength_pct > 100:
        msg = "product_strength_pct must be > 0 and <= 100"
        raise ValueError(msg)
    if product_density_kg_l <= 0:
        msg = "product_density_kg_l must be > 0"
        raise ValueError(msg)


def compute(
    flow_rate_m3_d: float,
    target_dose_mg_l: float,
    product_strength_pct: float,
    product_density_kg_l: float,
) -> dict[str, float]:
    """Compute chemical feed rate for a target active dose.

    Returns a dict with keys: active_mass_feed_kg_d, product_mass_feed_kg_d,
    volume_feed_l_d, annual_product_consumption_t.
    """
    _validate_inputs(
        flow_rate_m3_d,
        target_dose_mg_l,
        product_strength_pct,
        product_density_kg_l,
    )

    active_mass = flow_rate_m3_d * target_dose_mg_l / 1000.0
    product_mass = active_mass / (product_strength_pct / 100.0)
    volume_feed = product_mass / product_density_kg_l
    annual_consumption = product_mass * 365.0 / 1000.0

    return {
        "active_mass_feed_kg_d": round(active_mass, 2),
        "product_mass_feed_kg_d": round(product_mass, 2),
        "volume_feed_l_d": round(volume_feed, 2),
        "annual_product_consumption_t": round(annual_consumption, 2),
    }
