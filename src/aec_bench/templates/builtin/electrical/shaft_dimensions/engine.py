# ABOUTME: Computes reduced lift shaft width, depth, pit depth, and headroom.
# ABOUTME: Uses car dimensions, clearances, counterweight allowance, speed, and car count.


def _validate_inputs(
    car_internal_width_mm: float,
    car_internal_depth_mm: float,
    side_clearance_mm: float,
    front_clearance_mm: float,
    rear_clearance_mm: float,
    counterweight_width_mm: float,
    rated_speed_m_s: float,
    car_count: float,
    inter_car_clearance_mm: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "car_internal_width_mm": car_internal_width_mm,
        "car_internal_depth_mm": car_internal_depth_mm,
        "rated_speed_m_s": rated_speed_m_s,
        "car_count": car_count,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)
    for name, value in {
        "side_clearance_mm": side_clearance_mm,
        "front_clearance_mm": front_clearance_mm,
        "rear_clearance_mm": rear_clearance_mm,
        "counterweight_width_mm": counterweight_width_mm,
        "inter_car_clearance_mm": inter_car_clearance_mm,
    }.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)


def compute(
    car_internal_width_mm: float,
    car_internal_depth_mm: float,
    side_clearance_mm: float,
    front_clearance_mm: float,
    rear_clearance_mm: float,
    counterweight_width_mm: float,
    rated_speed_m_s: float,
    car_count: float,
    inter_car_clearance_mm: float,
) -> dict[str, float]:
    """Compute reduced lift shaft envelope dimensions."""
    _validate_inputs(
        car_internal_width_mm,
        car_internal_depth_mm,
        side_clearance_mm,
        front_clearance_mm,
        rear_clearance_mm,
        counterweight_width_mm,
        rated_speed_m_s,
        car_count,
        inter_car_clearance_mm,
    )

    shaft_width_mm = (
        car_count * (car_internal_width_mm + 2.0 * side_clearance_mm + counterweight_width_mm)
        + (car_count - 1.0) * inter_car_clearance_mm
    )
    shaft_depth_mm = car_internal_depth_mm + front_clearance_mm + rear_clearance_mm
    pit_depth_mm = 1200.0 + rated_speed_m_s * 250.0
    headroom_mm = 3600.0 + rated_speed_m_s * 500.0

    return {
        "shaft_width_mm": round(shaft_width_mm, 2),
        "shaft_depth_mm": round(shaft_depth_mm, 2),
        "pit_depth_mm": round(pit_depth_mm, 2),
        "headroom_mm": round(headroom_mm, 2),
    }
