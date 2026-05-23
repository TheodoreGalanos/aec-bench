# ABOUTME: Intersection sight distance computation engine for unsignalised intersections.
# ABOUTME: Implements ISD = V * t_gap / 3.6 per AGRD Part 4A with grade and lane corrections.


# Base gap acceptance times (seconds) for a two-lane road with grade <= 3%.
# From AGRD Part 4A Table 3.2, aligned with AASHTO Green Book Table 9-6.
# Left-turn gap times represent the controlling (larger) case.
_BASE_GAP_TIME: dict[str, dict[str, float]] = {
    "give_way": {
        "passenger": 6.5,
        "single_unit_truck": 8.5,
        "semi_trailer": 10.5,
    },
    "stop": {
        "passenger": 7.5,
        "single_unit_truck": 9.5,
        "semi_trailer": 11.5,
    },
}

# Additional time per extra lane to cross (beyond 2 lanes on the major road).
# Passenger vehicles add 0.5 s/lane; trucks add 0.7 s/lane.
_LANE_ADJUSTMENT: dict[str, float] = {
    "passenger": 0.5,
    "single_unit_truck": 0.7,
    "semi_trailer": 0.7,
}


def _validate_inputs(
    design_speed_kmh: float,
    control_type: str,
    approach_grade_pct: float,
    num_lanes_to_cross: int,
    vehicle_type: str,
    setback_distance_m: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if design_speed_kmh <= 0:
        msg = "design_speed_kmh must be > 0"
        raise ValueError(msg)
    if design_speed_kmh > 130:
        msg = "design_speed_kmh must be <= 130"
        raise ValueError(msg)

    valid_controls = set(_BASE_GAP_TIME.keys())
    if control_type not in valid_controls:
        msg = f"control_type must be one of {sorted(valid_controls)}"
        raise ValueError(msg)

    if approach_grade_pct < -10.0 or approach_grade_pct > 10.0:
        msg = "approach_grade_pct must be between -10 and 10"
        raise ValueError(msg)

    if num_lanes_to_cross < 2:
        msg = "num_lanes_to_cross must be >= 2"
        raise ValueError(msg)
    if num_lanes_to_cross > 8:
        msg = "num_lanes_to_cross must be <= 8"
        raise ValueError(msg)

    valid_vehicles = set(_LANE_ADJUSTMENT.keys())
    if vehicle_type not in valid_vehicles:
        msg = f"vehicle_type must be one of {sorted(valid_vehicles)}"
        raise ValueError(msg)

    if setback_distance_m <= 0:
        msg = "setback_distance_m must be > 0"
        raise ValueError(msg)
    if setback_distance_m > 30.0:
        msg = "setback_distance_m must be <= 30"
        raise ValueError(msg)


def _grade_time_adjustment(approach_grade_pct: float) -> float:
    """Calculate additional gap acceptance time for steep upgrade approaches.

    Per AGRD Part 4A / AASHTO: for upgrade grades exceeding 3%, add 0.2 s
    per percent grade above the 3% threshold.  Downgrades receive no
    adjustment (vehicles roll from stop more easily downhill).
    """
    if approach_grade_pct <= 3.0:
        return 0.0
    return 0.2 * (approach_grade_pct - 3.0)


def _lane_time_adjustment(vehicle_type: str, num_lanes_to_cross: int) -> float:
    """Calculate additional gap acceptance time for extra crossing lanes.

    For major roads with more than 2 lanes, add time per extra lane:
    0.5 s/lane for passenger vehicles, 0.7 s/lane for trucks.
    """
    extra_lanes = max(0, num_lanes_to_cross - 2)
    return _LANE_ADJUSTMENT[vehicle_type] * extra_lanes


def _gap_acceptance_time(
    control_type: str,
    vehicle_type: str,
    approach_grade_pct: float,
    num_lanes_to_cross: int,
) -> float:
    """Compute the total gap acceptance time including all corrections.

    t_gap = t_base + t_grade + t_lane
    """
    t_base = _BASE_GAP_TIME[control_type][vehicle_type]
    t_grade = _grade_time_adjustment(approach_grade_pct)
    t_lane = _lane_time_adjustment(vehicle_type, num_lanes_to_cross)
    return t_base + t_grade + t_lane


def _intersection_sight_distance(
    design_speed_kmh: float,
    gap_time_s: float,
) -> float:
    """Calculate the required intersection sight distance along the major road.

    ISD = V_major * t_gap / 3.6

    where V_major is the design speed of the major road in km/h and
    t_gap is the total gap acceptance time in seconds.  The factor 3.6
    converts km/h to m/s.
    """
    return design_speed_kmh * gap_time_s / 3.6


def compute(
    design_speed_kmh: float,
    control_type: str,
    approach_grade_pct: float,
    num_lanes_to_cross: int,
    vehicle_type: str,
    setback_distance_m: float,
) -> dict[str, float]:
    """Compute intersection sight distance and sight-triangle dimensions.

    Returns a dict with keys: gap_time_s, required_isd_m,
    sight_triangle_major_m, sight_triangle_minor_m.
    """
    _validate_inputs(
        design_speed_kmh,
        control_type,
        approach_grade_pct,
        num_lanes_to_cross,
        vehicle_type,
        setback_distance_m,
    )

    gap_time_s = _gap_acceptance_time(
        control_type,
        vehicle_type,
        approach_grade_pct,
        num_lanes_to_cross,
    )

    isd = _intersection_sight_distance(design_speed_kmh, gap_time_s)

    # Sight triangle: the major-road leg equals the ISD; the minor-road
    # leg is the setback distance from the edge of the travel way to the
    # driver eye position (typically 5-15 m depending on geometry).
    sight_triangle_major_m = isd
    sight_triangle_minor_m = setback_distance_m

    return {
        "gap_time_s": round(gap_time_s, 2),
        "required_isd_m": round(isd, 2),
        "sight_triangle_major_m": round(sight_triangle_major_m, 2),
        "sight_triangle_minor_m": round(sight_triangle_minor_m, 2),
    }
