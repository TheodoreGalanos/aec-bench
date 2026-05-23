# ABOUTME: Activated sludge production computation engine.
# ABOUTME: Estimates biomass and total sludge production from BOD removal and solids capture.


def _validate_inputs(
    flow_rate_m3_d: float,
    influent_bod_mg_l: float,
    effluent_bod_mg_l: float,
    influent_tss_mg_l: float,
    primary_tss_removal_pct: float,
    yield_coefficient: float,
    decay_coefficient_d_inv: float,
    srt_days: float,
    vss_to_tss_ratio: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if flow_rate_m3_d <= 0:
        msg = "flow_rate_m3_d must be > 0"
        raise ValueError(msg)
    if influent_bod_mg_l < effluent_bod_mg_l:
        msg = "influent_bod_mg_l must be >= effluent_bod_mg_l"
        raise ValueError(msg)
    if influent_tss_mg_l < 0:
        msg = "influent_tss_mg_l must be >= 0"
        raise ValueError(msg)
    if primary_tss_removal_pct < 0 or primary_tss_removal_pct > 100:
        msg = "primary_tss_removal_pct must be between 0 and 100"
        raise ValueError(msg)
    if yield_coefficient <= 0:
        msg = "yield_coefficient must be > 0"
        raise ValueError(msg)
    if decay_coefficient_d_inv < 0:
        msg = "decay_coefficient_d_inv must be >= 0"
        raise ValueError(msg)
    if srt_days <= 0:
        msg = "srt_days must be > 0"
        raise ValueError(msg)
    if vss_to_tss_ratio <= 0 or vss_to_tss_ratio > 1:
        msg = "vss_to_tss_ratio must be > 0 and <= 1"
        raise ValueError(msg)


def compute(
    flow_rate_m3_d: float,
    influent_bod_mg_l: float,
    effluent_bod_mg_l: float,
    influent_tss_mg_l: float,
    primary_tss_removal_pct: float,
    yield_coefficient: float,
    decay_coefficient_d_inv: float,
    srt_days: float,
    vss_to_tss_ratio: float,
) -> dict[str, float]:
    """Compute observed yield and sludge production.

    Returns a dict with keys: bod_removed_kg_d, observed_yield_vss_per_bod,
    biomass_production_kg_vss_d, primary_solids_kg_tss_d, total_sludge_kg_tss_d.
    """
    _validate_inputs(
        flow_rate_m3_d,
        influent_bod_mg_l,
        effluent_bod_mg_l,
        influent_tss_mg_l,
        primary_tss_removal_pct,
        yield_coefficient,
        decay_coefficient_d_inv,
        srt_days,
        vss_to_tss_ratio,
    )

    bod_removed = flow_rate_m3_d * (influent_bod_mg_l - effluent_bod_mg_l) / 1000.0
    observed_yield = yield_coefficient / (1.0 + decay_coefficient_d_inv * srt_days)
    biomass_vss = observed_yield * bod_removed
    biomass_tss = biomass_vss / vss_to_tss_ratio
    primary_solids = flow_rate_m3_d * influent_tss_mg_l * primary_tss_removal_pct / 100000.0
    total_sludge = biomass_tss + primary_solids

    return {
        "bod_removed_kg_d": round(bod_removed, 2),
        "observed_yield_vss_per_bod": round(observed_yield, 2),
        "biomass_production_kg_vss_d": round(biomass_vss, 2),
        "primary_solids_kg_tss_d": round(primary_solids, 2),
        "total_sludge_kg_tss_d": round(total_sludge, 2),
    }
