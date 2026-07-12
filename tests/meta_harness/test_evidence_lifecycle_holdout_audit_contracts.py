# ABOUTME: Tests the frozen-target, one-shot claim, and public receipt contracts for sealed audits.
# ABOUTME: Keeps private identities in write-once artifacts while proving public output is allowlisted.

from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.contracts.experiment_manifest import AgentConfig
from aec_bench.meta_harness.evidence_lifecycle_ablation_plan import (
    LifecycleAblationCondition,
    LifecycleAblationLimits,
    LifecycleAblationManifest,
    LifecycleAblationStudyDesign,
    LifecycleCalibrationSelectionPolicy,
    build_lifecycle_ablation_plan,
)
from aec_bench.meta_harness.evidence_lifecycle_calibration import (
    FrozenLifecycleCondition,
    LifecycleCalibrationCandidateResult,
    LifecycleCalibrationFreeze,
    LifecycleCalibrationPlannedCondition,
    LifecycleCalibrationRecordReference,
    LifecycleCalibrationSpendEnvelope,
)
from aec_bench.meta_harness.evidence_lifecycle_episode import (
    LifecycleExecutionMode,
    LifecycleVisibilityPolicy,
)
from aec_bench.meta_harness.evidence_lifecycle_holdout_audit import (
    LifecycleHoldoutAuditAlreadyClaimedError,
    LifecycleHoldoutAuditOutcomeCounts,
    LifecycleHoldoutAuditReceipt,
    LifecycleHoldoutTargetCommitment,
    build_lifecycle_holdout_audit_receipt,
    claim_lifecycle_holdout_audit,
    validate_lifecycle_holdout_target_freeze,
    write_lifecycle_holdout_audit_receipt,
    write_lifecycle_holdout_target_commitment,
    write_lifecycle_holdout_target_freeze,
)
from aec_bench.meta_harness.evidence_lifecycle_transfer import (
    LifecycleTransferCalibrationResult,
    LifecycleTransferCondition,
    LifecycleTransferRecordReference,
    LifecycleTransferStudyDesign,
    LifecycleTransferSummary,
    LifecycleTransferTargetResult,
)
from aec_bench.task_world_templates.lifecycles import materialize_sealed_lifecycle
from tests.support.sealed_lifecycle_provider import FakeSealedLifecycleProvider


def test_target_freeze_binds_package_tree_provider_protocol_resolver_and_verifier_identities(
    tmp_path: Path,
) -> None:
    manifest = _campaign_manifest(tmp_path)
    plan = build_lifecycle_ablation_plan(manifest)
    provider = FakeSealedLifecycleProvider()
    mount = materialize_sealed_lifecycle(provider, tmp_path / "sealed-package")

    target_path = write_lifecycle_holdout_target_freeze(
        calibration_manifest=manifest,
        mount=mount,
        commitment_salt="f" * 64,
        output_path=tmp_path / "private" / "target-freeze.json",
    )
    target = validate_lifecycle_holdout_target_freeze(
        calibration_manifest=manifest,
        target_freeze_path=target_path,
        mount=mount,
    )

    assert target.public_manifest_sha256 == plan.manifest_sha256
    assert target.public_plan_sha256 == plan.plan_sha256
    assert target.package_sha256 == mount.package_sha256
    assert target.package_tree_sha256 == mount.package_tree_sha256
    assert target.holdout_repetitions == 1
    assert (
        target.provider_identity.resolver_contract_sha256
        == provider.audit_contract_identity(mount.package_dir)["resolver_contract_sha256"]
    )
    assert (
        target.provider_identity.verifier_contract_sha256
        == provider.audit_contract_identity(mount.package_dir)["verifier_contract_sha256"]
    )
    public_path = write_lifecycle_holdout_target_commitment(
        target_freeze_path=target_path,
        output_path=tmp_path / "public" / "target-commitment.json",
    )
    public = LifecycleHoldoutTargetCommitment.model_validate_json(public_path.read_bytes())
    assert public.target_commitment_sha256 == target.public_target_commitment_sha256
    serialized = json.dumps(public.model_dump(mode="json"), sort_keys=True)
    assert target.package_sha256 not in serialized
    assert target.package_tree_sha256 not in serialized
    assert target.commitment_salt not in serialized


