# ABOUTME: Composite steel-concrete section property computation engine.
# ABOUTME: Calculates transformed area, neutral axis, inertia, and section moduli.


def _validate_inputs(
    top_flange_width_mm: float,
    top_flange_thickness_mm: float,
    web_depth_mm: float,
    web_thickness_mm: float,
    bottom_flange_width_mm: float,
    bottom_flange_thickness_mm: float,
    slab_width_mm: float,
    slab_thickness_mm: float,
    haunch_width_mm: float,
    haunch_thickness_mm: float,
    modular_ratio: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    values = {
        "top_flange_width_mm": top_flange_width_mm,
        "top_flange_thickness_mm": top_flange_thickness_mm,
        "web_depth_mm": web_depth_mm,
        "web_thickness_mm": web_thickness_mm,
        "bottom_flange_width_mm": bottom_flange_width_mm,
        "bottom_flange_thickness_mm": bottom_flange_thickness_mm,
        "slab_width_mm": slab_width_mm,
        "slab_thickness_mm": slab_thickness_mm,
        "haunch_width_mm": haunch_width_mm,
        "haunch_thickness_mm": haunch_thickness_mm,
        "modular_ratio": modular_ratio,
    }
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _rect_area(width_mm: float, depth_mm: float, modular_ratio: float = 1.0) -> float:
    """Return transformed rectangular area."""
    return width_mm * depth_mm / modular_ratio


def _rect_inertia(width_mm: float, depth_mm: float, modular_ratio: float = 1.0) -> float:
    """Return transformed rectangular second moment of area about its centroid."""
    return width_mm * depth_mm**3 / (12.0 * modular_ratio)


def compute(
    top_flange_width_mm: float,
    top_flange_thickness_mm: float,
    web_depth_mm: float,
    web_thickness_mm: float,
    bottom_flange_width_mm: float,
    bottom_flange_thickness_mm: float,
    slab_width_mm: float,
    slab_thickness_mm: float,
    haunch_width_mm: float,
    haunch_thickness_mm: float,
    modular_ratio: float,
) -> dict[str, float]:
    """Compute transformed composite section properties.

    Returns a dict with keys: transformed_area_mm2, neutral_axis_from_bottom_mm,
    transformed_inertia_mm4, bottom_section_modulus_mm3, top_section_modulus_mm3.
    """
    _validate_inputs(
        top_flange_width_mm,
        top_flange_thickness_mm,
        web_depth_mm,
        web_thickness_mm,
        bottom_flange_width_mm,
        bottom_flange_thickness_mm,
        slab_width_mm,
        slab_thickness_mm,
        haunch_width_mm,
        haunch_thickness_mm,
        modular_ratio,
    )

    steel_depth = bottom_flange_thickness_mm + web_depth_mm + top_flange_thickness_mm
    total_depth = steel_depth + haunch_thickness_mm + slab_thickness_mm
    components = (
        (
            _rect_area(bottom_flange_width_mm, bottom_flange_thickness_mm),
            bottom_flange_thickness_mm / 2.0,
            _rect_inertia(bottom_flange_width_mm, bottom_flange_thickness_mm),
        ),
        (
            _rect_area(web_thickness_mm, web_depth_mm),
            bottom_flange_thickness_mm + web_depth_mm / 2.0,
            _rect_inertia(web_thickness_mm, web_depth_mm),
        ),
        (
            _rect_area(top_flange_width_mm, top_flange_thickness_mm),
            bottom_flange_thickness_mm + web_depth_mm + top_flange_thickness_mm / 2.0,
            _rect_inertia(top_flange_width_mm, top_flange_thickness_mm),
        ),
        (
            _rect_area(haunch_width_mm, haunch_thickness_mm, modular_ratio),
            steel_depth + haunch_thickness_mm / 2.0,
            _rect_inertia(haunch_width_mm, haunch_thickness_mm, modular_ratio),
        ),
        (
            _rect_area(slab_width_mm, slab_thickness_mm, modular_ratio),
            steel_depth + haunch_thickness_mm + slab_thickness_mm / 2.0,
            _rect_inertia(slab_width_mm, slab_thickness_mm, modular_ratio),
        ),
    )

    transformed_area = sum(area for area, _, _ in components)
    neutral_axis = sum(area * centroid for area, centroid, _ in components) / transformed_area
    transformed_inertia = sum(inertia + area * (centroid - neutral_axis) ** 2 for area, centroid, inertia in components)
    bottom_section_modulus = transformed_inertia / neutral_axis
    top_section_modulus = transformed_inertia / (total_depth - neutral_axis)

    return {
        "transformed_area_mm2": round(transformed_area, 2),
        "neutral_axis_from_bottom_mm": round(neutral_axis, 2),
        "transformed_inertia_mm4": round(transformed_inertia, 2),
        "bottom_section_modulus_mm3": round(bottom_section_modulus, 2),
        "top_section_modulus_mm3": round(top_section_modulus, 2),
    }
