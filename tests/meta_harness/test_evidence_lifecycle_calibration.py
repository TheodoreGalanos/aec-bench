# ABOUTME: Tests public-only lifecycle calibration selection and immutable condition freezing.
# ABOUTME: Binds preregistered policy, complete campaign evidence, and exact interaction provenance.

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import ValidationError

import aec_bench.meta_harness.evidence_lifecycle_calibration as calibration_runtime
from aec_bench.contracts.experiment_manifest import AgentConfig
from aec_bench.contracts.trial_record import ArtifactReference, TrialRecord
from aec_bench.meta_harness.evidence_lifecycle_ablation import run_lifecycle_ablation
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
    build_lifecycle_calibration_freeze,
)
from aec_bench.meta_harness.evidence_lifecycle_episode import (
    LifecycleExecutionMode,
    LifecycleVisibilityPolicy,
)
from aec_bench.task_world_templates.lifecycles import materialize_sealed_lifecycle
from tests.support.sealed_lifecycle_provider import FakeSealedLifecycleProvider


def test_preregistered_selection_policy_changes_manifest_and_plan_identity(tmp_path: Path) -> None:
    baseline = _manifest(tmp_path, selection_policy=None)
    preregistered = _manifest(tmp_path, selection_policy=_selection_policy())

    baseline_plan = build_lifecycle_ablation_plan(baseline)
    preregistered_plan = build_lifecycle_ablation_plan(preregistered)

    assert baseline.selection_policy is None
    assert preregistered.selection_policy == _selection_policy()
    assert preregistered_plan.manifest_sha256 != baseline_plan.manifest_sha256
    assert preregistered_plan.plan_sha256 != baseline_plan.plan_sha256
    assert preregistered_plan.trials[0].trial_id != baseline_plan.trials[0].trial_id


def test_freeze_requires_preregistered_policy_and_every_planned_record(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="selection policy was not preregistered"):
        build_lifecycle_calibration_freeze(_manifest(tmp_path, selection_policy=None))

    with pytest.raises(ValueError, match="public calibration campaign is incomplete"):
        build_lifecycle_calibration_freeze(_manifest(tmp_path, selection_policy=_selection_policy()))


def test_preregistered_selection_requires_exact_repetitions_and_spend_envelope(tmp_path: Path) -> None:
    payload = _manifest(tmp_path, selection_policy=_selection_policy()).model_dump(mode="json")
    payload["repetitions"] = 2
    with pytest.raises(ValidationError, match="public repetitions"):
        LifecycleAblationManifest.model_validate(payload)

    payload = _manifest(tmp_path, selection_policy=_selection_policy()).model_dump(mode="json")
    payload["limits"]["max_estimated_cost_usd"] = None
    with pytest.raises(ValidationError, match="spend envelope"):
        LifecycleAblationManifest.model_validate(payload)


@pytest.mark.parametrize("field", ("estimated_cost_per_trial_usd", "max_estimated_cost_usd", "planned_cost"))
def test_preregistered_selection_requires_finite_spend_envelope(tmp_path: Path, field: str) -> None:
    payload = _manifest(tmp_path, selection_policy=_selection_policy()).model_dump(mode="json")
    if field == "estimated_cost_per_trial_usd":
        payload[field] = float("inf")
    elif field == "max_estimated_cost_usd":
        payload["limits"][field] = float("inf")
    else:
        payload["estimated_cost_per_trial_usd"] = 1e308
        payload["limits"]["max_estimated_cost_usd"] = 1e308

    with pytest.raises(ValidationError, match="finite estimated spend envelope"):
        LifecycleAblationManifest.model_validate(payload)


def test_preregistered_selection_requires_every_registered_public_variant(tmp_path: Path) -> None:
    payload = _manifest(tmp_path, selection_policy=_selection_policy()).model_dump(mode="json")
    payload["variants"] = ["administrative_no_op"]

    with pytest.raises(ValidationError, match="captured public variant ids"):
        LifecycleAblationManifest.model_validate(payload)

    payload = _manifest(tmp_path, selection_policy=_selection_policy()).model_dump(mode="json")
    payload["variants"] = ["administrative_no_op"]
    payload["selection_policy"]["public_variant_ids"] = ["administrative_no_op"]
    manifest = LifecycleAblationManifest.model_validate(payload)
    with pytest.raises(ValueError, match="every currently registered public variant"):
        build_lifecycle_ablation_plan(manifest)


def test_missing_provider_credentials_fail_before_campaign_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    manifest = _manifest(
        tmp_path,
        selection_policy=_selection_policy(),
        agents=(_agent("paid-model", "anthropic:claude-sonnet-4-6"),),
    )

    with pytest.raises(ValueError, match="provider configuration preflight failed.*ANTHROPIC_API_KEY"):
        run_lifecycle_ablation(manifest)

    assert not Path(manifest.output_root).exists()
    assert not Path(manifest.ledger_root).exists()


