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

import aec_bench.meta_harness.evidence_lifecycle_experiment as experiment_runtime
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.experiment_manifest import AgentConfig
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trial_record import (
    AgentReference,
    ArtifactReference,
    Completeness,
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
from aec_bench.meta_harness.evidence_lifecycle import (
    execute_lifecycle_operation,
    open_checkpoint_attempt,
    prepare_evidence_checkpoint,
    submit_evidence_checkpoint,
)
from aec_bench.meta_harness.evidence_lifecycle_ablation_plan import (
    LifecycleAblationCondition,
    LifecycleAblationLimits,
    LifecycleAblationManifest,
    LifecycleAblationPlan,
    LifecycleAblationStudyDesign,
    LifecycleAblationTrial,
    LifecycleRuntimeProvenance,
    build_lifecycle_ablation_plan,
)
from aec_bench.meta_harness.evidence_lifecycle_episode import (
    LifecycleExecutionMode,
    LifecycleVisibilityPolicy,
)
from aec_bench.meta_harness.evidence_lifecycle_experiment import LifecycleExperimentMetrics
from aec_bench.meta_harness.evidence_lifecycle_metrics import score_semantic_transitions
from aec_bench.meta_harness.evidence_lifecycle_state import EvidenceLifecycleRunState
from aec_bench.meta_harness.evidence_lifecycle_transfer import (
    LifecycleTransferCondition,
    LifecycleTransferEvaluationSpec,
    LifecycleTransferRecordReference,
    LifecycleTransferStudyDesign,
    build_lifecycle_transfer_evaluation,
)
from aec_bench.meta_harness.evidence_request_protocol import (
    EvidenceLifecycleError,
    validate_evidence_request_run_state,
)
from aec_bench.meta_harness.lifecycle_operation_protocol import (
    lifecycle_operation_protocol_identity,
    lifecycle_operation_source_identity,
)
from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.contracts import EvidenceLifecycleSpec
from aec_bench.task_world_templates.lifecycles import (
    lifecycle_package_variant,
    materialize_lifecycle_template,
)

_RUNTIME_SHA256 = "1" * 64


def test_distinct_complete_holdout_under_public_selected_condition_is_evaluated(
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

    assert result.status == "evaluated"
    assert result.study_design.interpretation == "descriptive_holdout_generalization"
    assert result.study_design.selection_basis == "public_calibration"
    assert result.study_design.causal_effects_supported is False
    assert result.study_design.cross_run_learning_supported is False
    assert result.calibration_support_count == 1
    assert result.eligible_target_count == 1
    assert result.mean_target_reward == 0.75
    assert result.target_results[0].verifier_reward == 0.75
    assert result.target_results[0].verifier_validity is not None
    assert result.target_results[0].verifier_validity.verifier_completed is True
    assert result.target_results[0].semantic_diagnostics == semantic
    assert target.record_path.read_bytes() == target_bytes
    assert TrialRecord.model_validate_json(target_bytes).evaluation.reward == 0.75
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
    assert result.target_results[0].reasons == ("target_package_matches_calibration",)
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
    assert result.target_results[0].reasons == ("target_package_matches_calibration",)


@pytest.mark.parametrize(
    ("completeness", "verifier_completed", "expected_reason"),
    [
        (Completeness.PARTIAL, True, "record_incomplete"),
        (Completeness.COMPLETE, False, "verifier_incomplete"),
    ],
)
def test_partial_or_unverified_target_is_not_evaluable(
    tmp_path: Path,
    completeness: Completeness,
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
        completeness=completeness,
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
        completeness=Completeness.PARTIAL,
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
    assert "record_incomplete" in result.calibration_results[0].reasons
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
        target.snapshot_path.write_text("tampered", encoding="utf-8")
        expected_reason = "artifact_sha256_mismatch"

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(target.reference,))
    )

    assert result.status == "not_evaluable"
    assert expected_reason in result.target_results[0].reasons
    assert result.mean_target_reward is None


def test_v3_snapshot_cannot_smuggle_v4_evidence_request_fields(tmp_path: Path) -> None:
    condition = _condition()
    calibration = _write_record(
        tmp_path,
        experiment_id="calibration",
        trial_id="calibration-001",
        visibility=Visibility.PUBLIC,
        package_sha256="a" * 64,
        reward=1.0,
        condition=condition,
        state_checkpoint_updates={
            "evidence_request_budget": 1,
            "evidence_request_budget_remaining": 1,
            "evidence_request_actions": [],
        },
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

    assert result.status == "not_evaluable"
    assert result.calibration_results[0].reasons == ("snapshot_contract_invalid",)
    assert result.target_results[0].reasons == ("no_public_calibration_support",)


@pytest.mark.parametrize(
    ("forge_catalog", "expected_status"),
    [(False, "supports_selected_condition"), (True, "not_supporting")],
)
def test_transfer_evaluator_fully_validates_v5_operation_snapshot(
    tmp_path: Path,
    forge_catalog: bool,
    expected_status: str,
) -> None:
    condition = _condition()
    calibration = _upgrade_to_v5_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-v5",
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
        assert result.target_results[0].reasons == ("no_public_calibration_support",)
    else:
        assert result.calibration_results[0].reasons == ()
        assert result.status == "evaluated"
        assert result.target_results[0].reasons == ()


def test_transfer_evaluator_rejects_rehashed_malformed_operation_tool_schema(tmp_path: Path) -> None:
    condition = _condition()
    calibration = _upgrade_to_v5_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-v5",
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
    calibration = _upgrade_to_v5_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-v5",
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


def test_transfer_evaluator_rejects_v5_evidence_state_absent_from_contract(tmp_path: Path) -> None:
    condition = _condition()
    calibration = _upgrade_to_v5_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-v5",
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
def test_transfer_evaluator_reconciles_v5_snapshot_inventory_with_manifest(
    tmp_path: Path,
    namespace: Literal["package", "operation"],
    mutation: Literal["missing", "extra", "mismatched"],
) -> None:
    condition = _condition()
    calibration = _upgrade_to_v5_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-v5",
            visibility=Visibility.PUBLIC,
            package_sha256="a" * 64,
            reward=1.0,
            condition=condition,
        ),
        forge_catalog=False,
    )
    _mutate_v5_snapshot_inventory(calibration, namespace=namespace, mutation=mutation)
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
    calibration = _upgrade_to_v5_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-v5",
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
    assert result.status == "evaluated"


