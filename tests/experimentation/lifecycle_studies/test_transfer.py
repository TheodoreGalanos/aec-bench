# ABOUTME: Tests descriptive holdout generalization over immutable lifecycle TrialRecords.
# ABOUTME: Enforces visibility, condition identity, provenance integrity, and non-causal summaries.

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pytest
from pydantic import ValidationError

import aec_bench.lifecycles.recording as experiment_runtime
from aec_bench.contracts.authority_evidence import AuthorityEvidenceKind
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.evidence_lifecycle import EvidenceCheckpointSpec, EvidenceLifecycleSpec
from aec_bench.contracts.experiment_manifest import AgentConfig
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trial_record import (
    AgentReference,
    ArtifactReference,
    AuthorityExpectation,
    EnvironmentSnapshot,
    EvaluationStatus,
    EvidenceStatus,
    ExecutionStatus,
    GitSourceRef,
    InputRecord,
    LifecycleExecutionRecord,
    LifecycleSessionRecord,
    LifecycleTrialProvenance,
    OutputRecord,
    ProviderRoute,
    RunManifest,
    TimingRecord,
    TrialRecord,
    UnresolvedSourceRef,
)
from aec_bench.evaluation.lifecycle import score_semantic_transitions
from aec_bench.experimentation.lifecycle_studies.ablation_plan import (
    LifecycleAblationCondition,
    LifecycleAblationLimits,
    LifecycleAblationManifest,
    LifecycleAblationPlan,
    LifecycleAblationStudyDesign,
    LifecycleAblationTrial,
    LifecycleRuntimeProvenance,
    build_lifecycle_ablation_plan,
)
from aec_bench.experimentation.lifecycle_studies.transfer import (
    LifecycleTransferCondition,
    LifecycleTransferEvaluationSpec,
    LifecycleTransferRecordReference,
    LifecycleTransferStudyDesign,
    build_lifecycle_transfer_evaluation,
)
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.ledger.reader import read_trial_record
from aec_bench.ledger.writer import write_trial_record
from aec_bench.lifecycles.catalogue import (
    lifecycle_operation_resolver,
    lifecycle_package_variant,
    materialize_lifecycle,
)
from aec_bench.lifecycles.recording import LifecycleExperimentMetrics
from aec_bench.lifecycles.runtime.episode import (
    LifecycleExecutionMode,
    LifecycleVisibilityPolicy,
)
from aec_bench.lifecycles.runtime.lifecycle import (
    execute_lifecycle_operation,
    open_checkpoint_attempt,
    release_checkpoint,
    submit_checkpoint,
)
from aec_bench.lifecycles.runtime.operation_protocol import (
    lifecycle_operation_protocol_identity,
    lifecycle_operation_source_identity,
)
from aec_bench.lifecycles.runtime.request_protocol import (
    EvidenceLifecycleError,
    validate_evidence_request_run_state,
)
from aec_bench.lifecycles.runtime.state import EvidenceLifecycleRunState

_RUNTIME_SHA256 = "1" * 64


def test_partial_holdout_cannot_stand_in_for_complete_target_evidence(
    tmp_path: Path,
) -> None:
    condition = _condition()
    calibration = _write_record(
        tmp_path,
        experiment_id="public-calibration",
        trial_id="calibration-001",
        visibility=Visibility.PUBLIC,
        package_sha256="a" * 64,
        reward=1.0,
        condition=condition,
    )
    semantic = score_semantic_transitions(
        checkpoint_ids=("initial", "corrected"),
        expected={"initial": {"decision": "hold"}, "corrected": {"decision": "release"}},
        actual={"initial": {"decision": "hold"}, "corrected": {"decision": "release"}},
    )
    target = _write_record(
        tmp_path,
        experiment_id="private-holdout",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=0.75,
        condition=condition,
        semantic_transition=semantic.model_dump(mode="json"),
    )
    target_bytes = target.record_path.read_bytes()

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.status == "not_evaluable"
    assert result.study_design.interpretation == "descriptive_holdout_generalization"
    assert result.study_design.selection_basis == "public_calibration"
    assert result.study_design.causal_effects_supported is False
    assert result.study_design.cross_run_learning_supported is False
    assert result.calibration_support_count == 1
    assert result.eligible_target_count == 0
    assert result.mean_target_reward is None
    assert result.target_results[0].reasons == ("source_not_reconstructive",)
    assert result.target_results[0].verifier_reward is None
    assert result.target_results[0].verifier_validity is None
    assert result.target_results[0].semantic_diagnostics is None
    assert target.record_path.read_bytes() == target_bytes
    assert read_trial_record(target.record_path).evaluation.reward == 0.75
    serialized = result.model_dump(mode="json")
    assert "transfer_effect" not in serialized
    assert "winner" not in serialized


@pytest.mark.parametrize(
    ("calibration_visibility", "expected_reason"),
    [
        (None, "missing_task_visibility"),
        (Visibility.HOLDOUT, "calibration_not_public"),
    ],
)
def test_calibration_requires_explicit_public_visibility(
    tmp_path: Path,
    calibration_visibility: Visibility | None,
    expected_reason: str,
) -> None:
    condition = _condition()
    calibration = _write_record(
        tmp_path,
        experiment_id="calibration",
        trial_id="calibration-001",
        visibility=calibration_visibility,
        package_sha256="a" * 64,
        reward=1.0,
        condition=condition,
    )
    target = _write_record(
        tmp_path,
        experiment_id="holdout",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.status == "not_evaluable"
    assert result.calibration_support_count == 0
    assert expected_reason in result.calibration_results[0].reasons
    assert "no_public_calibration_support" in result.target_results[0].reasons
    assert result.mean_target_reward is None


@pytest.mark.parametrize(
    ("target_visibility", "expected_reason"),
    [
        (None, "missing_task_visibility"),
        (Visibility.PUBLIC, "target_not_holdout"),
    ],
)
def test_target_requires_explicit_holdout_visibility(
    tmp_path: Path,
    target_visibility: Visibility | None,
    expected_reason: str,
) -> None:
    condition = _condition()
    calibration = _write_record(
        tmp_path,
        experiment_id="calibration",
        trial_id="calibration-001",
        visibility=Visibility.PUBLIC,
        package_sha256="a" * 64,
        reward=1.0,
        condition=condition,
    )
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=target_visibility,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.status == "not_evaluable"
    assert expected_reason in result.target_results[0].reasons
    assert result.mean_target_reward is None


def test_target_package_must_be_distinct_from_every_supporting_calibration_package(
    tmp_path: Path,
) -> None:
    condition = _condition()
    calibration = _write_record(
        tmp_path,
        experiment_id="calibration",
        trial_id="calibration-001",
        visibility=Visibility.PUBLIC,
        package_sha256="a" * 64,
        reward=1.0,
        condition=condition,
    )
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="a" * 64,
        reward=1.0,
        condition=condition,
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.status == "not_evaluable"
    assert result.target_results[0].reasons == (
        "source_not_reconstructive",
        "target_package_matches_calibration",
    )
    assert result.mean_target_reward is None


def test_target_package_must_be_distinct_from_any_integrity_valid_calibration_input(
    tmp_path: Path,
) -> None:
    selected = _condition()
    supporting = _write_record(
        tmp_path,
        experiment_id="calibration",
        trial_id="calibration-supporting",
        visibility=Visibility.PUBLIC,
        package_sha256="a" * 64,
        reward=1.0,
        condition=selected,
    )
    other_condition = _write_record(
        tmp_path,
        experiment_id="calibration",
        trial_id="calibration-other-model",
        visibility=None,
        package_sha256="b" * 64,
        reward=1.0,
        condition=selected.model_copy(update={"model": "other-model"}),
    )
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=selected,
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(
            condition=selected,
            calibration=(supporting.reference, other_condition.reference),
            targets=(target.reference,),
        )
    )

    assert result.calibration_support_count == 1
    assert "missing_task_visibility" in result.calibration_results[0].reasons
    assert result.status == "not_evaluable"
    assert result.target_results[0].reasons == (
        "source_not_reconstructive",
        "target_package_matches_calibration",
    )


@pytest.mark.parametrize(
    ("verifier_completed", "expected_reason"),
    [
        (True, "source_not_reconstructive"),
        (False, "verifier_incomplete"),
    ],
)
def test_partial_or_unverified_target_is_not_evaluable(
    tmp_path: Path,
    verifier_completed: bool,
    expected_reason: str,
) -> None:
    condition = _condition()
    calibration = _write_record(
        tmp_path,
        experiment_id="calibration",
        trial_id="calibration-001",
        visibility=Visibility.PUBLIC,
        package_sha256="a" * 64,
        reward=1.0,
        condition=condition,
    )
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=0.0,
        condition=condition,
        source_reconstructive=False,
        verifier_completed=verifier_completed,
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.status == "not_evaluable"
    assert expected_reason in result.target_results[0].reasons
    assert result.mean_target_reward is None


def test_partial_calibration_record_cannot_support_the_selected_condition(tmp_path: Path) -> None:
    condition = _condition()
    calibration = _write_record(
        tmp_path,
        experiment_id="calibration",
        trial_id="calibration-001",
        visibility=Visibility.PUBLIC,
        package_sha256="a" * 64,
        reward=1.0,
        condition=condition,
        source_reconstructive=False,
    )
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.calibration_support_count == 0
    assert "source_not_reconstructive" in result.calibration_results[0].reasons
    assert "no_public_calibration_support" in result.target_results[0].reasons


