# ABOUTME: Tests for the TrialRecord provenance contract in the aec-bench contracts package.
# ABOUTME: These tests define completeness rules and nested provenance requirements.

from typing import Literal

import pytest
from pydantic import ValidationError

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.evaluation_plane import EvaluationPlanRef
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trial_record import (
    AdaptationProvenance,
    AgentReference,
    ArtifactReference,
    Completeness,
    CostRecord,
    DerivationStepRecord,
    EnvironmentSnapshot,
    FileReference,
    InputRecord,
    LifecycleExecutionRecord,
    LifecycleSessionRecord,
    LifecycleTrialProvenance,
    MetaHarnessTrialProvenance,
    OutputRecord,
    ProposalSessionTrialProvenance,
    TaskReference,
    TimingRecord,
    TrialRecord,
)

_PUBLIC_LIFECYCLE_PROVENANCE_FIELDS = (
    "invocation_index",
    "ablation_manifest",
    "ablation_plan",
)


def build_trial_record(**overrides: object) -> TrialRecord:
    payload = {
        "trial_id": "trial-001",
        "experiment_id": "experiment-001",
        "timestamp": "2026-03-13T10:00:00Z",
        "task": TaskReference(
            task_id="electrical/voltage-drop/au-office-fitout",
            task_revision="git-sha-task",
        ),
        "agent": AgentReference(
            adapter="tool_loop",
            model="anthropic:claude-sonnet-4-20250514",
            adapter_revision="git-sha-adapter",
            configuration={"max_turns": 20},
        ),
        "environment": EnvironmentSnapshot(
            runtime_image="ghcr.io/example/task-image:latest",
            compute_backend="modal",
            tool_versions={"codes_search": "abc123"},
        ),
        "inputs": InputRecord(
            instruction="Review the task and write output.",
            system_prompt="Use tools carefully.",
            input_files=[
                FileReference(
                    path="/workspace/input/drawing.json",
                    hash="hash-123",
                    source="r2://bucket/drawing.json",
                )
            ],
        ),
        "outputs": OutputRecord(
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path="/workspace/output.jsonl",
                output_format="jsonl",
            ),
            raw_output_path="/workspace/output.jsonl",
            conversation_path="/workspace/conversation.jsonl",
            agent_result={"completion_status": "completed"},
        ),
        "evaluation": EvaluationResult(
            reward=1.0,
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=True,
                verifier_completed=True,
            ),
        ),
        "timing": TimingRecord(total_seconds=12.0, agent_seconds=8.0),
        "completeness": Completeness.COMPLETE,
    }
    payload.update(overrides)
    return TrialRecord.model_validate(payload)


def build_lifecycle_artifacts() -> dict[str, ArtifactReference]:
    return {
        "invocation_manifest": ArtifactReference(
            kind="lifecycle_manifest",
            path="_artifacts/trial-001/invocation-manifest.json",
            sha256="0" * 64,
            media_type="application/json",
        ),
        "invocation_index": ArtifactReference(
            kind="lifecycle_invocation_index",
            path="_artifacts/trial-001/invocation-index.jsonl",
            sha256="1" * 64,
            media_type="application/x-ndjson",
        ),
        "ablation_manifest": ArtifactReference(
            kind="lifecycle_ablation_manifest",
            path="_artifacts/trial-001/sweep/manifest.json",
            sha256="2" * 64,
            media_type="application/json",
        ),
        "ablation_plan": ArtifactReference(
            kind="lifecycle_ablation_plan",
            path="_artifacts/trial-001/sweep/plan.json",
            sha256="3" * 64,
            media_type="application/json",
        ),
    }