def test_transfer_evaluator_replays_nonempty_v5_history_from_reconciled_snapshot_bytes(
    tmp_path: Path,
) -> None:
    condition = _condition()
    calibration = _upgrade_to_v5_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-v5",
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
    assert result.status == "evaluated"


def test_transfer_evaluator_binds_action_free_current_source_to_packaged_resolver(
    tmp_path: Path,
) -> None:
    condition = _condition()
    calibration = _upgrade_to_v5_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-v5",
            visibility=Visibility.PUBLIC,
            package_sha256="a" * 64,
            reward=1.0,
            condition=condition,
        ),
        forge_catalog=False,
    )
    _forge_v5_current_source(calibration)
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


@pytest.mark.parametrize("identity", ["lifecycle_id", "world_id"])
def test_transfer_evaluator_binds_v5_spec_semantic_identity_across_snapshot(
    tmp_path: Path,
    identity: Literal["lifecycle_id", "world_id"],
) -> None:
    condition = _condition()
    calibration = _upgrade_to_v5_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-v5",
            visibility=Visibility.PUBLIC,
            package_sha256="a" * 64,
            reward=1.0,
            condition=condition,
        ),
        forge_catalog=False,
    )
    _forge_v5_spec_semantic_identity(calibration, identity=identity)
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
def test_transfer_evaluator_validates_v5_canonical_metadata_contents(
    tmp_path: Path,
    metadata: Literal["seal", "sweep_manifest", "sweep_plan"],
) -> None:
    condition = _condition()
    calibration = _upgrade_to_v5_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-v5",
            visibility=Visibility.PUBLIC,
            package_sha256="a" * 64,
            reward=1.0,
            condition=condition,
        ),
        forge_catalog=False,
    )
    _forge_v5_snapshot_metadata(calibration, metadata=metadata)
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


