# ABOUTME: Voltage drop computation engine per AS/NZS 3008.1.1.
# ABOUTME: Uses tabulated mV/A/m values for copper and aluminium multicore cables.

import math
from typing import Literal

# Voltage drop values (mV/A/m) for three-phase circuits at 75°C conductor temperature.
# Source: AS/NZS 3008.1.1, Table 42 (copper multicore) and Table 44 (aluminium multicore).
# Single-phase values are derived by multiplying three-phase values by 2/sqrt(3) ≈ 1.1547.
_VC_TABLE_3PH: dict[str, dict[str, float]] = {
    "copper": {
        "1.5": 28.60,
        "2.5": 15.60,
        "4": 9.71,
        "6": 6.49,
        "10": 3.86,
        "16": 2.43,
        "25": 1.54,
        "35": 1.11,
        "50": 0.81,
        "70": 0.57,
        "95": 0.43,
        "120": 0.35,
        "150": 0.29,
        "185": 0.25,
        "240": 0.21,
    },
    "aluminium": {
        "16": 3.95,
        "25": 2.50,
        "35": 1.81,
        "50": 1.31,
        "70": 0.93,
        "95": 0.69,
        "120": 0.56,
        "150": 0.47,
        "185": 0.40,
        "240": 0.33,
    },
}

# Nominal supply voltages for percentage calculation.
_SUPPLY_VOLTAGE: dict[str, float] = {
    "single_phase": 230.0,
    "three_phase": 400.0,
}

# Maximum allowable voltage drop percentage per AS/NZS 3000:2018 Clause 3.6.2.
_MAX_VOLTAGE_DROP_PERCENT = 5.0


def _validate_inputs(
    cable_size_mm2: str,
    length_m: float,
    load_current_a: float,
    power_factor: float,
    conductor_material: str,
    circuit_type: str,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if conductor_material not in _VC_TABLE_3PH:
        msg = f"conductor_material must be one of {list(_VC_TABLE_3PH.keys())}, got '{conductor_material}'"
        raise ValueError(msg)
    if cable_size_mm2 not in _VC_TABLE_3PH[conductor_material]:
        valid = list(_VC_TABLE_3PH[conductor_material].keys())
        msg = f"cable_size_mm2 '{cable_size_mm2}' not available for {conductor_material}. Valid sizes: {valid}"
        raise ValueError(msg)
    if length_m <= 0:
        msg = "length_m must be > 0"
        raise ValueError(msg)
    if load_current_a <= 0:
        msg = "load_current_a must be > 0"
        raise ValueError(msg)
    if power_factor <= 0 or power_factor > 1.0:
        msg = "power_factor must be > 0 and <= 1.0"
        raise ValueError(msg)
    if circuit_type not in _SUPPLY_VOLTAGE:
        msg = f"circuit_type must be one of {list(_SUPPLY_VOLTAGE.keys())}, got '{circuit_type}'"
        raise ValueError(msg)


def compute(
    cable_size_mm2: str,
    length_m: float,
    load_current_a: float,
    power_factor: float,
    conductor_material: Literal["copper", "aluminium"] = "copper",
    circuit_type: Literal["single_phase", "three_phase"] = "single_phase",
) -> dict[str, float]:
    """Compute voltage drop for a cable circuit per AS/NZS 3008.1.1.

    Uses tabulated mV/A/m values from AS/NZS 3008.1.1 Tables 42/44.
    The table values already account for conductor resistance and reactance
    at a specific power factor. For simplicity, this engine uses the tabulated
    values directly (which assume a typical power factor). The power_factor
    input is used as a scaling adjustment.

    Returns a dict with keys: vc_mv_per_a_m, voltage_drop_v, voltage_drop_percent,
    compliant.
    """
    _validate_inputs(
        cable_size_mm2,
        length_m,
        load_current_a,
        power_factor,
        conductor_material,
        circuit_type,
    )

    # Look up base three-phase mV/A/m value
    vc_3ph = _VC_TABLE_3PH[conductor_material][cable_size_mm2]

    # Convert to appropriate circuit type value
    # AS/NZS 3008 tables are three-phase values.
    # Single-phase: multiply by 2/sqrt(3) ≈ 1.1547
    if circuit_type == "single_phase":
        vc = vc_3ph * (2.0 / math.sqrt(3.0))
    else:
        vc = vc_3ph

    # The tabulated values assume unity power factor for the resistive component.
    # Scale by the actual power factor (conservative approximation for predominantly
    # resistive cables at the sizes in this table).
    vc_adjusted = vc * power_factor

    # Voltage drop: Vd = Vc × I × L / 1000
    voltage_drop_v = vc_adjusted * load_current_a * length_m / 1000.0

    # Percentage of nominal supply voltage
    supply_v = _SUPPLY_VOLTAGE[circuit_type]
    voltage_drop_pct = (voltage_drop_v / supply_v) * 100.0

    # Compliance check against AS/NZS 3000 5% limit
    compliant = 1.0 if voltage_drop_pct <= _MAX_VOLTAGE_DROP_PERCENT else 0.0

    return {
        "vc_mv_per_a_m": round(vc_adjusted, 2),
        "voltage_drop_v": round(voltage_drop_v, 2),
        "voltage_drop_percent": round(voltage_drop_pct, 2),
        "compliant": round(compliant, 2),
    }