def build_complete_lifecycle_record(
    *,
    visibility: Visibility,
    provenance_fields: tuple[str, ...],
    output_artifact_fields: tuple[str, ...] | None = None,
) -> TrialRecord:
    artifacts = build_lifecycle_artifacts()
    if output_artifact_fields is None:
        output_artifact_fields = ("invocation_manifest", *provenance_fields)
    lifecycle_provenance: dict[str, object] = {
        "lifecycle_id": "stormwater.drainage-model-evidence-lifecycle",
        "spec_sha256": "8" * 64,
        "package_sha256": "9" * 64,
        "repository_commit": "a" * 40,
        "repository_dirty": False,
        "repository_dirty_digest": "b" * 64,
        "runtime_provider": "anthropic",
        "runtime_distributions": ("anthropic==1.0.0", "pydantic-ai-slim==1.0.0"),
        "runtime_dependency_sha256": "c" * 64,
        "verifier_qualified_name": "aec_bench.verify_stormwater",
        "verifier_source_sha256": "d" * 64,
        "invocation_manifest": artifacts["invocation_manifest"],
    }
    lifecycle_provenance.update({field: artifacts[field] for field in provenance_fields})

    return build_trial_record(
        task=TaskReference(
            task_id="drainage/stormwater/lifecycle",
            task_revision="git-sha-task",
            visibility=visibility,
        ),
        outputs=OutputRecord(
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path="_artifacts/trial-001",
                output_format="evidence_lifecycle",
            ),
            artifacts=[artifacts[field] for field in output_artifact_fields],
        ),
        lifecycle_execution=LifecycleExecutionRecord(
            execution_mode="persistent_context",
            memory_visibility_policy="persistent_context",
            max_turns_per_session=60,
            status="completed",
            sessions=[
                LifecycleSessionRecord(
                    session_id="lifecycle.session-001",
                    checkpoint_ids=["initial_review", "response_review", "revisit"],
                    adapter="tool_loop",
                    resolved_model="anthropic:claude-sonnet-4-20250514",
                    status="completed",
                    artifacts=[artifacts["invocation_manifest"]],
                )
            ],
        ),
        lifecycle_provenance=lifecycle_provenance,
    )


# --- Valid construction ---


def test_trial_record_accepts_complete_payload_with_required_provenance() -> None:
    record = build_trial_record()

    assert record.completeness is Completeness.COMPLETE
    assert record.agent.adapter_revision == "git-sha-adapter"


def test_trial_record_allows_partial_payload_without_full_replay_provenance() -> None:
    record = build_trial_record(
        agent={
            "adapter": "tool_loop",
            "model": "anthropic:claude-sonnet-4-20250514",
            "configuration": {"max_turns": 20},
        },
        environment={
            "runtime_image": "ghcr.io/example/task-image:latest",
            "compute_backend": "modal",
        },
        inputs={
            "instruction": "Review the task and write output.",
        },
        completeness=Completeness.PARTIAL,
    )

    assert record.completeness is Completeness.PARTIAL


def test_trial_record_accepts_with_cost_record() -> None:
    record = build_trial_record(
        cost=CostRecord(
            tokens_in=1500,
            tokens_out=800,
            estimated_cost_usd=0.012,
        )
    )

    assert record.cost is not None
    assert record.cost.tokens_in == 1500


def test_trial_record_accepts_none_cost() -> None:
    record = build_trial_record(cost=None)

    assert record.cost is None


def test_trial_record_defaults_dataset_id_to_none() -> None:
    record = build_trial_record()

    assert record.dataset_id is None


def test_trial_record_accepts_dataset_id() -> None:
    record = build_trial_record(dataset_id="my-suite@1.0.0")

    assert record.dataset_id == "my-suite@1.0.0"


# --- Completeness validation ---


def test_trial_record_rejects_complete_payload_missing_optional_provenance() -> None:
    with pytest.raises(ValidationError):
        build_trial_record(
            agent={
                "adapter": "tool_loop",
                "model": "anthropic:claude-sonnet-4-20250514",
                "configuration": {"max_turns": 20},
            }
        )


def test_trial_record_rejects_complete_missing_tool_versions() -> None:
    with pytest.raises(ValidationError, match="tool_versions"):
        build_trial_record(
            environment=EnvironmentSnapshot(
                runtime_image="ghcr.io/example/task-image:latest",
                compute_backend="modal",
            )
        )


def test_trial_record_rejects_complete_missing_input_files() -> None:
    with pytest.raises(ValidationError, match="input_files"):
        build_trial_record(
            inputs=InputRecord(instruction="Review the task."),
        )


