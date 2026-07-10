# ABOUTME: Computes SSC-10 clarifier loading, sludge, and hydraulic constraint metrics.
# ABOUTME: Combines surface loading, solids loading, sludge production, blanket, HRT, and recycle checks.

from __future__ import annotations

import math


def compute(
    flow_rate_m3_d: float,
    clarifier_diameter_m: float,
    mlss_mg_l: float,
    max_sor_m3_m2_d: float,
    max_slr_kg_m2_d: float,
    influent_bod_mg_l: float,
    effluent_bod_mg_l: float,
    sludge_yield_kg_kg_bod: float,
    wasting_capacity_kg_d: float,
    sludge_blanket_limit_m: float,
    measured_sludge_blanket_m: float,
    clarifier_volume_m3: float,
    min_hrt_hr: float,
    recycle_percent: float,
) -> dict[str, float]:
    """Compute source-bound SSC-10 clarifier loading and sludge metrics."""
    surface_area_m2 = math.pi * clarifier_diameter_m**2 / 4.0
    surface_overflow_rate_m3_m2_d = flow_rate_m3_d / surface_area_m2
    sor_margin_m3_m2_d = max_sor_m3_m2_d - surface_overflow_rate_m3_m2_d
    solids_loading_kg_m2_d = flow_rate_m3_d * mlss_mg_l / 1000.0 / surface_area_m2
    slr_margin_kg_m2_d = max_slr_kg_m2_d - solids_loading_kg_m2_d
    bod_removed_kg_d = flow_rate_m3_d * (influent_bod_mg_l - effluent_bod_mg_l) / 1000.0
    sludge_production_kg_d = bod_removed_kg_d * sludge_yield_kg_kg_bod
    wasting_capacity_margin_kg_d = wasting_capacity_kg_d - sludge_production_kg_d
    sludge_blanket_margin_m = sludge_blanket_limit_m - measured_sludge_blanket_m
    clarifier_hrt_hr = clarifier_volume_m3 / flow_rate_m3_d * 24.0
    hrt_margin_hr = clarifier_hrt_hr - min_hrt_hr
    recycle_flow_m3_d = flow_rate_m3_d * recycle_percent / 100.0
    overall_pass_score = (
        1.0
        if min(
            sor_margin_m3_m2_d,
            slr_margin_kg_m2_d,
            wasting_capacity_margin_kg_d,
            sludge_blanket_margin_m,
            hrt_margin_hr,
        )
        >= 0.0
        else 0.0
    )

    return {
        "surface_overflow_rate_m3_m2_d": round(surface_overflow_rate_m3_m2_d, 3),
        "sor_margin_m3_m2_d": round(sor_margin_m3_m2_d, 3),
        "solids_loading_kg_m2_d": round(solids_loading_kg_m2_d, 3),
        "slr_margin_kg_m2_d": round(slr_margin_kg_m2_d, 3),
        "bod_removed_kg_d": round(bod_removed_kg_d, 3),
        "sludge_production_kg_d": round(sludge_production_kg_d, 3),
        "wasting_capacity_margin_kg_d": round(wasting_capacity_margin_kg_d, 3),
        "sludge_blanket_margin_m": round(sludge_blanket_margin_m, 3),
        "clarifier_hrt_hr": round(clarifier_hrt_hr, 3),
        "hrt_margin_hr": round(hrt_margin_hr, 3),
        "recycle_flow_m3_d": round(recycle_flow_m3_d, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
