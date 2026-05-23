# ABOUTME: Pollutant load estimation engine using the Event Mean Concentration (EMC) method.
# ABOUTME: Calculates annual runoff volume and TSS/TP/TN loads per MUSIC guidelines.


def _validate_inputs(
    catchment_area_ha: float,
    annual_rainfall_mm: float,
    runoff_coefficient: float,
    emc_tss_mg_l: float,
    emc_tp_mg_l: float,
    emc_tn_mg_l: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if catchment_area_ha <= 0:
        msg = "catchment_area_ha must be > 0"
        raise ValueError(msg)
    if annual_rainfall_mm <= 0:
        msg = "annual_rainfall_mm must be > 0"
        raise ValueError(msg)
    if runoff_coefficient <= 0:
        msg = "runoff_coefficient must be > 0"
        raise ValueError(msg)
    if runoff_coefficient > 1.0:
        msg = "runoff_coefficient must be <= 1.0"
        raise ValueError(msg)
    if emc_tss_mg_l < 0:
        msg = "emc_tss_mg_l must be >= 0"
        raise ValueError(msg)
    if emc_tp_mg_l < 0:
        msg = "emc_tp_mg_l must be >= 0"
        raise ValueError(msg)
    if emc_tn_mg_l < 0:
        msg = "emc_tn_mg_l must be >= 0"
        raise ValueError(msg)


def compute(
    catchment_area_ha: float,
    annual_rainfall_mm: float,
    runoff_coefficient: float,
    emc_tss_mg_l: float,
    emc_tp_mg_l: float,
    emc_tn_mg_l: float,
) -> dict[str, float]:
    """Estimate annual pollutant loads using the Event Mean Concentration method.

    Annual runoff volume:  V = C_runoff * P * A * 10  (m3/yr)
        where the factor 10 converts ha*mm to m3.
    Pollutant load:        L = EMC * V / 1000  (kg/yr)
        where EMC is in mg/L and V in m3; mg/L * m3 / 1000 = kg.

    Returns a dict with keys: annual_runoff_volume_m3, tss_load_kg_yr,
    tp_load_kg_yr, tn_load_kg_yr.
    """
    _validate_inputs(
        catchment_area_ha,
        annual_rainfall_mm,
        runoff_coefficient,
        emc_tss_mg_l,
        emc_tp_mg_l,
        emc_tn_mg_l,
    )

    # Annual runoff volume: V = C_runoff * P * A * 10  (ha*mm -> m3)
    annual_runoff_volume_m3 = runoff_coefficient * annual_rainfall_mm * catchment_area_ha * 10.0

    # Pollutant loads: L = EMC * V / 1000  (mg/L * m3 / 1000 = kg)
    tss_load_kg_yr = emc_tss_mg_l * annual_runoff_volume_m3 / 1000.0
    tp_load_kg_yr = emc_tp_mg_l * annual_runoff_volume_m3 / 1000.0
    tn_load_kg_yr = emc_tn_mg_l * annual_runoff_volume_m3 / 1000.0

    return {
        "annual_runoff_volume_m3": round(annual_runoff_volume_m3, 2),
        "tss_load_kg_yr": round(tss_load_kg_yr, 2),
        "tp_load_kg_yr": round(tp_load_kg_yr, 2),
        "tn_load_kg_yr": round(tn_load_kg_yr, 2),
    }