def test_freeze_refuses_to_run_inside_a_sealed_holdout_mount(tmp_path: Path) -> None:
    mount = materialize_sealed_lifecycle(
        FakeSealedLifecycleProvider(),
        tmp_path / "sealed-package",
    )
    manifest = _manifest(tmp_path, selection_policy=_selection_policy())

    with mount.activate(), pytest.raises(ValueError, match="sealed holdout is mounted"):
        build_lifecycle_calibration_freeze(manifest)


def test_selectable_campaign_rejects_injected_registry_before_writes(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, selection_policy=_selection_policy())

    with pytest.raises(ValueError, match="selectable calibration.*provider registry"):
        run_lifecycle_ablation(manifest, registry_factory=lambda *_args: object())

    assert not Path(manifest.output_root).exists()
    assert not Path(manifest.ledger_root).exists()


def test_historical_sweep_contract_loads_captured_plan_after_current_code_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest(tmp_path, selection_policy=_selection_policy())
    plan = build_lifecycle_ablation_plan(manifest)
    manifest_path = Path(manifest.ledger_root) / "snapshot" / "manifest.json"
    plan_path = manifest_path.with_name("plan.json")
    manifest_path.parent.mkdir(parents=True)
    manifest_bytes = _json_bytes(manifest.model_dump(mode="json"))
    plan_bytes = _json_bytes(plan.model_dump(mode="json"))
    manifest_path.write_bytes(manifest_bytes)
    plan_path.write_bytes(plan_bytes)
    record = SimpleNamespace(
        lifecycle_provenance=SimpleNamespace(
            ablation_manifest=_artifact_reference(
                manifest,
                manifest_path,
                manifest_bytes,
                "lifecycle_ablation_manifest",
            ),
            ablation_plan=_artifact_reference(manifest, plan_path, plan_bytes, "lifecycle_ablation_plan"),
        )
    )
    selection_policy = manifest.selection_policy
    assert selection_policy is not None
    monkeypatch.setattr(
        "aec_bench.meta_harness.evidence_lifecycle_ablation_plan._ablation_code_provenance",
        lambda _template_id: plan.code_provenance.model_copy(update={"trial_importer_source_sha256": "0" * 64}),
    )
    monkeypatch.setattr(
        "aec_bench.meta_harness.evidence_lifecycle_ablation_plan.lifecycle_variant_ids",
        lambda _template_id: (*selection_policy.public_variant_ids, "later_public_variant"),
    )

    historical_manifest, historical_plan = calibration_runtime._load_historical_sweep_contract(
        manifest,
        cast(TrialRecord, record),
    )

    assert historical_manifest == manifest
    assert historical_plan == plan


@pytest.mark.parametrize("tamper", ["winner", "duplicate_candidate", "record_partition", "frozen_condition"])
def test_typed_freeze_recomputes_selection_and_candidate_partition(tmp_path: Path, tamper: str) -> None:
    payload = _freeze_payload(tmp_path)
    if tamper == "winner":
        payload["selected_candidate_id"] = payload["candidates"][1]["candidate_id"]
        payload["selected_condition"] = payload["candidates"][1]["frozen_condition"]
        payload["selected_mean_verifier_reward"] = payload["candidates"][1]["mean_verifier_reward"]
    elif tamper == "duplicate_candidate":
        payload["candidates"].append(payload["candidates"][0])
    elif tamper == "frozen_condition":
        payload["candidates"][0]["frozen_condition"]["requested_model"] = "different-model"
    else:
        payload["public_calibration_records"] = payload["public_calibration_records"][:1]
    payload["freeze_sha256"] = _payload_sha256(payload, exclude={"freeze_sha256"})

    with pytest.raises(ValidationError, match="winner|candidate ids|record partition|planned condition"):
        LifecycleCalibrationFreeze.model_validate(payload)


@pytest.mark.parametrize("reward", (float("inf"), -0.1, 1.1))
def test_typed_freeze_requires_finite_bounded_rewards(tmp_path: Path, reward: float) -> None:
    payload = _freeze_payload(tmp_path)
    payload["candidates"][0]["mean_verifier_reward"] = reward
    payload["selected_mean_verifier_reward"] = reward
    payload["freeze_sha256"] = _payload_sha256(payload, exclude={"freeze_sha256"})

    with pytest.raises(ValidationError):
        LifecycleCalibrationFreeze.model_validate(payload)


def test_typed_freeze_requires_finite_spend_values(tmp_path: Path) -> None:
    payload = _freeze_payload(tmp_path)
    payload["spend_envelope"]["estimated_cost_per_trial_usd"] = float("inf")
    payload["spend_envelope"]["planned_estimated_cost_usd"] = float("inf")
    payload["spend_envelope"]["max_estimated_cost_usd"] = float("inf")
    payload["freeze_sha256"] = _payload_sha256(payload, exclude={"freeze_sha256"})

    with pytest.raises(ValidationError):
        LifecycleCalibrationFreeze.model_validate(payload)


