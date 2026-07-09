# ABOUTME: Computes SSC-06 pump affinity retrofit and energy performance metrics.
# ABOUTME: Combines speed-ratio affinity laws, energy savings, NPSH, and motor margin checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    existing_flow_l_s: float,
    existing_head_m: float,
    existing_shaft_power_kw: float,
    retrofit_speed_ratio: float,
    existing_motor_input_kw: float,
    annual_operating_hours: float,
    energy_tariff_per_kwh: float,
    existing_npsh_required_m: float,
    npsh_available_m: float,
    selected_motor_kw: float,
    motor_service_factor: float,
) -> dict[str, float]:
    """Compute source-bound pump affinity retrofit and energy metrics."""
    _require_positive(
        existing_flow_l_s=existing_flow_l_s,
        existing_head_m=existing_head_m,
        existing_shaft_power_kw=existing_shaft_power_kw,
        retrofit_speed_ratio=retrofit_speed_ratio,
        existing_motor_input_kw=existing_motor_input_kw,
        annual_operating_hours=annual_operating_hours,
        energy_tariff_per_kwh=energy_tariff_per_kwh,
        existing_npsh_required_m=existing_npsh_required_m,
        npsh_available_m=npsh_available_m,
        selected_motor_kw=selected_motor_kw,
        motor_service_factor=motor_service_factor,
    )
    if retrofit_speed_ratio > 1.0:
        msg = "retrofit_speed_ratio must be <= 1 for this baseline energy-saving case"
        raise ValueError(msg)
    if motor_service_factor < 1.0:
        msg = "motor_service_factor must be >= 1"
        raise ValueError(msg)

    retrofit_flow_l_s = existing_flow_l_s * retrofit_speed_ratio
    retrofit_head_m = existing_head_m * retrofit_speed_ratio**2
    retrofit_shaft_power_kw = existing_shaft_power_kw * retrofit_speed_ratio**3
    retrofit_motor_input_kw = retrofit_shaft_power_kw / 0.94
    annual_energy_savings_kwh = (existing_motor_input_kw - retrofit_motor_input_kw) * annual_operating_hours
    annual_cost_savings = annual_energy_savings_kwh * energy_tariff_per_kwh
    new_npsh_required_m = existing_npsh_required_m * retrofit_speed_ratio**2
    npsh_margin_m = npsh_available_m - new_npsh_required_m
    motor_margin_kw = selected_motor_kw - retrofit_shaft_power_kw * motor_service_factor
    overall_pass_score = 1.0 if min(annual_energy_savings_kwh, npsh_margin_m, motor_margin_kw) >= 0.0 else 0.0

    return {
        "retrofit_flow_l_s": round(retrofit_flow_l_s, 3),
        "retrofit_head_m": round(retrofit_head_m, 3),
        "retrofit_shaft_power_kw": round(retrofit_shaft_power_kw, 3),
        "retrofit_motor_input_kw": round(retrofit_motor_input_kw, 3),
        "annual_energy_savings_kwh": round(annual_energy_savings_kwh, 3),
        "annual_cost_savings": round(annual_cost_savings, 3),
        "new_npsh_required_m": round(new_npsh_required_m, 3),
        "npsh_margin_m": round(npsh_margin_m, 3),
        "motor_margin_kw": round(motor_margin_kw, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
