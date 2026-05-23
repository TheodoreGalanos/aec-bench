# ABOUTME: IEC 60909-0 three-phase fault current computation engine.
# ABOUTME: Calculates initial symmetrical and peak short-circuit currents for radial networks.

import math

# Voltage factor c_max table per IEC 60909-0 Table 1.
# Maps nominal voltage class to c_max for maximum fault current calculation.
_C_MAX_TABLE: dict[str, float] = {
    "lv": 1.05,  # Low voltage: Un <= 1 kV
    "mv": 1.10,  # Medium voltage: 1 kV < Un <= 35 kV
    "hv": 1.10,  # High voltage: 35 kV < Un <= 230 kV
}


def _voltage_class(system_voltage_kv: float) -> str:
    """Determine IEC 60909 voltage class from nominal system voltage."""
    if system_voltage_kv <= 1.0:
        return "lv"
    if system_voltage_kv <= 35.0:
        return "mv"
    return "hv"


def _validate_inputs(
    system_voltage_kv: float,
    source_fault_level_mva: float,
    transformer_rated_power_mva: float,
    transformer_impedance_percent: float,
    cable_resistance_ohm_per_km: float,
    cable_reactance_ohm_per_km: float,
    cable_length_m: float,
    voltage_factor_c: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if system_voltage_kv <= 0:
        msg = "system_voltage_kv must be > 0"
        raise ValueError(msg)
    if source_fault_level_mva <= 0:
        msg = "source_fault_level_mva must be > 0"
        raise ValueError(msg)
    if transformer_rated_power_mva <= 0:
        msg = "transformer_rated_power_mva must be > 0"
        raise ValueError(msg)
    if transformer_impedance_percent <= 0:
        msg = "transformer_impedance_percent must be > 0"
        raise ValueError(msg)
    if transformer_impedance_percent > 100:
        msg = "transformer_impedance_percent must be <= 100"
        raise ValueError(msg)
    if cable_resistance_ohm_per_km < 0:
        msg = "cable_resistance_ohm_per_km must be >= 0"
        raise ValueError(msg)
    if cable_reactance_ohm_per_km < 0:
        msg = "cable_reactance_ohm_per_km must be >= 0"
        raise ValueError(msg)
    if cable_length_m < 0:
        msg = "cable_length_m must be >= 0"
        raise ValueError(msg)
    if voltage_factor_c <= 0:
        msg = "voltage_factor_c must be > 0"
        raise ValueError(msg)
    if voltage_factor_c > 1.15:
        msg = "voltage_factor_c must be <= 1.15"
        raise ValueError(msg)


def _kappa(r_over_x: float) -> float:
    """Calculate the peak factor kappa per IEC 60909-0 Equation 55.

    kappa = 1.02 + 0.98 * exp(-3 * R/X)
    For purely reactive circuits (R/X = 0), kappa approaches 2.0.
    For purely resistive circuits (R/X -> inf), kappa approaches 1.02.
    """
    return 1.02 + 0.98 * math.exp(-3.0 * r_over_x)


def compute(
    system_voltage_kv: float,
    source_fault_level_mva: float,
    transformer_rated_power_mva: float,
    transformer_impedance_percent: float,
    cable_resistance_ohm_per_km: float,
    cable_reactance_ohm_per_km: float,
    cable_length_m: float,
    voltage_factor_c: float = 1.10,
) -> dict[str, float]:
    """Compute three-phase fault currents per IEC 60909-0 simplified method.

    Models a radial network with a single upstream source, one transformer,
    and one cable run to the fault point. Impedances are combined in series
    to find the total short-circuit impedance at the fault location.

    Returns a dict with keys: source_impedance_ohm, transformer_impedance_ohm,
    cable_impedance_ohm, total_impedance_ohm, initial_symmetrical_current_ka,
    peak_current_ka.
    """
    _validate_inputs(
        system_voltage_kv,
        source_fault_level_mva,
        transformer_rated_power_mva,
        transformer_impedance_percent,
        cable_resistance_ohm_per_km,
        cable_reactance_ohm_per_km,
        cable_length_m,
        voltage_factor_c,
    )

    # All impedances are referred to the secondary (system) voltage level.
    un = system_voltage_kv  # Nominal voltage in kV

    # Source impedance from upstream fault level.
    # Zs = c * Un^2 / Sk  where Sk is the source fault level in MVA.
    # The source is assumed purely reactive (Xs = Zs, Rs = 0).
    zs = voltage_factor_c * (un**2) / source_fault_level_mva
    rs = 0.0
    xs = zs

    # Transformer impedance from nameplate data.
    # Zt = (uk% / 100) * Un^2 / Sn
    # Transformer R/X ratio is typically small; assume purely reactive
    # for this simplified calculation (Xt = Zt, Rt = 0).
    zt = (transformer_impedance_percent / 100.0) * (un**2) / transformer_rated_power_mva
    rt = 0.0
    xt = zt

    # Cable impedance from per-unit-length values and route length.
    # Convert cable_length_m to km for the per-km impedance values.
    cable_length_km = cable_length_m / 1000.0
    rc = cable_resistance_ohm_per_km * cable_length_km
    xc = cable_reactance_ohm_per_km * cable_length_km
    zc = math.sqrt(rc**2 + xc**2)

    # Total impedance: series combination of source, transformer, and cable.
    # R and X components are summed separately, then combined into magnitude.
    r_total = rs + rt + rc
    x_total = xs + xt + xc
    z_total = math.sqrt(r_total**2 + x_total**2)

    # Initial symmetrical short-circuit current per IEC 60909-0 Equation 29.
    # Ik'' = c * Un / (sqrt(3) * Zk)
    # Un in kV, Zk in ohm -> Ik'' in kA.
    ik_pp = voltage_factor_c * un / (math.sqrt(3.0) * z_total)

    # Peak short-circuit current per IEC 60909-0 Equation 54.
    # ip = kappa * sqrt(2) * Ik''
    # Guard against x_total = 0 (purely resistive path, unlikely in practice).
    if x_total == 0.0:
        r_x_ratio = float("inf")
        kappa = 1.02
    else:
        r_x_ratio = r_total / x_total
        kappa = _kappa(r_x_ratio)

    ip = kappa * math.sqrt(2.0) * ik_pp

    return {
        "source_impedance_ohm": round(zs, 2),
        "transformer_impedance_ohm": round(zt, 2),
        "cable_impedance_ohm": round(zc, 2),
        "total_impedance_ohm": round(z_total, 2),
        "initial_symmetrical_current_ka": round(ik_pp, 2),
        "peak_current_ka": round(ip, 2),
    }