def _selection_policy() -> LifecycleCalibrationSelectionPolicy:
    return LifecycleCalibrationSelectionPolicy(
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
    )


def _manifest(
    tmp_path: Path,
    *,
    selection_policy: LifecycleCalibrationSelectionPolicy | None,
    agents: tuple[AgentConfig, ...] | None = None,
    max_trials: int = 4,
    max_estimated_cost_usd: float = 4.0,
) -> LifecycleAblationManifest:
    return LifecycleAblationManifest(
        experiment_id="ssc03-hydraulic-calibration-contract",
        lifecycle_template_id="hydraulic-interaction-lifecycle-review",
        variants=(
            "administrative_no_op",
            "major_idf_revision",
            "outlet_geometry_revision",
            "tailwater_revision",
        ),
        agents=agents or (_agent("deterministic-contract", "deterministic-replay"),),
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
                execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
                memory_visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
            ),
        ),
        repetitions=1,
        output_root=str(tmp_path / "output"),
        ledger_root=str(tmp_path / "ledger"),
        limits=LifecycleAblationLimits(
            max_trials=max_trials,
            max_estimated_cost_usd=max_estimated_cost_usd,
        ),
        estimated_cost_per_trial_usd=1.0,
        selection_policy=selection_policy,
    )


def _agent(name: str, model: str) -> AgentConfig:
    return AgentConfig(
        name=name,
        adapter="tool_loop",
        model=model,
        parameters={"max_turns_per_session": 12},
    )


def _freeze_payload(tmp_path: Path) -> dict[str, Any]:
    records = tuple(
        LifecycleCalibrationRecordReference(
            experiment_id="ssc03-calibration",
            trial_id=f"trial-{index}",
            ledger_path=str((tmp_path / f"trial-{index}.json").resolve()),
            sha256=str(index) * 64,
        )
        for index in (1, 2)
    )
    candidates = tuple(
        _candidate(
            model=model,
            reward=reward,
            record=record,
        )
        for model, reward, record in (
            ("model-high", 1.0, records[0]),
            ("model-low", 0.0, records[1]),
        )
    )
    selected_condition = candidates[0].frozen_condition
    assert selected_condition is not None
    payload: dict[str, Any] = {
        "schema_version": "1",
        "freeze_sha256": "0" * 64,
        "experiment_id": "ssc03-calibration",
        "manifest_sha256": "a" * 64,
        "plan_sha256": "b" * 64,
        "selection_policy": _selection_policy().model_dump(mode="json"),
        "spend_envelope": LifecycleCalibrationSpendEnvelope(
            planned_trials=2,
            estimated_cost_per_trial_usd=1.0,
            planned_estimated_cost_usd=2.0,
            max_estimated_cost_usd=2.0,
        ).model_dump(mode="json"),
        "selected_candidate_id": candidates[0].candidate_id,
        "selected_condition": selected_condition.model_dump(mode="json"),
        "selected_mean_verifier_reward": candidates[0].mean_verifier_reward,
        "public_calibration_records": [record.model_dump(mode="json") for record in records],
        "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
    }
    payload["freeze_sha256"] = _payload_sha256(payload, exclude={"freeze_sha256"})
    LifecycleCalibrationFreeze.model_validate(payload)
    return payload


def _candidate(
    *,
    model: str,
    reward: float,
    record: LifecycleCalibrationRecordReference,
) -> LifecycleCalibrationCandidateResult:
    planned = LifecycleCalibrationPlannedCondition(
        requested_model=model,
        requested_adapter="tool_loop",
        runtime_provider="deterministic",
        runtime_distributions=("aec-bench",),
        runtime_dependency_sha256="c" * 64,
        execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
        memory_visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
        max_turns_per_session=12,
    )
    frozen = FrozenLifecycleCondition(
        **planned.model_dump(mode="python"),
        resolved_model=model,
        resolved_adapter="tool_loop",
        interaction_protocol="lifecycle_operation",
        interaction_protocol_sha256="d" * 64,
        tool_schema_sha256="e" * 64,
    )
    candidate_id = f"condition-{_payload_sha256(planned.model_dump(mode='json'))}"
    return LifecycleCalibrationCandidateResult(
        candidate_id=candidate_id,
        planned_condition=planned,
        status="eligible",
        planned_trials=1,
        completed_records=1,
        mean_verifier_reward=reward,
        frozen_condition=frozen,
        records=(record,),
    )


def _artifact_reference(
    manifest: LifecycleAblationManifest,
    path: Path,
    content: bytes,
    kind: str,
) -> ArtifactReference:
    return ArtifactReference(
        kind=kind,
        path=path.relative_to(Path(manifest.ledger_root)).as_posix(),
        sha256=hashlib.sha256(content).hexdigest(),
        media_type="application/json",
    )


def _json_bytes(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _payload_sha256(payload: object, *, exclude: set[str] | None = None) -> str:
    if isinstance(payload, dict) and exclude:
        payload = {key: value for key, value in payload.items() if key not in exclude}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
