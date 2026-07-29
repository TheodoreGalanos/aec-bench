# ABOUTME: Exercises the installed CLI across a real pump-station start, action, resume, and verify journey.
# ABOUTME: Runs outside the repository working directory without research files or provider calls.

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast


def _run_cli(*args: str, cwd: Path) -> dict[str, Any]:
    executable = Path(sys.executable).parent / "aec-bench"
    completed = subprocess.run(
        [str(executable), "--json", "task", "pump-station-world", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return cast(dict[str, Any], json.loads(completed.stdout))


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
    assert verified["data"]["replayed_transition_ids"] == [
        "transition-0001",
        "transition-0002",
    ]
    assert evaluated["data"]["valid"] is True
    assert evaluated["data"]["metrics"]["handover_count"] == 1
    assert evaluated["data"]["metrics"]["handover_omission_count"] == 0
    assert evaluated["data"]["metrics"]["terminal_liability"]["review_required_physical_state"] is True
