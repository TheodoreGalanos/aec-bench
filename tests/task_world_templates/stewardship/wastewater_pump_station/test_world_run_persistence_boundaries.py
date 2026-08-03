# ABOUTME: Attacks the current pump run codec with damaged or extra stored content.
# ABOUTME: Proves reload fails closed and repository working files never gain authority.

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationWorldRunError,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)


def _start(root: Path) -> PumpStationWorldRun:
    return PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="persistence-run",
        episode_id="persistence-episode",
        world_branch_id="persistence-branch",
    )


def test_current_reload_rejects_unknown_stored_fields(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = _start(root)
    manifest_path = root / "manifest.json"
    document = json.loads(manifest_path.read_bytes())
    document["obsolete_field"] = "not-current"
    manifest_path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(PumpStationWorldRunError, match="artifact-shape"):
        PumpStationWorldRun.resume_reference_system(
            repository=PumpStationWorldRunRepository(root),
            snapshot=run.snapshot(),
        )


def test_current_reload_rejects_truncated_state(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = _start(root)
    state_path = root / "states" / f"{run.snapshot().state_id}.json"
    payload = state_path.read_bytes()
    state_path.write_bytes(payload[: len(payload) // 2])

    with pytest.raises(PumpStationWorldRunError):
        PumpStationWorldRun.resume_reference_system(
            repository=PumpStationWorldRunRepository(root),
            snapshot=run.snapshot(),
        )


def test_working_file_never_becomes_selected_history(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = _start(root)
    before = run.snapshot()
    working_path = root / ".current.forged.tmp"
    working_path.write_bytes((root / "current.json").read_bytes())

    repository = PumpStationWorldRunRepository(root)

    assert repository.current_snapshot() == before
    assert len(repository.commits()) == 1