def test_trial_record_accepts_typed_lifecycle_execution_and_provenance() -> None:
    invocation_manifest = ArtifactReference(
        kind="lifecycle_manifest",
        path="_artifacts/trial-001/experiment-manifest.json",
        sha256="a" * 64,
        media_type="application/json",
    )
    invocation_index = ArtifactReference(
        kind="lifecycle_invocation_index",
        path="_artifacts/trial-001/experiment-index.jsonl",
        sha256="1" * 64,
        media_type="application/x-ndjson",
    )
    ablation_manifest = ArtifactReference(
        kind="lifecycle_ablation_manifest",
        path="_artifacts/trial-001/sweep/manifest.json",
        sha256="2" * 64,
        media_type="application/json",
    )
    ablation_plan = ArtifactReference(
        kind="lifecycle_ablation_plan",
        path="_artifacts/trial-001/sweep/plan.json",
        sha256="3" * 64,
        media_type="application/json",
    )
    artifacts = [invocation_manifest, invocation_index, ablation_manifest, ablation_plan]
    record = build_trial_record(
        outputs=OutputRecord(
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path="_artifacts/trial-001",
                output_format="evidence_lifecycle",
            ),
            artifacts=artifacts,
        ),
        lifecycle_execution=LifecycleExecutionRecord(
            execution_mode="fresh_context",
            memory_visibility_policy="artifact_memory",
            max_turns_per_session=20,
            status="completed",
            sessions=[
                LifecycleSessionRecord(
                    session_id="initial_review.session-001",
                    checkpoint_ids=["initial_review"],
                    adapter="tool_loop",
                    resolved_model="anthropic:claude-sonnet-4-20250514",
                    status="completed",
                    artifacts=[invocation_manifest],
                )
            ],
        ),
        lifecycle_provenance=LifecycleTrialProvenance(
            lifecycle_id="stormwater.drainage-model-evidence-lifecycle",
            spec_sha256="b" * 64,
            package_sha256="c" * 64,
            repository_commit="d" * 40,
            repository_dirty=False,
            repository_dirty_digest="e" * 64,
            runtime_provider="anthropic",
            runtime_distributions=("anthropic==1.0.0", "pydantic-ai-slim==1.0.0"),
            runtime_dependency_sha256="1" * 64,
            verifier_qualified_name="aec_bench.verify_stormwater",
            verifier_source_sha256="f" * 64,
            invocation_manifest=invocation_manifest,
            invocation_index=invocation_index,
            ablation_manifest=ablation_manifest,
            ablation_plan=ablation_plan,
        ),
    )

    assert record.lifecycle_execution is not None
    assert record.lifecycle_execution.sessions[0].checkpoint_ids == ["initial_review"]
    assert record.lifecycle_provenance is not None
    assert record.lifecycle_provenance.package_sha256 == "c" * 64

    dirty = record.model_dump(mode="json")
    dirty["lifecycle_provenance"]["repository_dirty"] = True
    with pytest.raises(ValidationError, match="clean_repository"):
        TrialRecord.model_validate(dirty)


def test_complete_lifecycle_record_requires_hashed_output_artifacts() -> None:
    with pytest.raises(ValidationError, match="outputs.artifacts"):
        build_trial_record(
            lifecycle_execution={
                "execution_mode": "persistent_context",
                "memory_visibility_policy": "persistent_context",
                "max_turns_per_session": 60,
                "status": "completed",
                "sessions": [
                    {
                        "session_id": "session-001",
                        "checkpoint_ids": ["initial_review"],
                        "adapter": "tool_loop",
                        "resolved_model": "anthropic:claude-sonnet-4-20250514",
                        "status": "completed",
                        "artifacts": [
                            {
                                "kind": "lifecycle_manifest",
                                "path": "manifest.json",
                                "sha256": "f" * 64,
                                "media_type": "application/json",
                            }
                        ],
                    }
                ],
            },
            lifecycle_provenance={
                "lifecycle_id": "lifecycle.demo",
                "spec_sha256": "a" * 64,
                "package_sha256": "b" * 64,
                "repository_commit": "c" * 40,
                "repository_dirty": False,
                "repository_dirty_digest": "d" * 64,
                "runtime_provider": "anthropic",
                "runtime_distributions": ["anthropic==1.0.0", "pydantic-ai-slim==1.0.0"],
                "runtime_dependency_sha256": "1" * 64,
                "verifier_qualified_name": "demo.verify",
                "verifier_source_sha256": "e" * 64,
                "invocation_manifest": {
                    "kind": "lifecycle_manifest",
                    "path": "manifest.json",
                    "sha256": "f" * 64,
                    "media_type": "application/json",
                },
            },
        )


def test_complete_public_lifecycle_record_accepts_only_public_sweep_provenance() -> None:
    record = build_complete_lifecycle_record(
        visibility=Visibility.PUBLIC,
        provenance_fields=_PUBLIC_LIFECYCLE_PROVENANCE_FIELDS,
    )

    assert record.lifecycle_provenance is not None
    for field in _PUBLIC_LIFECYCLE_PROVENANCE_FIELDS:
        assert getattr(record.lifecycle_provenance, field) is not None


