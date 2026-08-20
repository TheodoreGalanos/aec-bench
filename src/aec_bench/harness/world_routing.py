# ABOUTME: Selects the fixed built-in Interactive World trial functions at the application boundary.
# ABOUTME: Rejects unsupported world and provider combinations before any trial execution starts.

from __future__ import annotations

from functools import partial
from pathlib import Path

from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.harness.dam_seepage_trial import run_dam_seepage_trial
from aec_bench.harness.prime_world_actor import run_prime_world_actor_session
from aec_bench.harness.pump_station_harbor.trial import run_pump_station_harbor_trial
from aec_bench.harness.pump_station_trial import run_pump_station_trial
from aec_bench.trials import PlannedTrial
from aec_bench.worlds.monitoring.dam_seepage.world import DAM_SEEPAGE_TASK_WORLD_ID
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import PUMP_STATION_TASK_WORLD_ID
from aec_bench.worlds.tasks import WorldTask


async def run_selected_world(task: WorldTask, trial: PlannedTrial, *, work_root: Path) -> TrialRecord:
    """Run one supported built-in world and provider route."""

    routes = {
        (DAM_SEEPAGE_TASK_WORLD_ID, "prime-agent"): partial(
            run_dam_seepage_trial,
            actor=run_prime_world_actor_session,
        ),
        (PUMP_STATION_TASK_WORLD_ID, "prime-agent"): partial(
            run_pump_station_trial,
            actor=run_prime_world_actor_session,
        ),
        (PUMP_STATION_TASK_WORLD_ID, "deepseek_harness"): partial(
            run_pump_station_harbor_trial,
            work_root=work_root / trial.trial_id,
        ),
    }
    key = (task.world.task_world_id, trial.agent.adapter)
    try:
        runner = routes[key]
    except KeyError as error:
        raise ValueError(f"unsupported world trial route: {key}") from error
    return await runner(task, trial)


def validate_world_routes(tasks: list[WorldTask], trials: list[PlannedTrial]) -> None:
    """Fail before execution when one planned built-in route is unsupported."""

    by_id = {task.task_id: task for task in tasks}
    supported = {
        (DAM_SEEPAGE_TASK_WORLD_ID, "prime-agent"),
        (PUMP_STATION_TASK_WORLD_ID, "prime-agent"),
        (PUMP_STATION_TASK_WORLD_ID, "deepseek_harness"),
    }
    for trial in trials:
        task = by_id.get(trial.task_id)
        if task is None:
            raise ValueError(f"planned world trial has no supplied task: {trial.task_id}")
        key = (task.world.task_world_id, trial.agent.adapter)
        if key not in supported:
            raise ValueError(f"unsupported world trial route: {key}")


__all__ = ("run_selected_world", "validate_world_routes")
