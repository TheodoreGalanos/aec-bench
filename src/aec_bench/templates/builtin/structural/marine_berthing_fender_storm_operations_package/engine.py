# ABOUTME: Computes SSC-04 marine berthing, fender, mooring, and storm operations metrics.
# ABOUTME: Combines berthing energy, fender capacity, mooring load, tide clearance, and operating window checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    vessel_mass_t: float,
    approach_velocity_m_s: float,
    eccentricity_factor: float,
    softness_factor: float,
    fender_energy_capacity_knm: float,
    wind_pressure_kpa: float,
    projected_area_m2: float,
    current_load_kn: float,
    mooring_line_count: float,
    mooring_line_capacity_kn: float,
    mooring_efficiency: float,
    storm_tide_level_m: float,
    deck_level_m: float,
    required_deck_clearance_m: float,
    allowable_downtime_h: float,
    tide_exceedance_h: float,
) -> dict[str, float]:
    """Compute deterministic marine berthing and storm-operation metrics."""
    _require_positive(
        vessel_mass_t=vessel_mass_t,
        approach_velocity_m_s=approach_velocity_m_s,
        eccentricity_factor=eccentricity_factor,
        softness_factor=softness_factor,
        fender_energy_capacity_knm=fender_energy_capacity_knm,
        wind_pressure_kpa=wind_pressure_kpa,
        projected_area_m2=projected_area_m2,
        mooring_line_count=mooring_line_count,
        mooring_line_capacity_kn=mooring_line_capacity_kn,
        mooring_efficiency=mooring_efficiency,
        deck_level_m=deck_level_m,
        required_deck_clearance_m=required_deck_clearance_m,
        allowable_downtime_h=allowable_downtime_h,
    )

    berthing_energy_knm = 0.5 * vessel_mass_t * approach_velocity_m_s**2 * eccentricity_factor * softness_factor
    fender_energy_margin_knm = fender_energy_capacity_knm - berthing_energy_knm
    environmental_mooring_load_kn = wind_pressure_kpa * projected_area_m2 + current_load_kn
    mooring_capacity_kn = mooring_line_count * mooring_line_capacity_kn * mooring_efficiency
    mooring_margin_kn = mooring_capacity_kn - environmental_mooring_load_kn
    deck_clearance_margin_m = deck_level_m - (storm_tide_level_m + required_deck_clearance_m)
    allowable_operating_window_margin_h = allowable_downtime_h - tide_exceedance_h

    pass_checks = [
        fender_energy_margin_knm >= 0.0,
        mooring_margin_kn >= 0.0,
        deck_clearance_margin_m >= 0.0,
        allowable_operating_window_margin_h >= 0.0,
    ]

    return {
        "berthing_energy_knm": round(berthing_energy_knm, 3),
        "fender_energy_margin_knm": round(fender_energy_margin_knm, 3),
        "environmental_mooring_load_kn": round(environmental_mooring_load_kn, 3),
        "mooring_capacity_kn": round(mooring_capacity_kn, 3),
        "mooring_margin_kn": round(mooring_margin_kn, 3),
        "storm_tide_operating_level_m": round(storm_tide_level_m, 3),
        "deck_clearance_margin_m": round(deck_clearance_margin_m, 3),
        "allowable_operating_window_margin_h": round(allowable_operating_window_margin_h, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
