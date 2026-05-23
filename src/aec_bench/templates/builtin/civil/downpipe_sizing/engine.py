# ABOUTME: AS/NZS 3500.3 downpipe sizing engine for roof drainage.
# ABOUTME: Computes design flow per downpipe and selects the smallest standard diameter with adequate capacity.


def _validate_inputs(
    roof_catchment_area_m2: float,
    rainfall_intensity_mm_hr: float,
    num_downpipes: int,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if roof_catchment_area_m2 <= 0:
        msg = "roof_catchment_area_m2 must be > 0"
        raise ValueError(msg)
    if rainfall_intensity_mm_hr <= 0:
        msg = "rainfall_intensity_mm_hr must be > 0"
        raise ValueError(msg)
    if num_downpipes <= 0:
        msg = "num_downpipes must be > 0"
        raise ValueError(msg)


# Standard uPVC round downpipe diameters (mm) and their approximate
# full-bore gravity flow capacities (L/s) per AS/NZS 3500.3 Table 4.3.
_CAPACITY_TABLE: list[tuple[int, float]] = [
    (65, 0.7),
    (80, 1.3),
    (90, 2.0),
    (100, 3.0),
    (125, 5.5),
    (150, 9.0),
]


def compute(
    roof_catchment_area_m2: float,
    rainfall_intensity_mm_hr: float,
    num_downpipes: int,
) -> dict[str, float]:
    """Size roof downpipes per AS/NZS 3500.3.

    Design flow per downpipe:
        Q = (I x A / num_downpipes) / 3600  (L/s)
    where I is in mm/hr and A is in m^2.

    The smallest standard uPVC round downpipe diameter whose full-bore
    capacity meets or exceeds the design flow is selected from the
    AS/NZS 3500.3 Table 4.3 capacity lookup.

    Returns a dict with keys: design_flow_l_s, selected_diameter_mm,
    selected_capacity_l_s, compliance.
    """
    _validate_inputs(roof_catchment_area_m2, rainfall_intensity_mm_hr, num_downpipes)

    # Design flow per downpipe (L/s)
    design_flow_l_s = (rainfall_intensity_mm_hr * roof_catchment_area_m2 / num_downpipes) / 3600.0

    # Select smallest standard diameter with adequate capacity
    selected_diameter_mm = 0.0
    selected_capacity_l_s = 0.0
    for diameter_mm, capacity_l_s in _CAPACITY_TABLE:
        if capacity_l_s >= design_flow_l_s:
            selected_diameter_mm = float(diameter_mm)
            selected_capacity_l_s = capacity_l_s
            break

    # If no standard size is adequate, select the largest available
    if selected_diameter_mm == 0.0:
        selected_diameter_mm = float(_CAPACITY_TABLE[-1][0])
        selected_capacity_l_s = _CAPACITY_TABLE[-1][1]

    # Compliance: 1.0 if selected capacity >= design flow, else 0.0
    compliance = 1.0 if selected_capacity_l_s >= design_flow_l_s else 0.0

    return {
        "design_flow_l_s": round(design_flow_l_s, 2),
        "selected_diameter_mm": round(selected_diameter_mm, 2),
        "selected_capacity_l_s": round(selected_capacity_l_s, 2),
        "compliance": round(compliance, 2),
    }
