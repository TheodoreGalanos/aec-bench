# ABOUTME: Computes five-minute lift handling capacity from group parameters.
# ABOUTME: Uses CIBSE-style 300-second capacity arithmetic with explicit loading factor.


def _validate_inputs(
    building_population: float,
    round_trip_time_s: float,
    car_capacity_persons: float,
    lift_count: float,
    car_loading_factor_pct: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "building_population": building_population,
        "round_trip_time_s": round_trip_time_s,
        "car_capacity_persons": car_capacity_persons,
        "lift_count": lift_count,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)
    if car_loading_factor_pct <= 0 or car_loading_factor_pct > 100:
        msg = "car_loading_factor_pct must be > 0 and <= 100"
        raise ValueError(msg)


def compute(
    building_population: float,
    round_trip_time_s: float,
    car_capacity_persons: float,
    lift_count: float,
    car_loading_factor_pct: float,
) -> dict[str, float]:
    """Compute passengers carried per five minutes and handling capacity percentage."""
    _validate_inputs(
        building_population,
        round_trip_time_s,
        car_capacity_persons,
        lift_count,
        car_loading_factor_pct,
    )

    loaded_capacity_persons = car_capacity_persons * car_loading_factor_pct / 100.0
    passengers_per_5min = 300.0 * lift_count * loaded_capacity_persons / round_trip_time_s
    handling_capacity_pct = passengers_per_5min / building_population * 100.0

    return {
        "passengers_per_5min": round(passengers_per_5min, 2),
        "handling_capacity_pct": round(handling_capacity_pct, 2),
    }
