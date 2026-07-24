# ABOUTME: Tests for the TrialRecord provenance contract in the aec-bench contracts package.
# ABOUTME: These tests define completeness rules and nested provenance requirements.

import pytest
from pydantic import ValidationError

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
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
    OutputRecord,
    TaskReference,
    TimingRecord,
    TrialRecord,
)

_PUBLIC_LIFECYCLE_PROVENANCE_FIELDS = (
    "invocation_index",
    "ablation_manifest",
    "ablation_plan",
)
_SEALED_HOLDOUT_PROVENANCE_FIELDS = (
    "calibration_freeze",
    "sealed_target_freeze",
    "sealed_audit_claim",
    "sealed_audit_manifest",
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
        "calibration_freeze": ArtifactReference(
            kind="lifecycle_calibration_freeze",
            path="_artifacts/trial-001/sealed/calibration-freeze.json",
            sha256="4" * 64,
            media_type="application/json",
        ),
        "sealed_target_freeze": ArtifactReference(
            kind="lifecycle_sealed_target_freeze",
            path="_artifacts/trial-001/sealed/target-freeze.json",
            sha256="5" * 64,
            media_type="application/json",
        ),
        "sealed_audit_claim": ArtifactReference(
            kind="lifecycle_sealed_audit_claim",
            path="_artifacts/trial-001/sealed/audit-claim.json",
            sha256="6" * 64,
            media_type="application/json",
        ),
        "sealed_audit_manifest": ArtifactReference(
            kind="lifecycle_sealed_audit_manifest",
            path="_artifacts/trial-001/sealed/audit-manifest.json",
            sha256="7" * 64,
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
        "lifecycle_id": "ssc03.drainage-model-evidence-lifecycle",
        "world_id": "aec.task_world.composite.drainage-model-evidence-lifecycle-review.v1",
        "spec_sha256": "8" * 64,
        "package_sha256": "9" * 64,
        "repository_commit": "a" * 40,
        "repository_dirty": False,
        "repository_dirty_digest": "b" * 64,
        "runtime_provider": "anthropic",
        "runtime_distributions": ("anthropic==1.0.0", "pydantic-ai-slim==1.0.0"),
        "runtime_dependency_sha256": "c" * 64,
        "verifier_qualified_name": "aec_bench.verify_ssc03",
        "verifier_source_sha256": "d" * 64,
        "invocation_manifest": artifacts["invocation_manifest"],
    }
    lifecycle_provenance.update({field: artifacts[field] for field in provenance_fields})

    return build_trial_record(
        task=TaskReference(
            task_id="drainage/ssc03/lifecycle",
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
            lifecycle_id="ssc03.drainage-model-evidence-lifecycle",
            world_id="aec.task_world.composite.drainage-model-evidence-lifecycle-review.v1",
            spec_sha256="b" * 64,
            package_sha256="c" * 64,
            repository_commit="d" * 40,
            repository_dirty=False,
            repository_dirty_digest="e" * 64,
            runtime_provider="anthropic",
            runtime_distributions=("anthropic==1.0.0", "pydantic-ai-slim==1.0.0"),
            runtime_dependency_sha256="1" * 64,
            verifier_qualified_name="aec_bench.verify_ssc03",
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
                "world_id": "world.demo",
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
    for field in _SEALED_HOLDOUT_PROVENANCE_FIELDS:
        assert getattr(record.lifecycle_provenance, field) is None


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


@pytest.mark.parametrize("sealed_field", _SEALED_HOLDOUT_PROVENANCE_FIELDS)
def test_complete_public_lifecycle_record_rejects_sealed_audit_provenance(
    sealed_field: str,
) -> None:
    with pytest.raises(ValidationError):
        build_complete_lifecycle_record(
            visibility=Visibility.PUBLIC,
            provenance_fields=(*_PUBLIC_LIFECYCLE_PROVENANCE_FIELDS, sealed_field),
        )


def test_complete_holdout_lifecycle_record_accepts_only_sealed_audit_provenance() -> None:
    record = build_complete_lifecycle_record(
        visibility=Visibility.HOLDOUT,
        provenance_fields=_SEALED_HOLDOUT_PROVENANCE_FIELDS,
    )

    assert record.lifecycle_provenance is not None
    for field in _SEALED_HOLDOUT_PROVENANCE_FIELDS:
        assert getattr(record.lifecycle_provenance, field) is not None
    for field in _PUBLIC_LIFECYCLE_PROVENANCE_FIELDS:
        assert getattr(record.lifecycle_provenance, field) is None


@pytest.mark.parametrize("missing_field", _SEALED_HOLDOUT_PROVENANCE_FIELDS)
def test_complete_holdout_lifecycle_record_requires_every_sealed_audit_reference(
    missing_field: str,
) -> None:
    provenance_fields = tuple(field for field in _SEALED_HOLDOUT_PROVENANCE_FIELDS if field != missing_field)

    with pytest.raises(ValidationError):
        build_complete_lifecycle_record(
            visibility=Visibility.HOLDOUT,
            provenance_fields=provenance_fields,
        )


@pytest.mark.parametrize("public_field", _PUBLIC_LIFECYCLE_PROVENANCE_FIELDS)
def test_complete_holdout_lifecycle_record_rejects_public_sweep_provenance(
    public_field: str,
) -> None:
    with pytest.raises(ValidationError):
        build_complete_lifecycle_record(
            visibility=Visibility.HOLDOUT,
            provenance_fields=(*_SEALED_HOLDOUT_PROVENANCE_FIELDS, public_field),
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
        *[
            pytest.param(
                Visibility.HOLDOUT,
                _SEALED_HOLDOUT_PROVENANCE_FIELDS,
                field,
                id=f"holdout-{field}",
            )
            for field in ("invocation_manifest", *_SEALED_HOLDOUT_PROVENANCE_FIELDS)
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
