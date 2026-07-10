# ABOUTME: Computes SSC-04 sea-level-rise scenario and asset-level review metrics.
# ABOUTME: Combines future level, freeboard, service, adaptation, cost, and traceability checks.

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
    present_high_tide_level_m: float,
    sea_level_rise_allowance_m: float,
    storm_surge_allowance_m: float,
    wave_allowance_m: float,
    asset_elevation_m: float,
    required_freeboard_m: float,
    service_threshold_m: float,
    adaptation_budget_usd: float,
    selected_adaptation_cost_usd: float,
    avoided_damage_usd: float,
    traced_scenarios: float,
    required_scenarios: float,
) -> dict[str, float]:
    """Compute deterministic sea-level-rise asset review metrics."""
    _require_positive(
        asset_elevation_m=asset_elevation_m,
        required_freeboard_m=required_freeboard_m,
        service_threshold_m=service_threshold_m,
        adaptation_budget_usd=adaptation_budget_usd,
        selected_adaptation_cost_usd=selected_adaptation_cost_usd,
        avoided_damage_usd=avoided_damage_usd,
        required_scenarios=required_scenarios,
    )
    _require_nonnegative(
        present_high_tide_level_m=present_high_tide_level_m,
        sea_level_rise_allowance_m=sea_level_rise_allowance_m,
        storm_surge_allowance_m=storm_surge_allowance_m,
        wave_allowance_m=wave_allowance_m,
        traced_scenarios=traced_scenarios,
    )

    future_stillwater_level_m = present_high_tide_level_m + sea_level_rise_allowance_m + storm_surge_allowance_m
    future_design_level_m = future_stillwater_level_m + wave_allowance_m
    asset_freeboard_margin_m = asset_elevation_m - (future_design_level_m + required_freeboard_m)
    service_threshold_exceedance_m = max(future_stillwater_level_m - service_threshold_m, 0.0)
    adaptation_raise_required_m = max(future_design_level_m + required_freeboard_m - asset_elevation_m, 0.0)
    adaptation_cost_margin_usd = adaptation_budget_usd - selected_adaptation_cost_usd
    benefit_cost_ratio = avoided_damage_usd / selected_adaptation_cost_usd
    scenario_trace_score = traced_scenarios / required_scenarios

    pass_checks = [
        asset_freeboard_margin_m >= 0.0,
        adaptation_cost_margin_usd >= 0.0,
        benefit_cost_ratio >= 1.0,
        scenario_trace_score >= 1.0,
    ]

    return {
        "future_stillwater_level_m": round(future_stillwater_level_m, 3),
        "future_design_level_m": round(future_design_level_m, 3),
        "asset_freeboard_margin_m": round(asset_freeboard_margin_m, 3),
        "service_threshold_exceedance_m": round(service_threshold_exceedance_m, 3),
        "adaptation_raise_required_m": round(adaptation_raise_required_m, 3),
        "adaptation_cost_margin_usd": round(adaptation_cost_margin_usd, 3),
        "benefit_cost_ratio": round(benefit_cost_ratio, 3),
        "scenario_trace_score": round(scenario_trace_score, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
