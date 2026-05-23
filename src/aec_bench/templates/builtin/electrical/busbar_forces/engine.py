# ABOUTME: IEEE 605 / IEC 60865-1 busbar short-circuit electromagnetic force engine.
# ABOUTME: Calculates force per unit length, peak force, and bending stress on rigid busbars.

import math
from typing import Literal

# Permeability of free space (H/m).
_MU_0 = 4.0 * math.pi * 1e-7

# Three-phase force geometry factor.
# For flat (coplanar) arrangement of three phases with equal spacing, the
# worst-case force on the centre phase uses the factor sqrt(3)/2 per
# IEC 60865-1 clause 5.2.  This accounts for the vector sum of forces from
# both adjacent phases during a symmetrical three-phase fault.
_THREE_PHASE_FACTOR = math.sqrt(3.0) / 2.0

# Bending moment coefficient beta for different support conditions.
# beta = 8 for simply-supported beam (uniform load), 12 for fixed-both-ends.
_SUPPORT_BETA: dict[str, float] = {
    "simply_supported": 8.0,
    "fixed_both_ends": 12.0,
}

# Busbar material properties: (yield strength R_p0.2 in MPa).
_MATERIAL_YIELD: dict[str, float] = {
    "copper": 200.0,
    "aluminium": 120.0,
}


def _validate_inputs(
    peak_short_circuit_current_ka: float,
    phase_spacing_mm: float,
    span_length_m: float,
    busbar_width_mm: float,
    busbar_thickness_mm: float,
    support_condition: str,
    busbar_material: str,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if peak_short_circuit_current_ka <= 0:
        msg = "peak_short_circuit_current_ka must be > 0"
        raise ValueError(msg)
    if phase_spacing_mm <= 0:
        msg = "phase_spacing_mm must be > 0"
        raise ValueError(msg)
    if span_length_m <= 0:
        msg = "span_length_m must be > 0"
        raise ValueError(msg)
    if busbar_width_mm <= 0:
        msg = "busbar_width_mm must be > 0"
        raise ValueError(msg)
    if busbar_thickness_mm <= 0:
        msg = "busbar_thickness_mm must be > 0"
        raise ValueError(msg)
    if support_condition not in _SUPPORT_BETA:
        valid = list(_SUPPORT_BETA.keys())
        msg = f"support_condition must be one of {valid}, got '{support_condition}'"
        raise ValueError(msg)
    if busbar_material not in _MATERIAL_YIELD:
        valid = list(_MATERIAL_YIELD.keys())
        msg = f"busbar_material must be one of {valid}, got '{busbar_material}'"
        raise ValueError(msg)


def _force_per_unit_length(peak_current_a: float, spacing_m: float) -> float:
    """Calculate electromagnetic force per unit length on the centre phase (N/m).

    Uses IEC 60865-1 formula for three-phase flat arrangement:
        Fm = (mu_0 / (2*pi)) * (sqrt(3)/2) * ip^2 / a
    where ip is the peak short-circuit current in amperes and a is the
    centre-to-centre phase spacing in metres.
    """
    return (_MU_0 / (2.0 * math.pi)) * _THREE_PHASE_FACTOR * (peak_current_a**2) / spacing_m


def _section_modulus_rectangular(width_mm: float, thickness_mm: float) -> float:
    """Calculate elastic section modulus for a rectangular busbar cross-section (mm^3).

    Z = w * t^2 / 6  where bending is about the axis perpendicular to the
    width face (i.e. the bar bends across its thickness).
    """
    return width_mm * (thickness_mm**2) / 6.0


def compute(
    peak_short_circuit_current_ka: float,
    phase_spacing_mm: float,
    span_length_m: float,
    busbar_width_mm: float,
    busbar_thickness_mm: float,
    support_condition: Literal["simply_supported", "fixed_both_ends"] = "simply_supported",
    busbar_material: Literal["copper", "aluminium"] = "copper",
) -> dict[str, float]:
    """Compute busbar short-circuit electromagnetic forces and stress per IEEE 605 / IEC 60865-1.

    Models a three-phase flat busbar arrangement where the centre phase
    experiences the maximum electromagnetic force during a symmetrical
    three-phase short circuit.  Calculates force per unit length, total
    peak force on one span, and the resulting bending stress.

    Returns a dict with keys: force_per_m_n, peak_force_n, busbar_stress_mpa.
    """
    _validate_inputs(
        peak_short_circuit_current_ka,
        phase_spacing_mm,
        span_length_m,
        busbar_width_mm,
        busbar_thickness_mm,
        support_condition,
        busbar_material,
    )

    # Convert units to SI base.
    ip_a = peak_short_circuit_current_ka * 1000.0  # kA -> A
    spacing_m = phase_spacing_mm / 1000.0  # mm -> m

    # Step 1: Force per unit length on the centre phase (N/m).
    fm = _force_per_unit_length(ip_a, spacing_m)

    # Step 2: Peak force over the span (N).
    # Total force = Fm * L where L is the span between supports.
    peak_force = fm * span_length_m

    # Step 3: Bending stress in the busbar (MPa).
    # Maximum bending moment M = Fm * L^2 / beta (N*m).
    beta = _SUPPORT_BETA[support_condition]
    bending_moment_nm = fm * (span_length_m**2) / beta

    # Section modulus of the rectangular busbar (mm^3 -> m^3 for consistency).
    z_mm3 = _section_modulus_rectangular(busbar_width_mm, busbar_thickness_mm)
    z_m3 = z_mm3 * 1e-9  # mm^3 -> m^3

    # Stress sigma = M / Z (Pa -> MPa).
    stress_pa = bending_moment_nm / z_m3
    stress_mpa = stress_pa / 1e6

    return {
        "force_per_m_n": round(fm, 2),
        "peak_force_n": round(peak_force, 2),
        "busbar_stress_mpa": round(stress_mpa, 2),
    }
