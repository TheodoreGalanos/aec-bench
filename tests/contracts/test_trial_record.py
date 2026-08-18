# ABOUTME: Tests the current run manifest, explicit trial statuses, and publication policy.
# ABOUTME: Confirms that authority evidence and typed extensions stay as exact artifact references.

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.authority_evidence import (
    ACTOR_INVOCATION_EVIDENCE_PROTOCOL,
    AuthorityEvidenceKind,
    AuthorityEvidenceRef,
)
from aec_bench.contracts.dataset import RepositoryDatasetRef
from aec_bench.contracts.trial_record import (
    AgentConfiguration,
    AuthorityExpectation,
    EvaluationStatus,
    EvidenceStatus,
    ExecutionEnvironmentRef,
    ExecutionStatus,
    GitSourceRef,
    ProviderRoute,
    PublicationPolicy,
    QualificationRequirement,
    RunManifest,
    SnapshotSourceRef,
    TimingRecord,
    TrialArtifactRef,
    TrialExtensionRef,
    TrialInput,
    TrialOutput,
    TrialRecord,
    UnresolvedSourceRef,
    derive_publication_eligibility,
)
from tests.support.trial_record_factories import make_trial_record


def _artifact(digit: str = "a") -> ArtifactRef:
    digest = digit * 64
    return ArtifactRef(
        artifact_id=f"artifacts/sha256/{digest[:2]}/{digest}",
        sha256=digest,
        size_bytes=12,
        media_type="application/json",
    )


def _manifest(**overrides: object) -> RunManifest:
    payload: dict[str, object] = {
        "run_id": "run-001",
        "experiment_id": "experiment-001",
        "dataset": RepositoryDatasetRef(
            dataset_id="dataset-001",
            source_revision="b" * 40,
            manifest_path="datasets/dataset-001.json",
        ),
        "source": GitSourceRef(revision="b" * 40),
        "agent": AgentConfiguration(adapter="tool_loop", model="model-001"),
        "execution_environment": ExecutionEnvironmentRef(runtime_image="image:1", compute_backend="local"),
        "provider_route": ProviderRoute(provider="test", route="test"),
    }
    payload.update(overrides)
    return RunManifest.model_validate(payload)


def test_trial_record_persists_three_independent_statuses_without_completeness() -> None:
    record = make_trial_record(
        execution_status=ExecutionStatus.COMPLETED,
        evaluation_status=EvaluationStatus.FAILED,
        evaluation=None,
        evidence_status=EvidenceStatus.INCOMPLETE,
    )

    payload = record.model_dump(mode="json")

    assert payload["execution_status"] == "completed"
    assert payload["evaluation_status"] == "failed"
    assert payload["evidence_status"] == "incomplete"
    assert "completeness" not in payload


def test_optional_forensic_artifacts_do_not_change_execution_status() -> None:
    record = make_trial_record(extension_refs=())

    assert record.execution_status is ExecutionStatus.COMPLETED
    assert record.evidence_status is EvidenceStatus.NOT_REQUIRED


def test_completed_execution_requires_output_and_completed_at() -> None:
    with pytest.raises(ValidationError, match="completed execution requires an output"):
        make_trial_record(output=None)

    with pytest.raises(ValidationError, match="terminal execution status and completed_at"):
        make_trial_record(completed_at=None)


def test_evaluation_failure_does_not_rewrite_execution_history() -> None:
    record = make_trial_record(
        execution_status=ExecutionStatus.COMPLETED,
        evaluation_status=EvaluationStatus.FAILED,
        evaluation=None,
    )

    assert record.execution_status is ExecutionStatus.COMPLETED
    assert record.evaluation_status is EvaluationStatus.FAILED


def test_trial_payload_references_shared_run_identity_once() -> None:
    record = make_trial_record(experiment_id="experiment-shared", run_id="run-shared")

    payload = record.model_dump(mode="json")

    assert payload["run_id"] == "run-shared"
    assert "experiment_id" not in payload
    assert "agent" not in payload
    assert "execution_environment" not in payload
    assert record.run_manifest.experiment_id == "experiment-shared"