@pytest.mark.parametrize(
    ("updates", "expected_reason"),
    [
        ({"model": "other-model"}, "model_mismatch"),
        ({"adapter": "other-adapter"}, "adapter_mismatch"),
        ({"runtime_dependency_sha256": "2" * 64}, "runtime_dependency_mismatch"),
        (
            {
                "execution_mode": "persistent_context",
                "memory_visibility_policy": "persistent_context",
            },
            "execution_mode_mismatch",
        ),
        ({"memory_visibility_policy": "raw_evidence_only"}, "memory_visibility_policy_mismatch"),
        ({"max_turns_per_session": 21}, "max_turns_per_session_mismatch"),
    ],
)
def test_target_must_match_every_selected_condition_dimension(
    tmp_path: Path,
    updates: dict[str, object],
    expected_reason: str,
) -> None:
    selected = _condition()
    calibration = _write_record(
        tmp_path,
        experiment_id="calibration",
        trial_id="calibration-001",
        visibility=Visibility.PUBLIC,
        package_sha256="a" * 64,
        reward=1.0,
        condition=selected,
    )
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=selected.model_copy(update=updates),
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=selected, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.status == "not_evaluable"
    assert expected_reason in result.target_results[0].reasons
    assert result.mean_target_reward is None


@pytest.mark.parametrize("tamper", ["record", "artifact"])
def test_tampered_record_or_snapshot_artifact_is_not_evaluable(tmp_path: Path, tamper: str) -> None:
    condition = _condition()
    calibration = _write_record(
        tmp_path,
        experiment_id="calibration",
        trial_id="calibration-001",
        visibility=Visibility.PUBLIC,
        package_sha256="a" * 64,
        reward=1.0,
        condition=condition,
    )
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )
    if tamper == "record":
        target.record_path.write_bytes(target.record_path.read_bytes() + b"\n")
        expected_reason = "record_sha256_mismatch"
    else:
        _published_artifact_path(target, "lifecycle_verification").write_text("tampered", encoding="utf-8")
        expected_reason = "record_invalid"

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.status == "not_evaluable"
    assert expected_reason in result.target_results[0].reasons
    assert result.mean_target_reward is None


@pytest.mark.parametrize(
    ("forge_catalog", "expected_status"),
    [(False, "supports_selected_condition"), (True, "not_supporting")],
)
def test_transfer_evaluator_fully_validates_operation_operation_snapshot(
    tmp_path: Path,
    forge_catalog: bool,
    expected_status: str,
) -> None:
    condition = _condition()
    calibration = _upgrade_to_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-operation",
            visibility=Visibility.PUBLIC,
            package_sha256="a" * 64,
            reward=1.0,
            condition=condition,
        ),
        forge_catalog=forge_catalog,
    )
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.calibration_results[0].status == expected_status
    if forge_catalog:
        assert result.calibration_results[0].reasons == ("snapshot_contract_invalid",)
        assert result.status == "not_evaluable"
        assert result.target_results[0].reasons == (
            "no_public_calibration_support",
            "source_not_reconstructive",
        )
    else:
        assert result.calibration_results[0].reasons == ()
        assert result.status == "not_evaluable"
        assert result.target_results[0].reasons == ("source_not_reconstructive",)


def test_transfer_evaluator_rejects_rehashed_malformed_operation_tool_schema(tmp_path: Path) -> None:
    condition = _condition()
    calibration = _upgrade_to_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-operation",
            visibility=Visibility.PUBLIC,
            package_sha256="a" * 64,
            reward=1.0,
            condition=condition,
        ),
        forge_catalog=False,
        forge_tool_schema=True,
    )
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.calibration_results[0].reasons == ("snapshot_contract_invalid",)
    assert result.status == "not_evaluable"


def test_transfer_evaluator_rejects_forged_operation_protocol_tool_projection(tmp_path: Path) -> None:
    condition = _condition()
    calibration = _upgrade_to_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-operation",
            visibility=Visibility.PUBLIC,
            package_sha256="a" * 64,
            reward=1.0,
            condition=condition,
        ),
        forge_catalog=False,
        forge_protocol_tool=True,
    )
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.calibration_results[0].reasons == ("snapshot_contract_invalid",)
    assert result.status == "not_evaluable"


def test_transfer_evaluator_rejects_operation_evidence_state_absent_from_contract(tmp_path: Path) -> None:
    condition = _condition()
    calibration = _upgrade_to_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-operation",
            visibility=Visibility.PUBLIC,
            package_sha256="a" * 64,
            reward=1.0,
            condition=condition,
        ),
        forge_catalog=False,
        forge_evidence_state=True,
    )
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.calibration_results[0].reasons == ("snapshot_contract_invalid",)
    assert result.status == "not_evaluable"


@pytest.mark.parametrize(
    ("namespace", "mutation"),
    [
        ("package", "missing"),
        ("package", "extra"),
        ("package", "mismatched"),
        ("operation", "missing"),
        ("operation", "extra"),
        ("operation", "mismatched"),
    ],
)
def test_transfer_evaluator_reconciles_operation_snapshot_inventory_with_manifest(
    tmp_path: Path,
    namespace: Literal["package", "operation"],
    mutation: Literal["missing", "extra", "mismatched"],
) -> None:
    condition = _condition()
    calibration = _upgrade_to_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-operation",
            visibility=Visibility.PUBLIC,
            package_sha256="a" * 64,
            reward=1.0,
            condition=condition,
        ),
        forge_catalog=False,
    )
    _mutate_operation_snapshot_inventory(calibration, namespace=namespace, mutation=mutation)
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.calibration_results[0].reasons == ("snapshot_contract_invalid",)
    assert result.status == "not_evaluable"


def test_transfer_evaluator_uses_one_exact_prefix_when_snapshot_path_contains_run_component(
    tmp_path: Path,
) -> None:
    condition = _condition()
    calibration = _upgrade_to_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-operation",
            visibility=Visibility.PUBLIC,
            package_sha256="a" * 64,
            reward=1.0,
            condition=condition,
        ),
        forge_catalog=False,
        snapshot_subdirectory="nested/run/archive",
    )
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.calibration_results[0].reasons == ()
    assert result.calibration_results[0].status == "supports_selected_condition"
    assert result.status == "not_evaluable"


def test_transfer_evaluator_replays_nonempty_operation_history_from_reconciled_snapshot_bytes(
    tmp_path: Path,
) -> None:
    condition = _condition()
    calibration = _upgrade_to_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-operation",
            visibility=Visibility.PUBLIC,
            package_sha256="a" * 64,
            reward=1.0,
            condition=condition,
        ),
        forge_catalog=False,
        execute_operation_action=True,
    )
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.calibration_results[0].reasons == ()
    assert result.calibration_results[0].status == "supports_selected_condition"
    assert result.status == "not_evaluable"


def test_transfer_evaluator_binds_action_free_current_source_to_packaged_resolver(
    tmp_path: Path,
) -> None:
    condition = _condition()
    calibration = _upgrade_to_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-operation",
            visibility=Visibility.PUBLIC,
            package_sha256="a" * 64,
            reward=1.0,
            condition=condition,
        ),
        forge_catalog=False,
    )
    _forge_operation_current_source(calibration)
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.calibration_results[0].reasons == ("snapshot_contract_invalid",)
    assert result.status == "not_evaluable"


def test_transfer_evaluator_binds_operation_spec_identity_across_snapshot(tmp_path: Path) -> None:
    condition = _condition()
    calibration = _upgrade_to_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-operation",
            visibility=Visibility.PUBLIC,
            package_sha256="a" * 64,
            reward=1.0,
            condition=condition,
        ),
        forge_catalog=False,
    )
    _forge_operation_spec_semantic_identity(calibration)
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.calibration_results[0].reasons == ("snapshot_contract_invalid",)
    assert result.status == "not_evaluable"


@pytest.mark.parametrize("metadata", ["seal", "sweep_manifest", "sweep_plan"])
def test_transfer_evaluator_validates_operation_canonical_metadata_contents(
    tmp_path: Path,
    metadata: Literal["seal", "sweep_manifest", "sweep_plan"],
) -> None:
    condition = _condition()
    calibration = _upgrade_to_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-operation",
            visibility=Visibility.PUBLIC,
            package_sha256="a" * 64,
            reward=1.0,
            condition=condition,
        ),
        forge_catalog=False,
    )
    _forge_operation_snapshot_metadata(calibration, metadata=metadata)
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.calibration_results[0].reasons == ("snapshot_contract_invalid",)
    assert result.status == "not_evaluable"


def test_transfer_evaluator_binds_operation_visibility_to_validated_package_variant(
    tmp_path: Path,
) -> None:
    condition = _condition()
    calibration = _write_record(
        tmp_path,
        experiment_id="calibration",
        trial_id="calibration-001",
        visibility=Visibility.PUBLIC,
        package_sha256="a" * 64,
        reward=1.0,
        condition=condition,
    )
    target = _upgrade_to_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="target",
            trial_id="target-operation",
            visibility=Visibility.HOLDOUT,
            package_sha256="b" * 64,
            reward=1.0,
            condition=condition,
        ),
        forge_catalog=False,
        manifest_visibility_override="holdout",
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.target_results[0].reasons == (
        "snapshot_contract_invalid",
        "source_not_reconstructive",
    )
    assert result.status == "not_evaluable"


def test_transfer_evaluator_binds_operation_package_template_to_record_task(
    tmp_path: Path,
) -> None:
    condition = _condition()
    calibration = _upgrade_to_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-operation",
            visibility=Visibility.PUBLIC,
            package_sha256="a" * 64,
            reward=1.0,
            condition=condition,
        ),
        forge_catalog=False,
    )
    _forge_operation_package_template(calibration)
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.calibration_results[0].reasons == ("snapshot_contract_invalid",)
    assert result.status == "not_evaluable"


@pytest.mark.parametrize("identity", ["package", "spec"])
def test_transfer_evaluator_recomputes_operation_package_and_spec_identities(
    tmp_path: Path,
    identity: Literal["package", "spec"],
) -> None:
    condition = _condition()
    calibration = _upgrade_to_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-operation",
            visibility=Visibility.PUBLIC,
            package_sha256="a" * 64,
            reward=1.0,
            condition=condition,
        ),
        forge_catalog=False,
    )
    _forge_operation_snapshot_identity(calibration, identity=identity)
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.calibration_results[0].reasons == ("snapshot_contract_invalid",)
    assert result.status == "not_evaluable"


