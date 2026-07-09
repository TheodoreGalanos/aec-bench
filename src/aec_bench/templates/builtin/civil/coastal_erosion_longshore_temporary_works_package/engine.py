# ABOUTME: Computes SSC-04 coastal erosion, longshore transport, and temporary works metrics.
# ABOUTME: Combines transport, temporary protection volume, sediment control, monitoring, and tolerance checks.

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
    transport_coefficient: float,
    wave_energy_factor: float,
    breaking_wave_angle_deg: float,
    exposure_days: float,
    capture_factor: float,
    selected_protection_volume_m3: float,
    disturbed_area_ha: float,
    design_rainfall_mm: float,
    runoff_coefficient: float,
    selected_sediment_basin_volume_m3: float,
    permitted_discharge_m3_s: float,
    pumped_discharge_m3_s: float,
    monitoring_stations_installed: float,
    required_monitoring_stations: float,
    allowable_alignment_offset_m: float,
    measured_alignment_offset_m: float,
) -> dict[str, float]:
    """Compute deterministic coastal erosion and temporary works metrics."""
    _require_positive(
        transport_coefficient=transport_coefficient,
        wave_energy_factor=wave_energy_factor,
        exposure_days=exposure_days,
        capture_factor=capture_factor,
        selected_protection_volume_m3=selected_protection_volume_m3,
        disturbed_area_ha=disturbed_area_ha,
        design_rainfall_mm=design_rainfall_mm,
        runoff_coefficient=runoff_coefficient,
        selected_sediment_basin_volume_m3=selected_sediment_basin_volume_m3,
        permitted_discharge_m3_s=permitted_discharge_m3_s,
        required_monitoring_stations=required_monitoring_stations,
        allowable_alignment_offset_m=allowable_alignment_offset_m,
    )
    _require_nonnegative(
        breaking_wave_angle_deg=breaking_wave_angle_deg,
        pumped_discharge_m3_s=pumped_discharge_m3_s,
        monitoring_stations_installed=monitoring_stations_installed,
        measured_alignment_offset_m=measured_alignment_offset_m,
    )

    longshore_transport_m3_day = (
        transport_coefficient * wave_energy_factor * math.sin(math.radians(2.0 * breaking_wave_angle_deg))
    )
    temporary_protection_volume_m3 = longshore_transport_m3_day * exposure_days * capture_factor
    protection_volume_margin_m3 = selected_protection_volume_m3 - temporary_protection_volume_m3
    sediment_basin_required_m3 = disturbed_area_ha * design_rainfall_mm * runoff_coefficient * 10.0
    sediment_basin_margin_m3 = selected_sediment_basin_volume_m3 - sediment_basin_required_m3
    discharge_capacity_margin_m3_s = permitted_discharge_m3_s - pumped_discharge_m3_s
    monitoring_coverage_fraction = monitoring_stations_installed / required_monitoring_stations
    construction_tolerance_margin_m = allowable_alignment_offset_m - measured_alignment_offset_m

    pass_checks = [
        protection_volume_margin_m3 >= 0.0,
        sediment_basin_margin_m3 >= 0.0,
        discharge_capacity_margin_m3_s >= 0.0,
        monitoring_coverage_fraction >= 1.0,
        construction_tolerance_margin_m >= 0.0,
    ]

    return {
        "longshore_transport_m3_day": round(longshore_transport_m3_day, 3),
        "temporary_protection_volume_m3": round(temporary_protection_volume_m3, 3),
        "protection_volume_margin_m3": round(protection_volume_margin_m3, 3),
        "sediment_basin_required_m3": round(sediment_basin_required_m3, 3),
        "sediment_basin_margin_m3": round(sediment_basin_margin_m3, 3),
        "discharge_capacity_margin_m3_s": round(discharge_capacity_margin_m3_s, 3),
        "monitoring_coverage_fraction": round(monitoring_coverage_fraction, 3),
        "construction_tolerance_margin_m": round(construction_tolerance_margin_m, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
