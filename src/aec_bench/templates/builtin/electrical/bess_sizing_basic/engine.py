# ABOUTME: Computes basic BESS power and energy capacity requirements.
# ABOUTME: Uses discharge duration, SOC window, efficiency, and EOL retention.


def _validate_inputs(
    required_discharge_power_mw: float,
    required_discharge_duration_h: float,
    usable_soc_range_pct: float,
    round_trip_efficiency_pct: float,
    end_of_life_capacity_retention_pct: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "required_discharge_power_mw": required_discharge_power_mw,
        "required_discharge_duration_h": required_discharge_duration_h,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)
    for name, value in {
        "usable_soc_range_pct": usable_soc_range_pct,
        "round_trip_efficiency_pct": round_trip_efficiency_pct,
        "end_of_life_capacity_retention_pct": end_of_life_capacity_retention_pct,
    }.items():
        if not 0 < value <= 100:
            msg = f"{name} must be > 0 and <= 100"
            raise ValueError(msg)


def compute(
    required_discharge_power_mw: float,
    required_discharge_duration_h: float,
    usable_soc_range_pct: float,
    round_trip_efficiency_pct: float,
    end_of_life_capacity_retention_pct: float,
) -> dict[str, float]:
    """Compute BESS nominal power and energy capacity requirements."""
    _validate_inputs(
        required_discharge_power_mw,
        required_discharge_duration_h,
        usable_soc_range_pct,
        round_trip_efficiency_pct,
        end_of_life_capacity_retention_pct,
    )

    usable_soc_fraction = usable_soc_range_pct / 100.0
    efficiency_fraction = round_trip_efficiency_pct / 100.0
    eol_retention_fraction = end_of_life_capacity_retention_pct / 100.0

    usable_energy_mwh = required_discharge_power_mw * required_discharge_duration_h
    nominal_energy_capacity_mwh = usable_energy_mwh / usable_soc_fraction / efficiency_fraction
    beginning_of_life_capacity_mwh = nominal_energy_capacity_mwh / eol_retention_fraction

    return {
        "nominal_power_rating_mw": round(required_discharge_power_mw, 2),
        "usable_energy_mwh": round(usable_energy_mwh, 2),
        "nominal_energy_capacity_mwh": round(nominal_energy_capacity_mwh, 2),
        "beginning_of_life_capacity_mwh": round(beginning_of_life_capacity_mwh, 2),
    }
