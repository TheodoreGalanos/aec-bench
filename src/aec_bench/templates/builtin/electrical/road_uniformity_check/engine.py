# ABOUTME: Computes road lighting overall and longitudinal uniformity ratios.
# ABOUTME: Compares overall uniformity against a target class value.


def _validate_inputs(
    minimum_luminance_cd_m2: float,
    average_luminance_cd_m2: float,
    longitudinal_min_luminance_cd_m2: float,
    longitudinal_max_luminance_cd_m2: float,
    target_overall_uniformity: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "minimum_luminance_cd_m2": minimum_luminance_cd_m2,
        "longitudinal_min_luminance_cd_m2": longitudinal_min_luminance_cd_m2,
    }.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)
    for name, value in {
        "average_luminance_cd_m2": average_luminance_cd_m2,
        "longitudinal_max_luminance_cd_m2": longitudinal_max_luminance_cd_m2,
        "target_overall_uniformity": target_overall_uniformity,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    minimum_luminance_cd_m2: float,
    average_luminance_cd_m2: float,
    longitudinal_min_luminance_cd_m2: float,
    longitudinal_max_luminance_cd_m2: float,
    target_overall_uniformity: float,
) -> dict[str, float]:
    """Compute road lighting uniformity ratios and target margin."""
    _validate_inputs(
        minimum_luminance_cd_m2,
        average_luminance_cd_m2,
        longitudinal_min_luminance_cd_m2,
        longitudinal_max_luminance_cd_m2,
        target_overall_uniformity,
    )

    overall_uniformity_uo = minimum_luminance_cd_m2 / average_luminance_cd_m2
    longitudinal_uniformity_ul = longitudinal_min_luminance_cd_m2 / longitudinal_max_luminance_cd_m2
    overall_uniformity_margin_pct = (overall_uniformity_uo / target_overall_uniformity - 1.0) * 100.0

    return {
        "overall_uniformity_uo": round(overall_uniformity_uo, 2),
        "longitudinal_uniformity_ul": round(longitudinal_uniformity_ul, 2),
        "overall_uniformity_margin_pct": round(overall_uniformity_margin_pct, 2),
    }
