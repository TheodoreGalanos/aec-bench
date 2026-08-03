# ABOUTME: Tests current pump run repository identity and filesystem boundaries.
# ABOUTME: Proves content moved under another identity is rejected and run directories are private.

from __future__ import annotations

import stat
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
        run_id="repository-run",
        episode_id="repository-episode",
        world_branch_id="repository-branch",
    )


def test_repository_rejects_content_under_the_wrong_identity(tmp_path: Path) -> None:
    run = _start(tmp_path / "run")
    correct_id = run.snapshot().state_id
    wrong_id = "0" * 64
    states = run.repository.root / "states"
    wrong_path = states / f"{wrong_id}.json"
    wrong_path.write_bytes((states / f"{correct_id}.json").read_bytes())
    wrong_path.chmod(0o600)

    with pytest.raises(PumpStationWorldRunError, match="artifact-integrity"):
        run.repository.load_state(wrong_id)


def test_repository_creates_private_run_directories(tmp_path: Path) -> None:
    root = tmp_path / "run"
    _start(root)

    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert stat.S_IMODE((root / "states").stat().st_mode) == 0o700