@pytest.mark.parametrize("missing_field", _PUBLIC_LIFECYCLE_PROVENANCE_FIELDS)
def test_complete_public_lifecycle_record_requires_every_public_sweep_reference(
    missing_field: str,
) -> None:
    provenance_fields = tuple(field for field in _PUBLIC_LIFECYCLE_PROVENANCE_FIELDS if field != missing_field)

    with pytest.raises(ValidationError):
        build_complete_lifecycle_record(
            visibility=Visibility.PUBLIC,
            provenance_fields=provenance_fields,
        )


def test_complete_holdout_lifecycle_record_is_not_supported() -> None:
    with pytest.raises(ValidationError, match="public_visibility"):
        build_complete_lifecycle_record(
            visibility=Visibility.HOLDOUT,
            provenance_fields=_PUBLIC_LIFECYCLE_PROVENANCE_FIELDS,
        )


@pytest.mark.parametrize(
    ("visibility", "provenance_fields", "omitted_output_field"),
    [
        *[
            pytest.param(
                Visibility.PUBLIC,
                _PUBLIC_LIFECYCLE_PROVENANCE_FIELDS,
                field,
                id=f"public-{field}",
            )
            for field in ("invocation_manifest", *_PUBLIC_LIFECYCLE_PROVENANCE_FIELDS)
        ],
    ],
)
def test_complete_lifecycle_record_requires_every_bound_reference_in_output_artifacts(
    visibility: Visibility,
    provenance_fields: tuple[str, ...],
    omitted_output_field: str,
) -> None:
    bound_fields = ("invocation_manifest", *provenance_fields)
    output_artifact_fields = tuple(field for field in bound_fields if field != omitted_output_field)

    with pytest.raises(ValidationError, match="output artifacts"):
        build_complete_lifecycle_record(
            visibility=visibility,
            provenance_fields=provenance_fields,
            output_artifact_fields=output_artifact_fields,
        )


def test_trial_record_accepts_complete_meta_harness_lineage() -> None:
    candidate_manifest = _artifact("meta_harness_candidate", "candidate.json", "1")
    harness_program_plan = _artifact("meta_harness_harness_program_plan", "harness-program-plan.json", "2")
    repair_decision = _artifact("meta_harness_repair_decision", "repair-decision.json", "3")
    record = build_trial_record(
        task=TaskReference(
            task_id="electrical/voltage-drop/au-office-fitout",
            task_revision="git-sha-task",
            visibility=Visibility.PUBLIC,
        ),
        outputs=OutputRecord(
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path="/workspace/output.jsonl",
                output_format="jsonl",
            ),
            artifacts=[candidate_manifest, harness_program_plan, repair_decision],
        ),
        meta_harness_provenance=_meta_harness_provenance(
            candidate_manifest=candidate_manifest,
            harness_program_plan=harness_program_plan,
            repair_decision=repair_decision,
        ),
    )

    restored = TrialRecord.model_validate(record.model_dump(mode="json"))

    assert restored.meta_harness_provenance is not None
    assert restored.meta_harness_provenance.harness_program_cell == "hx_px"
    assert restored.meta_harness_provenance.motif_ids == ("motif.alpha", "motif.beta")


def test_complete_meta_harness_record_requires_bound_artifacts() -> None:
    candidate_manifest = _artifact("meta_harness_candidate", "candidate.json", "1")

    with pytest.raises(ValidationError, match="meta-harness provenance must be included"):
        build_trial_record(
            outputs=OutputRecord(
                agent_output=AgentOutput(
                    status=AgentOutputStatus.COMPLETED,
                    output_path="/workspace/output.jsonl",
                    output_format="jsonl",
                ),
                artifacts=[],
            ),
            meta_harness_provenance=_meta_harness_provenance(
                candidate_manifest=candidate_manifest,
                harness_program_cell=None,
                paired_block_id=None,
                repair_attempt_id=None,
                repair_iteration=None,
            ),
        )


