# ABOUTME: Runs the pump-station entrypoint and verifier through a real local Harbor trial.
# ABOUTME: Proves phase ordering and artifacts without Docker isolation or provider calls.

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

from harbor.models.trial.config import TrialConfig  # type: ignore[import-untyped]
from harbor.trial.trial import Trial  # type: ignore[import-untyped]

from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evaluation.stewardship import (
    evaluate_pump_station_stewardship_run,
)
from aec_bench.harness.harbor_importing.core import import_harbor_trial
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
    PUMP_STATION_HARBOR_BRIDGE_MODE,
    PUMP_STATION_HARBOR_EXECUTION_KIND,
    export_pump_station_harbor_task,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
    PUMP_STATION_REFERENCE_CONTROLLER_ID,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def test_local_harbor_trial_runs_entrypoint_then_independent_verifier(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    exported = export_pump_station_harbor_task(
        repo_root / "tasks" / "stewardship" / "wastewater-pump-station",
        project_root=PROJECT_ROOT,
    )
    trial_name = "pump-station-local-runtime"
    config = TrialConfig.model_validate(
        {
            "task": {"path": str(exported.task_dir)},
            "trial_name": trial_name,
            "trials_dir": str(repo_root / "jobs" / "local-runtime"),
            "job_id": "5b496f28-6ab0-452d-b47a-32a318f6fedf",
            "agent": {
                "name": "pump-station-reference-controller",
                "import_path": "agents.entrypoint_agent:EntrypointAgent",
                "model_name": PUMP_STATION_REFERENCE_CONTROLLER_ID,
                "kwargs": {
                    "adapter": "tool_loop",
                    "execution_kind": PUMP_STATION_HARBOR_EXECUTION_KIND,
                    "world_session": {"bridge_mode": PUMP_STATION_HARBOR_BRIDGE_MODE},
                },
            },
            "environment": {
                "import_path": ("tests.support.harbor_local_environment:LocalFilesystemHarborEnvironment"),
                "delete": False,
                "kwargs": {"compute_backend": "local"},
            },
            "artifacts": [
                {
                    "source": "/workspace/world-session",
                    "destination": "agent/world-session",
                },
                {
                    "source": "/workspace/output.md",
                    "destination": "agent/output.md",
                },
            ],
        }
    )

    result = asyncio.run(Trial(config).run())

    assert result.exception_info is None
    assert result.agent_result is not None
    assert result.agent_result.n_input_tokens == 0
    assert result.agent_result.n_output_tokens == 0
    assert result.agent_result.metadata["execution_kind"] == (PUMP_STATION_HARBOR_EXECUTION_KIND)
    assert result.agent_result.metadata["world_session_status"] == "completed"
    assert result.verifier_result is not None
    assert result.verifier_result.rewards == {"reward": 1.0}

    trial_dir = config.trials_dir / trial_name
    record = import_harbor_trial(
        trial_dir=trial_dir,
        repo_root=repo_root,
    )
    reloaded = TrialRecord.model_validate_json(record.model_dump_json())
    assert reloaded == record
    assert record.world_execution is not None
    assert record.world_execution.transition_count == 12
    assert record.world_provenance is not None
    assert record.outputs.artifacts is not None
    world_session_dir = next(
        candidate
        for candidate in (
            trial_dir / "agent" / "world-session",
            trial_dir / "artifacts" / "agent" / "world-session",
        )
        if candidate.exists()
    )
    expected_evaluation = evaluate_pump_station_stewardship_run(
        run_dir=world_session_dir / "world-run",
        package_root=exported.package_dir,
        imported_artifact_sha256=tuple(sorted({artifact.sha256 for artifact in record.outputs.artifacts})),
    )
    assert record.evaluation.stewardship == expected_evaluation
    assert record.evaluation.stewardship.metrics.terminal_liability.active_restriction_count == 1

    operations = [
        json.loads(line)
        for line in (trial_dir / "environment-operations.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    uploads = [event["target"] for event in operations if event["event"] in {"upload_dir", "upload_file"}]
    assert uploads == [
        "/workspace/world-session",
        "/workspace/output.md",
        "/tests",
    ]
    verifier_index = next(
        index for index, event in enumerate(operations) if event.get("command", "").startswith("/tests/test.sh")
    )
    tests_index = next(index for index, event in enumerate(operations) if event.get("target") == "/tests")
    assert tests_index < verifier_index

    local_root = trial_dir / "local-environment"
    inventory = _read_json(local_root / "workspace" / "world-session" / "artifact-inventory.json")
    details = _read_json(trial_dir / "verifier" / "details.json")
    assert inventory["transition_count"] == 12
    assert details["valid"] is True
    assert details["reward_owner"] == "harbor_verifier"
