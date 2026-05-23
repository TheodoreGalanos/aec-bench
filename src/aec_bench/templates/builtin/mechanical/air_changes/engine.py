# ABOUTME: Air changes computation engine for room ventilation checks.
# ABOUTME: Calculates air changes per hour from supply airflow and room volume.


def _validate_inputs(
    supply_airflow_m3_h: float,
    room_volume_m3: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if supply_airflow_m3_h <= 0:
        msg = "supply_airflow_m3_h must be > 0"
        raise ValueError(msg)
    if room_volume_m3 <= 0:
        msg = "room_volume_m3 must be > 0"
        raise ValueError(msg)


def compute(
    supply_airflow_m3_h: float,
    room_volume_m3: float,
) -> dict[str, float]:
    """Compute air changes per hour.

    Returns a dict with key: air_changes_per_h.
    """
    _validate_inputs(supply_airflow_m3_h, room_volume_m3)

    air_changes = supply_airflow_m3_h / room_volume_m3

    return {
        "air_changes_per_h": round(air_changes, 2),
    }