def test_trial_record_binds_one_completed_proposal_session_and_cleanup() -> None:
    candidate_manifest = _artifact("meta_harness_candidate", "candidate.json", "1")
    session_receipt = _artifact(
        "proposal_session_receipt",
        "proposal-session/session-receipt.json",
        "4",
    )
    cleanup_receipt = _artifact(
        "proposal_cleanup_receipt",
        "proposal-session/cleanup-receipt.json",
        "5",
    )
    task_package_manifest = _artifact(
        "proposal_task_package_manifest",
        "proposal-session/task-package.json",
        "6",
    )
    runtime_archive_manifest = _artifact(
        "proposal_runtime_archive_manifest",
        "proposal-session/runtime-archive.json",
        "7",
    )
    proposal_session = ProposalSessionTrialProvenance(
        session_id="proposal-session.001",
        candidate_id="candidate.001",
        candidate_artifact_sha256="8" * 64,
        proposal_graph_sha256="9" * 64,
        compilation_sha256="a" * 64,
        session_plan_sha256="b" * 64,
        session_receipt=session_receipt,
        cleanup_receipt=cleanup_receipt,
        task_package_manifest=task_package_manifest,
        runtime_archive_manifest=runtime_archive_manifest,
        expected_trial_records=1,
        trial_ordinal=1,
    )
    record = build_trial_record(
        task=TaskReference(
            task_id="civil/proposal-session/source-free",
            task_revision="git-sha-task",
            visibility=Visibility.PUBLIC,
        ),
        outputs=OutputRecord(
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path="/workspace/output.md",
                output_format="markdown",
            ),
            artifacts=[
                candidate_manifest,
                session_receipt,
                cleanup_receipt,
                task_package_manifest,
                runtime_archive_manifest,
            ],
        ),
        meta_harness_provenance=_meta_harness_provenance(
            candidate_manifest=candidate_manifest,
            harness_program_cell=None,
            paired_block_id=None,
            repair_attempt_id=None,
            repair_iteration=None,
            proposal_session=proposal_session,
        ),
    )

    assert record.meta_harness_provenance is not None
    assert record.meta_harness_provenance.proposal_session == proposal_session
    assert proposal_session.expected_trial_records == 1
    assert proposal_session.trial_ordinal == 1


def test_trial_record_rejects_unbound_proposal_session_artifact() -> None:
    candidate_manifest = _artifact("meta_harness_candidate", "candidate.json", "1")
    proposal_session = ProposalSessionTrialProvenance(
        session_id="proposal-session.001",
        candidate_id="candidate.001",
        candidate_artifact_sha256="8" * 64,
        proposal_graph_sha256="9" * 64,
        compilation_sha256="a" * 64,
        session_plan_sha256="b" * 64,
        session_receipt=_artifact(
            "proposal_session_receipt",
            "proposal-session/session-receipt.json",
            "4",
        ),
        cleanup_receipt=_artifact(
            "proposal_cleanup_receipt",
            "proposal-session/cleanup-receipt.json",
            "5",
        ),
        task_package_manifest=_artifact(
            "proposal_task_package_manifest",
            "proposal-session/task-package.json",
            "6",
        ),
        runtime_archive_manifest=_artifact(
            "proposal_runtime_archive_manifest",
            "proposal-session/runtime-archive.json",
            "7",
        ),
        expected_trial_records=1,
        trial_ordinal=1,
    )

    with pytest.raises(ValidationError, match="proposal session provenance"):
        build_trial_record(
            task=TaskReference(
                task_id="civil/proposal-session/source-free",
                task_revision="git-sha-task",
                visibility=Visibility.PUBLIC,
            ),
            outputs=OutputRecord(
                agent_output=AgentOutput(
                    status=AgentOutputStatus.COMPLETED,
                    output_path="/workspace/output.md",
                    output_format="markdown",
                ),
                artifacts=[candidate_manifest, proposal_session.session_receipt],
            ),
            meta_harness_provenance=_meta_harness_provenance(
                candidate_manifest=candidate_manifest,
                harness_program_cell=None,
                paired_block_id=None,
                repair_attempt_id=None,
                repair_iteration=None,
                proposal_session=proposal_session,
            ),
        )


