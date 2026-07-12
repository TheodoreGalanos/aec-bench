# ABOUTME: Tests descriptive holdout generalization over immutable lifecycle TrialRecords.
# ABOUTME: Enforces visibility, condition identity, provenance integrity, and non-causal summaries.

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
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
from aec_bench.meta_harness.evidence_lifecycle_metrics import score_semantic_transitions
from aec_bench.meta_harness.evidence_lifecycle_transfer import (
    LifecycleTransferCondition,
    LifecycleTransferEvaluationSpec,
    LifecycleTransferRecordReference,
    LifecycleTransferStudyDesign,
    build_lifecycle_transfer_evaluation,
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


@pytest.mark.parametrize("integrity_failure", ["missing", "path_escape"])
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
        payload["outputs"]["artifacts"][0]["path"] = "../outside.json"
        target.record_path.write_text(json.dumps(payload), encoding="utf-8")
        reference = reference.model_copy(update={"sha256": _sha256(target.record_path)})
        expected_reason = "artifact_path_escapes_ledger"

    result = build_lifecycle_transfer_evaluation(
        _spec(condition=condition, calibration=(calibration.reference,), targets=(reference,))
    )

    assert result.status == "not_evaluable"
    assert expected_reason in result.target_results[0].reasons


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
        execution_mode="fresh_context",
        memory_visibility_policy="artifact_memory",
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
    repository_kind: str = "git",
    verification_overall: str | None = None,
    verification_lifecycle_id: str | None = None,
    verification_template_id: str = "drainage-model-evidence-lifecycle-review",
    state_checkpoint_updates: dict[str, object] | None = None,
) -> _WrittenRecord:
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
            execution_mode=condition.execution_mode,
            memory_visibility_policy=condition.memory_visibility_policy,
            max_turns_per_session=condition.max_turns_per_session,
            status="completed",
            sessions=[
                LifecycleSessionRecord(
                    session_id=f"{trial_id}-session",
                    checkpoint_ids=["initial", "corrected"],
                    requested_adapter=condition.adapter,
                    adapter=condition.adapter,
                    resolved_model=condition.model,
                    execution_mode=condition.execution_mode,
                    memory_visibility_policy=condition.memory_visibility_policy,
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
