# ABOUTME: Tests the additive stewardship execution and provenance fields on TrialRecord.
# ABOUTME: Preserves historical records while requiring paired, artifact-bound world evidence.

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aec_bench.contracts.trial_record import (
    AgentReference,
    ArtifactReference,
    Completeness,
    OutputRecord,
    WorldExecutionRecord,
    WorldTrialProvenance,
)
from aec_bench.contracts.world_session import StewardshipStateSnapshotRef
from tests.contracts.test_trial_record import build_trial_record


def _artifact(kind: str, digit: str) -> ArtifactReference:
    return ArtifactReference(
        kind=kind,
        path=f"jobs/trial-1/{kind}.json",
        sha256=digit * 64,
        media_type="application/json",
    )


def _snapshot(sequence: int, digit: str) -> StewardshipStateSnapshotRef:
    return StewardshipStateSnapshotRef(
        run_id="run-1",
        episode_id="episode-1",
        world_branch_id="branch-1",
        sequence=sequence,
        state_id=digit * 64,
        commit_id=digit * 64,
    )


def test_historical_trial_record_remains_valid_without_world_fields() -> None:
    record = build_trial_record()

    assert record.world_execution is None
    assert record.world_provenance is None


def test_world_execution_and_provenance_are_paired_and_artifact_bound() -> None:
    request = _artifact("world_session_request", "1")
    result = _artifact("world_session_result", "2")
    inventory = _artifact("world_artifact_inventory", "3")
    export = _artifact("world_export_manifest", "4")
    package = _artifact("world_package_manifest", "5")
    verification = _artifact("world_verification", "6")
    artifacts = [request, result, inventory, export, package, verification]
    execution = WorldExecutionRecord(
        execution_kind="stewardship_world_session",
        session_id="session-1",
        task_world_id="wastewater-pump-station-stewardship.v1",
        agent_tenure_id="tenure-1",
        adapter="tool_loop",
        resolved_model="deterministic-reference-controller",
        status="completed",
        start_snapshot=_snapshot(0, "a"),
        end_snapshot=_snapshot(12, "b"),
        transition_count=12,
        tool_names=("observe_pump_station", "continue_operation"),
    )
    provenance = WorldTrialProvenance(
        world_session_request=request,
        world_session_result=result,
        artifact_inventory=inventory,
        export_manifest=export,
        package_manifest=package,
        verification_report=verification,
    )

    with pytest.raises(ValidationError, match="world execution and provenance"):
        build_trial_record(
            completeness=Completeness.PARTIAL,
            world_execution=execution,
        )

    record = build_trial_record(
        completeness=Completeness.PARTIAL,
        agent=AgentReference(
            adapter="tool_loop",
            model="deterministic-reference-controller",
            adapter_revision="test",
        ),
        outputs=OutputRecord(artifacts=artifacts),
        world_execution=execution,
        world_provenance=provenance,
    )

    assert record.world_execution == execution
    assert record.world_provenance == provenance

    with pytest.raises(ValidationError, match="world provenance must be included"):
        build_trial_record(
            completeness=Completeness.PARTIAL,
            agent=AgentReference(
                adapter="tool_loop",
                model="deterministic-reference-controller",
                adapter_revision="test",
            ),
            outputs=OutputRecord(artifacts=artifacts[:-1]),
            world_execution=execution,
            world_provenance=provenance,
        )