def test_verified_world_evidence_requires_every_expected_authority() -> None:
    actor = AuthorityEvidenceRef(
        authority_kind=AuthorityEvidenceKind.ACTOR_INVOCATION,
        protocol=ACTOR_INVOCATION_EVIDENCE_PROTOCOL,
        artifact=_artifact(),
    )
    manifest = _manifest(
        expected_authorities=(
            AuthorityExpectation(
                authority_kind=AuthorityEvidenceKind.ACTOR_INVOCATION,
                protocol=ACTOR_INVOCATION_EVIDENCE_PROTOCOL,
            ),
            AuthorityExpectation(
                authority_kind=AuthorityEvidenceKind.WORLD,
                protocol="aec-bench/world-evidence/1",
            ),
        )
    )
    record = make_trial_record(
        run_id=manifest.run_id,
        input=TrialInput(instruction="Act.", task_revision="task", task_kind="world"),
        evidence_status=EvidenceStatus.VERIFIED,
        authority_evidence=(actor,),
    )

    with pytest.raises(ValueError, match="missing required authority references"):
        record.bind_run_manifest(manifest)


def test_required_evidence_cannot_be_declared_not_required() -> None:
    manifest = _manifest(
        expected_authorities=(
            AuthorityExpectation(
                authority_kind=AuthorityEvidenceKind.PROVIDER,
                protocol="provider-evidence/1",
            ),
        )
    )
    record = make_trial_record(run_id=manifest.run_id, evidence_status=EvidenceStatus.NOT_REQUIRED)

    with pytest.raises(ValueError, match="cannot be not_required"):
        record.bind_run_manifest(manifest)

    result = derive_publication_eligibility(record, manifest, PublicationPolicy(policy_id="published"))
    assert "evidence_not_verified" in result.reasons


def test_world_actor_and_world_causal_evidence_are_distinct_references() -> None:
    actor = AuthorityEvidenceRef(
        authority_kind=AuthorityEvidenceKind.ACTOR_INVOCATION,
        protocol=ACTOR_INVOCATION_EVIDENCE_PROTOCOL,
        artifact=_artifact("a"),
    )
    world = AuthorityEvidenceRef(
        authority_kind=AuthorityEvidenceKind.WORLD,
        protocol="aec-bench/world-evidence/1",
        artifact=_artifact("b"),
    )
    manifest = _manifest(
        expected_authorities=(
            AuthorityExpectation(authority_kind=actor.authority_kind, protocol=actor.protocol),
            AuthorityExpectation(authority_kind=world.authority_kind, protocol=world.protocol),
        )
    )
    record = make_trial_record(
        run_id=manifest.run_id,
        input=TrialInput(instruction="Act.", task_revision="task", task_kind="world"),
        evidence_status=EvidenceStatus.VERIFIED,
        authority_evidence=(actor, world),
    ).bind_run_manifest(manifest)

    assert record.authority_evidence == (actor, world)
    assert record.episode_artifact == world.artifact


def test_authority_evidence_cannot_be_duplicated_as_output_artifact() -> None:
    actor = AuthorityEvidenceRef(
        authority_kind=AuthorityEvidenceKind.ACTOR_INVOCATION,
        protocol=ACTOR_INVOCATION_EVIDENCE_PROTOCOL,
        artifact=_artifact(),
    )

    with pytest.raises(ValidationError, match="authority evidence must be referenced only"):
        make_trial_record(
            authority_evidence=(actor,),
            output=TrialOutput(artifacts=({"role": "actor-log", "artifact": actor.artifact},)),
        )


def test_provider_evidence_cannot_use_authority_reference_collection() -> None:
    provider = AuthorityEvidenceRef(
        authority_kind=AuthorityEvidenceKind.PROVIDER,
        protocol="provider-evidence/1",
        artifact=_artifact(),
    )

    with pytest.raises(ValidationError, match="provider evidence must use provider_evidence"):
        make_trial_record(authority_evidence=(provider,))