def test_transfer_evaluator_binds_v5_visibility_to_validated_package_variant(
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
    target = _upgrade_to_v5_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="target",
            trial_id="target-v5",
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

    assert result.target_results[0].reasons == ("snapshot_contract_invalid",)
    assert result.status == "not_evaluable"


@pytest.mark.parametrize("mutation", ["template_id", "lifecycle_contract"])
def test_transfer_evaluator_binds_v5_package_template_to_record_task(
    tmp_path: Path,
    mutation: Literal["template_id", "lifecycle_contract"],
) -> None:
    condition = _condition()
    calibration = _upgrade_to_v5_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-v5",
            visibility=Visibility.PUBLIC,
            package_sha256="a" * 64,
            reward=1.0,
            condition=condition,
        ),
        forge_catalog=False,
    )
    _forge_v5_package_template(calibration, mutation=mutation)
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
def test_transfer_evaluator_recomputes_v5_package_and_spec_identities(
    tmp_path: Path,
    identity: Literal["package", "spec"],
) -> None:
    condition = _condition()
    calibration = _upgrade_to_v5_operation_snapshot(
        _write_record(
            tmp_path,
            experiment_id="calibration",
            trial_id="calibration-v5",
            visibility=Visibility.PUBLIC,
            package_sha256="a" * 64,
            reward=1.0,
            condition=condition,
        ),
        forge_catalog=False,
    )
    _forge_v5_snapshot_identity(calibration, identity=identity)
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
    ["reward", "validity_errors", "completeness", "visibility", "package_sha256"],
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
    )
    target_visibility = Visibility.PUBLIC if tampered_field == "visibility" else Visibility.HOLDOUT
    target_package = "a" * 64 if tampered_field == "package_sha256" else "b" * 64
    target = _write_record(
        tmp_path,
        experiment_id="target",
        trial_id="target-001",
        visibility=target_visibility,
        package_sha256=target_package,
        reward=1.0,
        condition=condition,
        completeness=(Completeness.PARTIAL if tampered_field == "completeness" else Completeness.COMPLETE),
        repository_kind=("source_tree" if tampered_field == "completeness" else "git"),
    )
    payload = json.loads(target.record_path.read_text(encoding="utf-8"))
    if tampered_field == "reward":
        payload["evaluation"]["reward"] = 0.25
    elif tampered_field == "validity_errors":
        payload["evaluation"]["validity"]["errors"] = ["forged"]
    elif tampered_field == "completeness":
        payload["completeness"] = "complete"
    elif tampered_field == "visibility":
        payload["task"]["visibility"] = "holdout"
    else:
        payload["task"]["task_revision"] = "b" * 64
        payload["lifecycle_provenance"]["package_sha256"] = "b" * 64
    target.record_path.write_text(json.dumps(payload), encoding="utf-8")
    reference = target.reference.model_copy(update={"sha256": _sha256(target.record_path)})

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(reference,))
    )

    assert result.status == "not_evaluable"
    assert "snapshot_record_mismatch" in result.target_results[0].reasons
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
    payload = json.loads(target.record_path.read_text(encoding="utf-8"))
    payload["evaluation"]["reward"] = 0.25
    payload["outputs"]["artifacts"][0] = {
        "kind": "lifecycle_verification",
        "path": forged_verification.relative_to(target.record_path.parents[1]).as_posix(),
        "sha256": _sha256(forged_verification),
        "media_type": "application/json",
    }
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
        target.snapshot_path.unlink()
        expected_reason = "artifact_missing"
    else:
        payload = json.loads(target.record_path.read_text(encoding="utf-8"))
        payload["outputs"]["artifacts"][0]["path"] = (
            "../outside.json" if integrity_failure == "path_escape" else "invalid\0artifact.json"
        )
        target.record_path.write_text(json.dumps(payload), encoding="utf-8")
        reference = reference.model_copy(update={"sha256": _sha256(target.record_path)})
        expected_reason = (
            "artifact_path_escapes_ledger" if integrity_failure == "path_escape" else "artifact_unresolvable"
        )

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(reference,))
    )

    assert result.status == "not_evaluable"
    assert expected_reason in result.target_results[0].reasons


