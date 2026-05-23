# ABOUTME: Computes numeric lift car dimension margins and load density.
# ABOUTME: Uses car width, depth, door opening, rated load, and minimum dimensions.


def _validate_inputs(
    car_internal_width_mm: float,
    car_internal_depth_mm: float,
    door_clear_opening_mm: float,
    rated_load_kg: float,
    minimum_width_mm: float,
    minimum_depth_mm: float,
    minimum_door_opening_mm: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "car_internal_width_mm": car_internal_width_mm,
        "car_internal_depth_mm": car_internal_depth_mm,
        "door_clear_opening_mm": door_clear_opening_mm,
        "rated_load_kg": rated_load_kg,
        "minimum_width_mm": minimum_width_mm,
        "minimum_depth_mm": minimum_depth_mm,
        "minimum_door_opening_mm": minimum_door_opening_mm,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    car_internal_width_mm: float,
    car_internal_depth_mm: float,
    door_clear_opening_mm: float,
    rated_load_kg: float,
    minimum_width_mm: float,
    minimum_depth_mm: float,
    minimum_door_opening_mm: float,
) -> dict[str, float]:
    """Compute lift car accessibility dimension margins."""
    _validate_inputs(
        car_internal_width_mm,
        car_internal_depth_mm,
        door_clear_opening_mm,
        rated_load_kg,
        minimum_width_mm,
        minimum_depth_mm,
        minimum_door_opening_mm,
    )

    width_margin_mm = car_internal_width_mm - minimum_width_mm
    depth_margin_mm = car_internal_depth_mm - minimum_depth_mm
    door_opening_margin_mm = door_clear_opening_mm - minimum_door_opening_mm
    car_floor_area_m2 = car_internal_width_mm * car_internal_depth_mm / 1_000_000.0
    rated_load_density_kg_m2 = rated_load_kg / car_floor_area_m2

    return {
        "width_margin_mm": round(width_margin_mm, 2),
        "depth_margin_mm": round(depth_margin_mm, 2),
        "door_opening_margin_mm": round(door_opening_margin_mm, 2),
        "car_floor_area_m2": round(car_floor_area_m2, 2),
        "rated_load_density_kg_m2": round(rated_load_density_kg_m2, 2),
    }