def test_holdout_meta_harness_trial_rejects_repair_and_harness_program_visibility_mismatch() -> None:
    candidate_manifest = _artifact("meta_harness_candidate", "candidate.json", "1")
    repair_decision = _artifact("meta_harness_repair_decision", "repair-decision.json", "3")

    with pytest.raises(ValidationError, match="holdout.*repair"):
        build_trial_record(
            task=TaskReference(
                task_id="holdout/task",
                task_revision="git-sha-task",
                visibility=Visibility.HOLDOUT,
            ),
            meta_harness_provenance=_meta_harness_provenance(
                split="holdout",
                candidate_manifest=candidate_manifest,
                repair_attempt_id="repair.1",
                repair_decision=repair_decision,
                repair_iteration=1,
                harness_program_cell=None,
                paired_block_id=None,
                harness_program_plan=None,
            ),
        )

    with pytest.raises(ValidationError, match="calibration.*public"):
        build_trial_record(
            task=TaskReference(
                task_id="holdout/task",
                task_revision="git-sha-task",
                visibility=Visibility.HOLDOUT,
            ),
            outputs=OutputRecord(
                agent_output=AgentOutput(
                    status=AgentOutputStatus.COMPLETED,
                    output_path="/workspace/output.jsonl",
                    output_format="jsonl",
                ),
                artifacts=[candidate_manifest],
            ),
            meta_harness_provenance=_meta_harness_provenance(
                split="calibration",
                candidate_manifest=candidate_manifest,
                harness_program_cell=None,
                paired_block_id=None,
                repair_attempt_id=None,
                repair_iteration=None,
            ),
        )


def test_lifecycle_and_meta_harness_package_hashes_must_agree() -> None:
    invocation_manifest = _artifact("lifecycle_manifest", "manifest.json", "4")
    invocation_index = _artifact("lifecycle_invocation_index", "index.jsonl", "5")
    ablation_manifest = _artifact("lifecycle_ablation_manifest", "ablation.json", "6")
    ablation_plan = _artifact("lifecycle_ablation_plan", "ablation-plan.json", "7")
    candidate_manifest = _artifact("meta_harness_candidate", "candidate.json", "1")

    with pytest.raises(ValidationError, match="package hashes must agree"):
        build_trial_record(
            outputs=OutputRecord(
                agent_output=AgentOutput(
                    status=AgentOutputStatus.COMPLETED,
                    output_path="_artifacts/trial-001",
                    output_format="evidence_lifecycle",
                ),
                artifacts=[
                    invocation_manifest,
                    invocation_index,
                    ablation_manifest,
                    ablation_plan,
                    candidate_manifest,
                ],
            ),
            lifecycle_execution=LifecycleExecutionRecord(
                execution_mode="fresh_context",
                memory_visibility_policy="artifact_memory",
                max_turns_per_session=20,
                status="completed",
                sessions=[
                    LifecycleSessionRecord(
                        session_id="session.1",
                        adapter="tool_loop",
                        resolved_model="anthropic:claude-sonnet-4-20250514",
                        status="completed",
                        artifacts=[invocation_manifest],
                    )
                ],
            ),
            lifecycle_provenance=LifecycleTrialProvenance(
                lifecycle_id="lifecycle.demo",
                spec_sha256="a" * 64,
                package_sha256="b" * 64,
                repository_commit="c" * 40,
                repository_dirty=False,
                repository_dirty_digest="d" * 64,
                runtime_provider="anthropic",
                runtime_distributions=("anthropic==1.0.0",),
                runtime_dependency_sha256="e" * 64,
                verifier_qualified_name="demo.verify",
                verifier_source_sha256="f" * 64,
                invocation_manifest=invocation_manifest,
                invocation_index=invocation_index,
                ablation_manifest=ablation_manifest,
                ablation_plan=ablation_plan,
            ),
            meta_harness_provenance=_meta_harness_provenance(
                candidate_manifest=candidate_manifest,
                review_sidecar_sha256="9" * 64,
                harness_program_cell=None,
                paired_block_id=None,
                repair_attempt_id=None,
                repair_iteration=None,
            ),
        )


def test_lifecycle_execution_rejects_resolved_model_drift() -> None:
    with pytest.raises(ValidationError, match="resolved model must remain stable"):
        LifecycleExecutionRecord(
            execution_mode="fresh_context",
            memory_visibility_policy="artifact_memory",
            max_turns_per_session=20,
            status="completed",
            sessions=[
                LifecycleSessionRecord(
                    session_id="session-001",
                    checkpoint_ids=["initial_review"],
                    adapter="tool_loop",
                    resolved_model="model-a",
                    status="completed",
                ),
                LifecycleSessionRecord(
                    session_id="session-002",
                    checkpoint_ids=["response_review"],
                    adapter="tool_loop",
                    resolved_model="model-b",
                    status="completed",
                ),
            ],
        )


# --- Adaptation provenance ---