@pytest.mark.parametrize(
    "tampered_field",
    ["reward", "validity_errors", "execution_status", "visibility", "package_sha256"],
)
def test_rehashed_record_fields_must_still_match_the_immutable_snapshot(
    tmp_path: Path,
    tampered_field: str,
) -> None:
    condition = _condition()
    calibration = _write_record(
        tmp_path,
        experiment_id="calibration",
        trial_id="calibration-001",
        visibility=Visibility.PUBLIC,
        package_sha256="a" * 64,
        reward=1.0,
        condition=condition,
        source_reconstructive=True,
    )
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )
    payload = json.loads(calibration.record_path.read_text(encoding="utf-8"))
    if tampered_field == "reward":
        payload["evaluation"]["reward"] = 0.25
    elif tampered_field == "validity_errors":
        payload["evaluation"]["validity"]["errors"] = ["forged"]
    elif tampered_field == "execution_status":
        payload["execution_status"] = "failed"
    elif tampered_field == "visibility":
        payload["input"]["visibility"] = None
    else:
        payload["input"]["task_revision"] = "b" * 64
    calibration.record_path.write_text(json.dumps(payload), encoding="utf-8")
    reference = calibration.reference.model_copy(update={"sha256": _sha256(calibration.record_path)})

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(reference,), targets=(target.reference,))
    )

    assert result.status == "not_evaluable"
    assert "snapshot_record_mismatch" in result.calibration_results[0].reasons
    assert result.mean_target_reward is None


def test_repointed_verification_artifact_must_match_the_invocation_manifest(tmp_path: Path) -> None:
    condition = _condition()
    calibration = _write_record(
        tmp_path,
        experiment_id="calibration",
        trial_id="calibration-001",
        visibility=Visibility.PUBLIC,
        package_sha256="a" * 64,
        reward=1.0,
        condition=condition,
    )
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )
    forged_verification = target.snapshot_path.with_name("forged-verification.json")
    forged_payload = json.loads(target.snapshot_path.read_text(encoding="utf-8"))
    forged_payload["reward"] = 0.25
    forged_verification.write_text(json.dumps(forged_payload), encoding="utf-8")
    forged_reference = ArtifactRepository(target.record_path.parents[1] / "_artifacts").publish_bytes(
        data=forged_verification.read_bytes(),
        media_type="application/json",
    )
    payload = json.loads(target.record_path.read_text(encoding="utf-8"))
    payload["evaluation"]["reward"] = 0.25
    verification_artifact = next(
        item for item in payload["output"]["artifacts"] if item["role"] == "lifecycle_verification"
    )
    verification_artifact["artifact"] = forged_reference.model_dump(mode="json")
    target.record_path.write_text(json.dumps(payload), encoding="utf-8")
    reference = target.reference.model_copy(update={"sha256": _sha256(target.record_path)})

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(reference,))
    )

    assert result.status == "not_evaluable"
    assert "snapshot_record_mismatch" in result.target_results[0].reasons


@pytest.mark.parametrize("integrity_failure", ["missing", "path_escape", "embedded_nul"])
def test_missing_or_escaping_snapshot_artifact_is_not_evaluable(
    tmp_path: Path,
    integrity_failure: str,
) -> None:
    condition = _condition()
    calibration = _write_record(
        tmp_path,
        experiment_id="calibration",
        trial_id="calibration-001",
        visibility=Visibility.PUBLIC,
        package_sha256="a" * 64,
        reward=1.0,
        condition=condition,
    )
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )
    reference = target.reference
    if integrity_failure == "missing":
        _published_artifact_path(target, "lifecycle_verification").unlink()
        expected_reason = "record_invalid"
    else:
        payload = json.loads(target.record_path.read_text(encoding="utf-8"))
        verification_artifact = next(
            item for item in payload["output"]["artifacts"] if item["role"] == "lifecycle_verification"
        )
        verification_artifact["logical_path"] = (
            "../outside.json" if integrity_failure == "path_escape" else "invalid\0artifact.json"
        )
        target.record_path.write_text(json.dumps(payload), encoding="utf-8")
        reference = reference.model_copy(update={"sha256": _sha256(target.record_path)})
        expected_reason = "record_invalid"

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(reference,))
    )

    assert result.status == "not_evaluable"
    assert expected_reason in result.target_results[0].reasons


def test_evidence_request_state_contract_rejects_unknown_checkpoint_id(tmp_path: Path) -> None:
    package = materialize_lifecycle(
        "hydraulic-interaction-lifecycle-review",
        tmp_path / "package",
        variant_id="tailwater_revision",
    )
    run_dir = tmp_path / "run"
    operation_resolver = lifecycle_operation_resolver(package, run_dir)
    assert operation_resolver is not None
    release_checkpoint(package, run_dir, operation_resolver=operation_resolver)
    state = EvidenceLifecycleRunState.model_validate_json((run_dir / "state.json").read_bytes())
    state.checkpoint_runs[0].checkpoint_id = "unknown-checkpoint"
    spec = EvidenceLifecycleSpec.model_validate_json((package / "lifecycle.json").read_bytes())

    with pytest.raises(EvidenceLifecycleError, match="checkpoint state does not match"):
        validate_evidence_request_run_state(state, spec)


def test_incomplete_zero_reward_is_not_misreported_as_holdout_evidence(tmp_path: Path) -> None:
    condition = _condition()
    calibration = _write_record(
        tmp_path,
        experiment_id="calibration",
        trial_id="calibration-001",
        visibility=Visibility.PUBLIC,
        package_sha256="a" * 64,
        reward=1.0,
        condition=condition,
    )
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=0.0,
        condition=condition,
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.status == "not_evaluable"
    assert result.eligible_target_count == 0
    assert result.mean_target_reward is None
    assert result.target_results[0].reasons == ("source_not_reconstructive",)
    assert result.target_results[0].verifier_validity is None


def test_input_order_does_not_change_evaluation_identity_or_summary(tmp_path: Path) -> None:
    condition = _condition()
    calibrations = tuple(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id=f"calibration-{index}",
            visibility=Visibility.PUBLIC,
            package_sha256=character * 64,
            reward=1.0,
            condition=condition,
        )
        for index, character in enumerate(("a", "b"), start=1)
    )
    targets = tuple(
        _write_record(
            tmp_path,
            experiment_id="target",
            trial_id=f"target-{index}",
            visibility=Visibility.HOLDOUT,
            package_sha256=character * 64,
            reward=reward,
            condition=condition,
        )
        for index, (character, reward) in enumerate((("c", 0.25), ("d", 0.75)), start=1)
    )

    forward = build_lifecycle_transfer_evaluation(
        _spec(
            condition=condition,
            calibration=tuple(item.reference for item in calibrations),
            targets=tuple(item.reference for item in targets),
        )
    )
    reverse = build_lifecycle_transfer_evaluation(
        _spec(
            condition=condition,
            calibration=tuple(item.reference for item in reversed(calibrations)),
            targets=tuple(item.reference for item in reversed(targets)),
        )
    )

    assert forward == reverse
    assert forward.mean_target_reward is None


def test_cloned_record_identity_cannot_reuse_one_immutable_invocation(tmp_path: Path) -> None:
    condition = _condition()
    calibration = _write_record(
        tmp_path,
        experiment_id="calibration",
        trial_id="calibration-001",
        visibility=Visibility.PUBLIC,
        package_sha256="a" * 64,
        reward=1.0,
        condition=condition,
    )
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )
    clone_path = target.record_path.with_name("target-002.json")
    clone_payload = json.loads(target.record_path.read_text(encoding="utf-8"))
    clone_payload["trial_id"] = "target-002"
    clone_path.write_text(json.dumps(clone_payload), encoding="utf-8")
    clone_reference = LifecycleTransferRecordReference(
        experiment_id="target",
        trial_id="target-002",
        ledger_path=str(clone_path),
        sha256=_sha256(clone_path),
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(
            condition=condition,
            calibration=(calibration.reference,),
            targets=(target.reference, clone_reference),
        )
    )

    assert result.eligible_target_count == 0
    assert result.target_results[0].reasons == ("source_not_reconstructive",)
    assert result.target_results[1].status == "not_evaluable"
    assert "snapshot_record_mismatch" in result.target_results[1].reasons


def test_malformed_verifier_result_cannot_support_evaluation(tmp_path: Path) -> None:
    condition = _condition()
    calibration = _write_record(
        tmp_path,
        experiment_id="calibration",
        trial_id="calibration-001",
        visibility=Visibility.PUBLIC,
        package_sha256="a" * 64,
        reward=1.0,
        condition=condition,
        verification_overall="nonsense",
    )
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.calibration_support_count == 0
    assert "snapshot_contract_invalid" in result.calibration_results[0].reasons


@pytest.mark.parametrize(
    ("verification_lifecycle_id", "verification_template_id"),
    [
        ("wrong-lifecycle", "drainage-model-evidence-lifecycle-review"),
        ("lifecycle-calibration-001", "wrong-template"),
    ],
)
def test_verifier_identity_must_match_the_lifecycle_record(
    tmp_path: Path,
    verification_lifecycle_id: str,
    verification_template_id: str,
) -> None:
    condition = _condition()
    calibration = _write_record(
        tmp_path,
        experiment_id="calibration",
        trial_id="calibration-001",
        visibility=Visibility.PUBLIC,
        package_sha256="a" * 64,
        reward=1.0,
        condition=condition,
        verification_lifecycle_id=verification_lifecycle_id,
        verification_template_id=verification_template_id,
    )
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.calibration_support_count == 0
    assert "snapshot_record_mismatch" in result.calibration_results[0].reasons


@pytest.mark.parametrize("value", [True, 20.0, "20"])
def test_recorded_condition_turn_limit_is_a_strict_integer(value: object) -> None:
    payload = LifecycleExecutionRecord(
        execution_mode="fresh_context",
        memory_visibility_policy="artifact_memory",
        max_turns_per_session=20,
        status="completed",
        sessions=[
            LifecycleSessionRecord(
                session_id="session-001",
                adapter="tool_loop",
                resolved_model="model-a",
                status="completed",
            )
        ],
    ).model_dump(mode="json")
    payload["max_turns_per_session"] = value

    with pytest.raises(ValidationError, match="positive integer"):
        LifecycleExecutionRecord.model_validate(payload)


