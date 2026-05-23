# ABOUTME: Computes room average illuminance, uniformity, and lighting power density.
# ABOUTME: Uses a reduced lumen method with explicit utilisation and maintenance factors.


def _validate_inputs(
    room_length_m: float,
    room_width_m: float,
    luminaire_count: float,
    luminaire_luminous_flux_lm: float,
    utilisation_factor: float,
    maintenance_factor: float,
    total_lighting_power_w: float,
    minimum_illuminance_lux: float,
    target_illuminance_lux: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "room_length_m": room_length_m,
        "room_width_m": room_width_m,
        "luminaire_count": luminaire_count,
        "luminaire_luminous_flux_lm": luminaire_luminous_flux_lm,
        "total_lighting_power_w": total_lighting_power_w,
        "target_illuminance_lux": target_illuminance_lux,
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
    }.items():
        if not 0 < value <= 1:
            msg = f"{name} must be > 0 and <= 1"
            raise ValueError(msg)


def compute(
    room_length_m: float,
    room_width_m: float,
    luminaire_count: float,
    luminaire_luminous_flux_lm: float,
    utilisation_factor: float,
    maintenance_factor: float,
    total_lighting_power_w: float,
    minimum_illuminance_lux: float,
    target_illuminance_lux: float,
) -> dict[str, float]:
    """Compute reduced lumen-method room illuminance metrics."""
    _validate_inputs(
        room_length_m,
        room_width_m,
        luminaire_count,
        luminaire_luminous_flux_lm,
        utilisation_factor,
        maintenance_factor,
        total_lighting_power_w,
        minimum_illuminance_lux,
        target_illuminance_lux,
    )

    room_area_m2 = room_length_m * room_width_m
    average_illuminance_lux = (
        luminaire_count * luminaire_luminous_flux_lm * utilisation_factor * maintenance_factor
    ) / room_area_m2
    uniformity_ratio_uo = minimum_illuminance_lux / average_illuminance_lux
    specific_luminaire_power_density_w_m2_100lux = (
        total_lighting_power_w / room_area_m2 / (average_illuminance_lux / 100.0)
    )
    target_illuminance_margin_pct = (average_illuminance_lux / target_illuminance_lux - 1.0) * 100.0

    return {
        "average_illuminance_lux": round(average_illuminance_lux, 2),
        "uniformity_ratio_uo": round(uniformity_ratio_uo, 2),
        "specific_luminaire_power_density_w_m2_100lux": round(specific_luminaire_power_density_w_m2_100lux, 2),
        "target_illuminance_margin_pct": round(target_illuminance_margin_pct, 2),
    }
