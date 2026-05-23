# ABOUTME: Computes CCTV horizontal field of view and pixels per metre.
# ABOUTME: Uses pinhole-camera geometry for deterministic surveillance screening.


def _validate_inputs(
    horizontal_pixels: float,
    sensor_width_mm: float,
    lens_focal_length_mm: float,
    target_distance_m: float,
    target_ppm: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "horizontal_pixels": horizontal_pixels,
        "sensor_width_mm": sensor_width_mm,
        "lens_focal_length_mm": lens_focal_length_mm,
        "target_distance_m": target_distance_m,
        "target_ppm": target_ppm,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    horizontal_pixels: float,
    sensor_width_mm: float,
    lens_focal_length_mm: float,
    target_distance_m: float,
    target_ppm: float,
) -> dict[str, float]:
    """Compute horizontal field of view and pixel density at the target plane."""
    _validate_inputs(
        horizontal_pixels,
        sensor_width_mm,
        lens_focal_length_mm,
        target_distance_m,
        target_ppm,
    )

    horizontal_field_of_view_m = sensor_width_mm * target_distance_m / lens_focal_length_mm
    pixels_per_meter = horizontal_pixels / horizontal_field_of_view_m
    target_ppm_margin_pct = (pixels_per_meter / target_ppm - 1.0) * 100.0

    return {
        "horizontal_field_of_view_m": round(horizontal_field_of_view_m, 2),
        "pixels_per_meter": round(pixels_per_meter, 2),
        "target_ppm_margin_pct": round(target_ppm_margin_pct, 2),
    }
