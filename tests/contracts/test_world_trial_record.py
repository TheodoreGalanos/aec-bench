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
    TemporalWorldExecutionRecord,
    TemporalWorldTrialProvenance,
    TrialRecord,
    WorldExecutionRecord,
    WorldTemporalEvidenceExecution,
    WorldTemporalEvidenceProvenance,
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


def test_temporal_world_record_strictly_reloads_without_changing_disabled_shape() -> None:
    ordinary = build_trial_record()
    assert "temporal_evidence" not in ordinary.model_dump_json()

    base_artifacts = [
        _artifact("world_session_request", "1"),
        _artifact("world_session_result", "2"),
        _artifact("world_artifact_inventory", "3"),
        _artifact("world_export_manifest", "4"),
        _artifact("world_package_manifest", "5"),
        _artifact("world_verification", "6"),
    ]
    temporal_artifacts = [
        _artifact("temporal_capability", "7"),
        _artifact("temporal_corpus", "8"),
        _artifact("temporal_lineage", "9"),
        _artifact("temporal_availability", "a"),
        _artifact("temporal_retrieval_policy", "b"),
        _artifact("temporal_access_policy", "c"),
        _artifact("temporal_branch_policy", "d"),
        _artifact("temporal_cost_policy", "e"),
        _artifact("temporal_verification", "f"),
        _artifact("temporal_access_ledger", "0"),
    ]
    temporal_execution = WorldTemporalEvidenceExecution(
        profile="deterministic_snapshot",
        capability_id="capability-1",
        corpus_snapshot_id="corpus-1",
        retrieval_policy_id="retrieval-1",
        access_policy_id="access-1",
        availability_schedule_id="availability-1",
        branch_namespace_policy_id="branch-policy-1",
        cost_policy_id="cost-policy-1",
        access_count=2,
        reliance_count=1,
        carrier_count=0,
        verification_report_id="verification-1",
    )
    execution = TemporalWorldExecutionRecord(
        execution_kind="stewardship_world_session",
        session_id="session-temporal",
        task_world_id="wastewater-pump-station-stewardship.v1",
        agent_tenure_id="tenure-temporal",
        adapter="tool_loop",
        resolved_model="deterministic-reference-controller",
        status="completed",
        start_snapshot=_snapshot(0, "a"),
        end_snapshot=_snapshot(4, "b"),
        transition_count=4,
        tool_names=("search_evidence", "fetch_evidence", "continue_operation"),
        temporal_evidence=temporal_execution,
    )
    provenance = TemporalWorldTrialProvenance(
        world_session_request=base_artifacts[0],
        world_session_result=base_artifacts[1],
        artifact_inventory=base_artifacts[2],
        export_manifest=base_artifacts[3],
        package_manifest=base_artifacts[4],
        verification_report=base_artifacts[5],
        temporal_evidence=WorldTemporalEvidenceProvenance(
            capability=temporal_artifacts[0],
            corpus_manifest=temporal_artifacts[1],
            lineage_manifest=temporal_artifacts[2],
            availability_schedule=temporal_artifacts[3],
            retrieval_policy=temporal_artifacts[4],
            access_policy=temporal_artifacts[5],
            branch_policy=temporal_artifacts[6],
            cost_policy=temporal_artifacts[7],
            verification_report=temporal_artifacts[8],
            ledger_artifacts=(temporal_artifacts[9],),
        ),
    )
    record = build_trial_record(
        completeness=Completeness.PARTIAL,
        agent=AgentReference(
            adapter="tool_loop",
            model="deterministic-reference-controller",
            adapter_revision="test",
        ),
        outputs=OutputRecord(artifacts=[*base_artifacts, *temporal_artifacts]),
        world_execution=execution,
        world_provenance=provenance,
    )

    reloaded = TrialRecord.model_validate_json(record.model_dump_json())

    assert isinstance(reloaded.world_execution, TemporalWorldExecutionRecord)
    assert reloaded.world_execution.temporal_evidence == temporal_execution
    assert isinstance(reloaded.world_provenance, TemporalWorldTrialProvenance)
