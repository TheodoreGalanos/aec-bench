# ABOUTME: Runs the ASW-6A-R closeout review through exported local Harbor.
# ABOUTME: Proves reference-controller dispatch, hidden verification, and artifact parity.

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from harbor.models.trial.config import TrialConfig  # type: ignore[import-untyped]
from harbor.trial.trial import Trial  # type: ignore[import-untyped]

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
    PUMP_STATION_REVIEW_HARBOR_BRIDGE_MODE,
    PUMP_STATION_REVIEW_HARBOR_EXECUTION_KIND,
    export_pump_station_harbor_task,
    load_pump_station_harbor_bridge,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_job import (
    build_pump_station_harbor_job_config,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
    PUMP_STATION_REFERENCE_CONTROLLER_ID,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_verifier import (
    verify_pump_station_harbor_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_harbor import (
    PUMP_STATION_REVIEW_HARBOR_RUN_SCHEMA_VERSION,
    run_pump_station_review_reference_session,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_session import (
    PUMP_STATION_REVIEW_TOOL_NAMES,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def test_review_reference_has_exported_harbor_and_independent_verifier_parity(
    tmp_path: Path,
) -> None:
    task_dir = tmp_path / "tasks" / "stewardship" / "pump-station-review"
    exported = export_pump_station_harbor_task(
        task_dir,
        project_root=PROJECT_ROOT,
        maintenance_review=True,
    )
    bridge = load_pump_station_harbor_bridge(task_dir / "environment")

    first = run_pump_station_review_reference_session(
        bridge=bridge,
        output_dir=tmp_path / "first-review",
        session_identity="review-parity",
    )
    second = run_pump_station_review_reference_session(
        bridge=bridge,
        output_dir=tmp_path / "second-review",
        session_identity="review-parity",
    )
    verified = verify_pump_station_harbor_run(
        run_dir=first.output_dir,
        export_manifest_path=exported.manifest_path,
        package_dir=exported.package_dir,
    )

    assert bridge.maintenance_review is True
    assert bridge.execution_kind == PUMP_STATION_REVIEW_HARBOR_EXECUTION_KIND
    assert bridge.bridge_mode == PUMP_STATION_REVIEW_HARBOR_BRIDGE_MODE
    assert bridge.allowed_tools == PUMP_STATION_REVIEW_TOOL_NAMES
    assert first.verification.valid is True
    assert verified["valid"] is True
    assert verified["objective_complete"] is True
    assert first.public_case == second.public_case
    assert first.submission == second.submission
    assert first.verification == second.verification
    inventory = json.loads((first.output_dir / "artifact-inventory.json").read_text(encoding="utf-8"))
    assert inventory["schema_version"] == PUMP_STATION_REVIEW_HARBOR_RUN_SCHEMA_VERSION
    assert inventory["tool_names"] == list(PUMP_STATION_REVIEW_TOOL_NAMES)
    assert inventory["case_id"] == first.public_case.case_id
    assert inventory["review_id"] == first.submission.review_id


def test_local_harbor_trial_dispatches_reference_review_and_awards_reward(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    exported = export_pump_station_harbor_task(
        repo_root / "tasks" / "stewardship" / "pump-station-review",
        project_root=PROJECT_ROOT,
        maintenance_review=True,
    )
    trial_name = "pump-station-closeout-review"
    config = TrialConfig.model_validate(
        {
            "task": {"path": str(exported.task_dir)},
            "trial_name": trial_name,
            "trials_dir": str(repo_root / "jobs" / "review"),
            "job_id": "6d20da1f-e498-48e5-ac53-d79c3fe62f24",
            "agent": {
                "name": "pump-station-reference-reviewer",
                "import_path": "agents.entrypoint_agent:EntrypointAgent",
                "model_name": PUMP_STATION_REFERENCE_CONTROLLER_ID,
                "kwargs": {
                    "adapter": "tool_loop",
                    "execution_kind": (PUMP_STATION_REVIEW_HARBOR_EXECUTION_KIND),
                    "world_session": {
                        "bridge_mode": PUMP_STATION_REVIEW_HARBOR_BRIDGE_MODE,
                    },
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
    assert result.agent_result.metadata["world_session_status"] == "completed"
    assert result.verifier_result is not None
    assert result.verifier_result.rewards == {"reward": 1.0}


def test_review_harbor_job_is_reference_only_before_agent_authority(
    tmp_path: Path,
) -> None:
    exported = export_pump_station_harbor_task(
        tmp_path / "task",
        project_root=PROJECT_ROOT,
        maintenance_review=True,
    )

    reference = build_pump_station_harbor_job_config(
        task_dir=exported.task_dir,
        jobs_dir=tmp_path / "jobs",
    )

    agent = reference["agents"][0]
    assert agent["kwargs"]["execution_kind"] == (PUMP_STATION_REVIEW_HARBOR_EXECUTION_KIND)
    assert agent["kwargs"]["world_session"] == {
        "bridge_mode": PUMP_STATION_REVIEW_HARBOR_BRIDGE_MODE,
    }
    with pytest.raises(
        ValueError,
        match="separately approved direct host runner",
    ):
        build_pump_station_harbor_job_config(
            task_dir=exported.task_dir,
            jobs_dir=tmp_path / "model-jobs",
            model_name="unapproved-review-model",
        )
