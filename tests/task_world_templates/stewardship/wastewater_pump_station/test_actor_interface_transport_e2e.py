# ABOUTME: Exercises the current opaque-decision actor boundary through independent CLI processes.
# ABOUTME: Proves durable context recovery, stale-decision rejection, and serialized concurrent actions.

from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.task_world_templates.continual.episode import EpisodeFinishedError, EpisodeLimits
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.episode_runtime import (
    PumpStationEpisodeHost,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)


def _write_request(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run_actor(run_dir: Path, request_path: Path) -> subprocess.CompletedProcess[str]:
    executable = Path(sys.executable).parent / "aec-bench"
    return subprocess.run(
        [
            str(executable),
            "--json",
            "task",
            "pump-station-world",
            "actor-interface",
            "--run-dir",
            str(run_dir),
            "--request-path",
            str(request_path),
        ],
        cwd=request_path.parent,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )


def _result(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return cast(dict[str, Any], json.loads(completed.stdout)["data"])


def _invoke_payload(*, request_id: str, decision_id: str) -> dict[str, object]:
    return {
        "operation": "invoke",
        "request_id": request_id,
        "decision_id": decision_id,
        "action_name": "continue_operation",
        "arguments": {"reason": "Advance the registered episode under its current plan."},
    }


def test_installed_actor_calls_resolve_durable_context_across_processes(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "world"
    run = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(run_dir),
        run_id="installed-actor-run",
        episode_id="installed-actor-episode",
        world_branch_id="installed-actor-branch",
    )

    capabilities = _result(
        _run_actor(
            run_dir,
            _write_request(tmp_path / "capabilities.json", {"operation": "capabilities"}),
        )
    )
    observed = _result(
        _run_actor(
            run_dir,
            _write_request(tmp_path / "observe.json", {"operation": "observe"}),
        )
    )
    decision_id = cast(str, observed["decision_id"])
    accepted = _result(
        _run_actor(
            run_dir,
            _write_request(
                tmp_path / "invoke.json",
                _invoke_payload(request_id="installed-action-1", decision_id=decision_id),
            ),
        )
    )

    assert "continue_operation" in {action["name"] for action in capabilities["actions"]}
    assert set(observed) == {"decision_id", "view"}
    assert accepted["next_observation"]["decision_id"] != decision_id
    assert run.snapshot().sequence == 1
    assert run.verify().valid

    stale = _run_actor(
        run_dir,
        _write_request(
            tmp_path / "stale.json",
            _invoke_payload(request_id="installed-action-stale", decision_id=decision_id),
        ),
    )
    assert stale.returncode != 0
    assert "decision-stale" in stale.stderr + stale.stdout
    assert run.snapshot().sequence == 1


def test_concurrent_process_calls_advance_one_decision_once(tmp_path: Path) -> None:
    run_dir = tmp_path / "world"
    run = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(run_dir),
        run_id="concurrent-actor-run",
        episode_id="concurrent-actor-episode",
        world_branch_id="concurrent-actor-branch",
    )
    observed = _result(
        _run_actor(
            run_dir,
            _write_request(tmp_path / "observe.json", {"operation": "observe"}),
        )
    )
    decision_id = cast(str, observed["decision_id"])
    request_paths = tuple(
        _write_request(
            tmp_path / f"concurrent-{index}.json",
            _invoke_payload(request_id=f"concurrent-action-{index}", decision_id=decision_id),
        )
        for index in range(2)
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        completed = tuple(executor.map(lambda path: _run_actor(run_dir, path), request_paths))

    assert sorted(item.returncode == 0 for item in completed) == [False, True]
    rejected = next(item for item in completed if item.returncode != 0)
    assert "decision-stale" in rejected.stderr + rejected.stdout
    assert run.snapshot().sequence == 1
    assert len(run.repository.command_steps()) == 1
    assert run.verify().valid


def test_registered_episode_records_accepted_step_before_runtime_truncation(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "world"
    run = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(run_dir),
        run_id="limited-actor-run",
        episode_id="limited-actor-episode",
        world_branch_id="limited-actor-branch",
    )
    host = PumpStationEpisodeHost(run_dir, limits=EpisodeLimits(max_steps=1))
    observation = host.observe()

    result = host.invoke(
        WorldActorActionRequest(
            request_id="limited-action-1",
            decision_id=observation.decision_id,
            action_name="continue_operation",
            arguments={"reason": "Advance once, then stop at the host limit."},
        )
    )

    assert result.terminated is False
    assert result.truncated is True
    assert result.reason == "step limit reached"
    assert result.next_observation is None
    assert run.snapshot().sequence == 1
    assert len(run.repository.command_steps()) == 1
    assert run.verify().valid
    with pytest.raises(EpisodeFinishedError, match="episode is truncated"):
        PumpStationEpisodeHost(run_dir, limits=EpisodeLimits(max_steps=1)).observe()
