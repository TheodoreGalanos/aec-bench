# ABOUTME: Computes road lighting Power Density Index and specific power density.
# ABOUTME: Uses installed system power, maintained illuminance, and lit area.


def _validate_inputs(
    total_system_power_w: float,
    maintained_illuminance_lux: float,
    illuminated_area_m2: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "total_system_power_w": total_system_power_w,
        "maintained_illuminance_lux": maintained_illuminance_lux,
        "illuminated_area_m2": illuminated_area_m2,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    total_system_power_w: float,
    maintained_illuminance_lux: float,
    illuminated_area_m2: float,
) -> dict[str, float]:
    """Compute road lighting Power Density Index metrics."""
    _validate_inputs(
        total_system_power_w,
        maintained_illuminance_lux,
        illuminated_area_m2,
    )

    specific_power_density_w_per_m2 = total_system_power_w / illuminated_area_m2
    power_density_index_w_per_lux_m2 = total_system_power_w / maintained_illuminance_lux / illuminated_area_m2

    return {
        "power_density_index_w_per_lux_m2": round(power_density_index_w_per_lux_m2, 2),
        "specific_power_density_w_per_m2": round(specific_power_density_w_per_m2, 2),
    }
