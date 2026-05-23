# ABOUTME: Pipe invert level computation engine for stormwater drainage.
# ABOUTME: Calculates downstream invert, obvert level, cover depth, and grade fall.

from typing import Literal

# Valid nominal pipe diameters for stormwater drainage (mm).
_VALID_DIAMETERS = ("225", "300", "375", "450", "600", "750", "900")


def _validate_inputs(
    upstream_invert_m: float,
    pipe_length_m: float,
    pipe_grade_percent: float,
    pipe_diameter_mm: str,
    surface_level_ds_m: float,
    minimum_cover_mm: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if pipe_length_m <= 0:
        msg = "pipe_length_m must be > 0"
        raise ValueError(msg)
    if pipe_grade_percent <= 0:
        msg = "pipe_grade_percent must be > 0"
        raise ValueError(msg)
    if str(pipe_diameter_mm) not in _VALID_DIAMETERS:
        msg = f"pipe_diameter_mm must be one of {list(_VALID_DIAMETERS)}, got '{pipe_diameter_mm}'"
        raise ValueError(msg)
    if minimum_cover_mm < 0:
        msg = "minimum_cover_mm must be >= 0"
        raise ValueError(msg)


def compute(
    upstream_invert_m: float,
    pipe_length_m: float,
    pipe_grade_percent: float,
    pipe_diameter_mm: Literal["225", "300", "375", "450", "600", "750", "900"],
    surface_level_ds_m: float,
    minimum_cover_mm: float = 600.0,
) -> dict[str, float]:
    """Compute downstream invert level, obvert, cover depth, and grade fall.

    Formulae:
      1. Grade fall:        fall = (grade / 100) * length
      2. Downstream invert: IL_ds = IL_us - fall
      3. Obvert (crown):    OL_ds = IL_ds + D  (D in metres)
      4. Cover depth:       cover = surface_level_ds - OL_ds  (in mm)
      5. Cover adequate:    1.0 if cover >= minimum_cover, else 0.0

    Returns a dict with keys: downstream_invert_m, obvert_level_m,
    cover_depth_mm, grade_fall_m, cover_adequate.
    """
    _validate_inputs(
        upstream_invert_m,
        pipe_length_m,
        pipe_grade_percent,
        pipe_diameter_mm,
        surface_level_ds_m,
        minimum_cover_mm,
    )

    # Convert enum diameter string to numeric value
    diameter_mm = float(pipe_diameter_mm)

    # Grade fall over the pipe length
    grade_fall_m = (pipe_grade_percent / 100.0) * pipe_length_m

    # Downstream invert level
    downstream_invert_m = upstream_invert_m - grade_fall_m

    # Obvert (crown) level at downstream end
    diameter_m = diameter_mm / 1000.0
    obvert_level_m = downstream_invert_m + diameter_m

    # Cover depth at downstream end (surface level minus obvert), in mm
    cover_depth_mm = (surface_level_ds_m - obvert_level_m) * 1000.0

    # Cover adequacy check against minimum cover requirement
    cover_adequate = 1.0 if cover_depth_mm >= minimum_cover_mm else 0.0

    return {
        "downstream_invert_m": round(downstream_invert_m, 2),
        "obvert_level_m": round(obvert_level_m, 2),
        "cover_depth_mm": round(cover_depth_mm, 2),
        "grade_fall_m": round(grade_fall_m, 2),
        "cover_adequate": round(cover_adequate, 2),
    }
