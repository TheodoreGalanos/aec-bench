# ABOUTME: Proves current actor transitions publish, retry, recover, and replay exactly once.
# ABOUTME: Exercises the episode host and one durable command chain without historical profiles.

from __future__ import annotations

from pathlib import Path

import pytest

from aec_bench.contracts.world_interface import WorldActorActionRequest, WorldInterfaceError
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PumpStationEpisodeHost,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)


def _start(root: Path) -> PumpStationWorldRun:
    return PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="transition-run",
        episode_id="transition-episode",
        world_branch_id="transition-branch",
    )


def _request(host: PumpStationEpisodeHost, *, request_id: str = "action-1") -> WorldActorActionRequest:
    observation = host.observe()
    return WorldActorActionRequest(
        request_id=request_id,
        decision_id=observation.decision_id,
        action_name="continue_operation",
        arguments={"reason": "Advance the current world once."},
    )


def test_actor_request_retry_returns_the_one_selected_transition(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = _start(root)
    host = PumpStationEpisodeHost(root)
    request = _request(host)

    first = host.invoke(request)
    retry = PumpStationEpisodeHost(root).invoke(request)

    assert retry == first
    assert run.snapshot().sequence == 1
    assert len(run.repository.command_steps()) == 1
    assert run.verify().valid


def test_interrupted_publication_recovers_one_exact_actor_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "run"
    run = _start(root)
    interrupted_host = PumpStationEpisodeHost(root)
    request = _request(interrupted_host)

    def fail_selection(_pointer: object) -> None:
        raise OSError("interrupt after immutable staging")

    monkeypatch.setattr(interrupted_host._repository, "_replace_current", fail_selection)
    with pytest.raises(OSError, match="interrupt after immutable staging"):
        interrupted_host.invoke(request)

    assert run.snapshot().sequence == 0
    recovered = PumpStationEpisodeHost(root).invoke(request)

    assert recovered.status == "applied"
    assert run.snapshot().sequence == 1
    assert len(run.repository.command_steps()) == 1
    assert run.verify().valid


def test_reused_request_id_with_changed_content_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = _start(root)
    host = PumpStationEpisodeHost(root)
    request = _request(host)
    host.invoke(request)

    changed = WorldActorActionRequest(
        request_id=request.request_id,
        decision_id=request.decision_id,
        action_name=request.action_name,
        arguments={"reason": "Different content under the same request identity."},
    )
    with pytest.raises(WorldInterfaceError, match="actor-request-id-conflict"):
        PumpStationEpisodeHost(root).invoke(changed)

    assert run.snapshot().sequence == 1
    assert len(run.repository.command_steps()) == 1
