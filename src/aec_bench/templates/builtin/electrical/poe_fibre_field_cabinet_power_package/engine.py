# ABOUTME: Computes SSC-05 PoE, fibre, and field cabinet power metrics.
# ABOUTME: Combines device power rollup, UPS runtime, cabinet heat, and fibre link loss.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _require_fraction(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        msg = f"{name} must be between 0 and 1"
        raise ValueError(msg)


def compute(
    camera_count: float,
    camera_poe_w: float,
    radio_count: float,
    radio_poe_w: float,
    controller_count: float,
    controller_poe_w: float,
    poe_budget_w: float,
    ups_nominal_kwh: float,
    ups_usable_fraction: float,
    inverter_efficiency: float,
    non_poe_load_w: float,
    required_runtime_h: float,
    switch_heat_w: float,
    cabinet_thermal_w_per_c: float,
    max_temperature_rise_c: float,
    fibre_length_km: float,
    fibre_loss_db_per_km: float,
    splice_count: float,
    splice_loss_db: float,
    connector_count: float,
    connector_loss_db: float,
    patch_loss_db: float,
    optical_budget_db: float,
) -> dict[str, float]:
    """Compute source-bound field cabinet PoE, UPS, thermal, and fibre metrics."""
    _require_positive(
        camera_count=camera_count,
        camera_poe_w=camera_poe_w,
        radio_count=radio_count,
        radio_poe_w=radio_poe_w,
        controller_count=controller_count,
        controller_poe_w=controller_poe_w,
        poe_budget_w=poe_budget_w,
        ups_nominal_kwh=ups_nominal_kwh,
        non_poe_load_w=non_poe_load_w,
        required_runtime_h=required_runtime_h,
        switch_heat_w=switch_heat_w,
        cabinet_thermal_w_per_c=cabinet_thermal_w_per_c,
        max_temperature_rise_c=max_temperature_rise_c,
        fibre_length_km=fibre_length_km,
        fibre_loss_db_per_km=fibre_loss_db_per_km,
        splice_count=splice_count,
        splice_loss_db=splice_loss_db,
        connector_count=connector_count,
        connector_loss_db=connector_loss_db,
        optical_budget_db=optical_budget_db,
    )
    _require_fraction("ups_usable_fraction", ups_usable_fraction)
    _require_fraction("inverter_efficiency", inverter_efficiency)
    if patch_loss_db < 0.0:
        msg = "patch_loss_db must be >= 0"
        raise ValueError(msg)

    poe_load_w = camera_count * camera_poe_w + radio_count * radio_poe_w + controller_count * controller_poe_w
    poe_budget_margin_w = poe_budget_w - poe_load_w
    usable_ups_energy_kwh = ups_nominal_kwh * ups_usable_fraction * inverter_efficiency
    ups_runtime_hr = usable_ups_energy_kwh / ((poe_load_w + non_poe_load_w) / 1000.0)
    runtime_margin_hr = ups_runtime_hr - required_runtime_h
    cabinet_heat_w = poe_load_w + non_poe_load_w + switch_heat_w
    cabinet_temp_rise_c = cabinet_heat_w / cabinet_thermal_w_per_c
    temperature_margin_c = max_temperature_rise_c - cabinet_temp_rise_c
    fibre_loss_db = (
        fibre_length_km * fibre_loss_db_per_km
        + splice_count * splice_loss_db
        + connector_count * connector_loss_db
        + patch_loss_db
    )
    optical_margin_db = optical_budget_db - fibre_loss_db

    overall_pass_score = (
        1.0 if min(poe_budget_margin_w, runtime_margin_hr, temperature_margin_c, optical_margin_db) >= 0.0 else 0.0
    )

    return {
        "poe_load_w": round(poe_load_w, 3),
        "poe_budget_margin_w": round(poe_budget_margin_w, 3),
        "usable_ups_energy_kwh": round(usable_ups_energy_kwh, 3),
        "ups_runtime_hr": round(ups_runtime_hr, 3),
        "runtime_margin_hr": round(runtime_margin_hr, 3),
        "cabinet_heat_w": round(cabinet_heat_w, 3),
        "cabinet_temp_rise_c": round(cabinet_temp_rise_c, 3),
        "temperature_margin_c": round(temperature_margin_c, 3),
        "fibre_loss_db": round(fibre_loss_db, 3),
        "optical_margin_db": round(optical_margin_db, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
