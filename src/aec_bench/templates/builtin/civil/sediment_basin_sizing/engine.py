# ABOUTME: Sediment basin sizing computation engine per the Blue Book.
# ABOUTME: Calculates settling, sediment storage, and total volumes for Type D and Type F basins.

from typing import Literal

# Valid basin types per the Blue Book (Managing Urban Stormwater: Soils and Construction).
_VALID_BASIN_TYPES: list[str] = ["D", "F"]


def _validate_inputs(
    catchment_area_ha: float,
    volumetric_runoff_coeff_m3_ha: float,
    soil_loss_rate_m3_ha_yr: float,
    cleanout_interval_yr: float,
    basin_type: str,
    permanent_pool_volume_m3: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if catchment_area_ha <= 0:
        msg = "catchment_area_ha must be > 0"
        raise ValueError(msg)
    if catchment_area_ha > 100:
        msg = "catchment_area_ha must be <= 100 (practical limit for sediment basins)"
        raise ValueError(msg)
    if volumetric_runoff_coeff_m3_ha <= 0:
        msg = "volumetric_runoff_coeff_m3_ha must be > 0"
        raise ValueError(msg)
    if soil_loss_rate_m3_ha_yr < 0:
        msg = "soil_loss_rate_m3_ha_yr must be >= 0"
        raise ValueError(msg)
    if cleanout_interval_yr <= 0:
        msg = "cleanout_interval_yr must be > 0"
        raise ValueError(msg)
    if basin_type not in _VALID_BASIN_TYPES:
        msg = f"basin_type must be one of {_VALID_BASIN_TYPES}, got '{basin_type}'"
        raise ValueError(msg)
    if permanent_pool_volume_m3 < 0:
        msg = "permanent_pool_volume_m3 must be >= 0"
        raise ValueError(msg)


def compute(
    catchment_area_ha: float,
    volumetric_runoff_coeff_m3_ha: float,
    soil_loss_rate_m3_ha_yr: float,
    cleanout_interval_yr: float,
    basin_type: Literal["D", "F"] = "D",
    permanent_pool_volume_m3: float = 0.0,
) -> dict[str, float]:
    """Size a construction sediment basin per the Blue Book.

    Type D (dry) basins: settling zone + sediment storage.
    Type F (wet) basins: permanent pool + settling zone + sediment storage.

    Settling zone volume:   V_s   = Cv * A
    Sediment storage volume: V_sed = R * A * D
    Total basin volume:      V_total = V_pool + V_s + V_sed

    Where:
        Cv = volumetric runoff coefficient (m3/ha) based on rainfall region
        A  = contributing catchment area (ha)
        R  = soil loss rate (m3/ha/yr)
        D  = clean-out interval (years)
        V_pool = permanent pool volume (Type F only, 0 for Type D)

    Returns a dict with keys: settling_volume_m3, sediment_storage_volume_m3,
    total_basin_volume_m3.
    """
    _validate_inputs(
        catchment_area_ha,
        volumetric_runoff_coeff_m3_ha,
        soil_loss_rate_m3_ha_yr,
        cleanout_interval_yr,
        basin_type,
        permanent_pool_volume_m3,
    )

    # Settling zone volume: V_s = Cv * A
    settling_volume_m3 = volumetric_runoff_coeff_m3_ha * catchment_area_ha

    # Sediment storage volume: V_sed = R * A * D
    sediment_storage_volume_m3 = soil_loss_rate_m3_ha_yr * catchment_area_ha * cleanout_interval_yr

    # Total basin volume includes permanent pool for Type F
    pool_volume = permanent_pool_volume_m3 if basin_type == "F" else 0.0
    total_basin_volume_m3 = pool_volume + settling_volume_m3 + sediment_storage_volume_m3

    return {
        "settling_volume_m3": round(settling_volume_m3, 2),
        "sediment_storage_volume_m3": round(sediment_storage_volume_m3, 2),
        "total_basin_volume_m3": round(total_basin_volume_m3, 2),
    }
