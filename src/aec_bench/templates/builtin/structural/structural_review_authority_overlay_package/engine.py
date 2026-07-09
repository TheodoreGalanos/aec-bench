# ABOUTME: Computes SSC-14 structural review packet and authority overlay metrics.
# ABOUTME: Combines load combinations, material evidence, comment closeout, and authority flags.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    dead_load_kn: float,
    live_load_kn: float,
    wind_load_kn: float,
    uls_dead_factor: float,
    uls_live_factor: float,
    uls_wind_factor: float,
    sls_wind_factor: float,
    member_capacity_kn: float,
    sls_deflection_limit_mm: float,
    calculated_sls_deflection_mm: float,
    carbon_percent: float,
    manganese_percent: float,
    chromium_percent: float,
    molybdenum_percent: float,
    vanadium_percent: float,
    nickel_percent: float,
    copper_percent: float,
    carbon_equivalent_limit: float,
    required_evidence_items: float,
    present_evidence_items: float,
    review_comment_count: float,
    closed_review_comment_count: float,
    unresolved_critical_comments: float,
    authority_override_count: float,
    minimum_evidence_percent: float,
    minimum_comment_closeout_percent: float,
) -> dict[str, float]:
    """Compute deterministic SSC-14 structural review and authority overlay metrics."""
    _require_positive(
        uls_dead_factor=uls_dead_factor,
        uls_live_factor=uls_live_factor,
        uls_wind_factor=uls_wind_factor,
        member_capacity_kn=member_capacity_kn,
        sls_deflection_limit_mm=sls_deflection_limit_mm,
        carbon_equivalent_limit=carbon_equivalent_limit,
        required_evidence_items=required_evidence_items,
        review_comment_count=review_comment_count,
        minimum_evidence_percent=minimum_evidence_percent,
        minimum_comment_closeout_percent=minimum_comment_closeout_percent,
    )

    governing_uls_load_kn = uls_dead_factor * dead_load_kn + uls_live_factor * live_load_kn
    governing_uls_load_kn += uls_wind_factor * wind_load_kn
    governing_sls_load_kn = dead_load_kn + live_load_kn + sls_wind_factor * wind_load_kn
    uls_capacity_margin_kn = member_capacity_kn - governing_uls_load_kn
    sls_deflection_margin_mm = sls_deflection_limit_mm - calculated_sls_deflection_mm
    material_carbon_equivalent = (
        carbon_percent
        + manganese_percent / 6.0
        + (chromium_percent + molybdenum_percent + vanadium_percent) / 5.0
        + (nickel_percent + copper_percent) / 15.0
    )
    carbon_equivalent_margin = carbon_equivalent_limit - material_carbon_equivalent
    evidence_complete_percent = present_evidence_items / required_evidence_items * 100.0
    comment_closeout_percent = closed_review_comment_count / review_comment_count * 100.0

    pass_checks = [
        uls_capacity_margin_kn >= 0.0,
        sls_deflection_margin_mm >= 0.0,
        carbon_equivalent_margin >= 0.0,
        evidence_complete_percent >= minimum_evidence_percent,
        comment_closeout_percent >= minimum_comment_closeout_percent,
        unresolved_critical_comments == 0.0,
    ]

    return {
        "governing_uls_load_kn": round(governing_uls_load_kn, 3),
        "governing_sls_load_kn": round(governing_sls_load_kn, 3),
        "uls_capacity_margin_kn": round(uls_capacity_margin_kn, 3),
        "sls_deflection_margin_mm": round(sls_deflection_margin_mm, 3),
        "material_carbon_equivalent": round(material_carbon_equivalent, 3),
        "carbon_equivalent_margin": round(carbon_equivalent_margin, 3),
        "evidence_complete_percent": round(evidence_complete_percent, 3),
        "comment_closeout_percent": round(comment_closeout_percent, 3),
        "unresolved_critical_comments": round(unresolved_critical_comments, 3),
        "authority_override_count": round(authority_override_count, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
