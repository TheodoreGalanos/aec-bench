# ABOUTME: Computes SSC-14 wind or solar foundation package metrics.
# ABOUTME: Combines wind pressure, uplift, bearing, sliding, and anchor tension checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    wind_speed_m_s: float,
    wind_pressure_coefficient: float,
    tributary_array_area_m2: float,
    array_dead_load_kpa: float,
    foundation_length_m: float,
    foundation_width_m: float,
    foundation_depth_m: float,
    concrete_unit_weight_kn_m3: float,
    allowable_bearing_kpa: float,
    sliding_friction_coefficient: float,
    horizontal_shear_factor: float,
    anchor_count: int,
    anchor_tension_capacity_kn: float,
) -> dict[str, float]:
    """Compute deterministic SSC-14 renewable foundation metrics."""
    _require_positive(
        wind_speed_m_s=wind_speed_m_s,
        wind_pressure_coefficient=wind_pressure_coefficient,
        tributary_array_area_m2=tributary_array_area_m2,
        foundation_length_m=foundation_length_m,
        foundation_width_m=foundation_width_m,
        foundation_depth_m=foundation_depth_m,
        concrete_unit_weight_kn_m3=concrete_unit_weight_kn_m3,
        allowable_bearing_kpa=allowable_bearing_kpa,
        sliding_friction_coefficient=sliding_friction_coefficient,
        horizontal_shear_factor=horizontal_shear_factor,
        anchor_tension_capacity_kn=anchor_tension_capacity_kn,
    )
    if anchor_count <= 0:
        msg = "anchor_count must be > 0"
        raise ValueError(msg)

    source_velocity_pressure_kpa = 0.613 * wind_speed_m_s**2 / 1000.0
    array_wind_load_kn = source_velocity_pressure_kpa * wind_pressure_coefficient * tributary_array_area_m2
    array_dead_load_kn = array_dead_load_kpa * tributary_array_area_m2
    foundation_self_weight_kn = (
        foundation_length_m * foundation_width_m * foundation_depth_m * concrete_unit_weight_kn_m3
    )
    net_uplift_kn = array_wind_load_kn - array_dead_load_kn - foundation_self_weight_kn
    anchor_group_capacity_kn = anchor_count * anchor_tension_capacity_kn
    uplift_margin_kn = anchor_group_capacity_kn - net_uplift_kn
    bearing_pressure_kpa = (array_dead_load_kn + foundation_self_weight_kn) / (foundation_length_m * foundation_width_m)
    bearing_utilization = bearing_pressure_kpa / allowable_bearing_kpa
    horizontal_shear_kn = array_wind_load_kn * horizontal_shear_factor
    sliding_margin_kn = sliding_friction_coefficient * (array_dead_load_kn + foundation_self_weight_kn)
    sliding_margin_kn -= horizontal_shear_kn
    anchor_tension_per_anchor_kn = max(net_uplift_kn, 0.0) / anchor_count
    anchor_tension_utilization = anchor_tension_per_anchor_kn / anchor_tension_capacity_kn

    pass_checks = [
        uplift_margin_kn >= 0.0,
        bearing_utilization <= 1.0,
        sliding_margin_kn >= 0.0,
        anchor_tension_utilization <= 1.0,
    ]

    return {
        "source_velocity_pressure_kpa": round(source_velocity_pressure_kpa, 3),
        "array_wind_load_kn": round(array_wind_load_kn, 3),
        "array_dead_load_kn": round(array_dead_load_kn, 3),
        "foundation_self_weight_kn": round(foundation_self_weight_kn, 3),
        "net_uplift_kn": round(net_uplift_kn, 3),
        "uplift_margin_kn": round(uplift_margin_kn, 3),
        "bearing_pressure_kpa": round(bearing_pressure_kpa, 3),
        "bearing_utilization": round(bearing_utilization, 3),
        "horizontal_shear_kn": round(horizontal_shear_kn, 3),
        "sliding_margin_kn": round(sliding_margin_kn, 3),
        "anchor_tension_per_anchor_kn": round(anchor_tension_per_anchor_kn, 3),
        "anchor_tension_utilization": round(anchor_tension_utilization, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
