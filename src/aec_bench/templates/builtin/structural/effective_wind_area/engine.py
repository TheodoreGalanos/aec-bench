# ABOUTME: Effective wind area computation engine for facade pressure checks.
# ABOUTME: Calculates panel and supporting-member effective wind areas.


def _validate_inputs(
    panel_width_m: float,
    panel_height_m: float,
    supporting_member_span_m: float,
    tributary_width_m: float,
    minimum_effective_area_m2: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "panel_width_m": panel_width_m,
        "panel_height_m": panel_height_m,
        "supporting_member_span_m": supporting_member_span_m,
        "tributary_width_m": tributary_width_m,
        "minimum_effective_area_m2": minimum_effective_area_m2,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    panel_width_m: float,
    panel_height_m: float,
    supporting_member_span_m: float,
    tributary_width_m: float,
    minimum_effective_area_m2: float,
) -> dict[str, float]:
    """Compute effective wind area for cladding pressure selection.

    Returns a dict with keys: panel_area_m2, member_tributary_area_m2,
    effective_wind_area_m2, area_averaging_ratio.
    """
    _validate_inputs(
        panel_width_m,
        panel_height_m,
        supporting_member_span_m,
        tributary_width_m,
        minimum_effective_area_m2,
    )

    panel_area = panel_width_m * panel_height_m
    member_area = supporting_member_span_m * tributary_width_m
    raw_effective_area = max(panel_area, member_area)
    effective_area = max(raw_effective_area, minimum_effective_area_m2)
    area_averaging_ratio = effective_area / minimum_effective_area_m2

    return {
        "panel_area_m2": round(panel_area, 2),
        "member_tributary_area_m2": round(member_area, 2),
        "effective_wind_area_m2": round(effective_area, 2),
        "area_averaging_ratio": round(area_averaging_ratio, 2),
    }
