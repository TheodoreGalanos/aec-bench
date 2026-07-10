# ABOUTME: Computes SSC-09 envelope access, maintenance, and safety metrics.
# ABOUTME: Combines maintenance live load, wind screen load, fall arrest, access width, and tolerance checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    access_platform_area_m2: float,
    maintenance_live_load_kpa: float,
    access_support_capacity_kn: float,
    wind_pressure_kpa: float,
    wind_screen_area_m2: float,
    wind_anchor_capacity_kn: float,
    fall_arrest_user_count: float,
    fall_arrest_load_kn_per_user: float,
    fall_arrest_anchor_capacity_kn: float,
    access_clear_width_m: float,
    required_access_width_m: float,
    measured_tolerance_gap_mm: float,
    allowable_tolerance_gap_mm: float,
) -> dict[str, float]:
    """Compute deterministic envelope access and maintenance safety metrics."""
    _require_positive(
        access_platform_area_m2=access_platform_area_m2,
        maintenance_live_load_kpa=maintenance_live_load_kpa,
        access_support_capacity_kn=access_support_capacity_kn,
        wind_pressure_kpa=wind_pressure_kpa,
        wind_screen_area_m2=wind_screen_area_m2,
        wind_anchor_capacity_kn=wind_anchor_capacity_kn,
        fall_arrest_user_count=fall_arrest_user_count,
        fall_arrest_load_kn_per_user=fall_arrest_load_kn_per_user,
        fall_arrest_anchor_capacity_kn=fall_arrest_anchor_capacity_kn,
        access_clear_width_m=access_clear_width_m,
        required_access_width_m=required_access_width_m,
        allowable_tolerance_gap_mm=allowable_tolerance_gap_mm,
    )

    maintenance_live_load_kn = access_platform_area_m2 * maintenance_live_load_kpa
    maintenance_load_margin_kn = access_support_capacity_kn - maintenance_live_load_kn
    wind_screen_load_kn = wind_pressure_kpa * wind_screen_area_m2
    wind_anchor_margin_kn = wind_anchor_capacity_kn - wind_screen_load_kn
    fall_arrest_demand_kn = fall_arrest_user_count * fall_arrest_load_kn_per_user
    fall_arrest_margin_kn = fall_arrest_anchor_capacity_kn - fall_arrest_demand_kn
    access_width_margin_m = access_clear_width_m - required_access_width_m
    tolerance_margin_mm = allowable_tolerance_gap_mm - measured_tolerance_gap_mm

    pass_checks = [
        maintenance_load_margin_kn >= 0.0,
        wind_anchor_margin_kn >= 0.0,
        fall_arrest_margin_kn >= 0.0,
        access_width_margin_m >= 0.0,
        tolerance_margin_mm >= 0.0,
    ]

    return {
        "maintenance_live_load_kn": round(maintenance_live_load_kn, 3),
        "maintenance_load_margin_kn": round(maintenance_load_margin_kn, 3),
        "wind_screen_load_kn": round(wind_screen_load_kn, 3),
        "wind_anchor_margin_kn": round(wind_anchor_margin_kn, 3),
        "fall_arrest_demand_kn": round(fall_arrest_demand_kn, 3),
        "fall_arrest_margin_kn": round(fall_arrest_margin_kn, 3),
        "access_width_margin_m": round(access_width_margin_m, 3),
        "tolerance_margin_mm": round(tolerance_margin_mm, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
