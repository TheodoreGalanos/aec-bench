# ABOUTME: Tests private transfer evaluation against one explicit sealed lifecycle mount.
# ABOUTME: Proves exact frozen authority binding, replay, immutable snapshots, and public API isolation.

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.meta_harness import evidence_lifecycle_transfer as transfer_runtime
from aec_bench.meta_harness.evidence_lifecycle_calibration import (
    LifecycleCalibrationRecordReference,
)
from aec_bench.meta_harness.evidence_lifecycle_episode import (
    LifecycleExecutionMode,
    LifecycleVisibilityPolicy,
)
from aec_bench.meta_harness.evidence_lifecycle_experiment import runtime_dependency_provenance
from aec_bench.meta_harness.evidence_lifecycle_holdout_record import (
    finalize_lifecycle_holdout_trial_record,
)
from aec_bench.meta_harness.evidence_lifecycle_transfer import (
    LifecycleTransferCondition,
    LifecycleTransferEvaluationSpec,
    LifecycleTransferRecordReference,
    LifecycleTransferStudyDesign,
    build_lifecycle_transfer_evaluation,
)
from aec_bench.task_world_templates.lifecycles import (
    SealedLifecycleMount,
    materialize_sealed_lifecycle,
)
from tests.meta_harness.test_evidence_lifecycle_transfer import _write_record
from tests.support.sealed_lifecycle_audit import (
    CompletedSealedLifecycleAudit,
    build_completed_sealed_lifecycle_audit,
)
from tests.support.sealed_lifecycle_provider import FakeSealedLifecycleProvider


@dataclass(frozen=True)
class _SealedTransferFixture:
    audit: CompletedSealedLifecycleAudit
    private_ledger_root: Path
    target_record_path: Path
    spec: LifecycleTransferEvaluationSpec


@pytest.fixture(scope="module")
def sealed_transfer_fixture(tmp_path_factory: pytest.TempPathFactory) -> _SealedTransferFixture:
    return _sealed_transfer_fixture(tmp_path_factory.mktemp("sealed-transfer"))


@pytest.fixture(autouse=True)
def restore_sealed_transfer_fixture(
    sealed_transfer_fixture: _SealedTransferFixture,
) -> Any:
    provider = sealed_transfer_fixture.audit.mount.provider
    assert isinstance(provider, FakeSealedLifecycleProvider)
    audit_revision = provider.audit_revision
    failure_stage = provider.failure_stage
    calls = Counter(provider.calls)
    state_path = sealed_transfer_fixture.audit.run_dir / "state.json"
    state_bytes = state_path.read_bytes()
    yield
    provider.audit_revision = audit_revision
    provider.failure_stage = failure_stage
    provider.calls.clear()
    provider.calls.update(calls)
    state_path.write_bytes(state_bytes)


def test_sealed_evaluator_requires_explicit_target_mount(
    sealed_transfer_fixture: _SealedTransferFixture,
) -> None:
    fixture = sealed_transfer_fixture
    evaluator = transfer_runtime.build_sealed_lifecycle_transfer_evaluation

    with pytest.raises(TypeError, match="target_mount"):
        evaluator(fixture.spec)


def test_sealed_evaluator_requires_exactly_one_target_record(
    sealed_transfer_fixture: _SealedTransferFixture,
) -> None:
    fixture = sealed_transfer_fixture
    second = LifecycleTransferRecordReference(
        experiment_id="another-sealed-holdout",
        trial_id="another-target",
        ledger_path=str((fixture.private_ledger_root / "another-sealed-holdout" / "another-target.json").resolve()),
        sha256="9" * 64,
    )
    two_targets = LifecycleTransferEvaluationSpec.model_validate(
        {
            **fixture.spec.model_dump(mode="json"),
            "holdout_target_records": [
                *[item.model_dump(mode="json") for item in fixture.spec.holdout_target_records],
                second.model_dump(mode="json"),
            ],
        }
    )

    with pytest.raises(ValueError, match="exactly one target"):
        _evaluate(two_targets, target_mount=fixture.audit.mount)


def test_sealed_evaluator_replays_resolver_and_verifier_before_evaluating(
    sealed_transfer_fixture: _SealedTransferFixture,
) -> None:
    fixture = sealed_transfer_fixture
    provider = fixture.audit.mount.provider
    assert isinstance(provider, FakeSealedLifecycleProvider)
    provider.calls.clear()

    result = _evaluate(fixture.spec, target_mount=fixture.audit.mount)

    assert result.status == "evaluated"
    assert result.calibration_support_count == 1
    assert result.eligible_target_count == 1
    assert result.mean_target_reward == 1.0
    assert provider.calls["build_operation_resolver"] >= 1
    assert provider.calls["verify"] >= 1


