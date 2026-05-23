# ABOUTME: Computes overhead line capacitance and charging reactive power.
# ABOUTME: Uses reduced transposed-line GMD, conductor radius, and frequency relations.

import math

_EPSILON_0_F_PER_M = 8.854187817e-12


def _validate_inputs(
    conductor_radius_m: float,
    phase_spacing_ab_m: float,
    phase_spacing_bc_m: float,
    phase_spacing_ca_m: float,
    nominal_voltage_kv: float,
    frequency_hz: float,
    inductance_mh_per_km: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if conductor_radius_m <= 0:
        msg = "conductor_radius_m must be > 0"
        raise ValueError(msg)
    for name, value in {
        "phase_spacing_ab_m": phase_spacing_ab_m,
        "phase_spacing_bc_m": phase_spacing_bc_m,
        "phase_spacing_ca_m": phase_spacing_ca_m,
        "nominal_voltage_kv": nominal_voltage_kv,
        "frequency_hz": frequency_hz,
        "inductance_mh_per_km": inductance_mh_per_km,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    conductor_radius_m: float,
    phase_spacing_ab_m: float,
    phase_spacing_bc_m: float,
    phase_spacing_ca_m: float,
    nominal_voltage_kv: float,
    frequency_hz: float,
    inductance_mh_per_km: float,
) -> dict[str, float]:
    """Compute capacitance, charging Mvar per 100 km, and surge impedance."""
    _validate_inputs(
        conductor_radius_m,
        phase_spacing_ab_m,
        phase_spacing_bc_m,
        phase_spacing_ca_m,
        nominal_voltage_kv,
        frequency_hz,
        inductance_mh_per_km,
    )

    geometric_mean_distance_m = (phase_spacing_ab_m * phase_spacing_bc_m * phase_spacing_ca_m) ** (1.0 / 3.0)
    capacitance_f_per_m = (2.0 * math.pi * _EPSILON_0_F_PER_M) / math.log(
        geometric_mean_distance_m / conductor_radius_m
    )
    capacitance_nf_per_km = capacitance_f_per_m * 1_000_000_000.0 * 1000.0
    line_length_m = 100_000.0
    phase_voltage_v = nominal_voltage_kv * 1000.0 / math.sqrt(3.0)
    charging_mvar_per_100km = (
        3.0 * phase_voltage_v**2 * 2.0 * math.pi * frequency_hz * capacitance_f_per_m * line_length_m / 1_000_000.0
    )
    inductance_h_per_m = inductance_mh_per_km * 1e-6
    surge_impedance_ohm = math.sqrt(inductance_h_per_m / capacitance_f_per_m)

    return {
        "geometric_mean_distance_m": round(geometric_mean_distance_m, 2),
        "capacitance_nf_per_km": round(capacitance_nf_per_km, 2),
        "charging_mvar_per_100km": round(charging_mvar_per_100km, 2),
        "surge_impedance_ohm": round(surge_impedance_ohm, 2),
    }
