# ABOUTME: Computes two-way DC cable voltage drop and annual resistive energy loss.
# ABOUTME: Uses string current, cable length, cross-section, resistivity, and voltage.


def _validate_inputs(
    string_current_a: float,
    dc_cable_length_m: float,
    cable_cross_section_mm2: float,
    cable_resistivity_ohm_mm2_m: float,
    string_voltage_v: float,
    annual_operating_hours: float,
    maximum_voltage_drop_pct: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "string_current_a": string_current_a,
        "dc_cable_length_m": dc_cable_length_m,
        "cable_cross_section_mm2": cable_cross_section_mm2,
        "cable_resistivity_ohm_mm2_m": cable_resistivity_ohm_mm2_m,
        "string_voltage_v": string_voltage_v,
        "annual_operating_hours": annual_operating_hours,
        "maximum_voltage_drop_pct": maximum_voltage_drop_pct,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    string_current_a: float,
    dc_cable_length_m: float,
    cable_cross_section_mm2: float,
    cable_resistivity_ohm_mm2_m: float,
    string_voltage_v: float,
    annual_operating_hours: float,
    maximum_voltage_drop_pct: float,
) -> dict[str, float]:
    """Compute DC string cable voltage drop and annual energy loss."""
    _validate_inputs(
        string_current_a,
        dc_cable_length_m,
        cable_cross_section_mm2,
        cable_resistivity_ohm_mm2_m,
        string_voltage_v,
        annual_operating_hours,
        maximum_voltage_drop_pct,
    )

    loop_resistance_ohm = 2.0 * dc_cable_length_m * cable_resistivity_ohm_mm2_m / cable_cross_section_mm2
    voltage_drop_v = string_current_a * loop_resistance_ohm
    voltage_drop_pct = voltage_drop_v / string_voltage_v * 100.0
    annual_energy_loss_kwh = string_current_a * voltage_drop_v * annual_operating_hours / 1000.0
    voltage_drop_margin_pct = maximum_voltage_drop_pct - voltage_drop_pct

    return {
        "voltage_drop_v": round(voltage_drop_v, 2),
        "voltage_drop_pct": round(voltage_drop_pct, 2),
        "annual_energy_loss_kwh": round(annual_energy_loss_kwh, 2),
        "voltage_drop_margin_pct": round(voltage_drop_margin_pct, 2),
    }