def test_trial_record_accepts_adaptation_provenance() -> None:
    record = build_trial_record(
        adaptation=AdaptationProvenance(
            family_id="heat-load-audit",
            seed_task_id="mechanical/heat-load/audit-office-building/sydney-8rm",
            variation_key="city=perth__building_type=mixed-use",
            variation={"city": "perth", "building_type": "mixed-use"},
            derivation_lineage=[
                DerivationStepRecord(
                    axis="city",
                    parent_value="sydney",
                    value="perth",
                ),
                DerivationStepRecord(
                    axis="building_type",
                    parent_value="office",
                    value="mixed-use",
                ),
            ],
        )
    )

    assert record.adaptation is not None
    assert record.adaptation.family_id == "heat-load-audit"
    assert record.adaptation.derivation_lineage[0].axis == "city"


def test_trial_record_rejects_inconsistent_adaptation_lineage() -> None:
    with pytest.raises(ValidationError):
        build_trial_record(
            adaptation={
                "family_id": "heat-load-audit",
                "seed_task_id": "mechanical/heat-load/audit-office-building/sydney-8rm",
                "variation_key": "city=perth",
                "variation": {"city": "perth"},
                "derivation_lineage": [
                    {
                        "axis": "building_type",
                        "parent_value": "office",
                        "value": "mixed-use",
                    }
                ],
            }
        )


def test_derivation_step_rejects_same_value_as_parent() -> None:
    with pytest.raises(ValidationError, match="must change"):
        DerivationStepRecord(axis="jurisdiction", parent_value="au", value="au")


def test_adaptation_provenance_rejects_duplicate_lineage_axes() -> None:
    with pytest.raises(ValidationError, match="unique"):
        AdaptationProvenance(
            family_id="heat-load-audit",
            seed_task_id="mechanical/heat-load/audit-office-building/sydney-8rm",
            variation_key="city=perth",
            variation={"city": "perth"},
            derivation_lineage=[
                DerivationStepRecord(axis="city", parent_value="sydney", value="perth"),
                DerivationStepRecord(axis="city", parent_value="brisbane", value="perth"),
            ],
        )


def test_adaptation_provenance_rejects_empty_variation() -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        AdaptationProvenance(
            family_id="heat-load-audit",
            seed_task_id="task-001",
            variation_key="none",
            variation={},
        )


def _artifact(kind: str, path: str, digit: str) -> ArtifactReference:
    return ArtifactReference(
        kind=kind,
        path=path,
        sha256=digit * 64,
        media_type="application/json",
    )


def _meta_harness_provenance(
    *,
    candidate_manifest: ArtifactReference,
    split: Literal["discovery", "repair_gate", "calibration", "holdout"] = "repair_gate",
    review_sidecar_sha256: str = "b" * 64,
    harness_program_cell: Literal["h0_p0", "hx_p0", "h0_px", "hx_px"] | None = "hx_px",
    paired_block_id: str | None = "block.1",
    harness_program_plan: ArtifactReference | None = None,
    repair_attempt_id: str | None = "repair.1",
    repair_decision: ArtifactReference | None = None,
    repair_iteration: int | None = 1,
    proposal_session: ProposalSessionTrialProvenance | None = None,
) -> MetaHarnessTrialProvenance:
    return MetaHarnessTrialProvenance(
        run_id="run.meta-harness.001",
        policy_id="policy.1",
        kernel_id="kernel.aec-bench",
        kernel_sha256="a" * 64,
        harness_id="harness.1",
        harness_sha256="c" * 64,
        program_id="program.1",
        program_sha256="d" * 64,
        bundle_id="bundle.1",
        bundle_sha256="e" * 64,
        parent_bundle_id="bundle.parent",
        review_sidecar_sha256=review_sidecar_sha256,
        declared_surface_sha256="f" * 64,
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        split=split,
        repetition=1,
        harness_program_cell=harness_program_cell,
        paired_block_id=paired_block_id,
        repair_attempt_id=repair_attempt_id,
        repair_iteration=repair_iteration,
        candidate_manifest=candidate_manifest,
        harness_program_plan=harness_program_plan,
        repair_decision=repair_decision,
        motif_ids=("motif.alpha", "motif.beta"),
        proposal_session=proposal_session,
    )


