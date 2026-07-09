# ABOUTME: Computes SSC-15 concrete mix compliance and use-case metrics.
# ABOUTME: Combines strength, SCM, bearing, exposure, drainage, and evidence checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    specified_strength_mpa: float,
    submitted_mean_strength_mpa: float,
    standard_deviation_mpa: float,
    target_strength_factor: float,
    scm_replacement_percent: float,
    max_scm_replacement_percent: float,
    bearing_capacity_kpa: float,
    bearing_demand_kpa: float,
    exposure_cover_provided_mm: float,
    exposure_cover_required_mm: float,
    drainage_freeboard_provided_m: float,
    drainage_freeboard_required_m: float,
    matching_evidence_items: float,
    required_evidence_items: float,
) -> dict[str, float]:
    _require_positive(
        specified_strength_mpa=specified_strength_mpa,
        submitted_mean_strength_mpa=submitted_mean_strength_mpa,
        standard_deviation_mpa=standard_deviation_mpa,
        target_strength_factor=target_strength_factor,
        max_scm_replacement_percent=max_scm_replacement_percent,
        bearing_capacity_kpa=bearing_capacity_kpa,
        bearing_demand_kpa=bearing_demand_kpa,
        exposure_cover_required_mm=exposure_cover_required_mm,
        drainage_freeboard_required_m=drainage_freeboard_required_m,
        required_evidence_items=required_evidence_items,
    )

    target_mean_strength_mpa = specified_strength_mpa + target_strength_factor * standard_deviation_mpa
    strength_margin_mpa = submitted_mean_strength_mpa - target_mean_strength_mpa
    scm_replacement_margin_percent = max_scm_replacement_percent - scm_replacement_percent
    bearing_capacity_margin_kpa = bearing_capacity_kpa - bearing_demand_kpa
    bearing_utilization = bearing_demand_kpa / bearing_capacity_kpa
    exposure_cover_margin_mm = exposure_cover_provided_mm - exposure_cover_required_mm
    drainage_freeboard_margin_m = drainage_freeboard_provided_m - drainage_freeboard_required_m
    mix_evidence_match_fraction = matching_evidence_items / required_evidence_items

    overall_pass_score = (
        1.0
        if (
            strength_margin_mpa >= 0.0
            and scm_replacement_margin_percent >= 0.0
            and bearing_capacity_margin_kpa >= 0.0
            and exposure_cover_margin_mm >= 0.0
            and drainage_freeboard_margin_m >= 0.0
            and mix_evidence_match_fraction >= 1.0
        )
        else 0.0
    )

    return {
        "target_mean_strength_mpa": round(target_mean_strength_mpa, 3),
        "strength_margin_mpa": round(strength_margin_mpa, 3),
        "scm_replacement_margin_percent": round(scm_replacement_margin_percent, 3),
        "bearing_capacity_margin_kpa": round(bearing_capacity_margin_kpa, 3),
        "bearing_utilization": round(bearing_utilization, 3),
        "exposure_cover_margin_mm": round(exposure_cover_margin_mm, 3),
        "drainage_freeboard_margin_m": round(drainage_freeboard_margin_m, 3),
        "mix_evidence_match_fraction": round(mix_evidence_match_fraction, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
