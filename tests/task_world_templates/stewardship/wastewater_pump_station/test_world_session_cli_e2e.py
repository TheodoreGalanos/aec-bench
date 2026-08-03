# ABOUTME: Exercises the installed CLI across a real pump-station start, action, resume, and verify journey.
# ABOUTME: Runs outside the repository working directory without research files or provider calls.

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.local_interface import (
    PumpStationLocalInterfaceRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
)


def _run_cli_process(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    executable = Path(sys.executable).parent / "aec-bench"
    return subprocess.run(
        [str(executable), "--json", "task", "pump-station-world", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _run_cli(*args: str, cwd: Path) -> dict[str, Any]:
    completed = _run_cli_process(*args, cwd=cwd)
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return cast(dict[str, Any], json.loads(completed.stdout))


def _create_registered_run(root: Path, *, identity: str) -> PumpStationWorldRun[Any, Any]:
    return PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id=f"{identity}-run",
        episode_id=f"{identity}-episode",
        world_branch_id=f"{identity}-branch",
    )


def test_installed_cli_starts_advances_resumes_and_verifies_world(tmp_path: Path) -> None:
    run_dir = tmp_path / "pump-station-run"

    started = _run_cli(
        "start",
        "--run-dir",
        str(run_dir),
        "--run-id",
        "run-cli-1",
        "--episode-id",
        "episode-cli-1",
        "--world-branch-id",
        "branch-cli-1",
        "--session-id",
        "session-cli-1",
        "--agent-tenure-id",
        "tenure-cli-1",
        cwd=tmp_path,
    )
    advanced = _run_cli(
        "continue-operation",
        "--run-dir",
        str(run_dir),
        "--session-id",
        "session-cli-2",
        "--agent-tenure-id",
        "tenure-cli-1",
        "--proposal-id",
        "proposal-cli-1",
        "--reason",
        "Continue to the next declared event.",
        cwd=tmp_path,
    )
    resumed = _run_cli(
        "resume",
        "--run-dir",
        str(run_dir),
        "--session-id",
        "session-cli-3",
        "--agent-tenure-id",
        "tenure-cli-2",
        cwd=tmp_path,
    )
    advanced_after_handover = _run_cli(
        "continue-operation",
        "--run-dir",
        str(run_dir),
        "--session-id",
        "session-cli-4",
        "--agent-tenure-id",
        "tenure-cli-2",
        "--proposal-id",
        "proposal-cli-2",
        "--reason",
        "Continue after the fresh-tenure handover.",
        cwd=tmp_path,
    )
    verified = _run_cli("verify", "--run-dir", str(run_dir), cwd=tmp_path)
    evaluated = _run_cli("evaluate", "--run-dir", str(run_dir), cwd=tmp_path)

    assert started["data"]["snapshot"]["sequence"] == 0
    assert advanced["data"]["snapshot"]["sequence"] == 1
    assert resumed["data"]["snapshot"] == advanced["data"]["snapshot"]
    assert resumed["data"]["agent_tenure_id"] == "tenure-cli-2"
    assert advanced_after_handover["data"]["snapshot"]["sequence"] == 2
    assert verified["data"]["valid"] is True
    assert set(verified["data"]) == {
        "active_restriction_ids",
        "final_state_id",
        "issues",
        "open_obligation_ids",
        "replayed_transition_ids",
        "valid",
    }
    assert verified["data"]["replayed_transition_ids"] == [
        "transition-0001",
        "transition-0002",
    ]
    assert evaluated["data"]["valid"] is True
    assert evaluated["data"]["metrics"]["handover_count"] == 1
    assert evaluated["data"]["metrics"]["handover_omission_count"] == 0
    assert evaluated["data"]["metrics"]["terminal_liability"]["review_required_physical_state"] is True


def test_installed_cli_searches_fetches_and_verifies_temporal_evidence(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "temporal-run"
    started = _run_cli(
        "start",
        "--run-dir",
        str(run_dir),
        "--run-id",
        "run-temporal-cli",
        "--episode-id",
        "episode-temporal-cli",
        "--world-branch-id",
        "branch-temporal-cli",
        "--session-id",
        "session-temporal-cli",
        "--agent-tenure-id",
        "tenure-temporal-cli",
        "--temporal-evidence",
        cwd=tmp_path,
    )
    searched = _run_cli(
        "search-evidence",
        "--run-dir",
        str(run_dir),
        "--session-id",
        "session-temporal-cli",
        "--agent-tenure-id",
        "tenure-temporal-cli",
        "--request-id",
        "search-temporal-cli",
        "--query",
        "pump obstruction procedure",
        "--scope",
        "procedures",
        cwd=tmp_path,
    )
    reference = searched["data"]["receipt"]["references"][0]["opaque_reference"]
    fetched = _run_cli(
        "fetch-evidence",
        "--run-dir",
        str(run_dir),
        "--session-id",
        "session-temporal-cli",
        "--agent-tenure-id",
        "tenure-temporal-cli",
        "--request-id",
        "fetch-temporal-cli",
        "--reference",
        reference,
        cwd=tmp_path,
    )
    verified = _run_cli(
        "verify-temporal-evidence",
        "--run-dir",
        str(run_dir),
        cwd=tmp_path,
    )

    assert "search_evidence" in started["data"]["tool_names"]
    assert searched["data"]["receipt"]["public_status"] == "OK"
    assert fetched["data"]["receipt"]["public_status"] == "OK"
    assert verified["data"]["valid"] is True
    assert verified["data"]["access_count"] == 2


def test_legacy_combined_interface_rejects_a_registered_v4_run(tmp_path: Path) -> None:
    run_root = tmp_path / "registered-world"
    run = _create_registered_run(run_root, identity="legacy-interface-v4")
    snapshot = run.snapshot()
    request = PumpStationLocalInterfaceRequest(
        surface="actor",
        operation="capabilities",
        session_request=WorldSessionRequest(
            execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
            open_mode=WorldSessionOpenMode.RESUME,
            session_id="legacy-interface-v4-session",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            agent_tenure_id="legacy-interface-v4-tenure",
            run_id=snapshot.run_id,
            episode_id=snapshot.episode_id,
            world_branch_id=snapshot.world_branch_id,
            start_snapshot=StewardshipStateSnapshotRef(
                run_id=snapshot.run_id,
                episode_id=snapshot.episode_id,
                world_branch_id=snapshot.world_branch_id,
                sequence=snapshot.sequence,
                state_id=snapshot.state_id,
                commit_id=snapshot.commit_id,
            ),
        ),
    )
    request_path = tmp_path / "legacy-interface-request.json"
    request_path.write_text(request.model_dump_json(), encoding="utf-8")

    completed = _run_cli_process(
        "interface",
        "--run-dir",
        str(run_root),
        "--request-path",
        str(request_path),
        cwd=tmp_path,
    )

    assert completed.returncode != 0
    error_text = " ".join((completed.stderr + completed.stdout).split())
    assert "registered V4 runs require" in error_text
    assert "actor-interface" in error_text
    assert "control-interface" in error_text


def test_installed_verify_projects_registered_v4_replay_control_and_conservation(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "registered-world"
    run = _create_registered_run(run_root, identity="verify-v4")
    report = run.verify_v4()

    verified = _run_cli("verify", "--run-dir", str(run_root), cwd=tmp_path)["data"]

    assert set(verified) == {
        "actor_proposals_valid",
        "conservation",
        "final_state_id",
        "host_controls_valid",
        "issues",
        "replay_valid",
        "replayed_transition_ids",
        "valid",
    }
    assert verified["valid"] is report.valid
    assert verified["replay_valid"] is report.replay_valid
    assert verified["actor_proposals_valid"] is report.actor_proposals_valid
    assert verified["host_controls_valid"] is report.host_controls_valid
    assert verified["replayed_transition_ids"] == list(report.replayed_transition_ids)
    assert verified["final_state_id"] == report.final_state_id
    conservation = verified["conservation"]
    assert conservation["valid"] is report.conservation.valid
    assert conservation["duty"] == json.loads(json.dumps(asdict(report.conservation.duty)))
    assert conservation["resources"] == json.loads(json.dumps(asdict(report.conservation.resources)))
    assert conservation["work"] == json.loads(json.dumps(asdict(report.conservation.work)))
    assert conservation["liabilities"] == json.loads(json.dumps(asdict(report.conservation.liabilities)))
