# ABOUTME: Computes SSC-08 pedestrian clearance, forecourt, lighting, and signal metrics.
# ABOUTME: Combines clearance timing, all-red timing, density, discharge width, and illuminance checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    crossing_length_m: float,
    pedestrian_speed_m_s: float,
    startup_time_s: float,
    provided_pedestrian_phase_s: float,
    approach_speed_kmh: float,
    crossing_width_m: float,
    reaction_time_s: float,
    provided_all_red_s: float,
    forecourt_area_m2: float,
    peak_forecourt_demand_persons: float,
    maximum_forecourt_density_person_m2: float,
    discharge_width_factor_mm_per_person: float,
    provided_discharge_width_mm: float,
    luminaire_lumens: float,
    luminaire_count: float,
    light_loss_factor: float,
    utilization_factor: float,
    target_illuminance_lux: float,
) -> dict[str, float]:
    """Compute deterministic pedestrian forecourt and signal interface metrics."""
    _require_positive(
        crossing_length_m=crossing_length_m,
        pedestrian_speed_m_s=pedestrian_speed_m_s,
        startup_time_s=startup_time_s,
        provided_pedestrian_phase_s=provided_pedestrian_phase_s,
        approach_speed_kmh=approach_speed_kmh,
        crossing_width_m=crossing_width_m,
        reaction_time_s=reaction_time_s,
        provided_all_red_s=provided_all_red_s,
        forecourt_area_m2=forecourt_area_m2,
        peak_forecourt_demand_persons=peak_forecourt_demand_persons,
        maximum_forecourt_density_person_m2=maximum_forecourt_density_person_m2,
        discharge_width_factor_mm_per_person=discharge_width_factor_mm_per_person,
        provided_discharge_width_mm=provided_discharge_width_mm,
        luminaire_lumens=luminaire_lumens,
        luminaire_count=luminaire_count,
        light_loss_factor=light_loss_factor,
        utilization_factor=utilization_factor,
        target_illuminance_lux=target_illuminance_lux,
    )

    pedestrian_clearance_time_s = crossing_length_m / pedestrian_speed_m_s + startup_time_s
    pedestrian_phase_margin_s = provided_pedestrian_phase_s - pedestrian_clearance_time_s
    approach_speed_m_s = approach_speed_kmh / 3.6
    all_red_time_s = reaction_time_s + crossing_width_m / approach_speed_m_s
    all_red_margin_s = provided_all_red_s - all_red_time_s
    forecourt_density_person_m2 = peak_forecourt_demand_persons / forecourt_area_m2
    forecourt_density_margin_person_m2 = maximum_forecourt_density_person_m2 - forecourt_density_person_m2
    required_discharge_width_mm = peak_forecourt_demand_persons * discharge_width_factor_mm_per_person
    discharge_width_margin_mm = provided_discharge_width_mm - required_discharge_width_mm
    forecourt_average_illuminance_lux = (
        luminaire_lumens * luminaire_count * light_loss_factor * utilization_factor / forecourt_area_m2
    )
    illuminance_margin_lux = forecourt_average_illuminance_lux - target_illuminance_lux

    pass_checks = [
        pedestrian_phase_margin_s >= 0.0,
        all_red_margin_s >= 0.0,
        forecourt_density_margin_person_m2 >= 0.0,
        discharge_width_margin_mm >= 0.0,
        illuminance_margin_lux >= 0.0,
    ]

    return {
        "pedestrian_clearance_time_s": round(pedestrian_clearance_time_s, 3),
        "pedestrian_phase_margin_s": round(pedestrian_phase_margin_s, 3),
        "all_red_time_s": round(all_red_time_s, 3),
        "all_red_margin_s": round(all_red_margin_s, 3),
        "forecourt_density_person_m2": round(forecourt_density_person_m2, 3),
        "forecourt_density_margin_person_m2": round(forecourt_density_margin_person_m2, 3),
        "required_discharge_width_mm": round(required_discharge_width_mm, 3),
        "discharge_width_margin_mm": round(discharge_width_margin_mm, 3),
        "forecourt_average_illuminance_lux": round(forecourt_average_illuminance_lux, 3),
        "illuminance_margin_lux": round(illuminance_margin_lux, 3),
        "overall_pass_score": 1.0 if all(pass_checks) else 0.0,
    }