def test_sealed_evaluator_counts_a_verified_zero_reward_as_real_evidence(tmp_path: Path) -> None:
    fixture = _sealed_transfer_fixture(tmp_path, pass_verification=False)

    result = _evaluate(fixture.spec, target_mount=fixture.audit.mount)

    assert result.status == "evaluated"
    assert result.eligible_target_count == 1
    assert result.mean_target_reward == 0.0
    assert result.target_results[0].verifier_reward == 0.0
    assert result.target_results[0].verifier_validity is not None
    assert result.target_results[0].verifier_validity.verifier_completed is True


@pytest.mark.parametrize("failure_stage", ["current_source", "verify"])
def test_sealed_evaluator_fails_closed_when_private_replay_fails(
    sealed_transfer_fixture: _SealedTransferFixture,
    failure_stage: str,
) -> None:
    fixture = sealed_transfer_fixture
    provider = fixture.audit.mount.provider
    assert isinstance(provider, FakeSealedLifecycleProvider)
    provider.calls.clear()
    provider.failure_stage = failure_stage

    result = _evaluate(fixture.spec, target_mount=fixture.audit.mount)

    assert result.status == "not_evaluable"
    assert result.eligible_target_count == 0
    assert result.target_results[0].status == "not_evaluable"
    assert result.target_results[0].reasons
    serialized = json.dumps(result.model_dump(mode="json"), sort_keys=True)
    assert all(secret not in serialized for secret in provider.sentinels.values())
    expected_call = "verify" if failure_stage == "verify" else "build_operation_resolver"
    assert provider.calls[expected_call] >= 1


def test_sealed_evaluator_fails_closed_on_provider_semantic_drift(
    sealed_transfer_fixture: _SealedTransferFixture,
) -> None:
    fixture = sealed_transfer_fixture
    provider = fixture.audit.mount.provider
    assert isinstance(provider, FakeSealedLifecycleProvider)
    provider.audit_revision = "drifted-after-finalization"

    result = _evaluate(fixture.spec, target_mount=fixture.audit.mount)

    assert result.status == "not_evaluable"
    assert result.eligible_target_count == 0
    assert result.target_results[0].status == "not_evaluable"
    assert result.target_results[0].reasons
    serialized = json.dumps(result.model_dump(mode="json"), sort_keys=True)
    assert all(secret not in serialized for secret in provider.sentinels.values())


def test_sealed_evaluator_fails_closed_on_wrong_explicit_mount(
    sealed_transfer_fixture: _SealedTransferFixture,
    tmp_path: Path,
) -> None:
    wrong_provider = FakeSealedLifecycleProvider()
    wrong_provider.audit_revision = "different-target-contract"
    wrong_mount = materialize_sealed_lifecycle(wrong_provider, tmp_path / "wrong-package")

    result = _evaluate(sealed_transfer_fixture.spec, target_mount=wrong_mount)

    assert result.status == "not_evaluable"
    assert result.eligible_target_count == 0
    assert result.target_results[0].status == "not_evaluable"
    assert result.target_results[0].reasons
    serialized = json.dumps(result.model_dump(mode="json"), sort_keys=True)
    assert all(secret not in serialized for secret in wrong_provider.sentinels.values())


def test_sealed_evaluator_uses_snapshot_after_original_run_mutation(
    sealed_transfer_fixture: _SealedTransferFixture,
) -> None:
    fixture = sealed_transfer_fixture
    original_record = fixture.target_record_path.read_bytes()
    original_state = fixture.audit.run_dir / "state.json"
    original_state.write_text('{"mutated_after_finalization":true}\n', encoding="utf-8")

    result = _evaluate(fixture.spec, target_mount=fixture.audit.mount)

    assert result.status == "evaluated"
    assert result.eligible_target_count == 1
    assert result.mean_target_reward == 1.0
    assert fixture.target_record_path.read_bytes() == original_record


def test_sealed_evaluator_binds_selected_condition_to_snapshotted_freeze(
    sealed_transfer_fixture: _SealedTransferFixture,
) -> None:
    fixture = sealed_transfer_fixture
    different_condition = fixture.spec.selected_condition.model_copy(update={"model": "different-model"})
    mismatched = LifecycleTransferEvaluationSpec.model_validate(
        {
            **fixture.spec.model_dump(mode="json"),
            "selected_condition": different_condition.model_dump(mode="json"),
        }
    )

    with pytest.raises(ValueError, match="selected condition|frozen"):
        _evaluate(mismatched, target_mount=fixture.audit.mount)


