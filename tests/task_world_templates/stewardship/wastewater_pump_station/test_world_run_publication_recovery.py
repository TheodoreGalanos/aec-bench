# ABOUTME: Tests current registered action publication under retries and concurrency.
# ABOUTME: Proves one opaque decision can select only one durable transition.

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from aec_bench.contracts.world_interface import WorldActorActionRequest, WorldInterfaceError
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.episode_runtime import (
    PumpStationEpisodeHost,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)


def _start(root: Path) -> PumpStationWorldRun:
    return PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="publication-run",
        episode_id="publication-episode",
        world_branch_id="publication-branch",
    )


def test_retry_returns_the_selected_current_transition(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = _start(root)
    host = PumpStationEpisodeHost(root)
    observation = host.observe()
    request = WorldActorActionRequest(
        request_id="publication-retry",
        decision_id=observation.decision_id,
        action_name="continue_operation",
        arguments={"reason": "Select this transition once."},
    )

    first = host.invoke(request)
    retry = PumpStationEpisodeHost(root).invoke(request)

    assert retry == first
    assert run.snapshot().sequence == 1
    assert len(run.repository.command_steps()) == 1


def test_concurrent_current_actions_select_one_transition(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = _start(root)
    decision_id = PumpStationEpisodeHost(root).observe().decision_id
    requests = tuple(
        WorldActorActionRequest(
            request_id=f"publication-{index}",
            decision_id=decision_id,
            action_name="continue_operation",
            arguments={"reason": f"Concurrent candidate {index}."},
        )
        for index in range(2)
    )

    def invoke(request: WorldActorActionRequest) -> str:
        try:
            PumpStationEpisodeHost(root).invoke(request)
        except WorldInterfaceError as error:
            return str(error)
        return "applied"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(invoke, requests))

    assert outcomes.count("applied") == 1
    assert any("decision-stale" in outcome for outcome in outcomes)
    assert run.snapshot().sequence == 1
    assert len(run.repository.command_steps()) == 1
    assert run.verify().valid
