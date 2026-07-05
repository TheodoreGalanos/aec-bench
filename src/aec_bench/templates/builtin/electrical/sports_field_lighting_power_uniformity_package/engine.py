# ABOUTME: Computes SSC-13 sports/field lighting power and uniformity metrics.
# ABOUTME: Combines illuminance, uniformity, load, energy, and feeder checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    grid_lux_01: float,
    grid_lux_02: float,
    grid_lux_03: float,
    grid_lux_04: float,
    grid_lux_05: float,
    grid_lux_06: float,
    grid_lux_07: float,
    grid_lux_08: float,
    required_average_lux: float,
    required_uniformity_ratio: float,
    luminaire_count: float,
    luminaire_power_w: float,
    driver_loss_factor: float,
    event_hours: float,
    voltage_v: float,
    power_factor: float,
    feeder_rating_a: float,
) -> dict[str, float]:
    _require_positive(
        required_average_lux=required_average_lux,
        required_uniformity_ratio=required_uniformity_ratio,
        luminaire_count=luminaire_count,
        luminaire_power_w=luminaire_power_w,
        driver_loss_factor=driver_loss_factor,
        event_hours=event_hours,
        voltage_v=voltage_v,
        power_factor=power_factor,
        feeder_rating_a=feeder_rating_a,
    )

    lux_values = [
        grid_lux_01,
        grid_lux_02,
        grid_lux_03,
        grid_lux_04,
        grid_lux_05,
        grid_lux_06,
        grid_lux_07,
        grid_lux_08,
    ]
    average_illuminance_lux = sum(lux_values) / len(lux_values)
    minimum_illuminance_lux = min(lux_values)
    uniformity_ratio = minimum_illuminance_lux / average_illuminance_lux
    average_illuminance_margin_lux = average_illuminance_lux - required_average_lux
    uniformity_margin = uniformity_ratio - required_uniformity_ratio
    connected_load_w = luminaire_count * luminaire_power_w * driver_loss_factor
    connected_load_kw = connected_load_w / 1000.0
    event_energy_kwh = connected_load_kw * event_hours
    feeder_current_a = connected_load_w / (1.732 * voltage_v * power_factor)
    feeder_current_margin_a = feeder_rating_a - feeder_current_a
    overall_pass_score = (
        1.0
        if average_illuminance_margin_lux >= 0.0 and uniformity_margin >= 0.0 and feeder_current_margin_a >= 0.0
        else 0.0
    )

    return {
        "average_illuminance_lux": round(average_illuminance_lux, 3),
        "minimum_illuminance_lux": round(minimum_illuminance_lux, 3),
        "uniformity_ratio": round(uniformity_ratio, 3),
        "average_illuminance_margin_lux": round(average_illuminance_margin_lux, 3),
        "uniformity_margin": round(uniformity_margin, 3),
        "connected_load_kw": round(connected_load_kw, 3),
        "event_energy_kwh": round(event_energy_kwh, 3),
        "feeder_current_a": round(feeder_current_a, 3),
        "feeder_current_margin_a": round(feeder_current_margin_a, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
