# ABOUTME: Computes sports field average illuminance and uniformity ratios.
# ABOUTME: Uses reduced aggregate lumens and minimum/maximum grid illuminance.


def _validate_inputs(
    field_length_m: float,
    field_width_m: float,
    luminaire_count: float,
    luminaire_luminous_flux_lm: float,
    utilisation_factor: float,
    maintenance_factor: float,
    minimum_illuminance_lux: float,
    maximum_illuminance_lux: float,
    target_average_illuminance_lux: float,
    target_uniformity_u2: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "field_length_m": field_length_m,
        "field_width_m": field_width_m,
        "luminaire_count": luminaire_count,
        "luminaire_luminous_flux_lm": luminaire_luminous_flux_lm,
        "maximum_illuminance_lux": maximum_illuminance_lux,
        "target_average_illuminance_lux": target_average_illuminance_lux,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)
    if minimum_illuminance_lux < 0:
        msg = "minimum_illuminance_lux must be >= 0"
        raise ValueError(msg)
    for name, value in {
        "utilisation_factor": utilisation_factor,
        "maintenance_factor": maintenance_factor,
        "target_uniformity_u2": target_uniformity_u2,
    }.items():
        if not 0 < value <= 1:
            msg = f"{name} must be > 0 and <= 1"
            raise ValueError(msg)


def compute(
    field_length_m: float,
    field_width_m: float,
    luminaire_count: float,
    luminaire_luminous_flux_lm: float,
    utilisation_factor: float,
    maintenance_factor: float,
    minimum_illuminance_lux: float,
    maximum_illuminance_lux: float,
    target_average_illuminance_lux: float,
    target_uniformity_u2: float,
) -> dict[str, float]:
    """Compute reduced sports-field illuminance and uniformity metrics."""
    _validate_inputs(
        field_length_m,
        field_width_m,
        luminaire_count,
        luminaire_luminous_flux_lm,
        utilisation_factor,
        maintenance_factor,
        minimum_illuminance_lux,
        maximum_illuminance_lux,
        target_average_illuminance_lux,
        target_uniformity_u2,
    )

    field_area_m2 = field_length_m * field_width_m
    average_horizontal_illuminance_lux = (
        luminaire_count * luminaire_luminous_flux_lm * utilisation_factor * maintenance_factor
    ) / field_area_m2
    uniformity_u1_min_max = minimum_illuminance_lux / maximum_illuminance_lux
    uniformity_u2_min_avg = minimum_illuminance_lux / average_horizontal_illuminance_lux
    average_illuminance_margin_pct = (average_horizontal_illuminance_lux / target_average_illuminance_lux - 1.0) * 100.0
    uniformity_u2_margin_pct = (uniformity_u2_min_avg / target_uniformity_u2 - 1.0) * 100.0

    return {
        "average_horizontal_illuminance_lux": round(average_horizontal_illuminance_lux, 2),
        "uniformity_u1_min_max": round(uniformity_u1_min_max, 2),
        "uniformity_u2_min_avg": round(uniformity_u2_min_avg, 2),
        "average_illuminance_margin_pct": round(average_illuminance_margin_pct, 2),
        "uniformity_u2_margin_pct": round(uniformity_u2_margin_pct, 2),
    }
