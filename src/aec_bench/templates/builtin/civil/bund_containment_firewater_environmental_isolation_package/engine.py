# ABOUTME: Computes SSC-19 bund containment, firewater runoff, and isolation metrics.
# ABOUTME: Combines bund volume, rainfall, displacement, firewater runoff, sump capacity, and valve checks.

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
    largest_container_l: float,
    rainfall_depth_mm: float,
    bund_area_m2: float,
    foam_allowance_l: float,
    equipment_displacement_l: float,
    bund_capacity_l: float,
    firewater_flow_l_s: float,
    firewater_duration_min: float,
    isolation_sump_capacity_l: float,
    environmental_freeboard_l: float,
    outlet_headloss_m: float,
    max_outlet_headloss_m: float,
    isolation_valves_total: float,
    isolation_valves_verified: float,
) -> dict[str, float]:
    """Compute deterministic bund containment and isolation metrics."""
    _require_positive(
        largest_container_l=largest_container_l,
        rainfall_depth_mm=rainfall_depth_mm,
        bund_area_m2=bund_area_m2,
        foam_allowance_l=foam_allowance_l,
        bund_capacity_l=bund_capacity_l,
        firewater_flow_l_s=firewater_flow_l_s,
        firewater_duration_min=firewater_duration_min,
        isolation_sump_capacity_l=isolation_sump_capacity_l,
        environmental_freeboard_l=environmental_freeboard_l,
        max_outlet_headloss_m=max_outlet_headloss_m,
        isolation_valves_total=isolation_valves_total,
    )
    _require_nonnegative(
        equipment_displacement_l=equipment_displacement_l,
        outlet_headloss_m=outlet_headloss_m,
        isolation_valves_verified=isolation_valves_verified,
    )

    rainfall_allowance_l = rainfall_depth_mm / 1000.0 * bund_area_m2 * 1000.0
    required_bund_volume_l = largest_container_l + rainfall_allowance_l + foam_allowance_l - equipment_displacement_l
    bund_capacity_margin_l = bund_capacity_l - required_bund_volume_l
    firewater_runoff_volume_l = firewater_flow_l_s * firewater_duration_min * 60.0
    isolation_required_volume_l = firewater_runoff_volume_l + environmental_freeboard_l
    isolation_capacity_margin_l = isolation_sump_capacity_l - isolation_required_volume_l
    headloss_margin_m = max_outlet_headloss_m - outlet_headloss_m
    valve_verification_fraction = isolation_valves_verified / isolation_valves_total

    pass_checks = [
        bund_capacity_margin_l >= 0.0,
        isolation_capacity_margin_l >= 0.0,
        headloss_margin_m >= 0.0,
        valve_verification_fraction >= 1.0,
    ]

    return {
        "rainfall_allowance_l": round(rainfall_allowance_l, 3),
        "required_bund_volume_l": round(required_bund_volume_l, 3),
        "bund_capacity_margin_l": round(bund_capacity_margin_l, 3),
        "firewater_runoff_volume_l": round(firewater_runoff_volume_l, 3),
        "isolation_required_volume_l": round(isolation_required_volume_l, 3),
        "isolation_capacity_margin_l": round(isolation_capacity_margin_l, 3),
        "headloss_margin_m": round(headloss_margin_m, 3),
        "valve_verification_fraction": round(valve_verification_fraction, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
