# ABOUTME: Reduced load combination computation engine for structural actions.
# ABOUTME: Applies explicit factors to three action combinations and reports the governing case.


def _validate_inputs(*values: float) -> None:
    """Raise ValueError for invalid input parameters."""
    for value in values:
        if value < 0:
            msg = "load effects and factors must be >= 0"
            raise ValueError(msg)


def compute(
    dead_moment_knm: float,
    live_moment_knm: float,
    wind_moment_knm: float,
    seismic_moment_knm: float,
    dead_shear_kn: float,
    live_shear_kn: float,
    wind_shear_kn: float,
    seismic_shear_kn: float,
    combo_1_dead_factor: float,
    combo_1_live_factor: float,
    combo_2_dead_factor: float,
    combo_2_wind_factor: float,
    combo_3_dead_factor: float,
    combo_3_seismic_factor: float,
) -> dict[str, float]:
    """Compute three explicit load combinations and governing action effects.

    Returns a dict with keys: combo_1_moment_knm, combo_2_moment_knm,
    combo_3_moment_knm, governing_moment_knm, governing_shear_kn,
    governing_combination_index.
    """
    _validate_inputs(
        dead_moment_knm,
        live_moment_knm,
        wind_moment_knm,
        seismic_moment_knm,
        dead_shear_kn,
        live_shear_kn,
        wind_shear_kn,
        seismic_shear_kn,
        combo_1_dead_factor,
        combo_1_live_factor,
        combo_2_dead_factor,
        combo_2_wind_factor,
        combo_3_dead_factor,
        combo_3_seismic_factor,
    )

    combo_1_moment = combo_1_dead_factor * dead_moment_knm + combo_1_live_factor * live_moment_knm
    combo_2_moment = combo_2_dead_factor * dead_moment_knm + combo_2_wind_factor * wind_moment_knm
    combo_3_moment = combo_3_dead_factor * dead_moment_knm + combo_3_seismic_factor * seismic_moment_knm
    combo_1_shear = combo_1_dead_factor * dead_shear_kn + combo_1_live_factor * live_shear_kn
    combo_2_shear = combo_2_dead_factor * dead_shear_kn + combo_2_wind_factor * wind_shear_kn
    combo_3_shear = combo_3_dead_factor * dead_shear_kn + combo_3_seismic_factor * seismic_shear_kn

    combinations = [
        (1.0, combo_1_moment, combo_1_shear),
        (2.0, combo_2_moment, combo_2_shear),
        (3.0, combo_3_moment, combo_3_shear),
    ]
    governing_index, governing_moment, governing_shear = max(
        combinations,
        key=lambda item: item[1],
    )

    return {
        "combo_1_moment_knm": round(combo_1_moment, 2),
        "combo_2_moment_knm": round(combo_2_moment, 2),
        "combo_3_moment_knm": round(combo_3_moment, 2),
        "governing_moment_knm": round(governing_moment, 2),
        "governing_shear_kn": round(governing_shear, 2),
        "governing_combination_index": round(governing_index, 2),
    }
