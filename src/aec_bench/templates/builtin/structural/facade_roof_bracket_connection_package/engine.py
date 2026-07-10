# ABOUTME: Computes SSC-14 facade or roof bracket connection package metrics.
# ABOUTME: Combines wind tributary reactions, anchor checks, and material certificate screening.

from __future__ import annotations

import math


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
    wind_pressure_kpa: float,
    tributary_width_m: float,
    tributary_height_m: float,
    facade_dead_load_kpa: float,
    wind_load_factor: float,
    dead_load_factor: float,
    bracket_horizontal_capacity_kn: float,
    anchor_tension_capacity_kn: float,
    anchor_shear_capacity_kn: float,
    active_anchor_count: int,
    carbon_percent: float,
    manganese_percent: float,
    chromium_percent: float,
    molybdenum_percent: float,
    vanadium_percent: float,
    nickel_percent: float,
    copper_percent: float,
    carbon_equivalent_limit: float,
) -> dict[str, float]:
    """Compute deterministic SSC-14 facade or roof bracket connection metrics."""
    _require_positive(
        wind_pressure_kpa=wind_pressure_kpa,
        tributary_width_m=tributary_width_m,
        tributary_height_m=tributary_height_m,
        wind_load_factor=wind_load_factor,
        dead_load_factor=dead_load_factor,
        bracket_horizontal_capacity_kn=bracket_horizontal_capacity_kn,
        anchor_tension_capacity_kn=anchor_tension_capacity_kn,
        anchor_shear_capacity_kn=anchor_shear_capacity_kn,
        carbon_equivalent_limit=carbon_equivalent_limit,
    )
    _require_nonnegative(
        facade_dead_load_kpa=facade_dead_load_kpa,
        carbon_percent=carbon_percent,
        manganese_percent=manganese_percent,
        chromium_percent=chromium_percent,
        molybdenum_percent=molybdenum_percent,
        vanadium_percent=vanadium_percent,
        nickel_percent=nickel_percent,
        copper_percent=copper_percent,
    )
    if active_anchor_count <= 0:
        msg = "active_anchor_count must be > 0"
        raise ValueError(msg)

    tributary_area_m2 = tributary_width_m * tributary_height_m
    service_wind_load_kn = wind_pressure_kpa * tributary_area_m2
    service_dead_load_kn = facade_dead_load_kpa * tributary_area_m2
    factored_out_of_plane_reaction_kn = service_wind_load_kn * wind_load_factor
    factored_vertical_reaction_kn = service_dead_load_kn * dead_load_factor
    bracket_utilization = factored_out_of_plane_reaction_kn / bracket_horizontal_capacity_kn
    anchor_tension_per_anchor_kn = factored_out_of_plane_reaction_kn / active_anchor_count
    anchor_shear_per_anchor_kn = factored_vertical_reaction_kn / active_anchor_count
    anchor_combined_utilization = math.hypot(
        anchor_tension_per_anchor_kn / anchor_tension_capacity_kn,
        anchor_shear_per_anchor_kn / anchor_shear_capacity_kn,
    )
    carbon_equivalent = (
        carbon_percent
        + manganese_percent / 6.0
        + (chromium_percent + molybdenum_percent + vanadium_percent) / 5.0
        + (nickel_percent + copper_percent) / 15.0
    )
    carbon_equivalent_margin = carbon_equivalent_limit - carbon_equivalent

    pass_checks = [
        bracket_utilization <= 1.0,
        anchor_combined_utilization <= 1.0,
        carbon_equivalent_margin >= 0.0,
    ]

    return {
        "tributary_area_m2": round(tributary_area_m2, 3),
        "service_wind_load_kn": round(service_wind_load_kn, 3),
        "service_dead_load_kn": round(service_dead_load_kn, 3),
        "factored_out_of_plane_reaction_kn": round(factored_out_of_plane_reaction_kn, 3),
        "factored_vertical_reaction_kn": round(factored_vertical_reaction_kn, 3),
        "bracket_utilization": round(bracket_utilization, 3),
        "anchor_tension_per_anchor_kn": round(anchor_tension_per_anchor_kn, 3),
        "anchor_shear_per_anchor_kn": round(anchor_shear_per_anchor_kn, 3),
        "anchor_combined_utilization": round(anchor_combined_utilization, 3),
        "carbon_equivalent": round(carbon_equivalent, 3),
        "carbon_equivalent_margin": round(carbon_equivalent_margin, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