def test_sealed_evaluator_binds_public_refs_to_snapshotted_calibration_freeze(
    sealed_transfer_fixture: _SealedTransferFixture,
) -> None:
    fixture = sealed_transfer_fixture
    frozen_reference = fixture.spec.public_calibration_records[0]
    different_reference = frozen_reference.model_copy(update={"sha256": "8" * 64})
    mismatched = LifecycleTransferEvaluationSpec.model_validate(
        {
            **fixture.spec.model_dump(mode="json"),
            "public_calibration_records": [different_reference.model_dump(mode="json")],
        }
    )

    with pytest.raises(ValueError, match="public calibration|frozen"):
        _evaluate(mismatched, target_mount=fixture.audit.mount)


def test_public_evaluator_remains_mount_free_for_public_record_validation(tmp_path: Path) -> None:
    condition = _sealed_condition()
    calibration = _write_record(
        tmp_path,
        experiment_id="public-calibration",
        trial_id="public-record",
        visibility=Visibility.PUBLIC,
        package_sha256="a" * 64,
        reward=1.0,
        condition=condition,
    )
    missing_target = LifecycleTransferRecordReference(
        experiment_id="unavailable-holdout",
        trial_id="unavailable-target",
        ledger_path=str((tmp_path / "ledger" / "unavailable-holdout" / "unavailable-target.json").resolve()),
        sha256="7" * 64,
    )

    result = build_lifecycle_transfer_evaluation(
        _spec(
            condition=condition,
            calibration=(calibration.reference,),
            targets=(missing_target,),
        )
    )

    assert result.status == "not_evaluable"
    assert result.calibration_support_count == 1
    assert result.target_results[0].reasons == ("record_missing",)


def test_public_evaluator_requires_the_sealed_path_for_a_private_target(
    sealed_transfer_fixture: _SealedTransferFixture,
) -> None:
    result = build_lifecycle_transfer_evaluation(sealed_transfer_fixture.spec)

    assert result.status == "not_evaluable"
    assert result.calibration_support_count == 1
    assert result.target_results[0].reasons == ("sealed_target_mount_required",)


def _sealed_transfer_fixture(
    tmp_path: Path,
    *,
    pass_verification: bool = True,
) -> _SealedTransferFixture:
    condition = _sealed_condition()
    calibration = _write_record(
        tmp_path / "public",
        experiment_id="ssc03-calibration",
        trial_id="trial-public",
        visibility=Visibility.PUBLIC,
        package_sha256="a" * 64,
        reward=1.0,
        condition=condition,
    )
    calibration_reference = LifecycleCalibrationRecordReference.model_validate(
        calibration.reference.model_dump(mode="json")
    )
    sealed_root = tmp_path / "sealed"
    sealed_root.mkdir()
    audit = build_completed_sealed_lifecycle_audit(
        sealed_root,
        public_calibration_record=calibration_reference,
        pass_verification=pass_verification,
    )
    private_ledger_root = audit.private_ledger_root
    target_record_path = finalize_lifecycle_holdout_trial_record(
        run_dir=audit.run_dir,
        run_start_path=audit.run_start_path,
        calibration_freeze_path=audit.calibration_freeze_path,
        target_freeze_path=audit.target_freeze_path,
        claim_path=audit.claim_path,
        mount=audit.mount,
        selected_condition=audit.selected_condition,
        private_ledger_root=private_ledger_root,
        repository_dir=audit.repository_dir,
        agent_evidence=audit.agent_evidence,
        verified_result=audit.verified_result,
    )
    target_record = TrialRecord.model_validate_json(target_record_path.read_bytes())
    target_reference = LifecycleTransferRecordReference(
        experiment_id=target_record.experiment_id,
        trial_id=target_record.trial_id,
        ledger_path=str(target_record_path),
        sha256=_sha256(target_record_path),
    )
    return _SealedTransferFixture(
        audit=audit,
        private_ledger_root=private_ledger_root,
        target_record_path=target_record_path,
        spec=_spec(
            condition=condition,
            calibration=(calibration.reference,),
            targets=(target_reference,),
        ),
    )


def _sealed_condition() -> LifecycleTransferCondition:
    runtime = runtime_dependency_provenance(
        adapter_kind="tool_loop",
        model_name="anthropic:fixture-model",
    )
    return LifecycleTransferCondition(
        model="anthropic:fixture-model",
        adapter="tool_loop",
        runtime_dependency_sha256=str(runtime["dependency_inventory_sha256"]),
        execution_mode=LifecycleExecutionMode.PERSISTENT_CONTEXT,
        memory_visibility_policy=LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
        max_turns_per_session=12,
    )


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


def _evaluate(
    spec: LifecycleTransferEvaluationSpec,
    *,
    target_mount: SealedLifecycleMount,
) -> Any:
    evaluator = transfer_runtime.build_sealed_lifecycle_transfer_evaluation
    return evaluator(spec, target_mount=target_mount)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
