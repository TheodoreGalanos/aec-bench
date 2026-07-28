# ABOUTME: Integration-tests the certified package as input to pump-station physics.
# ABOUTME: Proves physical behavior comes from package data rather than fixed package identities.

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any, cast

import pytest

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    PumpStationEnvironment,
    ReferencePackage,
    assess_pump_station,
    initial_pump_station_state,
    load_reference_package,
    pump_station_model_from_package,
)


def _reference_expected(
    package: ReferencePackage,
    role: str,
) -> dict[str, Any]:
    checks = cast(tuple[object, ...], package.physical_reference_checks["checks"])
    for value in checks:
        row = cast(dict[str, Any], value)
        if row["role"] == role:
            return cast(dict[str, Any], row["expected"])
    raise AssertionError(f"missing reference role {role}")


def test_reference_package_builds_task_specific_physical_model() -> None:
    package = load_reference_package()

    model = pump_station_model_from_package(package)

    assert model.asset_id == "synthetic-wastewater-pump-station"
    assert model.pump_ids == ("pump-a", "pump-b")
    assert model.initial_duty_pump_id == "pump-a"
    assert model.initial_standby_pump_id == "pump-b"
    assert model.maximum_running_pumps == 1
    assert model.maximum_duty_transfers == 1
    assert model.degradation.obstruction_runtime_rate == Decimal("0.00000006944444444")
    assert model.degradation.obstruction_start_rate == Decimal("0.00015")
    assert model.degradation.clearance_runtime_rate == Decimal("0.00000003333333333")
    assert model.resources.repair_kit_initially_available is False
    assert model.resources.repair_kit_lead_seconds == 1_209_600
    assert model.resources.access_duration_seconds == 14_400
    assert model.resources.concurrent_intervention_limit == 1


def test_model_creation_does_not_depend_on_package_hashes_or_generation_names() -> None:
    package = load_reference_package()
    different_outer_identity = replace(
        package,
        profile_id="another-profile",
        generation_id="another-generation",
        package_content_id="another-package",
        manifest_content_id="another-manifest",
    )

    assert pump_station_model_from_package(different_outer_identity) == (pump_station_model_from_package(package))


def test_clean_capability_matches_promoted_compact_reference() -> None:
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    state = initial_pump_station_state(model)
    expected = _reference_expected(package, "clean")

    result = assess_pump_station(
        model,
        state,
        PumpStationEnvironment(
            inflow_m3_s=Decimal("0.0155"),
            wet_well_level_m=Decimal("1.65"),
            isolated=False,
        ),
    )

    assert result.capability.review_required is False
    assert result.capability.operating_flow_m3_s == pytest.approx(
        float(expected["finite_scalar"]),
        abs=1e-15,
    )