def test_duplicate_record_references_are_rejected(tmp_path: Path) -> None:
    condition = _condition()
    calibration = _write_record(
        tmp_path,
        experiment_id="calibration",
        trial_id="calibration-001",
        visibility=Visibility.PUBLIC,
        package_sha256="a" * 64,
        reward=1.0,
        condition=condition,
    )
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )

    with pytest.raises(ValidationError, match="duplicate lifecycle transfer record reference"):
        _spec(
            condition=condition,
            calibration=(calibration.reference, calibration.reference),
            targets=(target.reference,),
        )


def test_path_aliases_cannot_duplicate_one_physical_record(tmp_path: Path) -> None:
    condition = _condition()
    calibration = _write_record(
        tmp_path,
        experiment_id="calibration",
        trial_id="calibration-001",
        visibility=Visibility.PUBLIC,
        package_sha256="a" * 64,
        reward=1.0,
        condition=condition,
    )
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=Visibility.HOLDOUT,
        package_sha256="b" * 64,
        reward=1.0,
        condition=condition,
    )
    alias_path = target.record_path.parent / ".." / target.record_path.parent.name / target.record_path.name
    alias = target.reference.model_copy(update={"ledger_path": str(alias_path)})

    with pytest.raises(ValidationError, match="canonical"):
        _spec(
            condition=condition,
            calibration=(calibration.reference,),
            targets=(target.reference, alias),
        )


@pytest.mark.parametrize("value", [True, 1.0, "1"])
def test_selected_condition_turn_limit_is_a_strict_integer(value: object) -> None:
    payload = _condition().model_dump(mode="json")
    payload["max_turns_per_session"] = value

    with pytest.raises(ValidationError, match="positive integer"):
        LifecycleTransferCondition.model_validate(payload)


def _spec(
    *,
    condition: LifecycleTransferCondition,
    calibration: tuple[LifecycleTransferRecordReference, ...],
    targets: tuple[LifecycleTransferRecordReference, ...],
) -> LifecycleTransferEvaluationSpec:
    return LifecycleTransferEvaluationSpec(
        study_design=LifecycleTransferStudyDesign(
            interpretation="descriptive_holdout_generalization",
            selection_basis="public_calibration",
            causal_effects_supported=False,
            cross_run_learning_supported=False,
        ),
        selected_condition=condition,
        public_calibration_records=calibration,
        holdout_target_records=targets,
    )


def _condition() -> LifecycleTransferCondition:
    return LifecycleTransferCondition(
        model="model-a",
        adapter="tool_loop",
        runtime_dependency_sha256=_RUNTIME_SHA256,
        execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
        memory_visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
        max_turns_per_session=20,
    )


class _WrittenRecord:
    def __init__(
        self,
        *,
        reference: LifecycleTransferRecordReference,
        record_path: Path,
        snapshot_path: Path,
    ) -> None:
        self.reference = reference
        self.record_path = record_path
        self.snapshot_path = snapshot_path


def _published_artifact_path(written: _WrittenRecord, kind: str) -> Path:
    ledger_root = written.record_path.parents[1]
    record = read_trial_record(written.record_path, ledger_root=ledger_root)
    artifact = next(item.artifact for item in record.outputs.artifacts if item.role == kind)
    return ledger_root / "_artifacts" / artifact.artifact_id


