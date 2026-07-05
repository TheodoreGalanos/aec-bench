# ABOUTME: Computes SSC-09 facade pressure-zone difference and re-entrant geometry metrics.
# ABOUTME: Compares baseline and variant corner-zone loads, utilization, and support reassignment.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    baseline_corner_zone_area_m2: float,
    variant_corner_zone_area_m2: float,
    baseline_pressure_kpa: float,
    variant_pressure_kpa: float,
    tributary_area_m2: float,
    dead_load_kpa: float,
    anchor_tension_capacity_kn: float,
    anchor_shear_capacity_kn: float,
    allowable_utilization: float,
    support_points_reassigned: float,
    support_points_required: float,
) -> dict[str, float]:
    """Compute deterministic facade zone difference and support reassignment metrics."""
    _require_positive(
        baseline_corner_zone_area_m2=baseline_corner_zone_area_m2,
        variant_corner_zone_area_m2=variant_corner_zone_area_m2,
        baseline_pressure_kpa=baseline_pressure_kpa,
        variant_pressure_kpa=variant_pressure_kpa,
        tributary_area_m2=tributary_area_m2,
        dead_load_kpa=dead_load_kpa,
        anchor_tension_capacity_kn=anchor_tension_capacity_kn,
        anchor_shear_capacity_kn=anchor_shear_capacity_kn,
        allowable_utilization=allowable_utilization,
        support_points_required=support_points_required,
    )

    corner_zone_area_delta_m2 = variant_corner_zone_area_m2 - baseline_corner_zone_area_m2
    corner_zone_area_delta_percent = corner_zone_area_delta_m2 / baseline_corner_zone_area_m2 * 100.0
    pressure_delta_kpa = variant_pressure_kpa - baseline_pressure_kpa
    baseline_corner_load_kn = baseline_pressure_kpa * tributary_area_m2
    variant_corner_load_kn = variant_pressure_kpa * tributary_area_m2
    corner_load_delta_kn = variant_corner_load_kn - baseline_corner_load_kn
    dead_load_kn = dead_load_kpa * tributary_area_m2
    baseline_utilization = math.hypot(
        baseline_corner_load_kn / anchor_tension_capacity_kn,
        dead_load_kn / anchor_shear_capacity_kn,
    )
    variant_utilization = math.hypot(
        variant_corner_load_kn / anchor_tension_capacity_kn,
        dead_load_kn / anchor_shear_capacity_kn,
    )
    utilization_delta = variant_utilization - baseline_utilization
    utilization_margin = allowable_utilization - variant_utilization
    support_reassignment_fraction = support_points_reassigned / support_points_required

    pass_checks = [
        corner_zone_area_delta_m2 >= 0.0,
        pressure_delta_kpa >= 0.0,
        utilization_margin >= 0.0,
        support_reassignment_fraction >= 1.0,
    ]

    return {
        "corner_zone_area_delta_m2": round(corner_zone_area_delta_m2, 3),
        "corner_zone_area_delta_percent": round(corner_zone_area_delta_percent, 3),
        "pressure_delta_kpa": round(pressure_delta_kpa, 3),
        "baseline_corner_load_kn": round(baseline_corner_load_kn, 3),
        "variant_corner_load_kn": round(variant_corner_load_kn, 3),
        "corner_load_delta_kn": round(corner_load_delta_kn, 3),
        "baseline_utilization": round(baseline_utilization, 3),
        "variant_utilization": round(variant_utilization, 3),
        "utilization_delta": round(utilization_delta, 3),
        "utilization_margin": round(utilization_margin, 3),
        "support_reassignment_fraction": round(support_reassignment_fraction, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
