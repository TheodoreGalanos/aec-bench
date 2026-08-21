# ABOUTME: Tests public branch composition over the existing pump rollout implementation.
# ABOUTME: Proves branch creation is isolated and unsupported worlds fail before materialization.

from pathlib import Path

import pytest

from aec_bench import worlds
from aec_bench.contracts.continual_world import ContinualRolloutChildRequest
from aec_bench.worlds.monitoring.dam_seepage.world import DAM_SEEPAGE_TASK_WORLD_ID
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import PUMP_STATION_TASK_WORLD_ID
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import PumpStationWorldRun
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)


def test_branch_world_creates_isolated_tasks_without_changing_parent(tmp_path: Path) -> None:
    profile_id = worlds.profiles(PUMP_STATION_TASK_WORLD_ID)[0].id
    task = worlds.task(PUMP_STATION_TASK_WORLD_ID, profile=profile_id, instruction="Operate the station.")
    parent = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(tmp_path / "parent"),
        run_id="parent-run",
        episode_id="parent-episode",
        world_branch_id="parent-branch",
    )
    parent_before = parent.snapshot()
    lineage = worlds.branch_world(
        task=task,
        parent=parent,
        branches=(
            ContinualRolloutChildRequest(
                child_id="candidate",
                run_id="candidate-run",
                episode_id="candidate-episode",
                world_branch_id="candidate-branch",
            ),
        ),
        rollout_root=tmp_path / "rollouts",
        authority_id="branch-authority",
        request_id="branch-request",
        group_id="branch-group",
        reason="Test one isolated child.",
    )

    child_tasks = worlds.tasks_for_branches(task, lineage)

    assert parent.snapshot() == parent_before
    assert [child.task_id for child in child_tasks] == [f"{task.task_id}/branches/candidate"]
    assert child_tasks[0].profile == task.profile


def test_branch_world_rejects_world_without_capability_before_materialization(tmp_path: Path) -> None:
    task = worlds.task(
        DAM_SEEPAGE_TASK_WORLD_ID,
        profile="synthetic-rising-seepage",
        instruction="Monitor the dam.",
    )
    parent = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(tmp_path / "parent"),
        run_id="parent-run",
        episode_id="parent-episode",
        world_branch_id="parent-branch",
    )

    with pytest.raises(ValueError, match="does not support branching"):
        worlds.branch_world(
            task=task,
            parent=parent,
            branches=(
                ContinualRolloutChildRequest(
                    child_id="candidate",
                    run_id="candidate-run",
                    episode_id="candidate-episode",
                    world_branch_id="candidate-branch",
                ),
            ),
            rollout_root=tmp_path / "rollouts",
            authority_id="branch-authority",
            request_id="branch-request",
            group_id="branch-group",
            reason="Must fail.",
        )

    assert not (tmp_path / "rollouts").exists()
