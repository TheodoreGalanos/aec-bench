# ABOUTME: Computes SSC-19 fire-water sprinkler storage package metrics.
# ABOUTME: Combines hydrant flow, sprinkler demand, riser losses, pump boost, and tank storage.

from __future__ import annotations

import math

_FLOW_EXPONENT = 0.54
_HAZEN_WILLIAMS_COEFFICIENT = 4.52
_PSI_PER_FT_WATER = 0.433


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
    sprinkler_design_area_ft2: float,
    sprinkler_density_gpm_ft2: float,
    hose_allowance_gpm: float,
    sprinkler_head_k_factor_gpm_sqrt_psi: float,
    minimum_head_pressure_psi: float,
    installed_remote_head_count: float,
    hydrant_static_pressure_psi: float,
    hydrant_residual_pressure_psi: float,
    hydrant_test_flow_gpm: float,
    target_residual_pressure_psi: float,
    riser_pipe_length_ft: float,
    riser_fitting_equivalent_length_ft: float,
    riser_pipe_internal_diameter_in: float,
    hazen_williams_c: float,
    elevation_gain_ft: float,
    pump_boost_pressure_psi: float,
    remote_area_allowance_psi: float,
    required_duration_min: float,
    available_storage_gal: float,
) -> dict[str, float]:
    """Compute source-bound fire-water, sprinkler demand, and storage metrics."""
    _require_positive(
        sprinkler_design_area_ft2=sprinkler_design_area_ft2,
        sprinkler_density_gpm_ft2=sprinkler_density_gpm_ft2,
        sprinkler_head_k_factor_gpm_sqrt_psi=sprinkler_head_k_factor_gpm_sqrt_psi,
        minimum_head_pressure_psi=minimum_head_pressure_psi,
        installed_remote_head_count=installed_remote_head_count,
        hydrant_static_pressure_psi=hydrant_static_pressure_psi,
        hydrant_test_flow_gpm=hydrant_test_flow_gpm,
        target_residual_pressure_psi=target_residual_pressure_psi,
        riser_pipe_length_ft=riser_pipe_length_ft,
        riser_pipe_internal_diameter_in=riser_pipe_internal_diameter_in,
        hazen_williams_c=hazen_williams_c,
        required_duration_min=required_duration_min,
        available_storage_gal=available_storage_gal,
    )
    _require_nonnegative(
        hose_allowance_gpm=hose_allowance_gpm,
        hydrant_residual_pressure_psi=hydrant_residual_pressure_psi,
        riser_fitting_equivalent_length_ft=riser_fitting_equivalent_length_ft,
        elevation_gain_ft=elevation_gain_ft,
        pump_boost_pressure_psi=pump_boost_pressure_psi,
        remote_area_allowance_psi=remote_area_allowance_psi,
    )
    if hydrant_residual_pressure_psi >= hydrant_static_pressure_psi:
        msg = "hydrant_residual_pressure_psi must be < hydrant_static_pressure_psi"
        raise ValueError(msg)
    if target_residual_pressure_psi >= hydrant_static_pressure_psi:
        msg = "target_residual_pressure_psi must be < hydrant_static_pressure_psi"
        raise ValueError(msg)

    sprinkler_demand_gpm = sprinkler_design_area_ft2 * sprinkler_density_gpm_ft2
    total_fire_demand_gpm = sprinkler_demand_gpm + hose_allowance_gpm
    sprinkler_head_discharge_gpm = sprinkler_head_k_factor_gpm_sqrt_psi * math.sqrt(minimum_head_pressure_psi)
    required_remote_head_count = math.ceil(sprinkler_demand_gpm / sprinkler_head_discharge_gpm)
    remote_head_count_margin = installed_remote_head_count - required_remote_head_count

    pressure_drop_test_psi = hydrant_static_pressure_psi - hydrant_residual_pressure_psi
    target_pressure_drop_psi = hydrant_static_pressure_psi - target_residual_pressure_psi
    supply_curve_coefficient = hydrant_test_flow_gpm / pressure_drop_test_psi**_FLOW_EXPONENT
    available_flow_20psi_gpm = supply_curve_coefficient * target_pressure_drop_psi**_FLOW_EXPONENT
    water_supply_flow_margin_gpm = available_flow_20psi_gpm - total_fire_demand_gpm
    residual_pressure_at_demand_psi = hydrant_static_pressure_psi - (
        total_fire_demand_gpm / supply_curve_coefficient
    ) ** (1.0 / _FLOW_EXPONENT)

    friction_loss_per_ft_psi = (
        _HAZEN_WILLIAMS_COEFFICIENT
        * total_fire_demand_gpm**1.85
        / (hazen_williams_c**1.85 * riser_pipe_internal_diameter_in**4.87)
    )
    equivalent_length_ft = riser_pipe_length_ft + riser_fitting_equivalent_length_ft
    total_friction_loss_psi = friction_loss_per_ft_psi * equivalent_length_ft
    elevation_pressure_loss_psi = _PSI_PER_FT_WATER * elevation_gain_ft
    available_riser_pressure_psi = (
        residual_pressure_at_demand_psi - total_friction_loss_psi - elevation_pressure_loss_psi
    )
    boosted_riser_pressure_psi = available_riser_pressure_psi + pump_boost_pressure_psi
    required_riser_pressure_psi = minimum_head_pressure_psi + remote_area_allowance_psi
    pressure_margin_psi = boosted_riser_pressure_psi - required_riser_pressure_psi

    required_storage_gal = total_fire_demand_gpm * required_duration_min
    storage_margin_gal = available_storage_gal - required_storage_gal
    overall_pass_score = (
        1.0
        if min(
            remote_head_count_margin,
            water_supply_flow_margin_gpm,
            pressure_margin_psi,
            storage_margin_gal,
        )
        >= 0.0
        else 0.0
    )

    return {
        "sprinkler_demand_gpm": round(sprinkler_demand_gpm, 3),
        "total_fire_demand_gpm": round(total_fire_demand_gpm, 3),
        "sprinkler_head_discharge_gpm": round(sprinkler_head_discharge_gpm, 3),
        "required_remote_head_count": round(float(required_remote_head_count), 3),
        "remote_head_count_margin": round(remote_head_count_margin, 3),
        "pressure_drop_test_psi": round(pressure_drop_test_psi, 3),
        "supply_curve_coefficient": round(supply_curve_coefficient, 3),
        "available_flow_20psi_gpm": round(available_flow_20psi_gpm, 3),
        "water_supply_flow_margin_gpm": round(water_supply_flow_margin_gpm, 3),
        "residual_pressure_at_demand_psi": round(residual_pressure_at_demand_psi, 3),
        "friction_loss_per_ft_psi": round(friction_loss_per_ft_psi, 4),
        "equivalent_length_ft": round(equivalent_length_ft, 3),
        "total_friction_loss_psi": round(total_friction_loss_psi, 3),
        "elevation_pressure_loss_psi": round(elevation_pressure_loss_psi, 3),
        "available_riser_pressure_psi": round(available_riser_pressure_psi, 3),
        "boosted_riser_pressure_psi": round(boosted_riser_pressure_psi, 3),
        "required_riser_pressure_psi": round(required_riser_pressure_psi, 3),
        "pressure_margin_psi": round(pressure_margin_psi, 3),
        "required_storage_gal": round(required_storage_gal, 3),
        "storage_margin_gal": round(storage_margin_gal, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
