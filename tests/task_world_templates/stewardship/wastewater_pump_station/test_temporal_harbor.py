# ABOUTME: Tests provider-free Harbor execution of the temporal documentary-evidence world.
# ABOUTME: Proves export identity, production tools, independent replay, and artifact capture.

from __future__ import annotations

import json
from pathlib import Path

from aec_bench.harness.harbor_importing.artifact_io import artifact_reference
from aec_bench.harness.harbor_importing.stewardship import _temporal_trial_evidence
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
    export_pump_station_harbor_task,
    load_pump_station_harbor_bridge,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
    run_pump_station_evidence_health_reference_session,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_verifier import (
    verify_pump_station_harbor_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TEMPORAL_EVIDENCE_TOOL_NAMES,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def test_provider_free_harbor_replays_temporal_evidence_offline(
    tmp_path: Path,
) -> None:
    task_dir = tmp_path / "task"
    exported = export_pump_station_harbor_task(
        task_dir,
        project_root=PROJECT_ROOT,
        temporal_evidence=True,
    )
    bridge = load_pump_station_harbor_bridge(task_dir / "environment")

    assert bridge.temporal_evidence
    assert bridge.allowed_tools == PUMP_STATION_TEMPORAL_EVIDENCE_TOOL_NAMES

    completed = run_pump_station_evidence_health_reference_session(
        bridge=bridge,
        output_dir=tmp_path / "run",
        session_identity="temporal-harbor",
    )
    verified = verify_pump_station_harbor_run(
        run_dir=completed.output_dir,
        export_manifest_path=exported.manifest_path,
        package_dir=exported.package_dir,
    )

    assert verified["valid"] is True
    assert verified["temporal_evidence"]["valid"] is True
    assert verified["temporal_evidence"]["access_count"] == 2
    assert verified["temporal_evidence"]["reliance_count"] == 1

    inventory = json.loads(
        (completed.output_dir / "artifact-inventory.json").read_text(
            encoding="utf-8"
        )
    )
    references = {
        entry["path"]: artifact_reference(
            kind="world-session-artifact",
            path=completed.output_dir / entry["path"],
            repo_root=tmp_path,
        )
        for entry in inventory["artifacts"]
    }
    execution, provenance = _temporal_trial_evidence(
        inventory=inventory,
        references=references,
    )
    assert execution.access_count == 2
    assert execution.reliance_count == 1
    assert provenance.ledger_artifacts
