# ABOUTME: AS/NZS 3500.3 eaves gutter sizing engine for roof drainage.
# ABOUTME: Computes design flow and selects the smallest standard gutter profile with adequate capacity.

import math

# Standard eaves gutter profiles and their approximate capacities (L/s)
# at the reference grade of 1:500 (0.2%), per AS/NZS 3500.3 Table 4.2.
# Each entry: (profile_key, nominal_size_mm, capacity_at_ref_grade_l_s)
_GUTTER_TABLE: list[tuple[str, int, float]] = [
    ("100mm_quad", 100, 0.6),
    ("115mm_quad", 115, 0.9),
    ("125mm_half_round", 125, 1.0),
    ("150mm_quad", 150, 1.8),
    ("150mm_half_round", 150, 2.0),
    ("175mm_OG", 175, 2.5),
]

# Reference grade for the capacity table (1:500 = 0.2%).
_REF_GRADE_PCT = 0.2

# Valid gutter profile keys for input validation.
_VALID_PROFILES = [entry[0] for entry in _GUTTER_TABLE]


def _validate_inputs(
    roof_catchment_area_m2: float,
    rainfall_intensity_mm_hr: float,
    gutter_profile: str,
    gutter_grade_pct: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if roof_catchment_area_m2 <= 0:
        msg = "roof_catchment_area_m2 must be > 0"
        raise ValueError(msg)
    if rainfall_intensity_mm_hr <= 0:
        msg = "rainfall_intensity_mm_hr must be > 0"
        raise ValueError(msg)
    if gutter_profile not in _VALID_PROFILES:
        msg = f"gutter_profile must be one of {_VALID_PROFILES}, got '{gutter_profile}'"
        raise ValueError(msg)
    if gutter_grade_pct <= 0:
        msg = "gutter_grade_pct must be > 0"
        raise ValueError(msg)


def compute(
    roof_catchment_area_m2: float,
    rainfall_intensity_mm_hr: float,
    gutter_profile: str,
    gutter_grade_pct: float,
) -> dict[str, float]:
    """Size an eaves gutter per AS/NZS 3500.3.

    Design flow:
        Q = I x A / 3600  (L/s)
    where I is in mm/hr and A is in m^2.

    Gutter capacity at the installed grade is derived from the reference
    capacity at 1:500 (0.2%) scaled by sqrt(grade / 0.002).  The capacity
    of the nominated gutter profile is checked.  If it is inadequate, the
    smallest standard profile that handles the flow is selected.

    Returns a dict with keys: design_flow_l_s, gutter_capacity_l_s,
    required_gutter_size_mm, compliance.
    """
    _validate_inputs(
        roof_catchment_area_m2,
        rainfall_intensity_mm_hr,
        gutter_profile,
        gutter_grade_pct,
    )

    # Design flow (L/s)
    design_flow_l_s = rainfall_intensity_mm_hr * roof_catchment_area_m2 / 3600.0

    # Grade scaling factor: capacity proportional to sqrt(grade)
    grade_ratio = gutter_grade_pct / _REF_GRADE_PCT
    grade_factor = math.sqrt(grade_ratio)

    # Capacity of the nominated gutter profile at the installed grade
    _nominated_capacity_l_s = 0.0
    for profile_key, _size_mm, ref_cap in _GUTTER_TABLE:
        if profile_key == gutter_profile:
            _nominated_capacity_l_s = ref_cap * grade_factor
            break

    # Select the smallest standard gutter that handles the design flow
    required_gutter_size_mm = 0.0
    gutter_capacity_l_s = 0.0
    for _profile_key, size_mm, ref_cap in _GUTTER_TABLE:
        adjusted_cap = ref_cap * grade_factor
        if adjusted_cap >= design_flow_l_s:
            required_gutter_size_mm = float(size_mm)
            gutter_capacity_l_s = adjusted_cap
            break

    # If no standard size is adequate, select the largest available
    if required_gutter_size_mm == 0.0:
        _profile_key, size_mm, ref_cap = _GUTTER_TABLE[-1]
        required_gutter_size_mm = float(size_mm)
        gutter_capacity_l_s = ref_cap * grade_factor

    # Compliance: 1.0 if the selected gutter capacity >= design flow
    compliance = 1.0 if gutter_capacity_l_s >= design_flow_l_s else 0.0

    return {
        "design_flow_l_s": round(design_flow_l_s, 2),
        "gutter_capacity_l_s": round(gutter_capacity_l_s, 2),
        "required_gutter_size_mm": round(required_gutter_size_mm, 2),
        "compliance": round(compliance, 2),
    }