def _write_record(
    tmp_path: Path,
    *,
    experiment_id: str,
    trial_id: str,
    visibility: Visibility | None,
    package_sha256: str,
    reward: float,
    condition: LifecycleTransferCondition,
    source_reconstructive: bool | None = None,
    verifier_completed: bool = True,
    semantic_transition: dict[str, object] | None = None,
    repository_kind: Literal["git", "source_tree"] | None = None,
    verification_overall: str | None = None,
    verification_lifecycle_id: str | None = None,
    verification_template_id: str = "drainage-model-evidence-lifecycle-review",
) -> _WrittenRecord:
    reconstructive = visibility is Visibility.PUBLIC if source_reconstructive is None else source_reconstructive
    record_repository_kind = repository_kind or ("git" if reconstructive else "source_tree")
    source_revision = "a" * 40
    repository_commit = source_revision if record_repository_kind == "git" else "source-tree"
    execution_mode: Literal["persistent_context", "fresh_context"] = LifecycleExecutionMode(
        condition.execution_mode
    ).value
    memory_visibility_policy: Literal[
        "persistent_context",
        "artifact_memory",
        "raw_evidence_only",
        "current_release_only",
    ] = LifecycleVisibilityPolicy(condition.memory_visibility_policy).value
    ledger_root = tmp_path / "ledger"
    artifact_root = ledger_root / experiment_id / "_artifacts" / trial_id
    artifact_root.mkdir(parents=True, exist_ok=True)
    snapshot_path = artifact_root / "verification.json"
    verification_payload: dict[str, object] = {
        "reward": reward,
        "overall": verification_overall or ("pass" if verifier_completed else "incomplete"),
        "lifecycle_id": verification_lifecycle_id or f"lifecycle-{trial_id}",
        "template_id": verification_template_id,
        "passed": verifier_completed,
        "gates": {
            "terminal": {
                "passed": verifier_completed,
                "score": reward,
                "failures": [] if verifier_completed else ["incomplete"],
            }
        },
    }
    if semantic_transition is not None:
        verification_payload["semantic_metrics"] = semantic_transition
    snapshot_path.write_text(json.dumps(verification_payload, sort_keys=True), encoding="utf-8")
    snapshot = ArtifactReference(
        kind="lifecycle_verification",
        path=snapshot_path.relative_to(ledger_root).as_posix(),
        sha256=_sha256(snapshot_path),
        media_type="application/json",
    )
    lifecycle_spec = EvidenceLifecycleSpec(
        lifecycle_id=f"lifecycle-{trial_id}",
        checkpoints=[
            EvidenceCheckpointSpec(
                checkpoint_id="initial",
                title="Initial review",
                release_path="releases/initial",
                instruction_path="instructions/initial.md",
                submission_path="submissions/initial.json",
            ),
            EvidenceCheckpointSpec(
                checkpoint_id="corrected",
                title="Corrected review",
                release_path="releases/corrected",
                instruction_path="instructions/corrected.md",
                submission_path="submissions/corrected.json",
                depends_on=["initial"],
            ),
        ],
    )
    lifecycle_spec_path = artifact_root / "package" / "lifecycle.json"
    lifecycle_spec_path.parent.mkdir(parents=True, exist_ok=True)
    lifecycle_spec_path.write_text(lifecycle_spec.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")
    lifecycle_spec_sha256 = _canonical_sha256(lifecycle_spec.model_dump(mode="json", exclude_none=True))
    lifecycle_spec_reference = ArtifactReference(
        kind="lifecycle_package",
        path=lifecycle_spec_path.relative_to(ledger_root).as_posix(),
        sha256=_sha256(lifecycle_spec_path),
        media_type="application/json",
    )
    state_payload = {
        "schema_version": "6",
        "lifecycle_id": f"lifecycle-{trial_id}",
        "lifecycle_spec_sha256": lifecycle_spec_sha256,
        "package_sha256": package_sha256,
        "status": "complete",
        "active_checkpoint_id": None,
        "checkpoint_runs": [
            {
                "checkpoint_id": checkpoint_id,
                "status": "submitted",
                "submission_path": f"episodes/{checkpoint_id}/submission.json",
                "submission_sha256": "7" * 64,
            }
            for checkpoint_id in ("initial", "corrected")
        ],
    }
    state_path = artifact_root / "state.json"
    state_path.write_text(json.dumps(state_payload, sort_keys=True), encoding="utf-8")
    state_reference = ArtifactReference(
        kind="lifecycle_state",
        path=state_path.relative_to(ledger_root).as_posix(),
        sha256=_sha256(state_path),
        media_type="application/json",
    )
    metrics = LifecycleExperimentMetrics(
        checkpoint_count=len(lifecycle_spec.checkpoints),
        requests=0,
        tool_calls=0,
        reads=0,
        revisits=0,
        retries=0,
        failures=0,
        input_tokens=0,
        output_tokens=0,
        cache_read_tokens=0,
        cache_write_tokens=0,
    )
    metrics_path = artifact_root / "metrics.json"
    metrics_path.write_text(json.dumps(metrics.model_dump(mode="json"), sort_keys=True), encoding="utf-8")
    metrics_reference = ArtifactReference(
        kind="lifecycle_metrics",
        path=metrics_path.relative_to(ledger_root).as_posix(),
        sha256=_sha256(metrics_path),
        media_type="application/json",
    )
    invocation_path = artifact_root / "experiment-manifest.json"
    visibility_value = visibility.value if visibility is not None else None
    invocation_payload = {
        "schema_version": "1",
        "experiment_id": f"invocation-{trial_id}",
        "created_at": "2026-07-12T00:00:00+00:00",
        "repository": {
            "commit": repository_commit,
            "repository_kind": record_repository_kind,
            "dirty": False,
            "dirty_digest": "4" * 64,
        },
        "environment": {
            "runtime_provenance": {
                "provider": "local",
                "distributions": ["aec-bench==0.1.0"],
                "dependency_inventory_sha256": condition.runtime_dependency_sha256,
            }
        },
        "lifecycle": {
            "lifecycle_id": f"lifecycle-{trial_id}",
            "spec_sha256": lifecycle_spec_sha256,
            "package_sha256": package_sha256,
            "variant": {"visibility": visibility_value},
        },
        "verifier": {
            "qualified_name": "tests.verify",
            "source_sha256": "5" * 64,
        },
        "model": {
            "resolved_models": [condition.model],
            "resolved_adapters": [condition.adapter],
        },
        "execution": {
            "mode": condition.execution_mode,
            "memory_visibility_policy": condition.memory_visibility_policy,
            "max_turns_per_session": condition.max_turns_per_session,
            "status": "completed",
            "session_count": 1,
        },
        "interaction": {},
        "sweep": {
            "schema_version": "1",
            "sweep_experiment_id": experiment_id,
            "planned_trial_id": trial_id,
            "plan_sha256": "6" * 64,
            "condition_id": f"{condition.execution_mode}__{condition.memory_visibility_policy}",
            "repetition": 1,
        },
        "outputs": {
            "verification.json": snapshot.sha256,
            "metrics.json": metrics_reference.sha256,
            "artifacts": {
                "verification.json": snapshot.sha256,
                "metrics.json": metrics_reference.sha256,
                "state.json": state_reference.sha256,
                "package/lifecycle.json": lifecycle_spec_reference.sha256,
            },
        },
    }
    invocation_path.write_text(json.dumps(invocation_payload, sort_keys=True), encoding="utf-8")
    invocation = ArtifactReference(
        kind="lifecycle_manifest",
        path=invocation_path.relative_to(ledger_root).as_posix(),
        sha256=_sha256(invocation_path),
        media_type="application/json",
    )
    index_path = artifact_root / "index-entry.json"
    index_path.write_text(
        json.dumps(
            {
                "experiment_id": invocation_payload["experiment_id"],
                "manifest_sha256": _sha256(invocation_path),
                "sweep": invocation_payload["sweep"],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    invocation_index = ArtifactReference(
        kind="lifecycle_invocation_index",
        path=index_path.relative_to(ledger_root).as_posix(),
        sha256=_sha256(index_path),
        media_type="application/json",
    )
    ablation_manifest_path = artifact_root / "ablation-manifest.json"
    ablation_manifest_path.write_text(json.dumps({"schema_version": "1"}, sort_keys=True), encoding="utf-8")
    ablation_manifest = ArtifactReference(
        kind="lifecycle_ablation_manifest",
        path=ablation_manifest_path.relative_to(ledger_root).as_posix(),
        sha256=_sha256(ablation_manifest_path),
        media_type="application/json",
    )
    ablation_plan_path = artifact_root / "ablation-plan.json"
    ablation_plan_path.write_text(json.dumps({"schema_version": "1"}, sort_keys=True), encoding="utf-8")
    ablation_plan = ArtifactReference(
        kind="lifecycle_ablation_plan",
        path=ablation_plan_path.relative_to(ledger_root).as_posix(),
        sha256=_sha256(ablation_plan_path),
        media_type="application/json",
    )
    breakdown = {
        "lifecycle_gates": verification_payload["gates"],
        "semantic_transition": semantic_transition,
        "operational_metrics": {},
    }
    started_at = datetime(2026, 7, 12, tzinfo=UTC)
    run_id = f"{experiment_id}:{condition.adapter}:{condition.model}:local"
    manifest = RunManifest(
        run_id=run_id,
        experiment_id=experiment_id,
        source=(
            GitSourceRef(revision=source_revision)
            if reconstructive
            else UnresolvedSourceRef(reason="test fixture omits reconstructive source bytes")
        ),
        agent=AgentReference(
            adapter=condition.adapter,
            model=condition.model,
            adapter_revision=(source_revision if reconstructive else None),
            configuration={},
        ),
        execution_environment=EnvironmentSnapshot(
            runtime_image="python:3.13",
            compute_backend="local",
            tool_versions={"aec_bench": source_revision},
        ),
        provider_route=ProviderRoute(provider="local", route=condition.adapter),
        expected_authorities=(
            AuthorityExpectation(
                authority_kind=AuthorityEvidenceKind.LIFECYCLE,
                protocol="aec-bench/lifecycle-evidence/1",
            ),
        ),
    )
    record = TrialRecord(
        trial_id=trial_id,
        run_id=run_id,
        task_id="drainage-model-evidence-lifecycle-review",
        execution_status=ExecutionStatus.COMPLETED,
        evaluation_status=EvaluationStatus.COMPLETED,
        evidence_status=EvidenceStatus.PENDING,
        started_at=started_at,
        completed_at=started_at.replace(second=1),
        input=InputRecord(
            instruction="Review the evolving evidence.",
            task_revision=package_sha256,
            task_kind="lifecycle",
            visibility=visibility,
        ),
        output=OutputRecord(),
        evaluation=EvaluationResult(
            reward=reward,
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=verifier_completed,
                verifier_completed=verifier_completed,
                errors=[] if verifier_completed else ["terminal:incomplete"],
            ),
            breakdown=breakdown,
        ),
        timing=TimingRecord(total_seconds=1.0),
    ).bind_run_manifest(manifest)
    record.attach_extension(
        "lifecycle_execution",
        LifecycleExecutionRecord(
            execution_mode=execution_mode,
            memory_visibility_policy=memory_visibility_policy,
            max_turns_per_session=condition.max_turns_per_session,
            status="completed",
            sessions=[
                LifecycleSessionRecord(
                    session_id=f"{trial_id}-session",
                    checkpoint_ids=["initial", "corrected"],
                    requested_adapter=condition.adapter,
                    adapter=condition.adapter,
                    resolved_model=condition.model,
                    execution_mode=execution_mode,
                    memory_visibility_policy=memory_visibility_policy,
                    status="completed",
                    artifacts=[snapshot],
                )
            ],
        ),
    )
    record.attach_extension(
        "lifecycle_provenance",
        LifecycleTrialProvenance(
            lifecycle_id=f"lifecycle-{trial_id}",
            spec_sha256=lifecycle_spec_sha256,
            package_sha256=package_sha256,
            repository_commit=repository_commit,
            repository_kind=record_repository_kind,
            repository_dirty=False,
            repository_dirty_digest="4" * 64,
            runtime_provider="local",
            runtime_distributions=("aec-bench==0.1.0",),
            runtime_dependency_sha256=condition.runtime_dependency_sha256,
            verifier_qualified_name="tests.verify",
            verifier_source_sha256="5" * 64,
            invocation_manifest=invocation,
            invocation_index=invocation_index,
            ablation_manifest=ablation_manifest,
            ablation_plan=ablation_plan,
        ),
    )
    retained = (
        snapshot,
        state_reference,
        metrics_reference,
        lifecycle_spec_reference,
        invocation,
        invocation_index,
        ablation_manifest,
        ablation_plan,
    )
    for artifact in retained:
        role = (
            f"authority:{AuthorityEvidenceKind.LIFECYCLE.value}:aec-bench/lifecycle-evidence/1"
            if artifact == invocation
            else f"output:{artifact.kind}:{artifact.sha256}"
        )
        record.attach_artifact(
            role,
            ledger_root / artifact.path,
            media_type=artifact.media_type,
            logical_path=(None if artifact == invocation else artifact.path),
        )
    record_path = write_trial_record(ledger_root=ledger_root, record=record)
    return _WrittenRecord(
        reference=LifecycleTransferRecordReference(
            experiment_id=experiment_id,
            trial_id=trial_id,
            ledger_path=str(record_path),
            sha256=_sha256(record_path),
        ),
        record_path=record_path,
        snapshot_path=snapshot_path,
    )


def _upgrade_to_operation_snapshot(
    written: _WrittenRecord,
    *,
    forge_catalog: bool,
    forge_evidence_state: bool = False,
    forge_tool_schema: bool = False,
    forge_protocol_tool: bool = False,
    snapshot_subdirectory: str | None = None,
    execute_operation_action: bool = False,
    manifest_visibility_override: Literal["public", "holdout"] | None = None,
) -> _WrittenRecord:
    record = read_trial_record(written.record_path)
    assert record.lifecycle_provenance is not None
    assert record.outputs.artifacts is not None
    ledger_root = written.record_path.parent.parent
    original_artifact_root = written.snapshot_path.parent
    artifact_root = (
        original_artifact_root / snapshot_subdirectory if snapshot_subdirectory is not None else original_artifact_root
    )
    run_root = artifact_root / "run"
    package_root = artifact_root / "package"
    base_lifecycle_path = package_root / "lifecycle.json"
    if base_lifecycle_path.exists():
        base_lifecycle_path.unlink()
        package_root.rmdir()
    materialize_lifecycle(
        "hydraulic-interaction-lifecycle-review",
        package_root,
        variant_id="tailwater_revision",
    )
    package_variant = lifecycle_package_variant(package_root)
    assert package_variant is not None
    validated_spec = EvidenceLifecycleSpec.model_validate_json((package_root / "lifecycle.json").read_bytes())
    operation_resolver = lifecycle_operation_resolver(package_root, run_root)
    assert operation_resolver is not None
    for checkpoint_number, checkpoint in enumerate(validated_spec.checkpoints, start=1):
        release_checkpoint(package_root, run_root, operation_resolver=operation_resolver)
        open_checkpoint_attempt(
            package_root,
            run_root,
            operation_resolver=operation_resolver,
            session_id=f"fixture.session-{checkpoint_number:03d}",
            execution_mode="fresh_context",
        )
        if execute_operation_action and checkpoint_number == 1:
            current_source = json.loads(
                (run_root / "workspace" / "operations" / "current-source.json").read_text(encoding="utf-8")
            )
            execute_lifecycle_operation(
                package_root,
                run_root,
                operation_resolver=operation_resolver,
                checkpoint_id=checkpoint.checkpoint_id,
                operation_id="hydrology.design-10yr",
                visible_source_state_sha256=str(current_source["visible_source_state_sha256"]),
                reason="Exercise immutable transfer replay.",
                session_id=f"fixture.session-{checkpoint_number:03d}",
            )
        submission: dict[str, object] = {field: {} for field in checkpoint.required_submission_fields}
        submission["checkpoint_id"] = checkpoint.checkpoint_id
        submission_path = run_root / "workspace" / checkpoint.submission_path
        submission_path.parent.mkdir(parents=True, exist_ok=True)
        submission_path.write_text(json.dumps(submission, sort_keys=True), encoding="utf-8")
        submit_checkpoint(package_root, run_root, operation_resolver=operation_resolver)

    state_path = run_root / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if forge_evidence_state:
        state["checkpoint_runs"][0]["evidence_request_budget"] = 1
        state["checkpoint_runs"][0]["evidence_request_budget_remaining"] = 1
        state_path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    if forge_catalog:
        catalog_path = run_root / "workspace" / "checkpoints" / "revision_analysis" / "operations.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        catalog["operations"][0]["title"] = "Forged catalogue title"
        catalog_path.write_text(json.dumps(catalog, sort_keys=True), encoding="utf-8")

    spec_sha256 = _canonical_sha256(validated_spec.model_dump(mode="json", exclude_none=True))
    package_sha256 = _package_sha256(package_root)
    assert state["lifecycle_spec_sha256"] == spec_sha256
    assert state["package_sha256"] == package_sha256
    operation_actions = [
        action for checkpoint in state["checkpoint_runs"] for action in checkpoint["operation_actions"]
    ]

    metrics = LifecycleExperimentMetrics(
        checkpoint_count=len(validated_spec.checkpoints),
        requests=0,
        tool_calls=0,
        reads=0,
        revisits=0,
        operation_calls=len(operation_actions),
        completed_operations=sum(action["outcome"] == "completed" for action in operation_actions),
        already_current_operations=sum(action["outcome"] == "already_current" for action in operation_actions),
        rejected_operations=sum(action["outcome"] == "rejected" for action in operation_actions),
        operation_budget_consumed=sum(action["budget_consumed"] for action in operation_actions),
        operation_artifacts_produced=sum(
            len(action["artifacts"]) for action in operation_actions if action["outcome"] == "completed"
        ),
        retries=0,
        failures=0,
        input_tokens=0,
        output_tokens=0,
        cache_read_tokens=0,
        cache_write_tokens=0,
    )
    metrics_payload = metrics.model_dump(mode="json")
    metrics_path = run_root / "metrics.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics_payload, sort_keys=True), encoding="utf-8")
    verification_path = run_root / "verification.json"
    verification = json.loads(written.snapshot_path.read_text(encoding="utf-8"))
    verification["lifecycle_id"] = validated_spec.lifecycle_id
    verification["template_id"] = "hydraulic-interaction-lifecycle-review"
    verification_path.write_text(json.dumps(verification, sort_keys=True), encoding="utf-8")

    original_invocation_path = original_artifact_root / "experiment-manifest.json"
    invocation = json.loads(original_invocation_path.read_text(encoding="utf-8"))
    required_arguments = [
        "checkpoint_id",
        "operation_id",
        "visible_source_state_sha256",
        "reason",
    ]
    argument_titles = {
        "checkpoint_id": "Checkpoint Id",
        "operation_id": "Operation Id",
        "visible_source_state_sha256": "Visible Source State Sha256",
        "reason": "Reason",
    }
    properties: dict[str, dict[str, object]] = {
        argument: {"title": argument_titles[argument], "type": "string"} for argument in required_arguments
    }
    if forge_tool_schema:
        properties["reason"]["enum"] = []
    tool_schema = [
        {
            "name": "execute_operation",
            "description": "Execute one declared lifecycle operation.",
            "parameters": {
                "type": "object",
                "title": "execute_operation_args",
                "properties": properties,
                "required": required_arguments,
                "additionalProperties": False,
            },
        }
    ]
    encoded_tool_schema = json.dumps(tool_schema, sort_keys=True, separators=(",", ":")).encode("utf-8")
    protocol = {
        **lifecycle_operation_protocol_identity(),
        "tool_schema_sha256": hashlib.sha256(encoded_tool_schema).hexdigest(),
    }
    if forge_protocol_tool:
        protocol["tool"] = {
            "name": "execute_operation",
            "arguments": required_arguments[:-1],
        }
    invocation["interaction"] = {
        "tool_schema": tool_schema,
        "lifecycle_operation_protocol": protocol,
    }
    package_hashes = {
        path.relative_to(package_root).as_posix(): _sha256(path)
        for path in sorted(package_root.rglob("*"))
        if path.is_file()
    }
    run_hashes = experiment_runtime._run_artifact_hashes(run_root)
    invocation["lifecycle"].update(
        {
            "lifecycle_id": validated_spec.lifecycle_id,
            "spec_sha256": spec_sha256,
            "package_sha256": package_sha256,
            "package_files": package_hashes,
            "variant": {
                **package_variant,
                **({"visibility": manifest_visibility_override} if manifest_visibility_override is not None else {}),
            },
        }
    )
    ablation_manifest, ablation_plan, selected_trial = _operation_ablation_metadata(
        record,
        artifact_root=artifact_root,
        package_sha256=package_sha256,
        spec_sha256=spec_sha256,
        lifecycle_id=validated_spec.lifecycle_id,
    )
    invocation["sweep"] = {
        "schema_version": "1",
        "sweep_experiment_id": ablation_manifest.experiment_id,
        "planned_trial_id": selected_trial.trial_id,
        "plan_sha256": ablation_plan.plan_sha256,
        "condition_id": (f"{selected_trial.execution_mode.value}__{selected_trial.memory_visibility_policy.value}"),
        "repetition": selected_trial.repetition,
    }
    invocation["outputs"] = {
        "verification.json": run_hashes["verification.json"],
        "metrics.json": run_hashes["metrics.json"],
        "artifacts": run_hashes,
    }
    invocation_experiment_id = str(invocation["experiment_id"])
    canonical_dir = run_root / "experiments" / invocation_experiment_id
    canonical_dir.mkdir(parents=True, exist_ok=True)
    invocation_path = canonical_dir / "experiment-manifest.json"
    invocation_path.write_text(json.dumps(invocation, sort_keys=True), encoding="utf-8")
    canonical_metrics_path = canonical_dir / "metrics.json"
    canonical_metrics_path.write_bytes(metrics_path.read_bytes())
    canonical_verification_path = canonical_dir / "verification.json"
    canonical_verification_path.write_bytes(verification_path.read_bytes())
    index = {
        "experiment_id": invocation_experiment_id,
        "manifest_sha256": _sha256(invocation_path),
        "sweep": invocation["sweep"],
    }
    seal_path = canonical_dir / "index-entry.json"
    seal_path.write_text(
        json.dumps({**index, "manifest_path": "experiment-manifest.json"}, sort_keys=True),
        encoding="utf-8",
    )
    index_path = artifact_root / "experiment-index.jsonl"
    index_path.write_text(
        json.dumps(
            {
                **index,
                "manifest_path": f"run/experiments/{invocation_experiment_id}/experiment-manifest.json",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    sweep_root = artifact_root / "sweep"
    sweep_root.mkdir(parents=True, exist_ok=True)
    sweep_manifest_path = sweep_root / "manifest.json"
    sweep_manifest_path.write_text(
        json.dumps(ablation_manifest.model_dump(mode="json"), sort_keys=True),
        encoding="utf-8",
    )
    sweep_plan_path = sweep_root / "plan.json"
    sweep_plan_path.write_text(
        json.dumps(ablation_plan.model_dump(mode="json"), sort_keys=True),
        encoding="utf-8",
    )

    snapshot_paths = [
        *(package_root / relative for relative in sorted(package_hashes)),
        *(run_root / relative for relative in sorted(run_hashes)),
        invocation_path,
        canonical_metrics_path,
        canonical_verification_path,
        seal_path,
        index_path,
        sweep_manifest_path,
        sweep_plan_path,
    ]
    references = [
        ArtifactReference(
            kind=_snapshot_artifact_kind(path.relative_to(artifact_root)),
            path=path.relative_to(ledger_root).as_posix(),
            sha256=_sha256(path),
            media_type="application/json",
        )
        for path in snapshot_paths
    ]
    reference_by_kind = {reference.kind: reference for reference in references}
    verification_reference = reference_by_kind["lifecycle_verification"]
    invocation_reference = reference_by_kind["lifecycle_manifest"]
    index_reference = reference_by_kind["lifecycle_invocation_index"]
    ablation_manifest_reference = reference_by_kind["lifecycle_ablation_manifest"]
    ablation_plan_reference = reference_by_kind["lifecycle_ablation_plan"]
    breakdown = dict(record.evaluation.breakdown or {})
    operational_metrics = dict(metrics_payload)
    operational_metrics.pop("semantic_transition", None)
    breakdown["operational_metrics"] = operational_metrics
    evaluation = record.evaluation.model_copy(update={"breakdown": breakdown})
    provenance = record.lifecycle_provenance.model_copy(
        update={
            "lifecycle_id": validated_spec.lifecycle_id,
            "spec_sha256": spec_sha256,
            "package_sha256": package_sha256,
            "invocation_manifest": invocation_reference,
            "invocation_index": index_reference,
            "ablation_manifest": ablation_manifest_reference,
            "ablation_plan": ablation_plan_reference,
        }
    )
    execution = record.lifecycle_execution
    assert execution is not None
    execution = execution.model_copy(
        update={
            "sessions": [
                session.model_copy(
                    update={
                        "checkpoint_ids": [checkpoint.checkpoint_id for checkpoint in validated_spec.checkpoints],
                        "artifacts": [verification_reference],
                    }
                )
                for session in execution.sessions
            ]
        }
    )
    updated = record.model_copy(
        update={
            "task_id": "hydraulic-interaction-lifecycle-review",
            "input": record.input.model_copy(update={"task_revision": package_sha256}),
            "evaluation": evaluation,
        }
    )
    _rewrite_trial_record(
        written,
        updated,
        artifacts=references,
        lifecycle_execution=execution,
        lifecycle_provenance=provenance,
    )
    written.snapshot_path = verification_path
    return written


def _operation_ablation_metadata(
    record: TrialRecord,
    *,
    artifact_root: Path,
    package_sha256: str,
    spec_sha256: str,
    lifecycle_id: str,
) -> tuple[LifecycleAblationManifest, LifecycleAblationPlan, LifecycleAblationTrial]:
    assert record.lifecycle_execution is not None
    assert record.lifecycle_provenance is not None
    execution_mode = LifecycleExecutionMode(record.lifecycle_execution.execution_mode)
    visibility_policy = LifecycleVisibilityPolicy(record.lifecycle_execution.memory_visibility_policy)
    manifest = LifecycleAblationManifest(
        experiment_id=record.experiment_id,
        lifecycle_template_id="hydraulic-interaction-lifecycle-review",
        variants=("tailwater_revision",),
        agents=(
            AgentConfig(
                name="transfer-fixture",
                adapter=record.agent.adapter,
                model=record.agent.model,
                parameters={"max_turns_per_session": record.lifecycle_execution.max_turns_per_session},
            ),
        ),
        study_design=LifecycleAblationStudyDesign(
            interpretation="descriptive_calibration",
            turn_budget_scope="per_session",
            execution_order="deterministic_sequential_plan_order",
            randomized=False,
            counterbalanced=False,
            causal_effects_supported=False,
        ),
        conditions=(
            LifecycleAblationCondition(
                execution_mode=execution_mode,
                memory_visibility_policy=visibility_policy,
            ),
        ),
        output_root=str(artifact_root / "planned-output"),
        ledger_root=str(artifact_root / "planned-ledger"),
        limits=LifecycleAblationLimits(max_trials=1),
    )
    planned = build_lifecycle_ablation_plan(manifest)
    selected = planned.trials[0].model_copy(
        update={
            "trial_id": record.trial_id,
            "lifecycle_id": lifecycle_id,
            "spec_sha256": spec_sha256,
            "package_sha256": package_sha256,
            "runtime_provenance": LifecycleRuntimeProvenance(
                adapter=planned.trials[0].runtime_provenance.adapter,
                provider=record.lifecycle_provenance.runtime_provider,
                distributions=record.lifecycle_provenance.runtime_distributions,
                dependency_inventory_sha256=record.lifecycle_provenance.runtime_dependency_sha256,
            ),
            "max_turns_per_session": record.lifecycle_execution.max_turns_per_session,
            "execution_mode": execution_mode,
            "memory_visibility_policy": visibility_policy,
            "package_dir": str(artifact_root / "package"),
            "run_dir": str(artifact_root / "run"),
            "ledger_path": str(artifact_root / "ledger" / record.experiment_id / f"{record.trial_id}.json"),
        }
    )
    plan_payload = planned.model_dump(mode="json", exclude={"plan_sha256"})
    plan_payload["trials"] = [selected.model_dump(mode="json")]
    plan_payload["trial_count"] = 1
    plan = LifecycleAblationPlan.model_validate(
        {
            **plan_payload,
            "plan_sha256": _canonical_sha256(plan_payload),
        }
    )
    return manifest, plan, plan.trials[0]


def _snapshot_artifact_kind(relative: Path) -> str:
    path = relative.as_posix()
    if path.startswith("run/experiments/") and path.endswith("/experiment-manifest.json"):
        return "lifecycle_manifest"
    if path.startswith("run/experiments/") and path.endswith("/index-entry.json"):
        return "lifecycle_invocation_seal"
    if path == "experiment-index.jsonl":
        return "lifecycle_invocation_index"
    if path == "sweep/manifest.json":
        return "lifecycle_ablation_manifest"
    if path == "sweep/plan.json":
        return "lifecycle_ablation_plan"
    if path == "run/verification.json":
        return "lifecycle_verification"
    if path == "run/metrics.json":
        return "lifecycle_metrics"
    if path == "run/state.json":
        return "lifecycle_state"
    if path.startswith("package/"):
        return "lifecycle_package"
    if path.startswith("run/workspace/checkpoints/") and path.endswith("/operations.json"):
        return "lifecycle_operation_catalog"
    if path == "run/workspace/operations/current-source.json":
        return "lifecycle_operation_current_source"
    return "lifecycle_run_artifact"


def _mutate_operation_snapshot_inventory(
    written: _WrittenRecord,
    *,
    namespace: Literal["package", "operation"],
    mutation: Literal["missing", "extra", "mismatched"],
) -> None:
    record = read_trial_record(written.record_path)
    assert record.outputs.artifacts is not None
    state_reference = next(artifact for artifact in record.outputs.artifacts if artifact.kind == "lifecycle_state")
    ledger_root = written.record_path.parent.parent
    run_root = (ledger_root / state_reference.path).parent
    snapshot_root = run_root.parent
    if namespace == "package":
        relative = "template.json"
        reference_path = (snapshot_root / "package" / relative).relative_to(ledger_root).as_posix()
        extra_relative = "extra.json"
    else:
        relative = "workspace/checkpoints/revision_analysis/operations.json"
        reference_path = (run_root / relative).relative_to(ledger_root).as_posix()
        extra_relative = "lifecycle_operations/unexpected/action.json"

    if mutation == "missing":
        artifacts = [
            artifact
            for artifact in _snapshot_references(record, ledger_root=ledger_root)
            if artifact.path != reference_path
        ]
        _rewrite_trial_record(
            written,
            record,
            artifacts=artifacts,
        )
        return
    if mutation == "extra":
        root = snapshot_root / "package" if namespace == "package" else run_root
        extra_path = root / extra_relative
        extra_path.parent.mkdir(parents=True, exist_ok=True)
        extra_path.write_text(json.dumps({"unexpected": True}, sort_keys=True), encoding="utf-8")
        extra_reference = ArtifactReference(
            kind="lifecycle_package" if namespace == "package" else "lifecycle_operation_action",
            path=extra_path.relative_to(ledger_root).as_posix(),
            sha256=_sha256(extra_path),
            media_type="application/json",
        )
        _rewrite_trial_record(
            written,
            record,
            artifacts=[*_snapshot_references(record, ledger_root=ledger_root), extra_reference],
        )
        return

    assert record.lifecycle_provenance is not None
    manifest_reference = record.lifecycle_provenance.invocation_manifest
    manifest_path = ledger_root / manifest_reference.path
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if namespace == "package":
        manifest["lifecycle"]["package_files"][relative] = "f" * 64
    else:
        manifest["outputs"]["artifacts"][relative] = "f" * 64
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    _rehash_operation_manifest_metadata(written, record, manifest_path=manifest_path)


def _forge_operation_current_source(written: _WrittenRecord) -> None:
    record = read_trial_record(written.record_path)
    assert record.outputs.artifacts is not None
    assert record.lifecycle_provenance is not None
    ledger_root = written.record_path.parent.parent
    source_reference = next(
        artifact for artifact in record.outputs.artifacts if artifact.kind == "lifecycle_operation_current_source"
    )
    source_path = ledger_root / source_reference.path
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source_state = {"forged_action_free_source": True}
    physical_sha256, visible_sha256 = lifecycle_operation_source_identity(
        source_state=source_state,
        revision_id=str(source["revision_id"]),
    )
    source.update(
        {
            "source_state": source_state,
            "physical_source_state_sha256": physical_sha256,
            "visible_source_state_sha256": visible_sha256,
        }
    )
    source_path.write_text(json.dumps(source, sort_keys=True), encoding="utf-8")
    source_sha256 = _sha256(source_path)
    manifest_path = ledger_root / record.lifecycle_provenance.invocation_manifest.path
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outputs"]["artifacts"]["workspace/operations/current-source.json"] = source_sha256
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    _rehash_operation_manifest_metadata(written, record, manifest_path=manifest_path)


def _forge_operation_spec_semantic_identity(
    written: _WrittenRecord,
) -> None:
    record = read_trial_record(written.record_path)
    assert record.outputs.artifacts is not None
    assert record.lifecycle_provenance is not None
    ledger_root = written.record_path.parent.parent
    lifecycle_reference = next(
        artifact for artifact in record.outputs.artifacts if artifact.path.endswith("/package/lifecycle.json")
    )
    lifecycle_path = ledger_root / lifecycle_reference.path
    lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    lifecycle["lifecycle_id"] = "forged.lifecycle_id"
    lifecycle_path.write_text(json.dumps(lifecycle, sort_keys=True), encoding="utf-8")
    lifecycle_sha256 = _sha256(lifecycle_path)
    spec = EvidenceLifecycleSpec.model_validate(lifecycle)
    spec_sha256 = _canonical_sha256(spec.model_dump(mode="json", exclude_none=True))
    package_root = lifecycle_path.parent
    package_sha256 = _package_sha256(package_root)

    state_reference = next(artifact for artifact in record.outputs.artifacts if artifact.kind == "lifecycle_state")
    state_path = ledger_root / state_reference.path
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["lifecycle_spec_sha256"] = spec_sha256
    state["package_sha256"] = package_sha256
    state_path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    state_sha256 = _sha256(state_path)
    provenance = record.lifecycle_provenance.model_copy(
        update={"spec_sha256": spec_sha256, "package_sha256": package_sha256}
    )
    record = record.model_copy(
        update={
            "input": record.input.model_copy(update={"task_revision": package_sha256}),
        }
    )
    manifest_path = ledger_root / provenance.invocation_manifest.path
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["lifecycle"]["spec_sha256"] = spec_sha256
    manifest["lifecycle"]["package_sha256"] = package_sha256
    manifest["lifecycle"]["package_files"]["lifecycle.json"] = lifecycle_sha256
    manifest["outputs"]["artifacts"]["state.json"] = state_sha256
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    _rehash_operation_manifest_metadata(
        written,
        record,
        manifest_path=manifest_path,
        lifecycle_provenance=provenance,
    )


def _forge_operation_snapshot_metadata(
    written: _WrittenRecord,
    *,
    metadata: Literal["seal", "sweep_manifest", "sweep_plan"],
) -> None:
    record = read_trial_record(written.record_path)
    assert record.outputs.artifacts is not None
    assert record.lifecycle_provenance is not None
    ledger_root = written.record_path.parent.parent
    kind = {
        "seal": "lifecycle_invocation_seal",
        "sweep_manifest": "lifecycle_ablation_manifest",
        "sweep_plan": "lifecycle_ablation_plan",
    }[metadata]
    reference = next(artifact for artifact in record.outputs.artifacts if artifact.kind == kind)
    path = ledger_root / reference.path
    if metadata == "sweep_plan":
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["experiment_id"] = "unbound-experiment"
        plan_payload = {key: value for key, value in payload.items() if key != "plan_sha256"}
        payload["plan_sha256"] = _canonical_sha256(plan_payload)
    else:
        payload = {"schema_version": "1", "bogus": metadata}
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    reference = ArtifactReference(
        kind=reference.kind,
        path=reference.path,
        sha256=_sha256(path),
        media_type=reference.media_type,
    )
    provenance_updates: dict[str, object] = {}
    if metadata == "sweep_manifest":
        provenance_updates["ablation_manifest"] = reference
    elif metadata == "sweep_plan":
        provenance_updates["ablation_plan"] = reference
    provenance = record.lifecycle_provenance.model_copy(update=provenance_updates)
    _rewrite_trial_record(
        written,
        record,
        lifecycle_provenance=provenance,
    )


def _forge_operation_package_template(
    written: _WrittenRecord,
) -> None:
    record = read_trial_record(written.record_path)
    assert record.outputs.artifacts is not None
    assert record.lifecycle_provenance is not None
    ledger_root = written.record_path.parent.parent
    template_reference = next(
        artifact for artifact in record.outputs.artifacts if artifact.path.endswith("/package/template.json")
    )
    template_path = ledger_root / template_reference.path
    template = json.loads(template_path.read_text(encoding="utf-8"))
    template["template_id"] = "forged-template-id"
    template_path.write_text(json.dumps(template, sort_keys=True), encoding="utf-8")
    template_sha256 = _sha256(template_path)
    package_sha256 = _package_sha256(template_path.parent)

    state_reference = next(artifact for artifact in record.outputs.artifacts if artifact.kind == "lifecycle_state")
    state_path = ledger_root / state_reference.path
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["package_sha256"] = package_sha256
    state_path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    state_sha256 = _sha256(state_path)
    provenance = record.lifecycle_provenance.model_copy(update={"package_sha256": package_sha256})
    record = record.model_copy(
        update={
            "input": record.input.model_copy(update={"task_revision": package_sha256}),
        }
    )
    provenance, plan_sha256 = _update_operation_plan_trial_identities(
        record,
        provenance=provenance,
        ledger_root=ledger_root,
        updates={"package_sha256": package_sha256},
    )
    manifest_path = ledger_root / provenance.invocation_manifest.path
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["lifecycle"]["package_sha256"] = package_sha256
    manifest["lifecycle"]["package_files"]["template.json"] = template_sha256
    manifest["outputs"]["artifacts"]["state.json"] = state_sha256
    manifest["sweep"]["plan_sha256"] = plan_sha256
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    _rehash_operation_manifest_metadata(
        written,
        record,
        manifest_path=manifest_path,
        lifecycle_provenance=provenance,
    )


def _update_operation_plan_trial_identities(
    record: TrialRecord,
    *,
    provenance: LifecycleTrialProvenance,
    ledger_root: Path,
    updates: dict[str, object],
) -> tuple[LifecycleTrialProvenance, str]:
    assert record.outputs.artifacts is not None
    assert provenance.ablation_plan is not None
    reference = provenance.ablation_plan
    path = ledger_root / reference.path
    plan = json.loads(path.read_text(encoding="utf-8"))
    selected = next(trial for trial in plan["trials"] if trial["trial_id"] == record.trial_id)
    selected.update(updates)
    plan_payload = {key: value for key, value in plan.items() if key != "plan_sha256"}
    plan["plan_sha256"] = _canonical_sha256(plan_payload)
    path.write_text(json.dumps(plan, sort_keys=True), encoding="utf-8")
    reference = reference.model_copy(update={"sha256": _sha256(path)})
    return provenance.model_copy(update={"ablation_plan": reference}), str(plan["plan_sha256"])


def _forge_operation_snapshot_identity(
    written: _WrittenRecord,
    *,
    identity: Literal["package", "spec"],
) -> None:
    record = read_trial_record(written.record_path)
    assert record.outputs.artifacts is not None
    assert record.lifecycle_provenance is not None
    ledger_root = written.record_path.parent.parent
    state_reference = next(artifact for artifact in record.outputs.artifacts if artifact.kind == "lifecycle_state")
    state_path = ledger_root / state_reference.path
    state = json.loads(state_path.read_text(encoding="utf-8"))
    forged_sha256 = "f" * 64
    state_field = "package_sha256" if identity == "package" else "lifecycle_spec_sha256"
    provenance_field = "package_sha256" if identity == "package" else "spec_sha256"
    manifest_field = "package_sha256" if identity == "package" else "spec_sha256"
    state[state_field] = forged_sha256
    state_path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    state_sha256 = _sha256(state_path)
    provenance = record.lifecycle_provenance.model_copy(update={provenance_field: forged_sha256})
    if identity == "package":
        record = record.model_copy(update={"input": record.input.model_copy(update={"task_revision": forged_sha256})})

    manifest_path = ledger_root / provenance.invocation_manifest.path
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["lifecycle"][manifest_field] = forged_sha256
    manifest["outputs"]["artifacts"]["state.json"] = state_sha256
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    _rehash_operation_manifest_metadata(
        written,
        record,
        manifest_path=manifest_path,
        lifecycle_provenance=provenance,
    )


def _rehash_operation_manifest_metadata(
    written: _WrittenRecord,
    record: TrialRecord,
    *,
    manifest_path: Path,
    lifecycle_provenance: LifecycleTrialProvenance | None = None,
) -> None:
    assert record.outputs.artifacts is not None
    provenance = lifecycle_provenance or record.lifecycle_provenance
    assert provenance is not None
    assert provenance.invocation_index is not None
    ledger_root = written.record_path.parent.parent
    replacements: dict[str, ArtifactReference] = {}
    manifest_reference = provenance.invocation_manifest.model_copy(update={"sha256": _sha256(manifest_path)})
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    replacements[manifest_reference.path] = manifest_reference
    for kind in ("lifecycle_invocation_index", "lifecycle_invocation_seal"):
        reference = next(artifact for artifact in record.outputs.artifacts if artifact.kind == kind)
        path = ledger_root / reference.path
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["manifest_sha256"] = manifest_reference.sha256
        payload["sweep"] = manifest["sweep"]
        suffix = "\n" if kind == "lifecycle_invocation_index" else ""
        path.write_text(json.dumps(payload, sort_keys=True) + suffix, encoding="utf-8")
        replacements[reference.path] = ArtifactReference(
            kind=reference.kind,
            path=reference.path,
            sha256=_sha256(path),
            media_type=reference.media_type,
        )
    provenance = provenance.model_copy(
        update={
            "invocation_manifest": manifest_reference,
            "invocation_index": replacements[provenance.invocation_index.path],
        }
    )
    _rewrite_trial_record(
        written,
        record,
        lifecycle_provenance=provenance,
    )


def _snapshot_references(record: TrialRecord, *, ledger_root: Path) -> list[ArtifactReference]:
    references = [
        ArtifactReference(
            kind=artifact.kind,
            path=artifact.path,
            sha256=_sha256(ledger_root / artifact.path),
            media_type=artifact.media_type,
        )
        for artifact in record.outputs.artifacts
    ]
    provenance = record.lifecycle_provenance
    if provenance is not None and all(artifact.path != provenance.invocation_manifest.path for artifact in references):
        references.append(
            provenance.invocation_manifest.model_copy(
                update={"sha256": _sha256(ledger_root / provenance.invocation_manifest.path)}
            )
        )
    return references


def _rewrite_trial_record(
    written: _WrittenRecord,
    record: TrialRecord,
    *,
    artifacts: list[ArtifactReference] | None = None,
    lifecycle_execution: LifecycleExecutionRecord | None = None,
    lifecycle_provenance: LifecycleTrialProvenance | None = None,
) -> None:
    """Republish a forged fixture through the current exact-artifact contract."""

    ledger_root = written.record_path.parent.parent
    provenance = lifecycle_provenance or record.lifecycle_provenance
    execution = lifecycle_execution or record.lifecycle_execution
    references = _snapshot_references(record, ledger_root=ledger_root) if artifacts is None else artifacts
    output = record.outputs.model_copy(
        update={
            "raw_output": None,
            "conversation": None,
            "trajectory": None,
            "artifacts": (),
        }
    )
    rewritten = TrialRecord.model_validate(
        {
            **record.model_dump(mode="python"),
            "evidence_status": EvidenceStatus.PENDING,
            "output": output,
            "authority_evidence": (),
            "extension_refs": (),
        }
    ).bind_run_manifest(record.run_manifest)
    if execution is not None:
        rewritten.attach_extension("lifecycle_execution", execution)
    if provenance is not None:
        rewritten.attach_extension("lifecycle_provenance", provenance)
    for artifact in references:
        source = ledger_root / artifact.path
        if provenance is not None and artifact.path == provenance.invocation_manifest.path:
            role = f"authority:{AuthorityEvidenceKind.LIFECYCLE.value}:aec-bench/lifecycle-evidence/1"
            logical_path = None
        else:
            locator = hashlib.sha256(artifact.path.encode("utf-8")).hexdigest()[:12]
            role = f"output:{artifact.kind}:{artifact.sha256}-{locator}"
            logical_path = artifact.path
        rewritten.attach_artifact(
            role,
            source,
            media_type=artifact.media_type,
            logical_path=logical_path,
        )
    written.record_path.unlink()
    write_trial_record(ledger_root=ledger_root, record=rewritten)
    written.reference = LifecycleTransferRecordReference(
        experiment_id=rewritten.experiment_id,
        trial_id=rewritten.trial_id,
        ledger_path=str(written.record_path),
        sha256=_sha256(written.record_path),
    )


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _package_sha256(package_root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in package_root.rglob("*") if item.is_file()):
        relative = path.relative_to(package_root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
