# ABOUTME: IEEE 1584 arc flash incident energy computation engine.
# ABOUTME: Calculates arcing current, incident energy, arc flash boundary, and PPE category.

import math
from typing import Literal

# IEEE 1584-2002 arcing current equation coefficients for systems <= 1000 V.
# lg(Ia) = K + 0.662*lg(Ibf) + 0.0966*V + 0.000526*G + 0.5588*V*lg(Ibf) - 0.00304*G*lg(Ibf)
# K depends on enclosure type.
_K_ARC_OPEN = -0.153
_K_ARC_BOX = -0.097

# IEEE 1584-2002 normalized incident energy coefficients.
# lg(En) = K1 + K2 + 1.081*lg(Ia) + 0.0011*G
_K1_OPEN = -0.792
_K1_BOX = -0.555
_K2_UNGROUNDED = 0.0
_K2_GROUNDED = -0.113

# Calculation factor Cf: multiplier for incident energy.
# Cf = 1.5 for systems < 1 kV, Cf = 1.0 for systems >= 1 kV.
_CF_LOW_VOLTAGE = 1.5
_CF_HIGH_VOLTAGE = 1.0

# Distance exponents by equipment class per IEEE 1584 Table 4.
# Enclosure type maps to a typical equipment class.
_DISTANCE_EXPONENT: dict[str, float] = {
    "open": 2.000,
    "box": 1.473,
    "MCC": 0.973,
}

# Typical electrode gap (mm) by enclosure type per IEEE 1584 Table 3.
_TYPICAL_GAP: dict[str, float] = {
    "open": 40.0,
    "box": 32.0,
    "MCC": 25.0,
}

# Arc flash boundary threshold (cal/cm2) per NFPA 70E.
_AFB_THRESHOLD = 1.2

# PPE category thresholds per NFPA 70E Table 130.7(C)(15)(a).
# Category 0: E < 1.2 cal/cm2 (no arc-rated PPE required)
# Category 1: 1.2 <= E < 4 cal/cm2
# Category 2: 4 <= E < 8 cal/cm2
# Category 3: 8 <= E < 25 cal/cm2
# Category 4: 25 <= E < 40 cal/cm2
# Above 40 cal/cm2 is considered dangerous (exceeds PPE limits).
_PPE_THRESHOLDS: list[tuple[float, int]] = [
    (1.2, 0),
    (4.0, 1),
    (8.0, 2),
    (25.0, 3),
    (40.0, 4),
]


