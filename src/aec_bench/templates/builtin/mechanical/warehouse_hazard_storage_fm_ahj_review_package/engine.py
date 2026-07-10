# ABOUTME: Computes SSC-19 warehouse hazard, sprinkler, and FM/AHJ review metrics.
# ABOUTME: Combines storage hazard, sprinkler demand, water supply, pressure, and review closeout.

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
    storage_area_ft2: float,
    storage_height_ft: float,
    aisle_width_ft: float,
    required_aisle_width_ft: float,
    commodity_hazard_factor: float,
    base_density_gpm_ft2: float,
    remote_area_ft2: float,
    hose_allowance_gpm: float,
    sprinkler_k_factor: float,
    minimum_head_pressure_psi: float,
    available_supply_gpm: float,
    available_pressure_psi: float,
    required_pressure_psi: float,
    review_comments: float,
    resolved_comments: float,
    response_sections: float,
    required_response_sections: float,
    critical_open_comments: float,
) -> dict[str, float]:
    """Compute deterministic warehouse hazard and review metrics."""
    _require_positive(
        storage_area_ft2=storage_area_ft2,
        storage_height_ft=storage_height_ft,
        aisle_width_ft=aisle_width_ft,
        required_aisle_width_ft=required_aisle_width_ft,
        commodity_hazard_factor=commodity_hazard_factor,
        base_density_gpm_ft2=base_density_gpm_ft2,
        remote_area_ft2=remote_area_ft2,
        hose_allowance_gpm=hose_allowance_gpm,
        sprinkler_k_factor=sprinkler_k_factor,
        minimum_head_pressure_psi=minimum_head_pressure_psi,
        available_supply_gpm=available_supply_gpm,
        available_pressure_psi=available_pressure_psi,
        required_pressure_psi=required_pressure_psi,
        review_comments=review_comments,
        response_sections=response_sections,
        required_response_sections=required_response_sections,
    )
    _require_nonnegative(resolved_comments=resolved_comments, critical_open_comments=critical_open_comments)

    sprinkler_density_gpm_ft2 = commodity_hazard_factor * base_density_gpm_ft2
    sprinkler_demand_gpm = remote_area_ft2 * sprinkler_density_gpm_ft2
    total_fire_demand_gpm = sprinkler_demand_gpm + hose_allowance_gpm
    required_remote_head_count = math.ceil(
        sprinkler_demand_gpm / (sprinkler_k_factor * math.sqrt(minimum_head_pressure_psi))
    )
    water_supply_margin_gpm = available_supply_gpm - total_fire_demand_gpm
    pressure_margin_psi = available_pressure_psi - required_pressure_psi
    aisle_width_margin_ft = aisle_width_ft - required_aisle_width_ft
    comment_resolution_fraction = resolved_comments / review_comments
    authority_response_score = response_sections / required_response_sections

    pass_checks = [
        water_supply_margin_gpm >= 0.0,
        pressure_margin_psi >= 0.0,
        aisle_width_margin_ft >= 0.0,
        critical_open_comments == 0.0,
    ]

    return {
        "storage_area_ft2": round(storage_area_ft2, 3),
        "storage_height_ft": round(storage_height_ft, 3),
        "sprinkler_density_gpm_ft2": round(sprinkler_density_gpm_ft2, 3),
        "sprinkler_demand_gpm": round(sprinkler_demand_gpm, 3),
        "total_fire_demand_gpm": round(total_fire_demand_gpm, 3),
        "required_remote_head_count": round(float(required_remote_head_count), 3),
        "water_supply_margin_gpm": round(water_supply_margin_gpm, 3),
        "pressure_margin_psi": round(pressure_margin_psi, 3),
        "aisle_width_margin_ft": round(aisle_width_margin_ft, 3),
        "comment_resolution_fraction": round(comment_resolution_fraction, 3),
        "authority_response_score": round(authority_response_score, 3),
        "critical_open_comments": round(critical_open_comments, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
