# ABOUTME: Proves ASW-8 export, Harbor evidence, independent verification, and semantic parity.
# ABOUTME: Rejects altered stored results instead of trusting a recorded pass claim.

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from harbor.models.trial.config import TrialConfig  # type: ignore[import-untyped]
from harbor.trial.trial import Trial  # type: ignore[import-untyped]

from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.harness.harbor_importing.core import import_harbor_trial
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_execution import (
    PUMP_STATION_ASW_8_REFERENCE_CONTROLLER_ID,
    execute_asw_8_reference_controller,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_harbor import (
    PUMP_STATION_ASW_8_HARBOR_BRIDGE_MODE,
    PUMP_STATION_ASW_8_HARBOR_EXECUTION_KIND,
    export_asw_8_harbor_task,
    load_asw_8_harbor_bridge,
    run_asw_8_harbor_reference_session,
    verify_asw_8_harbor_session,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_job import (
    build_pump_station_harbor_job_config,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def test_harbor_v2_job_selects_the_bounded_model_route(tmp_path: Path) -> None:
    exported = export_asw_8_harbor_task(
        tmp_path / "task",
        project_root=PROJECT_ROOT,
    )

    config = build_pump_station_harbor_job_config(
        task_dir=exported.task_dir,
        jobs_dir=tmp_path / "jobs",
        backend="docker",
        model_name="bedrock:authorised-asw-8-model",
        max_turns=4,
    )

    agent = config["agents"][0]
    assert agent["name"] == "pump-station-model-controller"
    assert agent["kwargs"]["max_turns"] == 4
    assert agent["kwargs"]["world_session"] == {
        "bridge_mode": PUMP_STATION_ASW_8_HARBOR_BRIDGE_MODE,
        "controller": "model",
    }


def test_harbor_v2_recomputes_evidence_and_matches_direct_semantics(
    tmp_path: Path,
) -> None:
    exported = export_asw_8_harbor_task(
        tmp_path / "task",
        project_root=PROJECT_ROOT,
    )
    bridge = load_asw_8_harbor_bridge(exported.task_dir / "environment")
    run_dir = tmp_path / "session"
    harbor_result = run_asw_8_harbor_reference_session(
        bridge=bridge,
        output_dir=run_dir,
        session_identity="harbor-parity",
    )
    assert (run_dir / "world-run" / "temporal-evidence" / "capability.json").is_file()
    report, evaluation, outcome = verify_asw_8_harbor_session(
        run_dir=run_dir,
        export_manifest=exported.manifest_path,
        package_dir=exported.package_dir,
        reference_system_dir=exported.reference_system_dir,
    )
    direct = execute_asw_8_reference_controller(
        run_id="direct-parity",
        world_branch_id="branch-direct-parity",
    )

    assert report.valid is True
    assert evaluation.valid is True
    assert evaluation.reward == 1.0
    assert outcome == direct.semantic_outcome
    assert harbor_result.semantic_outcome == direct.semantic_outcome

    evaluation_path = run_dir / "evaluation.json"
    stored = json.loads(evaluation_path.read_text(encoding="utf-8"))
    stored["reward"] = 0.0
    evaluation_path.write_text(
        json.dumps(stored, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="stored evaluation.json differs"):
        verify_asw_8_harbor_session(
            run_dir=run_dir,
            export_manifest=exported.manifest_path,
            package_dir=exported.package_dir,
            reference_system_dir=exported.reference_system_dir,
        )


def test_local_harbor_v2_imports_a_strict_trial_record(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    exported = export_asw_8_harbor_task(
        repo_root / "tasks" / "stewardship" / "wastewater-pump-station-asw-8",
        project_root=PROJECT_ROOT,
    )
    trial_name = "asw-8-local-runtime"
    config = TrialConfig.model_validate(
        {
            "task": {"path": str(exported.task_dir)},
            "trial_name": trial_name,
            "trials_dir": str(repo_root / "jobs" / "local-runtime"),
            "job_id": "3fa79cba-6a9c-4f65-972e-e2bf245f2e9b",
            "agent": {
                "name": "pump-station-asw-8-reference-controller",
                "import_path": "agents.entrypoint_agent:EntrypointAgent",
                "model_name": PUMP_STATION_ASW_8_REFERENCE_CONTROLLER_ID,
                "kwargs": {
                    "adapter": "tool_loop",
                    "execution_kind": PUMP_STATION_ASW_8_HARBOR_EXECUTION_KIND,
                    "world_session": {
                        "bridge_mode": PUMP_STATION_ASW_8_HARBOR_BRIDGE_MODE,
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
    assert result.verifier_result is not None
    assert result.verifier_result.rewards == {"reward": 1.0}
    record = import_harbor_trial(
        trial_dir=config.trials_dir / trial_name,
        repo_root=repo_root,
    )
    assert TrialRecord.model_validate_json(record.model_dump_json()) == record
    assert record.world_execution is not None
    assert record.world_execution.transition_count > 0
    assert record.world_provenance is not None
    assert record.evaluation.stewardship is not None
    assert record.evaluation.stewardship.schema_version == "stewardship-evaluation.v2"
    assert record.evaluation.stewardship.valid is True