def _validate_inputs(
    system_voltage_v: float,
    bolted_fault_current_ka: float,
    clearing_time_s: float,
    working_distance_mm: float,
    electrode_gap_mm: float,
    enclosure_type: str,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if system_voltage_v <= 0:
        msg = "system_voltage_v must be > 0"
        raise ValueError(msg)
    if system_voltage_v > 15000:
        msg = "system_voltage_v must be <= 15000 (IEEE 1584 range)"
        raise ValueError(msg)
    if bolted_fault_current_ka <= 0:
        msg = "bolted_fault_current_ka must be > 0"
        raise ValueError(msg)
    if clearing_time_s <= 0:
        msg = "clearing_time_s must be > 0"
        raise ValueError(msg)
    if working_distance_mm <= 0:
        msg = "working_distance_mm must be > 0"
        raise ValueError(msg)
    if electrode_gap_mm <= 0:
        msg = "electrode_gap_mm must be > 0"
        raise ValueError(msg)
    if enclosure_type not in _DISTANCE_EXPONENT:
        valid = list(_DISTANCE_EXPONENT.keys())
        msg = f"enclosure_type must be one of {valid}, got '{enclosure_type}'"
        raise ValueError(msg)


def _arcing_current_low_voltage(
    ibf: float,
    voltage_kv: float,
    gap_mm: float,
    enclosure_type: str,
) -> float:
    """Calculate arcing current (kA) for systems <= 1000 V using IEEE 1584-2002 Eq. 1.

    lg(Ia) = K + 0.662*lg(Ibf) + 0.0966*V + 0.000526*G + 0.5588*V*lg(Ibf) - 0.00304*G*lg(Ibf)
    where V is in kV and G is the electrode gap in mm.
    """
    k = _K_ARC_OPEN if enclosure_type == "open" else _K_ARC_BOX
    lg_ibf = math.log10(ibf)
    lg_ia = (
        k
        + 0.662 * lg_ibf
        + 0.0966 * voltage_kv
        + 0.000526 * gap_mm
        + 0.5588 * voltage_kv * lg_ibf
        - 0.00304 * gap_mm * lg_ibf
    )
    return 10.0**lg_ia


def _arcing_current_high_voltage(ibf: float) -> float:
    """Calculate arcing current (kA) for systems > 1000 V using IEEE 1584-2002 Eq. 2.

    lg(Ia) = 0.00402 + 0.983 * lg(Ibf)
    """
    lg_ia = 0.00402 + 0.983 * math.log10(ibf)
    return 10.0**lg_ia


def _normalized_incident_energy(
    ia: float,
    gap_mm: float,
    enclosure_type: str,
    grounding: str,
) -> float:
    """Calculate normalized incident energy En (J/cm2) per IEEE 1584-2002 Eq. 3.

    lg(En) = K1 + K2 + 1.081*lg(Ia) + 0.0011*G
    En is normalized to an arcing time of 0.2 s and a distance of 610 mm.
    """
    k1 = _K1_OPEN if enclosure_type == "open" else _K1_BOX
    k2 = _K2_GROUNDED if grounding == "grounded" else _K2_UNGROUNDED
    lg_en = k1 + k2 + 1.081 * math.log10(ia) + 0.0011 * gap_mm
    return 10.0**lg_en


def _incident_energy(
    en: float,
    cf: float,
    t: float,
    d: float,
    x: float,
) -> float:
    """Calculate incident energy E (cal/cm2) per IEEE 1584-2002 Eq. 4.

    E = 4.184 * Cf * En * (t / 0.2) * (610^x / D^x)
    where t is arcing time in seconds, D is working distance in mm.
    """
    return 4.184 * cf * en * (t / 0.2) * (610.0**x / d**x)


def _arc_flash_boundary(
    en: float,
    cf: float,
    t: float,
    x: float,
    eb: float,
) -> float:
    """Calculate arc flash boundary distance (mm) per IEEE 1584-2002 Eq. 5.

    DB = [4.184 * Cf * En * (t / 0.2) * (610^x / Eb)] ^ (1/x)
    where Eb is the incident energy threshold (1.2 cal/cm2).
    """
    numerator = 4.184 * cf * en * (t / 0.2) * (610.0**x)
    return (numerator / eb) ** (1.0 / x)


def _ppe_category(incident_energy: float) -> int:
    """Determine PPE category from incident energy (cal/cm2).

    Returns integer 0-4 per NFPA 70E thresholds.
    Values above 40 cal/cm2 are clamped to category 4.
    """
    category = 0
    for threshold, cat in _PPE_THRESHOLDS:
        if incident_energy >= threshold:
            category = cat
        else:
            break
    return category


def compute(
    system_voltage_v: float,
    bolted_fault_current_ka: float,
    clearing_time_s: float,
    working_distance_mm: float,
    electrode_gap_mm: float = 32.0,
    enclosure_type: Literal["open", "box", "MCC"] = "box",
) -> dict[str, float]:
    """Compute arc flash incident energy and related values per IEEE 1584.

    Uses IEEE 1584-2002 empirical method for systems 208 V to 15 kV.
    For systems <= 1000 V, applies the detailed arcing current equation.
    For systems > 1000 V, applies the simplified Lee/IEEE equation.
    Grounding is assumed grounded (conservative for industrial systems).

    Returns a dict with keys: arcing_current_ka, incident_energy_cal_cm2,
    arc_flash_boundary_mm, ppe_category.
    """
    _validate_inputs(
        system_voltage_v,
        bolted_fault_current_ka,
        clearing_time_s,
        working_distance_mm,
        electrode_gap_mm,
        enclosure_type,
    )

    voltage_kv = system_voltage_v / 1000.0

    # Step 1: Calculate arcing current based on voltage level
    if system_voltage_v <= 1000.0:
        ia = _arcing_current_low_voltage(
            bolted_fault_current_ka,
            voltage_kv,
            electrode_gap_mm,
            enclosure_type,
        )
        cf = _CF_LOW_VOLTAGE
    else:
        ia = _arcing_current_high_voltage(bolted_fault_current_ka)
        cf = _CF_HIGH_VOLTAGE

    # Step 2: Calculate normalized incident energy (grounded system assumed)
    en = _normalized_incident_energy(ia, electrode_gap_mm, enclosure_type, "grounded")

    # Step 3: Calculate incident energy at working distance
    x = _DISTANCE_EXPONENT[enclosure_type]
    energy = _incident_energy(en, cf, clearing_time_s, working_distance_mm, x)

    # Step 4: Calculate arc flash boundary (distance where E = 1.2 cal/cm2)
    afb = _arc_flash_boundary(en, cf, clearing_time_s, x, _AFB_THRESHOLD)

    # Step 5: Determine PPE category
    ppe = _ppe_category(energy)

    return {
        "arcing_current_ka": round(ia, 2),
        "incident_energy_cal_cm2": round(energy, 2),
        "arc_flash_boundary_mm": round(afb, 2),
        "ppe_category": round(float(ppe), 2),
    }
