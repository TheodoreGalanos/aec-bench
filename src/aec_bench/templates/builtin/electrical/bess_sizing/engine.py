# ABOUTME: Battery energy storage system (BESS) sizing computation engine.
# ABOUTME: Calculates nominal power, energy capacity, BOL capacity, and usable energy per IEC 62933.


def _validate_inputs(
    power_requirement_mw: float,
    discharge_duration_hours: float,
    depth_of_discharge_pct: float,
    round_trip_efficiency_pct: float,
    degradation_allowance_pct: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if power_requirement_mw <= 0:
        msg = "power_requirement_mw must be > 0"
        raise ValueError(msg)
    if discharge_duration_hours <= 0:
        msg = "discharge_duration_hours must be > 0"
        raise ValueError(msg)
    if depth_of_discharge_pct <= 0:
        msg = "depth_of_discharge_pct must be > 0"
        raise ValueError(msg)
    if depth_of_discharge_pct > 100:
        msg = "depth_of_discharge_pct must be <= 100"
        raise ValueError(msg)
    if round_trip_efficiency_pct <= 0:
        msg = "round_trip_efficiency_pct must be > 0"
        raise ValueError(msg)
    if round_trip_efficiency_pct > 100:
        msg = "round_trip_efficiency_pct must be <= 100"
        raise ValueError(msg)
    if degradation_allowance_pct < 0:
        msg = "degradation_allowance_pct must be >= 0"
        raise ValueError(msg)
    if degradation_allowance_pct >= 100:
        msg = "degradation_allowance_pct must be < 100"
        raise ValueError(msg)


def compute(
    power_requirement_mw: float,
    discharge_duration_hours: float,
    depth_of_discharge_pct: float,
    round_trip_efficiency_pct: float,
    degradation_allowance_pct: float,
) -> dict[str, float]:
    """Compute BESS sizing per IEC 62933 methodology.

    Determines the nominal power rating, required energy, beginning-of-life
    capacity, and usable energy for a battery energy storage system.

    Returns a dict with keys: nominal_power_mw, required_energy_mwh,
    bol_capacity_mwh, usable_energy_mwh.
    """
    _validate_inputs(
        power_requirement_mw,
        discharge_duration_hours,
        depth_of_discharge_pct,
        round_trip_efficiency_pct,
        degradation_allowance_pct,
    )

    # Convert percentages to fractions
    dod = depth_of_discharge_pct / 100.0
    eta_rt = round_trip_efficiency_pct / 100.0
    degradation = degradation_allowance_pct / 100.0

    # Nominal power rating equals the peak discharge power demand
    nominal_power_mw = power_requirement_mw

    # Required energy is the discharge power sustained over the duration
    # E_required = P × t_discharge
    required_energy_mwh = power_requirement_mw * discharge_duration_hours

    # Beginning-of-life (BOL) capacity must account for:
    #   - Depth of discharge: only a fraction of total capacity is usable
    #   - Round-trip efficiency: energy losses during charge/discharge cycle
    #   - Degradation: capacity fade over the system lifetime
    # E_bol = E_required / (DoD × η_rt × (1 - degradation))
    bol_capacity_mwh = required_energy_mwh / (dod * eta_rt * (1.0 - degradation))

    # Usable energy at BOL, after accounting for DoD and round-trip efficiency
    # E_usable = E_bol × DoD × η_rt
    usable_energy_mwh = bol_capacity_mwh * dod * eta_rt

    return {
        "nominal_power_mw": round(nominal_power_mw, 2),
        "required_energy_mwh": round(required_energy_mwh, 2),
        "bol_capacity_mwh": round(bol_capacity_mwh, 2),
        "usable_energy_mwh": round(usable_energy_mwh, 2),
    }
