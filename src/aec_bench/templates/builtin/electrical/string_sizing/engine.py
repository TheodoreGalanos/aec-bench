# ABOUTME: Solar PV string sizing computation engine per AS/NZS 5033 and IEC 62548.
# ABOUTME: Calculates temperature-corrected voltages and max/min modules per string.

import math


def _validate_inputs(
    voc_stc_v: float,
    vmp_stc_v: float,
    temp_coeff_voc_pct_per_c: float,
    temp_coeff_vmp_pct_per_c: float,
    site_min_temp_c: float,
    site_max_temp_c: float,
    inverter_max_dc_voltage_v: float,
    inverter_min_mppt_voltage_v: float,
    inverter_nominal_mppt_voltage_v: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if voc_stc_v <= 0:
        msg = "voc_stc_v must be > 0"
        raise ValueError(msg)
    if vmp_stc_v <= 0:
        msg = "vmp_stc_v must be > 0"
        raise ValueError(msg)
    if vmp_stc_v >= voc_stc_v:
        msg = "vmp_stc_v must be < voc_stc_v"
        raise ValueError(msg)
    if temp_coeff_voc_pct_per_c >= 0:
        msg = "temp_coeff_voc_pct_per_c must be < 0 (voltage decreases with temperature)"
        raise ValueError(msg)
    if temp_coeff_vmp_pct_per_c >= 0:
        msg = "temp_coeff_vmp_pct_per_c must be < 0 (voltage decreases with temperature)"
        raise ValueError(msg)
    if site_min_temp_c >= site_max_temp_c:
        msg = "site_min_temp_c must be < site_max_temp_c"
        raise ValueError(msg)
    if inverter_max_dc_voltage_v <= 0:
        msg = "inverter_max_dc_voltage_v must be > 0"
        raise ValueError(msg)
    if inverter_min_mppt_voltage_v <= 0:
        msg = "inverter_min_mppt_voltage_v must be > 0"
        raise ValueError(msg)
    if inverter_nominal_mppt_voltage_v <= 0:
        msg = "inverter_nominal_mppt_voltage_v must be > 0"
        raise ValueError(msg)
    # Cross-parameter constraints handled by clamping in compute()
    # rather than validation, since the sampler generates params independently.


def compute(
    voc_stc_v: float,
    vmp_stc_v: float,
    temp_coeff_voc_pct_per_c: float,
    temp_coeff_vmp_pct_per_c: float,
    site_min_temp_c: float,
    site_max_temp_c: float,
    inverter_max_dc_voltage_v: float,
    inverter_min_mppt_voltage_v: float,
    inverter_nominal_mppt_voltage_v: float,
) -> dict[str, float]:
    """Compute solar PV string sizing per AS/NZS 5033 and IEC 62548.

    Temperature correction adjusts module voltages for site extremes:
    - Cold temperatures increase Voc (risk of exceeding inverter max voltage)
    - Hot temperatures decrease Vmp (risk of dropping below MPPT range)

    Returns a dict with keys: voc_corrected_cold_v, vmp_corrected_hot_v,
    max_modules_per_string, min_modules_per_string.
    """
    _validate_inputs(
        voc_stc_v,
        vmp_stc_v,
        temp_coeff_voc_pct_per_c,
        temp_coeff_vmp_pct_per_c,
        site_min_temp_c,
        site_max_temp_c,
        inverter_max_dc_voltage_v,
        inverter_min_mppt_voltage_v,
        inverter_nominal_mppt_voltage_v,
    )

    # Clamp cross-parameter relationships for sampler-generated values
    inverter_min_mppt_voltage_v = min(inverter_min_mppt_voltage_v, inverter_max_dc_voltage_v * 0.9)
    inverter_nominal_mppt_voltage_v = max(
        inverter_min_mppt_voltage_v,
        min(inverter_nominal_mppt_voltage_v, inverter_max_dc_voltage_v),
    )

    # Temperature-corrected Voc at coldest site temperature.
    # At cold temperatures, Voc increases because the negative temp coefficient
    # applied to a negative delta-T (T_min - 25) produces a positive correction.
    # Formula: Voc_cold = Voc_stc * (1 + (temp_coeff_voc / 100) * (T_min - 25))
    voc_corrected_cold = voc_stc_v * (1.0 + (temp_coeff_voc_pct_per_c / 100.0) * (site_min_temp_c - 25.0))

    # Temperature-corrected Vmp at hottest site temperature.
    # At hot temperatures, Vmp decreases because the negative temp coefficient
    # applied to a positive delta-T (T_max - 25) produces a negative correction.
    # Formula: Vmp_hot = Vmp_stc * (1 + (temp_coeff_vmp / 100) * (T_max - 25))
    vmp_corrected_hot = vmp_stc_v * (1.0 + (temp_coeff_vmp_pct_per_c / 100.0) * (site_max_temp_c - 25.0))

    # Maximum modules per string: limited by inverter max DC input voltage
    # at coldest temperature. Round DOWN to avoid exceeding inverter limit.
    max_modules = math.floor(inverter_max_dc_voltage_v / voc_corrected_cold)

    # Minimum modules per string: must keep string voltage above inverter
    # minimum MPPT voltage at hottest temperature. Round UP to ensure the
    # MPPT range is always reached.
    min_modules = math.ceil(inverter_min_mppt_voltage_v / vmp_corrected_hot)

    return {
        "voc_corrected_cold_v": round(voc_corrected_cold, 2),
        "vmp_corrected_hot_v": round(vmp_corrected_hot, 2),
        "max_modules_per_string": round(float(max_modules), 2),
        "min_modules_per_string": round(float(min_modules), 2),
    }
