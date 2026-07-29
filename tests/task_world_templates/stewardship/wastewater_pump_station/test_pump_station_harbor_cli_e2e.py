# ABOUTME: Exercises installed CLI export, job preparation, Harbor import, and TrialRecord reload.
# ABOUTME: Uses a real pump-station session and exact task evidence without provider calls.

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import yaml

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
    load_pump_station_harbor_bridge,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
    PUMP_STATION_REFERENCE_CONTROLLER_ID,
    run_pump_station_reference_session,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _run_cli(*args: str, cwd: Path) -> dict[str, Any]:
    executable = Path(sys.executable).parent / "aec-bench"
    completed = subprocess.run(
        [str(executable), "--json", "task", "pump-station-world", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return cast(dict[str, Any], json.loads(completed.stdout))


def test_installed_cli_exports_prepares_imports_and_reloads_harbor_trial(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    task_dir = repo_root / "tasks" / "stewardship" / "wastewater-pump-station"
    exported = _run_cli(
        "export-harbor",
        "--task-dir",
        str(task_dir),
        "--project-root",
        str(PROJECT_ROOT),
        cwd=tmp_path,
    )
    config_path = repo_root / "pump-station-harbor.yaml"
    prepared = _run_cli(
        "run-harbor",
        "--task-dir",
        str(task_dir),
        "--project-root",
        str(PROJECT_ROOT),
        "--jobs-dir",
        str(repo_root / "jobs"),
        "--config-path",
        str(config_path),
        "--no-execute",
        cwd=tmp_path,
    )
    remote_preparations = {}
    for backend in ("modal", "morph"):
        remote_preparations[backend] = _run_cli(
            "run-harbor",
            "--task-dir",
            str(task_dir),
            "--project-root",
            str(PROJECT_ROOT),
            "--jobs-dir",
            str(repo_root / f"jobs-{backend}"),
            "--config-path",
            str(repo_root / f"pump-station-{backend}.yaml"),
            "--backend",
            backend,
            "--model",
            "au.anthropic.claude-sonnet-4-6",
            "--max-turns",
            "30",
            "--no-execute",
            cwd=tmp_path,
        )
    bridge = load_pump_station_harbor_bridge(task_dir / "environment")
    source_run = tmp_path / "source-world-session"
    completed = run_pump_station_reference_session(
        bridge=bridge,
        output_dir=source_run,
        session_identity="installed-cli-harbor",
    )
    trial_dir = repo_root / "jobs" / "job-cli" / "trial-cli"
    agent_dir = trial_dir / "artifacts" / "agent"
    agent_dir.mkdir(parents=True)
    shutil.copytree(source_run, agent_dir / "world-session")
    (agent_dir / "output.md").write_text(
        "The deterministic wastewater pump-station session completed.\n",
        encoding="utf-8",
    )
    verifier_dir = trial_dir / "verifier"
    verifier_dir.mkdir()
    (verifier_dir / "reward.json").write_text(
        '{"reward": 1.0}\n',
        encoding="utf-8",
    )
    (verifier_dir / "details.json").write_text(
        json.dumps(
            {
                "valid": True,
                "reward_owner": "harbor_verifier",
                "task_world_id": completed.result.task_world_id,
            }
        ),
        encoding="utf-8",
    )
    (trial_dir / "result.json").write_text(
        json.dumps(
            {
                "trial_name": "trial-cli",
                "task_checksum": "pump-station-export",
                "config": {
                    "task": {"path": "tasks/stewardship/wastewater-pump-station"},
                    "agent": {
                        "name": "pump-station-reference-controller",
                        "model_name": PUMP_STATION_REFERENCE_CONTROLLER_ID,
                        "import_path": "agents.entrypoint_agent:EntrypointAgent",
                        "kwargs": {
                            "adapter": "tool_loop",
                            "execution_kind": "stewardship_world_session",
                            "world_session": {"bridge_mode": ("wastewater_pump_station_reference")},
                        },
                    },
                    "environment": {"type": "docker", "kwargs": {}},
                    "job_id": "job-cli",
                },
                "agent_info": {
                    "name": "entrypoint",
                    "version": "1.0.0",
                },
                "agent_result": {
                    "metadata": {
                        "adapter_name": "tool_loop",
                        "execution_kind": "stewardship_world_session",
                        "model": PUMP_STATION_REFERENCE_CONTROLLER_ID,
                        "reward_owner": "harbor_verifier",
                    }
                },
                "started_at": "2026-07-29T00:00:00Z",
                "finished_at": "2026-07-29T00:00:01Z",
            }
        ),
        encoding="utf-8",
    )
    record_path = repo_root / "trial-record.json"
    imported = _run_cli(
        "import-harbor-trial",
        "--trial-dir",
        str(trial_dir),
        "--repo-root",
        str(repo_root),
        "--record-path",
        str(record_path),
        cwd=tmp_path,
    )
    reloaded = _run_cli(
        "reload-trial-record",
        "--record-path",
        str(record_path),
        cwd=tmp_path,
    )

    assert Path(exported["data"]["manifest_path"]).is_file()
    assert prepared["data"]["executed"] is False
    assert {backend: result["data"]["backend"] for backend, result in remote_preparations.items()} == {
        "modal": "modal",
        "morph": "morph",
    }
    for backend in ("modal", "morph"):
        remote_config = yaml.safe_load((repo_root / f"pump-station-{backend}.yaml").read_text(encoding="utf-8"))
        assert remote_config["agents"][0]["model_name"] == ("au.anthropic.claude-sonnet-4-6")
        assert "AWS_BEARER_TOKEN_BEDROCK" not in json.dumps(remote_config)
    assert config_path.is_file()
    assert imported["data"]["trial_id"] == "trial-cli"
    assert imported["data"]["transition_count"] == 12
    assert reloaded["data"]["trial_id"] == "trial-cli"
    assert reloaded["data"]["execution_kind"] == ("stewardship_world_session")