def test_typed_extension_cannot_copy_a_raw_digest() -> None:
    extension = TrialExtensionRef(extension_kind="lifecycle", artifact=_artifact())

    assert extension.model_dump(mode="json") == {
        "extension_kind": "lifecycle",
        "artifact": _artifact().model_dump(mode="json"),
    }
    with pytest.raises(ValidationError):
        TrialExtensionRef.model_validate({**extension.model_dump(mode="json"), "sha256": "c" * 64})


@pytest.mark.parametrize("logical_path", ("/host/output.json", "../output.json", r"folder\output.json"))
def test_output_artifact_logical_path_must_be_portable(logical_path: str) -> None:
    with pytest.raises(ValidationError, match="logical_path"):
        TrialArtifactRef(role="output", artifact=_artifact(), logical_path=logical_path)


def test_dirty_source_is_not_publishable_without_reconstructive_bytes() -> None:
    record = make_trial_record()
    unresolved = _manifest(source=UnresolvedSourceRef(reason="working tree is dirty"))
    snapshot = _manifest(source=SnapshotSourceRef(artifact=_artifact()))
    policy = PublicationPolicy(policy_id="published-results")

    unresolved_result = derive_publication_eligibility(record, unresolved, policy)
    snapshot_result = derive_publication_eligibility(record, snapshot, policy)

    assert "source_not_reconstructive" in unresolved_result.reasons
    assert snapshot_result.eligible


def test_publishable_world_requires_quiescent_actor_close_reference() -> None:
    record = make_trial_record(input=TrialInput(instruction="Act.", task_revision="task", task_kind="world"))

    result = derive_publication_eligibility(record, _manifest(), PublicationPolicy(policy_id="world"))

    assert "actor_authority_not_closed" in result.reasons


def test_qualification_run_requires_provider_evidence_policy() -> None:
    qualification = QualificationRequirement(
        matrix_id="matrix-001",
        provider_route="deepseek-official",
        feature="live_world_episode",
        evidence_level="live",
    )

    with pytest.raises(ValidationError, match="qualification runs require provider evidence"):
        _manifest(
            provider_route=ProviderRoute(provider="deepseek", route="deepseek-official"),
            qualification=qualification,
        )

    manifest = _manifest(
        provider_route=ProviderRoute(provider="deepseek", route="deepseek-official"),
        expected_authorities=(
            AuthorityExpectation(
                authority_kind=AuthorityEvidenceKind.PROVIDER,
                protocol="aec-bench/deepseek-evidence/2",
            ),
        ),
        qualification=qualification,
    )
    record = make_trial_record(evidence_status=EvidenceStatus.INCOMPLETE)

    result = derive_publication_eligibility(record, manifest, PublicationPolicy(policy_id="qualification"))

    assert "qualification_evidence_level_not_verified" in result.reasons


def test_provider_request_ids_are_not_trial_identity_fields() -> None:
    assert "provider_request_id" not in TrialRecord.model_fields
    assert "tool_call_id" not in TrialRecord.model_fields
    assert "provider_request_id" not in RunManifest.model_fields


def test_timing_must_match_trial_timestamps() -> None:
    started = datetime(2026, 8, 18, tzinfo=UTC)

    with pytest.raises(ValidationError, match="timing.total_seconds"):
        TrialRecord(
            trial_id="trial",
            run_id="run",
            task_id="task",
            execution_status=ExecutionStatus.COMPLETED,
            evaluation_status=EvaluationStatus.NOT_REQUESTED,
            evidence_status=EvidenceStatus.NOT_REQUIRED,
            started_at=started,
            completed_at=started + timedelta(seconds=2),
            input=TrialInput(instruction="Do work.", task_revision="revision"),
            output=TrialOutput(),
            timing=TimingRecord(total_seconds=1),
        )
