# ABOUTME: Carbon equivalent computation engine for structural steel weldability checks.
# ABOUTME: Calculates IIW carbon equivalent and numeric weldability risk indicators.


def _validate_inputs(
    carbon_pct: float,
    manganese_pct: float,
    chromium_pct: float,
    molybdenum_pct: float,
    vanadium_pct: float,
    nickel_pct: float,
    copper_pct: float,
    caution_threshold_pct: float,
    high_risk_threshold_pct: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    values = {
        "carbon_pct": carbon_pct,
        "manganese_pct": manganese_pct,
        "chromium_pct": chromium_pct,
        "molybdenum_pct": molybdenum_pct,
        "vanadium_pct": vanadium_pct,
        "nickel_pct": nickel_pct,
        "copper_pct": copper_pct,
        "caution_threshold_pct": caution_threshold_pct,
        "high_risk_threshold_pct": high_risk_threshold_pct,
    }
    for name, value in values.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)
    if caution_threshold_pct >= high_risk_threshold_pct:
        msg = "caution_threshold_pct must be < high_risk_threshold_pct"
        raise ValueError(msg)


def compute(
    carbon_pct: float,
    manganese_pct: float,
    chromium_pct: float,
    molybdenum_pct: float,
    vanadium_pct: float,
    nickel_pct: float,
    copper_pct: float,
    caution_threshold_pct: float,
    high_risk_threshold_pct: float,
) -> dict[str, float]:
    """Compute IIW carbon equivalent and numeric weldability risk.

    Returns a dict with keys: carbon_equivalent_pct, caution_margin_pct,
    high_risk_margin_pct, weldability_risk_index, preheat_indicated.
    """
    _validate_inputs(
        carbon_pct,
        manganese_pct,
        chromium_pct,
        molybdenum_pct,
        vanadium_pct,
        nickel_pct,
        copper_pct,
        caution_threshold_pct,
        high_risk_threshold_pct,
    )

    ce = (
        carbon_pct
        + manganese_pct / 6.0
        + (chromium_pct + molybdenum_pct + vanadium_pct) / 5.0
        + (nickel_pct + copper_pct) / 15.0
    )
    caution_margin = ce - caution_threshold_pct
    high_risk_margin = ce - high_risk_threshold_pct

    if ce < caution_threshold_pct:
        risk_index = 0.0
    elif ce < high_risk_threshold_pct:
        risk_index = 1.0
    else:
        risk_index = 2.0

    return {
        "carbon_equivalent_pct": round(ce, 2),
        "caution_margin_pct": round(caution_margin, 2),
        "high_risk_margin_pct": round(high_risk_margin, 2),
        "weldability_risk_index": round(risk_index, 2),
        "preheat_indicated": round(1.0 if ce >= caution_threshold_pct else 0.0, 2),
    }
