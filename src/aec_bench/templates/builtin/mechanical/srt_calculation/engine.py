# ABOUTME: Solids retention time computation engine for activated sludge systems.
# ABOUTME: Calculates system solids, daily solids loss, and mean cell residence time.


def _validate_inputs(
    aeration_volume_m3: float,
    mlss_concentration_mg_l: float,
    was_flow_m3_d: float,
    was_tss_mg_l: float,
    effluent_tss_mg_l: float,
    effluent_flow_m3_d: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "aeration_volume_m3": aeration_volume_m3,
        "mlss_concentration_mg_l": mlss_concentration_mg_l,
        "was_flow_m3_d": was_flow_m3_d,
        "was_tss_mg_l": was_tss_mg_l,
        "effluent_flow_m3_d": effluent_flow_m3_d,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)
    if effluent_tss_mg_l < 0:
        msg = "effluent_tss_mg_l must be >= 0"
        raise ValueError(msg)


def compute(
    aeration_volume_m3: float,
    mlss_concentration_mg_l: float,
    was_flow_m3_d: float,
    was_tss_mg_l: float,
    effluent_tss_mg_l: float,
    effluent_flow_m3_d: float,
) -> dict[str, float]:
    """Compute activated sludge solids retention time.

    Returns a dict with keys: solids_in_system_kg, solids_wasted_kg_d,
    effluent_solids_loss_kg_d, total_solids_loss_kg_d, srt_days.
    """
    _validate_inputs(
        aeration_volume_m3,
        mlss_concentration_mg_l,
        was_flow_m3_d,
        was_tss_mg_l,
        effluent_tss_mg_l,
        effluent_flow_m3_d,
    )

    solids_inventory = aeration_volume_m3 * mlss_concentration_mg_l / 1000.0
    solids_wasted = was_flow_m3_d * was_tss_mg_l / 1000.0
    effluent_loss = effluent_flow_m3_d * effluent_tss_mg_l / 1000.0
    total_loss = solids_wasted + effluent_loss
    srt = solids_inventory / total_loss

    return {
        "solids_in_system_kg": round(solids_inventory, 2),
        "solids_wasted_kg_d": round(solids_wasted, 2),
        "effluent_solids_loss_kg_d": round(effluent_loss, 2),
        "total_solids_loss_kg_d": round(total_loss, 2),
        "srt_days": round(srt, 2),
    }
