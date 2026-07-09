# ABOUTME: Computes SSC-02 OLE thermal stress, hot tension, sag, and clearance metrics.
# ABOUTME: Uses a deterministic single-span sag and thermal-expansion source-pack check.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    span_length_m: float,
    conductor_unit_weight_n_m: float,
    initial_tension_kn: float,
    thermal_expansion_per_c: float,
    youngs_modulus_mpa: float,
    temp_delta_c: float,
    cross_section_mm2: float,
    static_clearance_m: float,
    signal_envelope_m: float,
    max_allowed_sag_m: float,
    allowable_thermal_stress_mpa: float,
) -> dict[str, float]:
    """Compute source-bound OLE thermal, sag, and signal-clearance metrics."""
    _require_positive(
        span_length_m=span_length_m,
        conductor_unit_weight_n_m=conductor_unit_weight_n_m,
        initial_tension_kn=initial_tension_kn,
        thermal_expansion_per_c=thermal_expansion_per_c,
        youngs_modulus_mpa=youngs_modulus_mpa,
        temp_delta_c=temp_delta_c,
        cross_section_mm2=cross_section_mm2,
        static_clearance_m=static_clearance_m,
        signal_envelope_m=signal_envelope_m,
        max_allowed_sag_m=max_allowed_sag_m,
        allowable_thermal_stress_mpa=allowable_thermal_stress_mpa,
    )

    thermal_stress_mpa = youngs_modulus_mpa * thermal_expansion_per_c * temp_delta_c
    thermal_tension_loss_kn = thermal_stress_mpa * cross_section_mm2 / 1000.0
    hot_tension_kn = initial_tension_kn - thermal_tension_loss_kn
    if hot_tension_kn <= 0.0:
        msg = "hot_tension_kn must be > 0"
        raise ValueError(msg)

    sag_m = conductor_unit_weight_n_m * span_length_m**2 / (8.0 * hot_tension_kn * 1000.0)
    clearance_at_sag_m = static_clearance_m - sag_m
    clearance_margin_m = clearance_at_sag_m - signal_envelope_m
    sag_margin_m = max_allowed_sag_m - sag_m
    thermal_stress_margin_mpa = allowable_thermal_stress_mpa - thermal_stress_mpa
    overall_pass_score = 1.0 if min(clearance_margin_m, sag_margin_m, thermal_stress_margin_mpa) >= 0.0 else 0.0

    return {
        "thermal_stress_mpa": round(thermal_stress_mpa, 3),
        "thermal_tension_loss_kn": round(thermal_tension_loss_kn, 3),
        "hot_tension_kn": round(hot_tension_kn, 3),
        "sag_m": round(sag_m, 3),
        "clearance_at_sag_m": round(clearance_at_sag_m, 3),
        "clearance_margin_m": round(clearance_margin_m, 3),
        "sag_margin_m": round(sag_margin_m, 3),
        "thermal_stress_margin_mpa": round(thermal_stress_margin_mpa, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
