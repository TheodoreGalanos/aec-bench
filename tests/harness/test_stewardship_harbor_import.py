# ABOUTME: Tests allowlisted Harbor import selection for stewardship world sessions.
# ABOUTME: Verifies exact world evidence survives Harbor import and TrialRecord reload.

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from aec_bench.contracts.authority_evidence import AuthorityEvidenceKind
from aec_bench.harness.harbor_importing.contracts import HarborImportError
from aec_bench.harness.harbor_importing.core import import_harbor_trial
from aec_bench.harness.pump_station_harbor.export import (
    PUMP_STATION_HARBOR_BRIDGE_MODE,
    export_pump_station_harbor_task,
    load_pump_station_harbor_bridge,
)
from aec_bench.harness.pump_station_harbor.importing import load_pump_station_import_evidence
from aec_bench.harness.pump_station_harbor.session import (
    CompletedPumpStationReferenceSession,
    run_pump_station_reference_session,
)
from aec_bench.ledger.reader import read_trial_record
from aec_bench.ledger.writer import write_trial_record
from aec_bench.worlds.stewardship.wastewater_pump_station.continual_definition import (
    pump_station_continual_world_definition,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_controller import (
    PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _write_harbor_trial(
    *,
    repo_root: Path,
    source_run_dir: Path,
    completed: CompletedPumpStationReferenceSession,
    model_name: str,
) -> Path:
    trial_dir = repo_root / "jobs" / "job-world" / "trial-world"
    run_dir = trial_dir / "artifacts" / "agent" / "world-session"
    run_dir.parent.mkdir(parents=True)
    shutil.copytree(source_run_dir, run_dir)
    (trial_dir / "artifacts" / "agent" / "output.md").write_text(
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
                "trial_name": "trial-world",
                "task_checksum": "pump-station-export",
                "config": {
                    "task": {"path": "tasks/stewardship/wastewater-pump-station"},
                    "agent": {
                        "name": "pump-station-reference-controller",
                        "model_name": model_name,
                        "import_path": "agents.entrypoint_agent:EntrypointAgent",
                        "kwargs": {
                            "adapter": "tool_loop",
                            "execution_kind": "stewardship_world_session",
                            "world_session": {"bridge_mode": PUMP_STATION_HARBOR_BRIDGE_MODE},
                        },
                    },
                    "environment": {"type": "docker", "kwargs": {}},
                    "job_id": "job-world",
                },
                "agent_info": {
                    "name": "entrypoint",
                    "version": "1.0.0",
                },
                "agent_result": {
                    "metadata": {
                        "adapter_name": "tool_loop",
                        "execution_kind": "stewardship_world_session",
                        "model": model_name,
                        "reward_owner": "harbor_verifier",
                        "world_session_status": "completed",
                    }
                },
                "started_at": "2026-07-29T00:00:00Z",
                "finished_at": "2026-07-29T00:00:01Z",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return trial_dir


def test_verified_world_session_imports_and_reloads_exact_trial_record(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    task_dir = repo_root / "tasks" / "stewardship" / "wastewater-pump-station"
    exported = export_pump_station_harbor_task(
        task_dir,
        project_root=PROJECT_ROOT,
        profile_ref=pump_station_continual_world_definition().profiles[0],
    )
    bridge = load_pump_station_harbor_bridge(task_dir / "environment")
    source_run_dir = tmp_path / "source-world-session"
    completed = run_pump_station_reference_session(
        bridge=bridge,
        output_dir=source_run_dir,
        session_identity="trial-world-session",
    )
    trial_dir = _write_harbor_trial(
        repo_root=repo_root,
        source_run_dir=source_run_dir,
        completed=completed,
        model_name=PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
    )

    record = import_harbor_trial(
        trial_dir=trial_dir,
        repo_root=repo_root,
        evidence_loader=load_pump_station_import_evidence,
    )
    record_path = write_trial_record(ledger_root=repo_root / "ledger", record=record)
    reloaded = read_trial_record(record_path)

    assert reloaded.trial_id == record.trial_id
    assert reloaded.agent.adapter == "tool_loop"
    assert reloaded.episode_artifact is not None
    world_evidence = next(
        item for item in reloaded.authority_evidence if item.authority_kind is AuthorityEvidenceKind.WORLD
    )
    assert reloaded.episode_artifact == world_evidence.artifact
    assert all(item.artifact != reloaded.episode_artifact for item in reloaded.outputs.artifacts)
    assert "world_session" not in reloaded.agent.configuration
    assert "world_session_evidence" not in reloaded.agent.configuration
    assert reloaded.agent.configuration["execution_kind"] == "stewardship_world_session"
    assert exported.manifest_path.exists()


def test_registered_world_session_imports_through_the_current_run(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    task_dir = repo_root / "tasks" / "stewardship" / "wastewater-pump-station"
    profile_ref = pump_station_continual_world_definition().profiles[0]
    exported = export_pump_station_harbor_task(
        task_dir,
        project_root=PROJECT_ROOT,
        profile_ref=profile_ref,
    )
    bridge = load_pump_station_harbor_bridge(task_dir / "environment")
    source_run_dir = tmp_path / "registered-world-session"
    completed = run_pump_station_reference_session(
        bridge=bridge,
        output_dir=source_run_dir,
        session_identity="registered-trial-world-session",
    )
    trial_dir = _write_harbor_trial(
        repo_root=repo_root,
        source_run_dir=source_run_dir,
        completed=completed,
        model_name=PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
    )

    record = import_harbor_trial(
        trial_dir=trial_dir,
        repo_root=repo_root,
        evidence_loader=load_pump_station_import_evidence,
    )
    record_path = write_trial_record(ledger_root=repo_root / "ledger", record=record)
    reloaded = read_trial_record(record_path)

    assert reloaded.trial_id == record.trial_id
    assert reloaded.episode_artifact is not None
    assert all(item.artifact != reloaded.episode_artifact for item in reloaded.outputs.artifacts)
    assert reloaded.evaluation.stewardship is not None
    assert reloaded.evaluation.stewardship.valid
    assert exported.manifest_path.exists()


def test_stewardship_import_rejects_changed_world_artifact(
    tmp_path: Path,
) -> None:
    test_verified_world_session_imports_and_reloads_exact_trial_record(tmp_path)
    repo_root = tmp_path / "repo"
    trial_dir = repo_root / "jobs" / "job-world" / "trial-world"
    result_path = trial_dir / "artifacts" / "agent" / "world-session" / "world-session-result.json"
    result_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(
        HarborImportError,
        match="world-session verification failed",
    ):
        import_harbor_trial(
            trial_dir=trial_dir,
            repo_root=repo_root,
            evidence_loader=load_pump_station_import_evidence,
        )