def test_target_freeze_is_idempotent_and_rejects_package_or_provider_semantic_drift(tmp_path: Path) -> None:
    manifest = _campaign_manifest(tmp_path)
    provider = FakeSealedLifecycleProvider()
    mount = materialize_sealed_lifecycle(provider, tmp_path / "sealed-package")
    target_path = tmp_path / "private" / "target-freeze.json"

    first = write_lifecycle_holdout_target_freeze(
        calibration_manifest=manifest,
        mount=mount,
        commitment_salt="f" * 64,
        output_path=target_path,
    )
    second = write_lifecycle_holdout_target_freeze(
        calibration_manifest=manifest,
        mount=mount,
        commitment_salt="f" * 64,
        output_path=target_path,
    )
    assert first == second == target_path

    provider.audit_revision = "drifted"
    with pytest.raises(ValueError, match="sealed target freeze does not match the active provider"):
        validate_lifecycle_holdout_target_freeze(
            calibration_manifest=manifest,
            target_freeze_path=target_path,
            mount=mount,
        )


def test_audit_claim_binds_both_freezes_and_consumes_the_one_execution_slot(tmp_path: Path) -> None:
    manifest = _campaign_manifest(tmp_path)
    calibration_path, calibration = _write_calibration_freeze(tmp_path, manifest=manifest)
    provider = FakeSealedLifecycleProvider()
    mount = materialize_sealed_lifecycle(provider, tmp_path / "sealed-package")
    target_path = write_lifecycle_holdout_target_freeze(
        calibration_manifest=manifest,
        mount=mount,
        commitment_salt="f" * 64,
        output_path=tmp_path / "private" / "target-freeze.json",
    )
    claim_path = tmp_path / "private" / "audit" / "claim.json"

    claim = claim_lifecycle_holdout_audit(
        calibration_freeze_path=calibration_path,
        target_freeze_path=target_path,
        mount=mount,
        output_path=claim_path,
    )

    assert claim.calibration_freeze_sha256 == calibration.freeze_sha256
    assert (
        claim.target_freeze_sha256
        == validate_lifecycle_holdout_target_freeze(
            calibration_manifest=manifest,
            target_freeze_path=target_path,
            mount=mount,
        ).target_freeze_sha256
    )
    assert claim.holdout_repetition == 1
    assert claim.status == "claimed"
    with pytest.raises(LifecycleHoldoutAuditAlreadyClaimedError, match="sealed holdout audit already claimed"):
        claim_lifecycle_holdout_audit(
            calibration_freeze_path=calibration_path,
            target_freeze_path=target_path,
            mount=mount,
            output_path=claim_path,
        )


def test_private_roots_are_owner_only_and_concurrent_claim_allows_one_slot(tmp_path: Path) -> None:
    manifest = _campaign_manifest(tmp_path)
    calibration_path, _ = _write_calibration_freeze(tmp_path, manifest=manifest)
    provider = FakeSealedLifecycleProvider()
    mount = materialize_sealed_lifecycle(provider, tmp_path / "sealed-package")
    insecure_root = tmp_path / "insecure-private"
    insecure_root.mkdir(mode=0o755)
    os.chmod(insecure_root, 0o755)
    with pytest.raises(ValueError, match="owner-only"):
        write_lifecycle_holdout_target_freeze(
            calibration_manifest=manifest,
            mount=mount,
            commitment_salt="f" * 64,
            output_path=insecure_root / "target-freeze.json",
        )
    assert not (insecure_root / "target-freeze.json").exists()

    target_path = write_lifecycle_holdout_target_freeze(
        calibration_manifest=manifest,
        mount=mount,
        commitment_salt="f" * 64,
        output_path=tmp_path / "private" / "target-freeze.json",
    )
    claim_path = tmp_path / "private" / "audit" / "claim.json"

    def claim() -> str:
        try:
            return claim_lifecycle_holdout_audit(
                calibration_freeze_path=calibration_path,
                target_freeze_path=target_path,
                mount=mount,
                output_path=claim_path,
            ).status
        except LifecycleHoldoutAuditAlreadyClaimedError:
            return "already_claimed"

    with ThreadPoolExecutor(max_workers=4) as executor:
        outcomes = list(executor.map(lambda _: claim(), range(4)))

    assert outcomes.count("claimed") == 1
    assert outcomes.count("already_claimed") == 3
    assert claim_path.stat().st_mode & 0o077 == 0


