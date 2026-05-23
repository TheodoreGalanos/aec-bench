# ABOUTME: Pipe support dead-load computation engine for structural support checks.
# ABOUTME: Calculates operating and hydrotest line loads from pipe geometry and densities.

import math


def _validate_inputs(
    pipe_outer_diameter_mm: float,
    pipe_wall_thickness_mm: float,
    steel_density_kg_m3: float,
    contents_density_kg_m3: float,
    insulation_thickness_mm: float,
    insulation_density_kg_m3: float,
    hydrotest_density_kg_m3: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if pipe_outer_diameter_mm <= 0:
        msg = "pipe_outer_diameter_mm must be > 0"
        raise ValueError(msg)
    if pipe_wall_thickness_mm <= 0:
        msg = "pipe_wall_thickness_mm must be > 0"
        raise ValueError(msg)
    if 2.0 * pipe_wall_thickness_mm >= pipe_outer_diameter_mm:
        msg = "pipe wall thickness must leave a positive internal diameter"
        raise ValueError(msg)
    if insulation_thickness_mm < 0:
        msg = "insulation_thickness_mm must be >= 0"
        raise ValueError(msg)
    for name, value in {
        "steel_density_kg_m3": steel_density_kg_m3,
        "contents_density_kg_m3": contents_density_kg_m3,
        "insulation_density_kg_m3": insulation_density_kg_m3,
        "hydrotest_density_kg_m3": hydrotest_density_kg_m3,
    }.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)


def _annulus_area_m2(outer_diameter_mm: float, inner_diameter_mm: float) -> float:
    """Return circular annulus area from diameters in millimetres."""
    return math.pi / 4.0 * ((outer_diameter_mm / 1000.0) ** 2 - (inner_diameter_mm / 1000.0) ** 2)


def _circle_area_m2(diameter_mm: float) -> float:
    """Return circular area from diameter in millimetres."""
    return math.pi / 4.0 * (diameter_mm / 1000.0) ** 2


def _line_load_kn_m(area_m2: float, density_kg_m3: float) -> float:
    """Return gravity line load in kN/m for a material area and density."""
    return area_m2 * density_kg_m3 * 9.81 / 1000.0


def compute(
    pipe_outer_diameter_mm: float,
    pipe_wall_thickness_mm: float,
    steel_density_kg_m3: float,
    contents_density_kg_m3: float,
    insulation_thickness_mm: float,
    insulation_density_kg_m3: float,
    hydrotest_density_kg_m3: float,
) -> dict[str, float]:
    """Compute pipe support operating and hydrotest dead line loads.

    Returns a dict with keys: steel_pipe_load_kn_m, contents_load_kn_m,
    insulation_load_kn_m, operating_line_load_kn_m, hydrotest_line_load_kn_m.
    """
    _validate_inputs(
        pipe_outer_diameter_mm,
        pipe_wall_thickness_mm,
        steel_density_kg_m3,
        contents_density_kg_m3,
        insulation_thickness_mm,
        insulation_density_kg_m3,
        hydrotest_density_kg_m3,
    )

    pipe_inner_diameter = pipe_outer_diameter_mm - 2.0 * pipe_wall_thickness_mm
    insulation_outer_diameter = pipe_outer_diameter_mm + 2.0 * insulation_thickness_mm

    steel_area = _annulus_area_m2(pipe_outer_diameter_mm, pipe_inner_diameter)
    contents_area = _circle_area_m2(pipe_inner_diameter)
    insulation_area = _annulus_area_m2(insulation_outer_diameter, pipe_outer_diameter_mm)

    steel_pipe_load = _line_load_kn_m(steel_area, steel_density_kg_m3)
    contents_load = _line_load_kn_m(contents_area, contents_density_kg_m3)
    insulation_load = _line_load_kn_m(insulation_area, insulation_density_kg_m3)
    hydrotest_contents_load = _line_load_kn_m(contents_area, hydrotest_density_kg_m3)
    operating_line_load = steel_pipe_load + contents_load + insulation_load
    hydrotest_line_load = steel_pipe_load + hydrotest_contents_load + insulation_load

    return {
        "steel_pipe_load_kn_m": round(steel_pipe_load, 3),
        "contents_load_kn_m": round(contents_load, 3),
        "insulation_load_kn_m": round(insulation_load, 3),
        "operating_line_load_kn_m": round(operating_line_load, 3),
        "hydrotest_line_load_kn_m": round(hydrotest_line_load, 3),
    }
