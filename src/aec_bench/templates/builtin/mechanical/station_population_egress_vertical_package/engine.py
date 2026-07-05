# ABOUTME: Computes SSC-08 station population egress vertical movement package metrics.
# ABOUTME: Combines occupancy, egress, vertical movement, ventilation, and alarm checks.

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
    floor_area_m2: float,
    area_per_occupant_m2: float,
    egress_width_per_occupant_mm: float,
    provided_egress_width_mm: float,
    max_egress_time_s: float,
    egress_flow_rate_persons_per_m_s: float,
    peak_vertical_demand_persons_per_5min: float,
    escalator_speed_m_s: float,
    escalator_step_width_mm: float,
    escalator_step_pitch_mm: float,
    escalator_loading_factor_percent: float,
    lift_round_trip_time_s: float,
    lift_car_capacity_persons: float,
    lift_count: float,
    lift_loading_factor_percent: float,
    required_lift_handling_percent: float,
    ventilation_airflow_m3_h: float,
    concourse_volume_m3: float,
    required_air_changes_per_h: float,
    nac_strobe_quantity: float,
    nac_strobe_current_a: float,
    nac_horn_quantity: float,
    nac_horn_current_a: float,
    nac_speaker_quantity: float,
    nac_speaker_current_a: float,
    nac_circuit_capacity_a: float,
) -> dict[str, float]:
    """Compute station occupancy, egress, movement, ventilation, and alarm metrics."""
    _require_positive(
        floor_area_m2=floor_area_m2,
        area_per_occupant_m2=area_per_occupant_m2,
        egress_width_per_occupant_mm=egress_width_per_occupant_mm,
        provided_egress_width_mm=provided_egress_width_mm,
        max_egress_time_s=max_egress_time_s,
        egress_flow_rate_persons_per_m_s=egress_flow_rate_persons_per_m_s,
        peak_vertical_demand_persons_per_5min=peak_vertical_demand_persons_per_5min,
        escalator_speed_m_s=escalator_speed_m_s,
        escalator_step_width_mm=escalator_step_width_mm,
        escalator_step_pitch_mm=escalator_step_pitch_mm,
        lift_round_trip_time_s=lift_round_trip_time_s,
        lift_car_capacity_persons=lift_car_capacity_persons,
        lift_count=lift_count,
        required_lift_handling_percent=required_lift_handling_percent,
        ventilation_airflow_m3_h=ventilation_airflow_m3_h,
        concourse_volume_m3=concourse_volume_m3,
        required_air_changes_per_h=required_air_changes_per_h,
        nac_circuit_capacity_a=nac_circuit_capacity_a,
    )
    _require_nonnegative(
        nac_strobe_quantity=nac_strobe_quantity,
        nac_strobe_current_a=nac_strobe_current_a,
        nac_horn_quantity=nac_horn_quantity,
        nac_horn_current_a=nac_horn_current_a,
        nac_speaker_quantity=nac_speaker_quantity,
        nac_speaker_current_a=nac_speaker_current_a,
    )
    if escalator_loading_factor_percent <= 0.0 or escalator_loading_factor_percent > 100.0:
        msg = "escalator_loading_factor_percent must be > 0 and <= 100"
        raise ValueError(msg)
    if lift_loading_factor_percent <= 0.0 or lift_loading_factor_percent > 100.0:
        msg = "lift_loading_factor_percent must be > 0 and <= 100"
        raise ValueError(msg)
    if nac_strobe_quantity + nac_horn_quantity + nac_speaker_quantity <= 0.0:
        msg = "at least one NAC appliance quantity must be > 0"
        raise ValueError(msg)

    calculated_occupants = floor_area_m2 / area_per_occupant_m2
    design_occupants = float(math.ceil(calculated_occupants))
    occupant_density_person_m2 = design_occupants / floor_area_m2

    required_egress_width_mm = design_occupants * egress_width_per_occupant_mm
    egress_width_margin_mm = provided_egress_width_mm - required_egress_width_mm
    egress_width_utilization = required_egress_width_mm / provided_egress_width_mm
    provided_egress_width_m = provided_egress_width_mm / 1000.0
    egress_flow_time_s = design_occupants / (provided_egress_width_m * egress_flow_rate_persons_per_m_s)
    egress_time_margin_s = max_egress_time_s - egress_flow_time_s

    escalator_steps_per_second = escalator_speed_m_s / (escalator_step_pitch_mm / 1000.0)
    escalator_persons_per_step = 1.0 if escalator_step_width_mm < 800.0 else 2.0
    escalator_practical_capacity_persons_per_h = (
        escalator_steps_per_second * escalator_persons_per_step * 3600.0 * escalator_loading_factor_percent / 100.0
    )
    escalator_capacity_persons_per_5min = escalator_practical_capacity_persons_per_h / 12.0

    lift_loaded_capacity_persons = lift_car_capacity_persons * lift_loading_factor_percent / 100.0
    lift_passengers_per_5min = 300.0 * lift_count * lift_loaded_capacity_persons / lift_round_trip_time_s
    lift_handling_capacity_percent = lift_passengers_per_5min / design_occupants * 100.0
    lift_handling_margin_percent = lift_handling_capacity_percent - required_lift_handling_percent

    vertical_capacity_persons_per_5min = escalator_capacity_persons_per_5min + lift_passengers_per_5min
    vertical_capacity_margin_persons_per_5min = (
        vertical_capacity_persons_per_5min - peak_vertical_demand_persons_per_5min
    )

    ventilation_air_changes_per_h = ventilation_airflow_m3_h / concourse_volume_m3
    ventilation_ach_margin = ventilation_air_changes_per_h - required_air_changes_per_h

    nac_total_load_a = (
        nac_strobe_quantity * nac_strobe_current_a
        + nac_horn_quantity * nac_horn_current_a
        + nac_speaker_quantity * nac_speaker_current_a
    )
    nac_spare_capacity_a = nac_circuit_capacity_a - nac_total_load_a
    nac_utilization_percent = nac_total_load_a / nac_circuit_capacity_a * 100.0

    overall_pass_score = (
        1.0
        if (
            egress_width_margin_mm >= 0.0
            and egress_time_margin_s >= 0.0
            and vertical_capacity_margin_persons_per_5min >= 0.0
            and lift_handling_margin_percent >= 0.0
            and ventilation_ach_margin >= 0.0
            and nac_spare_capacity_a >= 0.0
        )
        else 0.0
    )

    return {
        "calculated_occupants": round(calculated_occupants, 3),
        "design_occupants": round(design_occupants, 3),
        "occupant_density_person_m2": round(occupant_density_person_m2, 3),
        "required_egress_width_mm": round(required_egress_width_mm, 3),
        "egress_width_margin_mm": round(egress_width_margin_mm, 3),
        "egress_width_utilization": round(egress_width_utilization, 3),
        "egress_flow_time_s": round(egress_flow_time_s, 3),
        "egress_time_margin_s": round(egress_time_margin_s, 3),
        "escalator_practical_capacity_persons_per_h": round(escalator_practical_capacity_persons_per_h, 3),
        "escalator_capacity_persons_per_5min": round(escalator_capacity_persons_per_5min, 3),
        "lift_passengers_per_5min": round(lift_passengers_per_5min, 3),
        "lift_handling_capacity_percent": round(lift_handling_capacity_percent, 3),
        "lift_handling_margin_percent": round(lift_handling_margin_percent, 3),
        "vertical_capacity_persons_per_5min": round(vertical_capacity_persons_per_5min, 3),
        "vertical_capacity_margin_persons_per_5min": round(vertical_capacity_margin_persons_per_5min, 3),
        "ventilation_air_changes_per_h": round(ventilation_air_changes_per_h, 3),
        "ventilation_ach_margin": round(ventilation_ach_margin, 3),
        "nac_total_load_a": round(nac_total_load_a, 3),
        "nac_spare_capacity_a": round(nac_spare_capacity_a, 3),
        "nac_utilization_percent": round(nac_utilization_percent, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