def test_audit_claim_rejects_calibration_freeze_that_does_not_match_target_commitment(tmp_path: Path) -> None:
    manifest = _campaign_manifest(tmp_path)
    calibration_path, calibration = _write_calibration_freeze(tmp_path, manifest=manifest)
    provider = FakeSealedLifecycleProvider()
    mount = materialize_sealed_lifecycle(provider, tmp_path / "sealed-package")
    target_path = write_lifecycle_holdout_target_freeze(
        calibration_manifest=manifest,
        mount=mount,
        commitment_salt="f" * 64,
        output_path=tmp_path / "private" / "target-freeze.json",
    )
    payload = calibration.model_dump(mode="json")
    payload["plan_sha256"] = "9" * 64
    payload["freeze_sha256"] = _payload_sha256(payload, exclude={"freeze_sha256"})
    mismatched = LifecycleCalibrationFreeze.model_validate(payload)
    mismatched_path = tmp_path / "mismatched-calibration-freeze.json"
    mismatched_path.write_text(
        json.dumps(mismatched.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    claim_path = tmp_path / "private" / "audit" / "claim.json"

    with pytest.raises(ValueError, match="does not match the precommitted target campaign"):
        claim_lifecycle_holdout_audit(
            calibration_freeze_path=mismatched_path,
            target_freeze_path=target_path,
            mount=mount,
            output_path=claim_path,
        )
    assert not claim_path.exists()


def test_public_receipt_is_an_exact_allowlist_recomputed_from_private_summary(tmp_path: Path) -> None:
    manifest = _campaign_manifest(tmp_path)
    _, calibration = _write_calibration_freeze(tmp_path, manifest=manifest)
    provider = FakeSealedLifecycleProvider()
    mount = materialize_sealed_lifecycle(provider, tmp_path / "sealed-package")
    target_path = write_lifecycle_holdout_target_freeze(
        calibration_manifest=manifest,
        mount=mount,
        commitment_salt="f" * 64,
        output_path=tmp_path / "private" / "target-freeze.json",
    )
    summary = _transfer_summary(tmp_path, reward=1.0)

    receipt = build_lifecycle_holdout_audit_receipt(
        calibration_freeze=calibration,
        target_freeze_path=target_path,
        private_summary=summary,
    )

    assert set(receipt.model_dump(mode="json")) == {
        "schema_version",
        "publication_sha256",
        "calibration_freeze_sha256",
        "target_commitment_sha256",
        "interpretation",
        "causal_effects_supported",
        "cross_run_learning_supported",
        "target_record_count",
        "eligible_target_count",
        "mean_target_reward",
        "outcome_counts",
    }
    assert receipt.outcome_counts == LifecycleHoldoutAuditOutcomeCounts(
        evaluated_pass=1,
        evaluated_fail=0,
        not_evaluable=0,
    )
    serialized = json.dumps(receipt.model_dump(mode="json"), sort_keys=True)
    assert str(tmp_path) not in serialized
    assert "trial-holdout" not in serialized
    assert "model-high" not in serialized

    output = tmp_path / "public" / "holdout-audit-receipt.json"
    assert write_lifecycle_holdout_audit_receipt(receipt, output) == output
    assert write_lifecycle_holdout_audit_receipt(receipt, output) == output
    assert LifecycleHoldoutAuditReceipt.model_validate_json(output.read_bytes()) == receipt


def test_public_receipt_rejects_private_fields_and_inconsistent_aggregates(tmp_path: Path) -> None:
    manifest = _campaign_manifest(tmp_path)
    _, calibration = _write_calibration_freeze(tmp_path, manifest=manifest)
    provider = FakeSealedLifecycleProvider()
    mount = materialize_sealed_lifecycle(provider, tmp_path / "sealed-package")
    target_path = write_lifecycle_holdout_target_freeze(
        calibration_manifest=manifest,
        mount=mount,
        commitment_salt="f" * 64,
        output_path=tmp_path / "private" / "target-freeze.json",
    )
    receipt = build_lifecycle_holdout_audit_receipt(
        calibration_freeze=calibration,
        target_freeze_path=target_path,
        private_summary=_transfer_summary(tmp_path, reward=0.0),
    )
    payload = receipt.model_dump(mode="json")
    payload["private_record_path"] = str(tmp_path / "private" / "record.json")
    with pytest.raises(ValidationError):
        LifecycleHoldoutAuditReceipt.model_validate(payload)

    payload = receipt.model_dump(mode="json")
    payload["eligible_target_count"] = 0
    payload["publication_sha256"] = _payload_sha256(payload, exclude={"publication_sha256"})
    with pytest.raises(ValidationError, match="outcome counts"):
        LifecycleHoldoutAuditReceipt.model_validate(payload)


def _campaign_manifest(tmp_path: Path) -> LifecycleAblationManifest:
    return LifecycleAblationManifest(
        experiment_id="ssc03-calibration",
        lifecycle_template_id="hydraulic-interaction-lifecycle-review",
        variants=(
            "administrative_no_op",
            "major_idf_revision",
            "outlet_geometry_revision",
            "tailwater_revision",
        ),
        agents=(
            AgentConfig(
                name="hydraulic-calibration-model",
                adapter="tool_loop",
                model="model-high",
                parameters={"max_turns_per_session": 12},
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
                execution_mode=LifecycleExecutionMode.PERSISTENT_CONTEXT,
                memory_visibility_policy=LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
            ),
        ),
        repetitions=1,
        output_root=str((tmp_path / "output").resolve()),
        ledger_root=str((tmp_path / "ledger").resolve()),
        limits=LifecycleAblationLimits(max_trials=4, max_estimated_cost_usd=4.0),
        estimated_cost_per_trial_usd=1.0,
        selection_policy=LifecycleCalibrationSelectionPolicy(
            objective="max_mean_verifier_reward",
            candidate_coverage="all_public_variants_and_repetitions",
            public_variant_ids=(
                "administrative_no_op",
                "major_idf_revision",
                "outlet_geometry_revision",
                "tailwater_revision",
            ),
            incomplete_candidate="ineligible",
            tie_break="canonical_condition_identity",
            interaction_protocol="lifecycle_operation",
            public_repetitions=1,
            holdout_repetitions=1,
        ),
    )


def _write_calibration_freeze(
    tmp_path: Path,
    *,
    manifest: LifecycleAblationManifest | None = None,
) -> tuple[Path, LifecycleCalibrationFreeze]:
    manifest = manifest or _campaign_manifest(tmp_path)
    plan = build_lifecycle_ablation_plan(manifest)
    record = LifecycleCalibrationRecordReference(
        experiment_id="ssc03-calibration",
        trial_id="trial-public",
        ledger_path=str((tmp_path / "trial-public.json").resolve()),
        sha256="1" * 64,
    )
    planned = LifecycleCalibrationPlannedCondition(
        requested_model="model-high",
        requested_adapter="tool_loop",
        runtime_provider="deterministic",
        runtime_distributions=("aec-bench",),
        runtime_dependency_sha256="c" * 64,
        execution_mode=LifecycleExecutionMode.PERSISTENT_CONTEXT,
        memory_visibility_policy=LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
        max_turns_per_session=12,
    )
    frozen = FrozenLifecycleCondition(
        **planned.model_dump(mode="python"),
        resolved_model="model-high",
        resolved_adapter="tool_loop",
        interaction_protocol="lifecycle_operation",
        interaction_protocol_sha256="d" * 64,
        tool_schema_sha256="e" * 64,
    )
    candidate = LifecycleCalibrationCandidateResult(
        candidate_id=f"condition-{_payload_sha256(planned.model_dump(mode='json'))}",
        planned_condition=planned,
        status="eligible",
        planned_trials=1,
        completed_records=1,
        mean_verifier_reward=1.0,
        frozen_condition=frozen,
        records=(record,),
    )
    policy = manifest.selection_policy
    assert policy is not None
    payload = {
        "schema_version": "1",
        "freeze_sha256": "0" * 64,
        "experiment_id": "ssc03-calibration",
        "manifest_sha256": plan.manifest_sha256,
        "plan_sha256": plan.plan_sha256,
        "selection_policy": policy.model_dump(mode="json"),
        "spend_envelope": LifecycleCalibrationSpendEnvelope(
            planned_trials=1,
            estimated_cost_per_trial_usd=1.0,
            planned_estimated_cost_usd=1.0,
            max_estimated_cost_usd=1.0,
        ).model_dump(mode="json"),
        "selected_candidate_id": candidate.candidate_id,
        "selected_condition": frozen.model_dump(mode="json"),
        "selected_mean_verifier_reward": 1.0,
        "public_calibration_records": [record.model_dump(mode="json")],
        "candidates": [candidate.model_dump(mode="json")],
    }
    payload["freeze_sha256"] = _payload_sha256(payload, exclude={"freeze_sha256"})
    freeze = LifecycleCalibrationFreeze.model_validate(payload)
    path = tmp_path / "calibration-freeze.json"
    path.write_text(json.dumps(freeze.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path, freeze


def _transfer_summary(tmp_path: Path, *, reward: float) -> LifecycleTransferSummary:
    selected = LifecycleTransferCondition(
        model="model-high",
        adapter="tool_loop",
        runtime_dependency_sha256="c" * 64,
        execution_mode=LifecycleExecutionMode.PERSISTENT_CONTEXT,
        memory_visibility_policy=LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
        max_turns_per_session=12,
    )
    calibration_reference = LifecycleTransferRecordReference(
        experiment_id="ssc03-calibration",
        trial_id="trial-public",
        ledger_path=str((tmp_path / "ssc03-calibration" / "trial-public.json").resolve()),
        sha256="1" * 64,
    )
    holdout_reference = LifecycleTransferRecordReference(
        experiment_id="ssc03-holdout",
        trial_id="trial-holdout",
        ledger_path=str((tmp_path / "ssc03-holdout" / "trial-holdout.json").resolve()),
        sha256="2" * 64,
    )
    return LifecycleTransferSummary(
        evaluation_id="private-evaluation-id",
        status="evaluated",
        study_design=LifecycleTransferStudyDesign(
            interpretation="descriptive_holdout_generalization",
            selection_basis="public_calibration",
            causal_effects_supported=False,
            cross_run_learning_supported=False,
        ),
        selected_condition=selected,
        calibration_record_count=1,
        calibration_support_count=1,
        target_record_count=1,
        eligible_target_count=1,
        mean_target_reward=reward,
        calibration_results=(
            LifecycleTransferCalibrationResult(
                record=calibration_reference,
                status="supports_selected_condition",
            ),
        ),
        target_results=(
            LifecycleTransferTargetResult(
                record=holdout_reference,
                status="eligible",
                verifier_reward=reward,
            ),
        ),
    )


def _payload_sha256(payload: object, *, exclude: set[str] | None = None) -> str:
    if isinstance(payload, dict) and exclude:
        payload = {key: value for key, value in payload.items() if key not in exclude}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
