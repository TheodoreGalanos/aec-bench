# ABOUTME: Elevation pressure computation engine for hydraulic systems.
# ABOUTME: Calculates static pressure change from elevation difference and density.

_G = 9.81


def _validate_inputs(fluid_density_kg_m3: float, elevation_change_m: float) -> None:
    """Raise ValueError for invalid input parameters."""
    if fluid_density_kg_m3 <= 0:
        msg = "fluid_density_kg_m3 must be > 0"
        raise ValueError(msg)


def compute(fluid_density_kg_m3: float, elevation_change_m: float) -> dict[str, float]:
    """Compute pressure change from elevation difference.

    Returns a dict with keys: elevation_head_m, pressure_change_kpa,
    pressure_change_bar.
    """
    _validate_inputs(fluid_density_kg_m3, elevation_change_m)

    pressure_change_kpa = fluid_density_kg_m3 * _G * elevation_change_m / 1000.0
    pressure_change_bar = pressure_change_kpa / 100.0

    return {
        "elevation_head_m": round(elevation_change_m, 2),
        "pressure_change_kpa": round(pressure_change_kpa, 2),
        "pressure_change_bar": round(pressure_change_bar, 3),
    }
