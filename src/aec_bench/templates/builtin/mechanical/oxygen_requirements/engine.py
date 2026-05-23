# ABOUTME: Activated sludge oxygen demand computation engine.
# ABOUTME: Calculates carbonaceous, nitrogenous, and denitrification-adjusted oxygen demand.


def _validate_inputs(
    flow_rate_m3_d: float,
    influent_bod_mg_l: float,
    effluent_bod_mg_l: float,
    influent_tkn_mg_l: float,
    effluent_tkn_mg_l: float,
    sludge_production_kg_d: float,
    denitrified_nitrogen_mg_l: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if flow_rate_m3_d <= 0:
        msg = "flow_rate_m3_d must be > 0"
        raise ValueError(msg)
    if influent_bod_mg_l < effluent_bod_mg_l:
        msg = "influent_bod_mg_l must be >= effluent_bod_mg_l"
        raise ValueError(msg)
    if influent_tkn_mg_l < effluent_tkn_mg_l:
        msg = "influent_tkn_mg_l must be >= effluent_tkn_mg_l"
        raise ValueError(msg)
    for name, value in {
        "effluent_bod_mg_l": effluent_bod_mg_l,
        "effluent_tkn_mg_l": effluent_tkn_mg_l,
        "sludge_production_kg_d": sludge_production_kg_d,
        "denitrified_nitrogen_mg_l": denitrified_nitrogen_mg_l,
    }.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)


def compute(
    flow_rate_m3_d: float,
    influent_bod_mg_l: float,
    effluent_bod_mg_l: float,
    influent_tkn_mg_l: float,
    effluent_tkn_mg_l: float,
    sludge_production_kg_d: float,
    denitrified_nitrogen_mg_l: float,
) -> dict[str, float]:
    """Compute process oxygen demand for BOD and nitrogen oxidation.

    Returns a dict with keys: bod_removed_kg_d, carbonaceous_oxygen_kg_d,
    nitrogenous_oxygen_kg_d, denitrification_credit_kg_d, total_oxygen_kg_d.
    """
    _validate_inputs(
        flow_rate_m3_d,
        influent_bod_mg_l,
        effluent_bod_mg_l,
        influent_tkn_mg_l,
        effluent_tkn_mg_l,
        sludge_production_kg_d,
        denitrified_nitrogen_mg_l,
    )

    bod_removed = flow_rate_m3_d * (influent_bod_mg_l - effluent_bod_mg_l) / 1000.0
    nitrogen_removed = flow_rate_m3_d * (influent_tkn_mg_l - effluent_tkn_mg_l) / 1000.0
    denitrified_n = flow_rate_m3_d * denitrified_nitrogen_mg_l / 1000.0
    carbonaceous = bod_removed - 1.42 * sludge_production_kg_d
    if carbonaceous < 0:
        carbonaceous = 0.0
    nitrogenous = 4.57 * nitrogen_removed
    denitrification_credit = 2.86 * denitrified_n
    total = carbonaceous + nitrogenous - denitrification_credit
    if total < 0:
        total = 0.0

    return {
        "bod_removed_kg_d": round(bod_removed, 2),
        "carbonaceous_oxygen_kg_d": round(carbonaceous, 2),
        "nitrogenous_oxygen_kg_d": round(nitrogenous, 2),
        "denitrification_credit_kg_d": round(denitrification_credit, 2),
        "total_oxygen_kg_d": round(total, 2),
    }