def test_meta_harness_provenance_accepts_opaque_evaluation_plan_ref_and_loads_legacy_without_it() -> None:
    candidate = _artifact("meta-harness-candidate-manifest", "/tmp/candidate.json", "a")
    current = _meta_harness_provenance(
        candidate_manifest=candidate,
        harness_program_plan=_artifact("meta-harness-harness-program-plan", "/tmp/harness-program.json", "b"),
        repair_decision=_artifact("meta-harness-repair-decision", "/tmp/repair.json", "c"),
    )
    legacy_payload = current.model_dump(mode="json")

    restored_legacy = MetaHarnessTrialProvenance.model_validate(legacy_payload)

    assert restored_legacy.evaluation_plan_ref is None

    plan_ref = EvaluationPlanRef(
        plan_id="evaluation-plan.stage-9",
        evaluation_generation="evaluation-generation-1",
    )
    governed = current.model_copy(update={"evaluation_plan_ref": plan_ref})
    restored_governed = MetaHarnessTrialProvenance.model_validate(governed.model_dump(mode="json"))

    assert restored_governed.evaluation_plan_ref == plan_ref


# --- Nested model isolation ---


def test_task_reference_rejects_blank_task_id() -> None:
    with pytest.raises(ValidationError):
        TaskReference(task_id="  ", task_revision="sha-abc")


def test_agent_reference_rejects_blank_adapter() -> None:
    with pytest.raises(ValidationError):
        AgentReference(adapter="", model="claude")


def test_environment_snapshot_rejects_blank_compute_backend() -> None:
    with pytest.raises(ValidationError):
        EnvironmentSnapshot(runtime_image="image:latest", compute_backend="  ")


def test_file_reference_rejects_blank_hash() -> None:
    with pytest.raises(ValidationError):
        FileReference(path="/workspace/file.json", hash="  ")


def test_input_record_rejects_blank_instruction() -> None:
    with pytest.raises(ValidationError):
        InputRecord(instruction="   ")


def test_output_record_accepts_all_none_fields() -> None:
    output = OutputRecord()

    assert output.agent_output is None
    assert output.raw_output_path is None
    assert output.terminated is False
    assert output.truncated is False
    assert output.final_reason is None


def test_output_record_rejects_conflicting_terminal_state() -> None:
    with pytest.raises(ValidationError, match="both terminated and truncated"):
        OutputRecord(terminated=True, truncated=True)


def test_episode_artifact_must_be_attached_to_outputs() -> None:
    episode = ArtifactReference(
        kind="episode-inventory",
        path="artifacts/episode/inventory.json",
        sha256="a" * 64,
        media_type="application/json",
    )

    with pytest.raises(ValidationError, match="episode artifact must be included"):
        build_trial_record(
            episode_artifact=episode,
            outputs=OutputRecord(artifacts=[]),
        )

    record = build_trial_record(
        episode_artifact=episode,
        outputs=OutputRecord(artifacts=[episode]),
    )
    assert record.episode_artifact == episode


def test_obsolete_world_projection_fields_fail_current_validation() -> None:
    with pytest.raises(ValidationError):
        build_trial_record(world_execution={}, world_provenance={})


def test_timing_record_rejects_negative_total_seconds() -> None:
    with pytest.raises(ValidationError):
        TimingRecord(total_seconds=-1.0)


def test_cost_record_rejects_negative_tokens() -> None:
    with pytest.raises(ValidationError):
        CostRecord(tokens_in=-100)


# --- Round-trip serialization ---


def test_trial_record_roundtrip_serialization() -> None:
    original = build_trial_record()

    serialized = original.model_dump(mode="json")
    restored = TrialRecord.model_validate(serialized)

    assert restored == original
    assert restored.completeness is Completeness.COMPLETE
    assert restored.task.task_id == "electrical/voltage-drop/au-office-fitout"
    assert restored.agent.adapter_revision == "git-sha-adapter"


def test_trial_record_roundtrip_with_adaptation() -> None:
    original = build_trial_record(
        adaptation=AdaptationProvenance(
            family_id="heat-load-audit",
            seed_task_id="mechanical/heat-load/audit-office-building/sydney-8rm",
            variation_key="city=perth",
            variation={"city": "perth"},
            derivation_lineage=[DerivationStepRecord(axis="city", parent_value="sydney", value="perth")],
        ),
        cost=CostRecord(tokens_in=1000, tokens_out=500, estimated_cost_usd=0.01),
    )

    serialized = original.model_dump(mode="json")
    restored = TrialRecord.model_validate(serialized)

    assert restored == original
    assert restored.adaptation is not None
    assert restored.adaptation.derivation_lineage[0].value == "perth"
    assert restored.cost is not None
    assert restored.cost.tokens_in == 1000
