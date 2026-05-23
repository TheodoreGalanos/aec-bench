# ABOUTME: Rail thermal stress computation engine for continuously welded rail (CWR).
# ABOUTME: Implements AREMA/ARTC thermal stress sigma = E * alpha * dT and force F = sigma * A / 1000.


def _validate_inputs(
    rail_area_mm2: float,
    thermal_expansion_coeff_micro_per_c: float,
    elastic_modulus_mpa: float,
    temperature_change_c: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if rail_area_mm2 <= 0:
        msg = "rail_area_mm2 must be > 0"
        raise ValueError(msg)
    if thermal_expansion_coeff_micro_per_c <= 0:
        msg = "thermal_expansion_coeff_micro_per_c must be > 0"
        raise ValueError(msg)
    if elastic_modulus_mpa <= 0:
        msg = "elastic_modulus_mpa must be > 0"
        raise ValueError(msg)
    # temperature_change_c can be negative (cooling), zero (neutral), or positive (heating)


def compute(
    rail_area_mm2: float,
    thermal_expansion_coeff_micro_per_c: float,
    elastic_modulus_mpa: float,
    temperature_change_c: float,
) -> dict[str, float]:
    """Compute thermal stress, force, and stress state in continuously welded rail.

    Returns a dict with keys: thermal_stress_mpa, thermal_force_kn, stress_state.

    Thermal stress: sigma = E * alpha * |dT|  (always reported as positive magnitude)
    Thermal force:  F = sigma * A / 1000       (kN, positive magnitude)
    Stress state:   1.0 = compression (rail hotter than neutral),
                   -1.0 = tension (rail cooler than neutral),
                    0.0 = neutral (no temperature change)
    """
    _validate_inputs(
        rail_area_mm2,
        thermal_expansion_coeff_micro_per_c,
        elastic_modulus_mpa,
        temperature_change_c,
    )

    # Convert coefficient from x10^-6 /C to /C for calculation
    alpha = thermal_expansion_coeff_micro_per_c * 1e-6

    # Thermal stress magnitude (MPa)
    # sigma = E * alpha * |dT|
    thermal_stress = elastic_modulus_mpa * alpha * abs(temperature_change_c)

    # Thermal force magnitude (kN)
    # F = sigma * A / 1000  (converting N to kN)
    thermal_force = thermal_stress * rail_area_mm2 / 1000.0

    # Stress state: compression when rail is hotter than neutral temp (dT > 0),
    # tension when cooler (dT < 0), neutral when no change (dT = 0)
    if temperature_change_c > 0:
        stress_state = 1.0
    elif temperature_change_c < 0:
        stress_state = -1.0
    else:
        stress_state = 0.0

    return {
        "thermal_stress_mpa": round(thermal_stress, 2),
        "thermal_force_kn": round(thermal_force, 2),
        "stress_state": round(stress_state, 2),
    }
