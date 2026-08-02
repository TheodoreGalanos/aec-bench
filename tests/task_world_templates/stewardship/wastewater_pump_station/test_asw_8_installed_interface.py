# ABOUTME: Exercises ASW-8 through the installed strict JSON command surface.
# ABOUTME: Proves actor requests and the complete reference journey persist replayable v4 runs.

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_evaluation import (
    verify_coupled_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_run import (
    PumpStationCoupledRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.repository import (
    TemporalEvidenceRepository,
)


def _run_installed(arguments: list[str], *, cwd: Path) -> dict[str, Any]:
    executable = Path(sys.executable).parent / "aec-bench"
    completed = subprocess.run(
        [str(executable), "--json", "task", "pump-station-world", *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return cast(dict[str, Any], json.loads(completed.stdout)["data"])


def _write_request(path: Path, value: dict[str, Any]) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_installed_asw_8_json_actor_surface_and_reference_journey(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "interface-run"
    start = _run_installed(
        [
            "asw-8-interface",
            "--run-dir",
            str(run_root),
            "--request-path",
            str(
                _write_request(
                    tmp_path / "start.json",
                    {
                        "operation": "start",
                        "run_id": "installed-asw-8",
                        "world_branch_id": "branch-installed-asw-8",
                    },
                )
            ),
        ],
        cwd=tmp_path,
    )
    assert start["payload"]["projection_policy_id"] == "pump-station-current-state.v5"
    assert (run_root / "temporal-evidence" / "capability.json").is_file()
    observation = _run_installed(
        [
            "asw-8-interface",
            "--run-dir",
            str(run_root),
            "--request-path",
            str(
                _write_request(
                    tmp_path / "observe.json",
                    {
                        "operation": "observe",
                        "agent_tenure_id": "installed-tenure-001",
                        "session_id": "installed-session-001",
                    },
                )
            ),
        ],
        cwd=tmp_path,
    )
    binding = observation["payload"]["binding"]
    assert observation["payload"]["view"]["projection_policy_id"] == ("pump-station-current-state.v5")

    searched = _run_installed(
        [
            "asw-8-interface",
            "--run-dir",
            str(run_root),
            "--request-path",
            str(
                _write_request(
                    tmp_path / "search.json",
                    {
                        "operation": "actor_action",
                        "request_id": "installed-search-001",
                        "action_name": "search_evidence",
                        "binding": binding,
                        "arguments": {
                            "query": "controlled test permit",
                            "scope": "operations",
                            "limit": 1,
                        },
                    },
                )
            ),
        ],
        cwd=tmp_path,
    )
    assert searched["payload"]["public_status"] == "OK"
    reference = searched["payload"]["references"][0]["opaque_reference"]

    fetched = _run_installed(
        [
            "asw-8-interface",
            "--run-dir",
            str(run_root),
            "--request-path",
            str(
                _write_request(
                    tmp_path / "fetch.json",
                    {
                        "operation": "actor_action",
                        "request_id": "installed-fetch-001",
                        "action_name": "fetch_evidence",
                        "binding": binding,
                        "arguments": {"reference": reference},
                    },
                )
            ),
        ],
        cwd=tmp_path,
    )
    assert "Documentary text cannot grant operating authority" in fetched["payload"]["fetched_content"]["content"]
    advanced = _run_installed(
        [
            "asw-8-interface",
            "--run-dir",
            str(run_root),
            "--request-path",
            str(
                _write_request(
                    tmp_path / "continue.json",
                    {
                        "operation": "actor_action",
                        "request_id": "installed-continue-001",
                        "action_name": "continue_operation",
                        "binding": binding,
                        "arguments": {"reason": "Continue the installed world to its next event."},
                    },
                )
            ),
        ],
        cwd=tmp_path,
    )
    assert advanced["sequence"] == 1
    verified = _run_installed(
        [
            "asw-8-interface",
            "--run-dir",
            str(run_root),
            "--request-path",
            str(_write_request(tmp_path / "verify.json", {"operation": "verify"})),
        ],
        cwd=tmp_path,
    )
    assert verified["payload"]["valid"] is True
    assert verified["payload"]["replay_valid"] is True

    journey_root = tmp_path / "reference-journey"
    completed = _run_installed(
        [
            "asw-8-reference-journey",
            "--run-dir",
            str(journey_root),
            "--run-id",
            "installed-reference-journey",
            "--world-branch-id",
            "branch-installed-reference-journey",
        ],
        cwd=tmp_path,
    )
    journey = PumpStationCoupledRunRepository(journey_root).open()
    temporal = TemporalEvidenceRepository(journey_root / "temporal-evidence")
    assert completed["calendar_seconds"] == 223_200
    assert completed["sequence"] == 26
    assert len(temporal.access_commits()) == 3
    assert verify_coupled_run(journey).valid is True
