# ABOUTME: Computes SSC-15 pipe product velocity, slope, and certificate metrics.
# ABOUTME: Combines hydraulic capacity, pressure certificate, lining, and source checks.

from __future__ import annotations

import math


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    flow_l_s: float,
    internal_diameter_mm: float,
    pipe_slope: float,
    minimum_slope: float,
    manning_n: float,
    min_velocity_m_s: float,
    max_velocity_m_s: float,
    design_pressure_kpa: float,
    certificate_pressure_rating_kpa: float,
    design_temperature_c: float,
    lining_temperature_rating_c: float,
) -> dict[str, float]:
    _require_positive(
        flow_l_s=flow_l_s,
        internal_diameter_mm=internal_diameter_mm,
        pipe_slope=pipe_slope,
        minimum_slope=minimum_slope,
        manning_n=manning_n,
        min_velocity_m_s=min_velocity_m_s,
        max_velocity_m_s=max_velocity_m_s,
        certificate_pressure_rating_kpa=certificate_pressure_rating_kpa,
    )

    diameter_m = internal_diameter_mm / 1000.0
    area_m2 = math.pi * diameter_m**2 / 4.0
    flow_m3_s = flow_l_s / 1000.0
    flow_velocity_m_s = flow_m3_s / area_m2
    hydraulic_radius_m = diameter_m / 4.0
    manning_capacity_l_s = (
        (1.0 / manning_n) * area_m2 * hydraulic_radius_m ** (2.0 / 3.0) * math.sqrt(pipe_slope) * 1000.0
    )

    velocity_low_margin_m_s = flow_velocity_m_s - min_velocity_m_s
    velocity_high_margin_m_s = max_velocity_m_s - flow_velocity_m_s
    capacity_margin_l_s = manning_capacity_l_s - flow_l_s
    slope_margin = pipe_slope - minimum_slope
    pressure_certificate_margin_kpa = certificate_pressure_rating_kpa - design_pressure_kpa
    lining_temperature_margin_c = lining_temperature_rating_c - design_temperature_c

    overall_pass_score = (
        1.0
        if (
            velocity_low_margin_m_s >= 0.0
            and velocity_high_margin_m_s >= 0.0
            and capacity_margin_l_s >= 0.0
            and slope_margin >= 0.0
            and pressure_certificate_margin_kpa >= 0.0
            and lining_temperature_margin_c >= 0.0
        )
        else 0.0
    )

    return {
        "flow_velocity_m_s": round(flow_velocity_m_s, 3),
        "velocity_low_margin_m_s": round(velocity_low_margin_m_s, 3),
        "velocity_high_margin_m_s": round(velocity_high_margin_m_s, 3),
        "manning_capacity_l_s": round(manning_capacity_l_s, 3),
        "capacity_margin_l_s": round(capacity_margin_l_s, 3),
        "slope_margin": round(slope_margin, 3),
        "pressure_certificate_margin_kpa": round(pressure_certificate_margin_kpa, 3),
        "lining_temperature_margin_c": round(lining_temperature_margin_c, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
