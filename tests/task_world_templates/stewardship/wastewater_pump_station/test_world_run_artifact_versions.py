# ABOUTME: Proves the one current persisted run shape fails closed on unknown versions.
# ABOUTME: Covers manifest, snapshot, opening commit, pointer, command, and receipt records.

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.episode_runtime import (
    PumpStationEpisodeHost,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationCurrentRunPointer,
    PumpStationWorldRunError,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    load_pump_station_artifact,
)


def test_current_persisted_versions_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="versions-run",
        episode_id="versions-episode",
        world_branch_id="versions-branch",
    )
    snapshot = run.snapshot()
    opening_commit = run.repository.commits()[0]
    pointer = load_pump_station_artifact(
        (root / "current.json").read_bytes(),
        PumpStationCurrentRunPointer,
    )

    with pytest.raises(PumpStationWorldRunError, match="serialization-version"):
        replace(run.manifest, serialization_version="pump-station-world-run.unknown")
    with pytest.raises(PumpStationWorldRunError, match="snapshot-version"):
        replace(snapshot, snapshot_version="pump-station-state-snapshot.unknown")
    with pytest.raises(PumpStationWorldRunError, match="serialization-version"):
        replace(opening_commit, serialization_version="pump-station-world-run.unknown")
    with pytest.raises(PumpStationWorldRunError, match="serialization-version"):
        replace(pointer, serialization_version="pump-station-world-run.unknown")

    host = PumpStationEpisodeHost(root)
    observation = host.observe()
    host.invoke(
        WorldActorActionRequest(
            request_id="versioned-action",
            decision_id=observation.decision_id,
            action_name="continue_operation",
            arguments={"reason": "Create one current command and receipt."},
        )
    )
    step = run.repository.command_steps()[0]
    with pytest.raises(PumpStationWorldRunError, match="command-version"):
        replace(step.command, command_version="pump-station-world-command.unknown")
    assert not hasattr(step.transition.receipt, "receipt_version")
