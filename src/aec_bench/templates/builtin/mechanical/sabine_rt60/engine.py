# ABOUTME: Sabine reverberation time computation engine for room acoustics.
# ABOUTME: Calculates equivalent absorption area and RT60 from volume and surfaces.


def _validate_inputs(
    room_volume_m3: float,
    floor_area_m2: float,
    floor_absorption: float,
    wall_area_m2: float,
    wall_absorption: float,
    ceiling_area_m2: float,
    ceiling_absorption: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "room_volume_m3": room_volume_m3,
        "floor_area_m2": floor_area_m2,
        "wall_area_m2": wall_area_m2,
        "ceiling_area_m2": ceiling_area_m2,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)
    for name, value in {
        "floor_absorption": floor_absorption,
        "wall_absorption": wall_absorption,
        "ceiling_absorption": ceiling_absorption,
    }.items():
        if value < 0 or value > 1:
            msg = f"{name} must be between 0 and 1"
            raise ValueError(msg)


def compute(
    room_volume_m3: float,
    floor_area_m2: float,
    floor_absorption: float,
    wall_area_m2: float,
    wall_absorption: float,
    ceiling_area_m2: float,
    ceiling_absorption: float,
) -> dict[str, float]:
    """Compute single-band reverberation time using Sabine's formula.

    Returns a dict with keys: equivalent_absorption_area_m2,
    average_absorption_coefficient, rt60_s.
    """
    _validate_inputs(
        room_volume_m3,
        floor_area_m2,
        floor_absorption,
        wall_area_m2,
        wall_absorption,
        ceiling_area_m2,
        ceiling_absorption,
    )

    equivalent_area = (
        floor_area_m2 * floor_absorption + wall_area_m2 * wall_absorption + ceiling_area_m2 * ceiling_absorption
    )
    total_surface_area = floor_area_m2 + wall_area_m2 + ceiling_area_m2
    average_absorption = equivalent_area / total_surface_area
    rt60 = 0.161 * room_volume_m3 / equivalent_area

    return {
        "equivalent_absorption_area_m2": round(equivalent_area, 2),
        "average_absorption_coefficient": round(average_absorption, 2),
        "rt60_s": round(rt60, 2),
    }
