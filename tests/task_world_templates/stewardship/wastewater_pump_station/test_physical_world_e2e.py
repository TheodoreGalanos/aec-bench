# ABOUTME: Exercises complete in-memory wastewater pump-station physical journeys.
# ABOUTME: Covers certified no-action progression and an intervention without research files.

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    OperatingInterval,
    PumpIntervention,
    PumpInterventionKind,
    PumpStationEnvironment,
    PumpStationResources,
    ReferencePackage,
    advance_pump_station,
    apply_pump_intervention,
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


def _environment() -> PumpStationEnvironment:
    return PumpStationEnvironment(
        inflow_m3_s=Decimal("0.0155"),
        wet_well_level_m=Decimal("1.65"),
        isolated=False,
    )


def test_no_action_progression_matches_certified_capability_sequence() -> None:
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    state = initial_pump_station_state(model)
    capabilities = [assess_pump_station(model, state, _environment()).capability]
    intervals = (
        (3_600_000, 500),
        (3_600_000, 500),
        (3_600_000, 1_000),
    )

    for runtime_seconds, completed_starts in intervals:
        result = advance_pump_station(
            model,
            state,
            OperatingInterval(
                elapsed_seconds=runtime_seconds,
                duty_runtime_seconds=runtime_seconds,
                duty_completed_starts=completed_starts,
                environment=_environment(),
            ),
        )
        state = result.state
        capabilities.append(result.capability)

    assert [item.review_required for item in capabilities] == [
        False,
        False,
        True,
        True,
    ]
    assert [item.operating_flow_m3_s for item in capabilities] == pytest.approx(
        [
            0.02739942396643039,
            0.02339426856122102,
            0.02037250978021602,
            0.01781623171840774,
        ],
        abs=1e-15,
    )
    expected_drop = Decimal(
        cast(
            str,
            _reference_expected(package, "no-maintenance")["finite_scalar"],
        )
    )
    actual_drop = Decimal(str(capabilities[0].operating_flow_m3_s)) - Decimal(str(capabilities[-1].operating_flow_m3_s))
    assert actual_drop == pytest.approx(expected_drop, abs=Decimal("1e-15"))
    assert state.calendar_seconds == 10_800_000
    assert state.pump("pump-a").exposure.runtime_seconds == 10_800_000
    assert state.pump("pump-a").exposure.completed_starts == 2_000


def test_obstruction_clearing_restores_capability_without_resetting_history() -> None:
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    state = initial_pump_station_state(model)
    degraded = advance_pump_station(
        model,
        state,
        OperatingInterval(
            elapsed_seconds=7_200_000,
            duty_runtime_seconds=7_200_000,
            duty_completed_starts=1_000,
            environment=_environment(),
        ),
    )

    cleared = apply_pump_intervention(
        model,
        degraded.state,
        PumpIntervention(
            kind=PumpInterventionKind.CLEAR_OBSTRUCTION,
            pump_id="pump-a",
        ),
        PumpStationResources(
            access_window_seconds=14_400,
            repair_kit_available=False,
            available_intervention_slots=1,
        ),
        _environment(),
    )

    before = degraded.state.pump("pump-a")
    after = cleared.state.pump("pump-a")
    assert after.condition.obstruction < before.condition.obstruction
    assert after.condition.clearance_loss == before.condition.clearance_loss
    assert after.exposure == before.exposure
    assert cleared.state.calendar_seconds == degraded.state.calendar_seconds
    assert cleared.capability.operating_flow_m3_s > degraded.capability.operating_flow_m3_s
    assert not hasattr(cleared.observation, "obstruction")
    assert not hasattr(cleared.observation, "clearance_loss")


def test_physical_journey_runs_with_research_tree_absent(
    tmp_path: Path,
) -> None:
    repository_root = Path(__file__).resolve().parents[4]
    isolated_root = tmp_path / "isolated"
    isolated_source = isolated_root / "src"
    shutil.copytree(
        repository_root / "src" / "aec_bench",
        isolated_source / "aec_bench",
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(isolated_source)
    environment["PYTHONNOUSERSITE"] = "1"
    script = """
import json
from decimal import Decimal
from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    OperatingInterval,
    PumpStationEnvironment,
    advance_pump_station,
    initial_pump_station_state,
    load_reference_package,
    pump_station_model_from_package,
)

model = pump_station_model_from_package(load_reference_package())
state = initial_pump_station_state(model)
result = advance_pump_station(
    model,
    state,
    OperatingInterval(
        elapsed_seconds=3600000,
        duty_runtime_seconds=3600000,
        duty_completed_starts=500,
        environment=PumpStationEnvironment(
            inflow_m3_s=Decimal("0.0155"),
            wet_well_level_m=Decimal("1.65"),
            isolated=False,
        ),
    ),
)
print(json.dumps({
    "calendar_seconds": result.state.calendar_seconds,
    "review_required": result.capability.review_required,
    "runtime_seconds": result.state.pump("pump-a").exposure.runtime_seconds,
}, sort_keys=True))
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=isolated_root,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )

    assert not (isolated_root / "research").exists()
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "calendar_seconds": 3_600_000,
        "review_required": False,
        "runtime_seconds": 3_600_000,
    }