def test_evidence_request_state_contract_rejects_unknown_checkpoint_id(tmp_path: Path) -> None:
    package = materialize_lifecycle_template(
        get_template("hydraulic-interaction-lifecycle-review"),
        tmp_path / "package",
        variant_id="tailwater_revision",
    )
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    state = EvidenceLifecycleRunState.model_validate_json((run_dir / "state.json").read_bytes())
    state.checkpoint_runs[0].checkpoint_id = "unknown-checkpoint"
    spec = EvidenceLifecycleSpec.model_validate_json((package / "lifecycle.json").read_bytes())

    with pytest.raises(EvidenceLifecycleError, match="checkpoint state does not match"):
        validate_evidence_request_run_state(state, spec)


def test_eligible_zero_reward_is_evaluated_as_zero_not_missing_evidence(tmp_path: Path) -> None:
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

    assert result.status == "evaluated"
    assert result.eligible_target_count == 1
    assert result.mean_target_reward == 0.0
    assert result.target_results[0].verifier_validity is not None


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
    assert forward.mean_target_reward == 0.5


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

    assert result.eligible_target_count == 1
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


def _write_record(
    tmp_path: Path,
    *,
    experiment_id: str,
    trial_id: str,
    visibility: Visibility | None,
    package_sha256: str,
    reward: float,
    condition: LifecycleTransferCondition,
    completeness: Completeness = Completeness.COMPLETE,
    verifier_completed: bool = True,
    semantic_transition: dict[str, object] | None = None,
    repository_kind: Literal["git", "source_tree"] = "git",
    verification_overall: str | None = None,
    verification_lifecycle_id: str | None = None,
    verification_template_id: str = "drainage-model-evidence-lifecycle-review",
    state_checkpoint_updates: dict[str, object] | None = None,
) -> _WrittenRecord:
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
    checkpoint_updates = state_checkpoint_updates or {}
    state_payload = {
        "schema_version": "3",
        "lifecycle_id": f"lifecycle-{trial_id}",
        "world_id": f"world-{trial_id}",
        "lifecycle_spec_sha256": "3" * 64,
        "package_sha256": package_sha256,
        "status": "complete",
        "active_checkpoint_id": None,
        "checkpoint_runs": [
            {
                "checkpoint_id": checkpoint_id,
                "status": "submitted",
                "submission_path": f"episodes/{checkpoint_id}/submission.json",
                "submission_sha256": "7" * 64,
                **checkpoint_updates,
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
    invocation_path = artifact_root / "experiment-manifest.json"
    visibility_value = visibility.value if visibility is not None else None
    invocation_payload = {
        "schema_version": "1",
        "experiment_id": f"invocation-{trial_id}",
        "created_at": "2026-07-12T00:00:00+00:00",
        "repository": {
            "commit": "commit-abc",
            "repository_kind": repository_kind,
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
            "world_id": f"world-{trial_id}",
            "spec_sha256": "3" * 64,
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
            "artifacts": {
                "verification.json": snapshot.sha256,
                "state.json": state_reference.sha256,
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
    record = TrialRecord(
        trial_id=trial_id,
        experiment_id=experiment_id,
        timestamp=datetime(2026, 7, 12, tzinfo=UTC),
        task=TaskReference(
            task_id="drainage-model-evidence-lifecycle-review",
            task_revision=package_sha256,
            visibility=visibility,
        ),
        agent=AgentReference(
            adapter=condition.adapter,
            model=condition.model,
            adapter_revision="commit-abc",
            configuration={},
        ),
        environment=EnvironmentSnapshot(
            runtime_image="python:3.13",
            compute_backend="local",
            tool_versions={"aec_bench": "commit-abc"},
        ),
        inputs=InputRecord(
            instruction="Review the evolving evidence.",
            input_files=[FileReference(path="input.json", hash="input-sha")],
        ),
        outputs=OutputRecord(
            artifacts=[
                snapshot,
                state_reference,
                invocation,
                invocation_index,
                ablation_manifest,
                ablation_plan,
            ]
        ),
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
        lifecycle_execution=LifecycleExecutionRecord(
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
        lifecycle_provenance=LifecycleTrialProvenance(
            lifecycle_id=f"lifecycle-{trial_id}",
            world_id=f"world-{trial_id}",
            spec_sha256="3" * 64,
            package_sha256=package_sha256,
            repository_commit="commit-abc",
            repository_kind=repository_kind,
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
        completeness=completeness,
    )
    record_path = ledger_root / experiment_id / f"{trial_id}.json"
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
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


def _upgrade_to_v5_operation_snapshot(
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
    record = TrialRecord.model_validate_json(written.record_path.read_text(encoding="utf-8"))
    assert record.lifecycle_provenance is not None
    assert record.outputs.artifacts is not None
    ledger_root = written.record_path.parent.parent
    original_artifact_root = written.snapshot_path.parent
    artifact_root = (
        original_artifact_root / snapshot_subdirectory if snapshot_subdirectory is not None else original_artifact_root
    )
    run_root = artifact_root / "run"
    package_root = artifact_root / "package"
    materialize_lifecycle_template(
        get_template("hydraulic-interaction-lifecycle-review"),
        package_root,
        variant_id="tailwater_revision",
    )
    package_variant = lifecycle_package_variant(package_root)
    assert package_variant is not None
    validated_spec = EvidenceLifecycleSpec.model_validate_json((package_root / "lifecycle.json").read_bytes())
    for checkpoint_number, checkpoint in enumerate(validated_spec.checkpoints, start=1):
        prepare_evidence_checkpoint(package_root, run_root)
        open_checkpoint_attempt(
            package_root,
            run_root,
            session_id=f"fixture.session-{checkpoint_number:03d}",
            execution_mode="fresh_context",
        )
        if execute_operation_action and checkpoint_number == 1:
            current_source = json.loads(
                (run_root / "workspace" / "hydraulics" / "current-source.json").read_text(encoding="utf-8")
            )
            execute_lifecycle_operation(
                package_root,
                run_root,
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
        submit_evidence_checkpoint(package_root, run_root)

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
            "world_id": validated_spec.world_id,
            "spec_sha256": spec_sha256,
            "package_sha256": package_sha256,
            "package_files": package_hashes,
            "variant": {
                **package_variant,
                **({"visibility": manifest_visibility_override} if manifest_visibility_override is not None else {}),
            },
        }
    )
    ablation_manifest, ablation_plan, selected_trial = _v5_ablation_metadata(
        record,
        artifact_root=artifact_root,
        package_sha256=package_sha256,
        spec_sha256=spec_sha256,
        lifecycle_id=validated_spec.lifecycle_id,
        world_id=validated_spec.world_id,
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
    outputs = record.outputs.model_copy(update={"artifacts": references})
    breakdown = dict(record.evaluation.breakdown or {})
    operational_metrics = dict(metrics_payload)
    operational_metrics.pop("semantic_transition", None)
    breakdown["operational_metrics"] = operational_metrics
    evaluation = record.evaluation.model_copy(update={"breakdown": breakdown})
    provenance = record.lifecycle_provenance.model_copy(
        update={
            "lifecycle_id": validated_spec.lifecycle_id,
            "world_id": validated_spec.world_id,
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
            "task": record.task.model_copy(
                update={
                    "task_id": "hydraulic-interaction-lifecycle-review",
                    "task_revision": package_sha256,
                }
            ),
            "outputs": outputs,
            "evaluation": evaluation,
            "lifecycle_execution": execution,
            "lifecycle_provenance": provenance,
        }
    )
    written.record_path.write_text(updated.model_dump_json(indent=2), encoding="utf-8")
    return _WrittenRecord(
        reference=LifecycleTransferRecordReference(
            experiment_id=updated.experiment_id,
            trial_id=updated.trial_id,
            ledger_path=str(written.record_path),
            sha256=_sha256(written.record_path),
        ),
        record_path=written.record_path,
        snapshot_path=verification_path,
    )


def _v5_ablation_metadata(
    record: TrialRecord,
    *,
    artifact_root: Path,
    package_sha256: str,
    spec_sha256: str,
    lifecycle_id: str,
    world_id: str,
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
            "world_id": world_id,
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
    if path == "run/workspace/hydraulics/current-source.json":
        return "lifecycle_operation_current_source"
    return "lifecycle_run_artifact"


def _mutate_v5_snapshot_inventory(
    written: _WrittenRecord,
    *,
    namespace: Literal["package", "operation"],
    mutation: Literal["missing", "extra", "mismatched"],
) -> None:
    record = TrialRecord.model_validate_json(written.record_path.read_text(encoding="utf-8"))
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
        artifacts = [artifact for artifact in record.outputs.artifacts if artifact.path != reference_path]
        _write_trial_record(
            written, record.model_copy(update={"outputs": record.outputs.model_copy(update={"artifacts": artifacts})})
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
        _write_trial_record(
            written,
            record.model_copy(
                update={
                    "outputs": record.outputs.model_copy(
                        update={"artifacts": [*record.outputs.artifacts, extra_reference]}
                    )
                }
            ),
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
    _rehash_v5_manifest_metadata(written, record, manifest_path=manifest_path)


def _forge_v5_current_source(written: _WrittenRecord) -> None:
    record = TrialRecord.model_validate_json(written.record_path.read_text(encoding="utf-8"))
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
    source_reference = source_reference.model_copy(update={"sha256": _sha256(source_path)})
    artifacts = [
        source_reference if artifact.kind == "lifecycle_operation_current_source" else artifact
        for artifact in record.outputs.artifacts
    ]
    record = record.model_copy(update={"outputs": record.outputs.model_copy(update={"artifacts": artifacts})})
    assert record.lifecycle_provenance is not None
    manifest_path = ledger_root / record.lifecycle_provenance.invocation_manifest.path
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outputs"]["artifacts"]["workspace/hydraulics/current-source.json"] = source_reference.sha256
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    _rehash_v5_manifest_metadata(written, record, manifest_path=manifest_path)


def _forge_v5_spec_semantic_identity(
    written: _WrittenRecord,
    *,
    identity: Literal["lifecycle_id", "world_id"],
) -> None:
    record = TrialRecord.model_validate_json(written.record_path.read_text(encoding="utf-8"))
    assert record.outputs.artifacts is not None
    assert record.lifecycle_provenance is not None
    ledger_root = written.record_path.parent.parent
    lifecycle_reference = next(
        artifact for artifact in record.outputs.artifacts if artifact.path.endswith("/package/lifecycle.json")
    )
    lifecycle_path = ledger_root / lifecycle_reference.path
    lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    lifecycle[identity] = f"forged.{identity}"
    lifecycle_path.write_text(json.dumps(lifecycle, sort_keys=True), encoding="utf-8")
    lifecycle_reference = lifecycle_reference.model_copy(update={"sha256": _sha256(lifecycle_path)})
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
    state_reference = state_reference.model_copy(update={"sha256": _sha256(state_path)})
    artifacts = [
        lifecycle_reference
        if artifact.path == lifecycle_reference.path
        else state_reference
        if artifact.kind == "lifecycle_state"
        else artifact
        for artifact in record.outputs.artifacts
    ]
    provenance = record.lifecycle_provenance.model_copy(
        update={"spec_sha256": spec_sha256, "package_sha256": package_sha256}
    )
    record = record.model_copy(
        update={
            "task": record.task.model_copy(update={"task_revision": package_sha256}),
            "outputs": record.outputs.model_copy(update={"artifacts": artifacts}),
            "lifecycle_provenance": provenance,
        }
    )
    manifest_path = ledger_root / provenance.invocation_manifest.path
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["lifecycle"]["spec_sha256"] = spec_sha256
    manifest["lifecycle"]["package_sha256"] = package_sha256
    manifest["lifecycle"]["package_files"]["lifecycle.json"] = lifecycle_reference.sha256
    manifest["outputs"]["artifacts"]["state.json"] = state_reference.sha256
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    _rehash_v5_manifest_metadata(written, record, manifest_path=manifest_path)


def _forge_v5_snapshot_metadata(
    written: _WrittenRecord,
    *,
    metadata: Literal["seal", "sweep_manifest", "sweep_plan"],
) -> None:
    record = TrialRecord.model_validate_json(written.record_path.read_text(encoding="utf-8"))
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
    reference = reference.model_copy(update={"sha256": _sha256(path)})
    artifacts = [reference if artifact.kind == kind else artifact for artifact in record.outputs.artifacts]
    provenance_updates: dict[str, object] = {}
    if metadata == "sweep_manifest":
        provenance_updates["ablation_manifest"] = reference
    elif metadata == "sweep_plan":
        provenance_updates["ablation_plan"] = reference
    provenance = record.lifecycle_provenance.model_copy(update=provenance_updates)
    _write_trial_record(
        written,
        record.model_copy(
            update={
                "outputs": record.outputs.model_copy(update={"artifacts": artifacts}),
                "lifecycle_provenance": provenance,
            }
        ),
    )


def _forge_v5_package_template(
    written: _WrittenRecord,
    *,
    mutation: Literal["template_id", "lifecycle_contract"],
) -> None:
    record = TrialRecord.model_validate_json(written.record_path.read_text(encoding="utf-8"))
    assert record.outputs.artifacts is not None
    assert record.lifecycle_provenance is not None
    ledger_root = written.record_path.parent.parent
    template_reference = next(
        artifact for artifact in record.outputs.artifacts if artifact.path.endswith("/package/template.json")
    )
    template_path = ledger_root / template_reference.path
    template = json.loads(template_path.read_text(encoding="utf-8"))
    if mutation == "template_id":
        template["template_id"] = "forged-template-id"
    else:
        template["evidence_lifecycle"]["lifecycle_id"] = "forged.template.lifecycle"
    template_path.write_text(json.dumps(template, sort_keys=True), encoding="utf-8")
    template_reference = template_reference.model_copy(update={"sha256": _sha256(template_path)})
    package_sha256 = _package_sha256(template_path.parent)

    state_reference = next(artifact for artifact in record.outputs.artifacts if artifact.kind == "lifecycle_state")
    state_path = ledger_root / state_reference.path
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["package_sha256"] = package_sha256
    state_path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    state_reference = state_reference.model_copy(update={"sha256": _sha256(state_path)})
    artifacts = [
        template_reference
        if artifact.path == template_reference.path
        else state_reference
        if artifact.kind == "lifecycle_state"
        else artifact
        for artifact in record.outputs.artifacts
    ]
    provenance = record.lifecycle_provenance.model_copy(update={"package_sha256": package_sha256})
    record = record.model_copy(
        update={
            "task": record.task.model_copy(update={"task_revision": package_sha256}),
            "outputs": record.outputs.model_copy(update={"artifacts": artifacts}),
            "lifecycle_provenance": provenance,
        }
    )
    record, plan_sha256 = _update_v5_plan_trial_identities(
        record,
        ledger_root=ledger_root,
        updates={"package_sha256": package_sha256},
    )
    manifest_path = ledger_root / provenance.invocation_manifest.path
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["lifecycle"]["package_sha256"] = package_sha256
    manifest["lifecycle"]["package_files"]["template.json"] = template_reference.sha256
    manifest["outputs"]["artifacts"]["state.json"] = state_reference.sha256
    manifest["sweep"]["plan_sha256"] = plan_sha256
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    _rehash_v5_manifest_metadata(written, record, manifest_path=manifest_path)


def _update_v5_plan_trial_identities(
    record: TrialRecord,
    *,
    ledger_root: Path,
    updates: dict[str, object],
) -> tuple[TrialRecord, str]:
    assert record.outputs.artifacts is not None
    assert record.lifecycle_provenance is not None
    assert record.lifecycle_provenance.ablation_plan is not None
    reference = record.lifecycle_provenance.ablation_plan
    path = ledger_root / reference.path
    plan = json.loads(path.read_text(encoding="utf-8"))
    selected = next(trial for trial in plan["trials"] if trial["trial_id"] == record.trial_id)
    selected.update(updates)
    plan_payload = {key: value for key, value in plan.items() if key != "plan_sha256"}
    plan["plan_sha256"] = _canonical_sha256(plan_payload)
    path.write_text(json.dumps(plan, sort_keys=True), encoding="utf-8")
    reference = reference.model_copy(update={"sha256": _sha256(path)})
    artifacts = [
        reference if artifact.kind == "lifecycle_ablation_plan" else artifact for artifact in record.outputs.artifacts
    ]
    provenance = record.lifecycle_provenance.model_copy(update={"ablation_plan": reference})
    return (
        record.model_copy(
            update={
                "outputs": record.outputs.model_copy(update={"artifacts": artifacts}),
                "lifecycle_provenance": provenance,
            }
        ),
        str(plan["plan_sha256"]),
    )


def _forge_v5_snapshot_identity(
    written: _WrittenRecord,
    *,
    identity: Literal["package", "spec"],
) -> None:
    record = TrialRecord.model_validate_json(written.record_path.read_text(encoding="utf-8"))
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
    state_reference = state_reference.model_copy(update={"sha256": _sha256(state_path)})
    artifacts = [
        state_reference if artifact.kind == "lifecycle_state" else artifact for artifact in record.outputs.artifacts
    ]
    provenance = record.lifecycle_provenance.model_copy(update={provenance_field: forged_sha256})
    updates: dict[str, object] = {
        "outputs": record.outputs.model_copy(update={"artifacts": artifacts}),
        "lifecycle_provenance": provenance,
    }
    if identity == "package":
        updates["task"] = record.task.model_copy(update={"task_revision": forged_sha256})
    record = record.model_copy(update=updates)

    manifest_path = ledger_root / provenance.invocation_manifest.path
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["lifecycle"][manifest_field] = forged_sha256
    manifest["outputs"]["artifacts"]["state.json"] = state_reference.sha256
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    _rehash_v5_manifest_metadata(written, record, manifest_path=manifest_path)


def _rehash_v5_manifest_metadata(written: _WrittenRecord, record: TrialRecord, *, manifest_path: Path) -> None:
    assert record.outputs.artifacts is not None
    assert record.lifecycle_provenance is not None
    assert record.lifecycle_provenance.invocation_index is not None
    ledger_root = written.record_path.parent.parent
    replacements: dict[str, ArtifactReference] = {}
    manifest_reference = record.lifecycle_provenance.invocation_manifest.model_copy(
        update={"sha256": _sha256(manifest_path)}
    )
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
        replacements[reference.path] = reference.model_copy(update={"sha256": _sha256(path)})
    artifacts = [replacements.get(artifact.path, artifact) for artifact in record.outputs.artifacts]
    provenance = record.lifecycle_provenance.model_copy(
        update={
            "invocation_manifest": manifest_reference,
            "invocation_index": replacements[record.lifecycle_provenance.invocation_index.path],
        }
    )
    _write_trial_record(
        written,
        record.model_copy(
            update={
                "outputs": record.outputs.model_copy(update={"artifacts": artifacts}),
                "lifecycle_provenance": provenance,
            }
        ),
    )


def _write_trial_record(written: _WrittenRecord, record: TrialRecord) -> None:
    written.record_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    written.reference = LifecycleTransferRecordReference(
        experiment_id=record.experiment_id,
        trial_id=record.trial_id,
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
