# ABOUTME: Proves registered pump worlds use the canonical Harbor export, episode host, and verifier.
# ABOUTME: Covers exact profile authority, durable episode evidence, and the integration entrypoint.

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path

import pytest
from harbor.models.trial.config import TrialConfig  # type: ignore[import-untyped]
from harbor.trial.trial import Trial  # type: ignore[import-untyped]

from aec_bench.harness.pump_station_harbor.export import (
    PUMP_STATION_HARBOR_BRIDGE_MODE,
    PUMP_STATION_HARBOR_EXECUTION_KIND,
    export_pump_station_harbor_task,
    load_pump_station_harbor_bridge,
)
from aec_bench.harness.pump_station_harbor.job import (
    build_pump_station_harbor_job_config,
)
from aec_bench.harness.pump_station_harbor.session import (
    run_pump_station_reference_session,
)
from aec_bench.harness.pump_station_harbor.verifier import (
    verify_pump_station_harbor_run,
)
from aec_bench.worlds.catalogue import default_interactive_world_catalogue
from aec_bench.worlds.stewardship.wastewater_pump_station.actor_interface import (
    PUMP_STATION_ACTOR_ACTION_NAMES,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.continual_definition import (
    pump_station_continual_world_definition,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PUMP_STATION_TASK_WORLD_ID,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_controller import (
    PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_registered_profile_export_uses_the_canonical_harbor_bridge(
    tmp_path: Path,
) -> None:
    definition = pump_station_continual_world_definition()
    profile_ref = definition.profiles[0]
    exported = export_pump_station_harbor_task(
        tmp_path / "task",
        project_root=PROJECT_ROOT,
        profile_ref=profile_ref,
    )

    bridge = load_pump_station_harbor_bridge(exported.task_dir / "environment")
    manifest = json.loads(exported.manifest_path.read_text(encoding="utf-8"))
    config = build_pump_station_harbor_job_config(
        task_dir=exported.task_dir,
        jobs_dir=tmp_path / "jobs",
        model_name="bedrock:authorised-registered-model",
        max_turns=4,
    )

    assert "schema_version" not in manifest
    assert manifest["world_build"] == asdict(definition.build)
    assert manifest["continual_profile"] == asdict(profile_ref)
    assert bridge.profile_ref == profile_ref
    assert bridge.reference_system_root == exported.task_dir / "tests" / "reference-system"
    assert bridge.allowed_tools == PUMP_STATION_ACTOR_ACTION_NAMES
    assert config["agents"][0]["name"] == "pump-station-model-controller"
    assert config["agents"][0]["kwargs"]["world_session"] == {
        "bridge_mode": PUMP_STATION_HARBOR_BRIDGE_MODE,
        "controller": "model",
    }


def test_registered_reference_session_uses_standard_evidence_and_replays_offline(
    tmp_path: Path,
) -> None:
    profile_ref = pump_station_continual_world_definition().profiles[0]
    exported = export_pump_station_harbor_task(
        tmp_path / "task",
        project_root=PROJECT_ROOT,
        profile_ref=profile_ref,
    )
    bridge = load_pump_station_harbor_bridge(exported.task_dir / "environment")
    output_dir = tmp_path / "world-session"

    completed = run_pump_station_reference_session(
        bridge=bridge,
        output_dir=output_dir,
        session_identity="registered-reference",
    )
    verified = verify_pump_station_harbor_run(
        run_dir=output_dir,
        export_manifest_path=bridge.export_manifest_path,
        package_dir=bridge.package_root,
        reference_system_dir=bridge.reference_system_root,
        verifier_runtime_path=bridge.verifier_runtime_path,
    )

    assert completed.request.session_id == "episode.registered-reference"
    assert completed.request.agent_tenure_id == "actor.registered-reference"
    assert completed.request.start_snapshot is not None
    assert completed.request.start_snapshot.sequence == 0
    assert completed.result.snapshot.sequence == 25
    assert completed.verification.valid
    assert verified["valid"] is True
    assert verified["transition_count"] == 25
    assert (output_dir / "world-run" / "temporal-evidence" / "capability.json").is_file()
    assert not (output_dir / "temporal-evidence").exists()
    assert not (output_dir / "evaluation.json").exists()
    assert not (output_dir / "semantic-outcome.json").exists()

    report_path = output_dir / "verification-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["valid"] = False
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact inventory differs"):
        verify_pump_station_harbor_run(
            run_dir=output_dir,
            export_manifest_path=bridge.export_manifest_path,
            package_dir=bridge.package_root,
            reference_system_dir=bridge.reference_system_root,
            verifier_runtime_path=bridge.verifier_runtime_path,
        )


def test_registered_profile_runs_through_the_real_local_harbor_entrypoint(
    tmp_path: Path,
) -> None:
    catalogue = default_interactive_world_catalogue()
    definition = catalogue.get(PUMP_STATION_TASK_WORLD_ID)
    assert definition is pump_station_continual_world_definition()
    profile_ref = definition.profiles[0]
    exported = export_pump_station_harbor_task(
        tmp_path / "task",
        project_root=PROJECT_ROOT,
        profile_ref=profile_ref,
    )
    trial_name = "registered-pump-world"
    config = TrialConfig.model_validate(
        {
            "task": {"path": str(exported.task_dir)},
            "trial_name": trial_name,
            "trials_dir": str(tmp_path / "trials"),
            "job_id": "3fa79cba-6a9c-4f65-972e-e2bf245f2e9b",
            "agent": {
                "name": "pump-station-reference-controller",
                "import_path": "agents.entrypoint_agent:EntrypointAgent",
                "model_name": PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
                "kwargs": {
                    "adapter": "tool_loop",
                    "execution_kind": PUMP_STATION_HARBOR_EXECUTION_KIND,
                    "world_session": {"bridge_mode": PUMP_STATION_HARBOR_BRIDGE_MODE},
                },
            },
            "environment": {
                "import_path": "tests.support.harbor_local_environment:LocalFilesystemHarborEnvironment",
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
    assert result.agent_result.metadata["world_session_status"] == "completed"
    assert result.agent_result.metadata["world_session_id"] == "episode.registered-pump-world"
    assert result.verifier_result is not None
    assert result.verifier_result.rewards == {"reward": 1.0}
