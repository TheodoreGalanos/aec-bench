# ABOUTME: Computes SSC-09 rainscreen drainage, cavity, fire stop, and material-review metrics.
# ABOUTME: Combines cavity/drainage margins, evidence completeness, fire spacing, thermal breaks, and review closure.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _require_nonnegative(**values: float) -> None:
    """Raise ValueError when any supplied value is negative."""
    for name, value in values.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)


def compute(
    cavity_depth_mm: float,
    minimum_cavity_depth_mm: float,
    open_joint_area_cm2_m: float,
    required_vent_area_cm2_m: float,
    drainage_slot_area_cm2: float,
    required_drainage_slot_area_cm2: float,
    product_documents_submitted: float,
    product_documents_required: float,
    fire_stop_spacing_m: float,
    max_fire_stop_spacing_m: float,
    thermal_break_count: float,
    bracket_count: float,
    review_comments: float,
    resolved_review_comments: float,
    critical_open_comments: float,
) -> dict[str, float]:
    """Compute deterministic rainscreen cavity, fire, and material review metrics."""
    _require_positive(
        cavity_depth_mm=cavity_depth_mm,
        minimum_cavity_depth_mm=minimum_cavity_depth_mm,
        open_joint_area_cm2_m=open_joint_area_cm2_m,
        required_vent_area_cm2_m=required_vent_area_cm2_m,
        drainage_slot_area_cm2=drainage_slot_area_cm2,
        required_drainage_slot_area_cm2=required_drainage_slot_area_cm2,
        product_documents_required=product_documents_required,
        fire_stop_spacing_m=fire_stop_spacing_m,
        max_fire_stop_spacing_m=max_fire_stop_spacing_m,
        bracket_count=bracket_count,
        review_comments=review_comments,
    )
    _require_nonnegative(
        product_documents_submitted=product_documents_submitted,
        thermal_break_count=thermal_break_count,
        resolved_review_comments=resolved_review_comments,
        critical_open_comments=critical_open_comments,
    )

    cavity_depth_margin_mm = cavity_depth_mm - minimum_cavity_depth_mm
    vent_area_margin_cm2_m = open_joint_area_cm2_m - required_vent_area_cm2_m
    drainage_slot_margin_cm2 = drainage_slot_area_cm2 - required_drainage_slot_area_cm2
    material_evidence_score = product_documents_submitted / product_documents_required
    fire_stop_spacing_margin_m = max_fire_stop_spacing_m - fire_stop_spacing_m
    thermal_break_coverage_fraction = thermal_break_count / bracket_count
    review_resolution_fraction = resolved_review_comments / review_comments

    pass_checks = [
        cavity_depth_margin_mm >= 0.0,
        vent_area_margin_cm2_m >= 0.0,
        drainage_slot_margin_cm2 >= 0.0,
        material_evidence_score >= 0.9,
        fire_stop_spacing_margin_m >= 0.0,
        thermal_break_coverage_fraction >= 0.95,
        review_resolution_fraction >= 1.0,
        critical_open_comments == 0.0,
    ]

    return {
        "cavity_depth_margin_mm": round(cavity_depth_margin_mm, 3),
        "vent_area_margin_cm2_m": round(vent_area_margin_cm2_m, 3),
        "drainage_slot_margin_cm2": round(drainage_slot_margin_cm2, 3),
        "material_evidence_score": round(material_evidence_score, 3),
        "fire_stop_spacing_margin_m": round(fire_stop_spacing_margin_m, 3),
        "thermal_break_coverage_fraction": round(thermal_break_coverage_fraction, 3),
        "review_resolution_fraction": round(review_resolution_fraction, 3),
        "critical_open_comments": round(critical_open_comments, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
