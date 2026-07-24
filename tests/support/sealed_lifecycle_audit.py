# ABOUTME: Builds one completed deterministic sealed lifecycle and its frozen audit authority.
# ABOUTME: Supplies real workspace and control-tool evidence to private holdout record tests.

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

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
from aec_bench.meta_harness.evidence_lifecycle_experiment import runtime_dependency_provenance
from aec_bench.meta_harness.evidence_lifecycle_holdout_audit import (
    claim_lifecycle_holdout_audit,
    write_lifecycle_holdout_target_freeze,
)
from aec_bench.meta_harness.evidence_lifecycle_holdout_execution_contract import (
    build_lifecycle_holdout_run_start,
)
from aec_bench.meta_harness.evidence_lifecycle_local import (
    build_lifecycle_tool_schema,
    run_local_evidence_lifecycle_session,
)
from aec_bench.meta_harness.lifecycle_operation_protocol import (
    lifecycle_operation_protocol_identity,
)
from aec_bench.task_world_templates.lifecycles import (
    SealedLifecycleMount,
    materialize_sealed_lifecycle,
    verify_lifecycle_template,
)
from tests.support.sealed_lifecycle_provider import (
    FIXTURE_CHECKPOINT_ID,
    FIXTURE_OPERATION_ID,
    FakeSealedLifecycleProvider,
)


@dataclass(frozen=True)
class CompletedSealedLifecycleAudit:
    """Collect the private inputs to one holdout record finalization."""

    mount: SealedLifecycleMount
    run_dir: Path
    run_start_path: Path
    private_ledger_root: Path
    calibration_freeze_path: Path
    target_freeze_path: Path
    claim_path: Path
    repository_dir: Path
    selected_condition: FrozenLifecycleCondition
    agent_evidence: dict[str, Any]
    verified_result: dict[str, Any]


def build_completed_sealed_lifecycle_audit(
    tmp_path: Path,
    *,
    public_calibration_record: LifecycleCalibrationRecordReference | None = None,
    pass_verification: bool = True,
) -> CompletedSealedLifecycleAudit:
    """Run one deterministic sealed task through the production workspace/control boundary."""
    tmp_path = Path(tmp_path).resolve()
    private_root = tmp_path / "private"
    private_root.mkdir(mode=0o700)
    os.chmod(private_root, 0o700)
    provider = FakeSealedLifecycleProvider()
    mount = materialize_sealed_lifecycle(provider, private_root / "package")
    manifest = _campaign_manifest(tmp_path)
    calibration_freeze_path, calibration = _write_calibration_freeze(
        private_root / "authority" / "calibration-freeze.json",
        manifest=manifest,
        tmp_path=tmp_path,
        public_calibration_record=public_calibration_record,
    )
    target_freeze_path = write_lifecycle_holdout_target_freeze(
        calibration_manifest=manifest,
        mount=mount,
        commitment_salt="f" * 64,
        output_path=private_root / "authority" / "target-freeze.json",
    )
    claim_path = private_root / "authority" / "claim.json"
    claim_lifecycle_holdout_audit(
        calibration_freeze_path=calibration_freeze_path,
        target_freeze_path=target_freeze_path,
        mount=mount,
        output_path=claim_path,
    )
    execution_root = private_root / "execution"
    execution_root.mkdir(mode=0o700)
    run_dir = execution_root / "run"
    run_dir.mkdir(mode=0o700)
    private_ledger_root = private_root / "ledger"
    claim = json.loads(claim_path.read_text(encoding="utf-8"))
    target = json.loads(target_freeze_path.read_text(encoding="utf-8"))
    run_start = build_lifecycle_holdout_run_start(
        claim_sha256=claim["claim_sha256"],
        calibration_freeze_sha256=calibration.freeze_sha256,
        target_freeze_sha256=target["target_freeze_sha256"],
        selected_condition=calibration.selected_condition,
        private_execution_root=str(execution_root.resolve()),
        run_dir=str(run_dir.resolve()),
        private_ledger_root=str(private_ledger_root.resolve(strict=False)),
        python_version=platform.python_version(),
    )
    run_start_path = execution_root / "run-start.json"
    run_start_bytes = (json.dumps(run_start.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode()
    run_start_path.write_bytes(run_start_bytes)
    (run_dir / "run-start.json").write_bytes(run_start_bytes)
    os.chmod(run_start_path, 0o600)
    os.chmod(run_dir / "run-start.json", 0o600)
    recorder = _CapturingRecorder(private_root / "captured-record")
    registry = _SealedLifecycleRegistry(
        package_dir=mount.package_dir,
        run_dir=run_dir,
        resolved_model=calibration.selected_condition.resolved_model,
        resolved_adapter=calibration.selected_condition.resolved_adapter,
        submission_offset=0 if pass_verification else 1,
    )
    with mount.activate():
        task_run = run_local_evidence_lifecycle_session(
            package_dir=mount.package_dir,
            run_dir=run_dir,
            model=calibration.selected_condition.requested_model,
            verifier=verify_lifecycle_template,
            adapter_kind=calibration.selected_condition.requested_adapter,
            max_turns=calibration.selected_condition.max_turns_per_session,
            registry=registry,
            visibility_policy=calibration.selected_condition.memory_visibility_policy,
            require_adapter_identity_match=True,
            experiment_recorder=recorder,
            run_authorization_sha256=run_start.run_start_sha256,
        )
    assert recorder.call is not None
    verified_result = recorder.call["verification"]
    assert verified_result["passed"] is pass_verification
    assert verified_result["reward"] == (1.0 if pass_verification else 0.0)
    assert task_run["evidence"]["lifecycle"]["status"] == "complete"
    agent_evidence = dict(recorder.call["agent"])
    agent_evidence["runtime"] = {
        "provider": calibration.selected_condition.runtime_provider,
        "distributions": list(calibration.selected_condition.runtime_distributions),
        "dependency_sha256": calibration.selected_condition.runtime_dependency_sha256,
        "python_version": platform.python_version(),
    }
    agent_evidence["interaction"] = {
        "protocol": calibration.selected_condition.interaction_protocol,
        "protocol_sha256": calibration.selected_condition.interaction_protocol_sha256,
        "tool_schema": recorder.call["tool_schema"],
        "tool_schema_sha256": calibration.selected_condition.tool_schema_sha256,
    }
    repository_dir = _copy_repository_source(private_root / "repository")
    return CompletedSealedLifecycleAudit(
        mount=mount,
        run_dir=run_dir,
        run_start_path=run_start_path,
        private_ledger_root=private_ledger_root,
        calibration_freeze_path=calibration_freeze_path,
        target_freeze_path=target_freeze_path,
        claim_path=claim_path,
        repository_dir=repository_dir,
        selected_condition=calibration.selected_condition,
        agent_evidence=agent_evidence,
        verified_result=verified_result,
    )


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
                name="fixture-calibration-model",
                adapter="tool_loop",
                model="fixture-model",
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
        output_root=str((tmp_path / "public-output").resolve()),
        ledger_root=str((tmp_path / "public-ledger").resolve()),
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
    output_path: Path,
    *,
    manifest: LifecycleAblationManifest,
    tmp_path: Path,
    public_calibration_record: LifecycleCalibrationRecordReference | None = None,
) -> tuple[Path, LifecycleCalibrationFreeze]:
    plan = build_lifecycle_ablation_plan(manifest)
    model = "anthropic:fixture-model"
    runtime = runtime_dependency_provenance(adapter_kind="tool_loop", model_name=model)
    record = public_calibration_record or LifecycleCalibrationRecordReference(
        experiment_id=manifest.experiment_id,
        trial_id="trial-public",
        ledger_path=str((tmp_path / "public-ledger" / manifest.experiment_id / "trial-public.json").resolve()),
        sha256="1" * 64,
    )
    planned = LifecycleCalibrationPlannedCondition(
        requested_model=model,
        requested_adapter="tool_loop",
        runtime_provider=str(runtime["provider"]),
        runtime_distributions=tuple(runtime["distributions"]),
        runtime_dependency_sha256=str(runtime["dependency_inventory_sha256"]),
        execution_mode=LifecycleExecutionMode.PERSISTENT_CONTEXT,
        memory_visibility_policy=LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
        max_turns_per_session=12,
    )
    tool_schema = _operation_tool_schema()
    frozen = FrozenLifecycleCondition(
        **planned.model_dump(mode="python"),
        resolved_model=model,
        resolved_adapter="tool_loop",
        interaction_protocol="lifecycle_operation",
        interaction_protocol_sha256=lifecycle_operation_protocol_identity()["sha256"],
        tool_schema_sha256=_canonical_sha256(tool_schema),
    )
    candidate = LifecycleCalibrationCandidateResult(
        candidate_id=f"condition-{_canonical_sha256(planned.model_dump(mode='json'))}",
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
        "experiment_id": manifest.experiment_id,
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
    payload["freeze_sha256"] = _canonical_sha256(
        {key: value for key, value in payload.items() if key != "freeze_sha256"}
    )
    freeze = LifecycleCalibrationFreeze.model_validate(payload)
    output_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(output_path.parent, 0o700)
    output_path.write_text(
        json.dumps(freeze.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(output_path, 0o600)
    return output_path, freeze


class _CapturingRecorder:
    def __init__(self, output_root: Path) -> None:
        self.output_root = Path(output_root)
        self.call: dict[str, Any] | None = None

    def __call__(self, **kwargs: Any) -> dict[str, str]:
        self.call = kwargs
        return {
            "experiment_id": "captured-private-experiment",
            "manifest": str(self.output_root / "audit-manifest.json"),
            "canonical_manifest": str(self.output_root / "audit-manifest.json"),
            "manifest_sha256": "f" * 64,
            "metrics": str(self.output_root / "record.json"),
            "verification": str(self.output_root / "record.json"),
            "index": str(self.output_root / "record.json"),
        }


class _SealedLifecycleRegistry:
    def __init__(
        self,
        *,
        package_dir: Path,
        run_dir: Path,
        resolved_model: str,
        resolved_adapter: str,
        submission_offset: int = 0,
    ) -> None:
        self.package_dir = Path(package_dir)
        self.run_dir = Path(run_dir)
        self.resolved_model = resolved_model
        self.resolved_adapter = resolved_adapter
        self.submission_offset = submission_offset

    def build(self, *, native_tools: list[Any], **_kwargs: Any) -> Any:
        read_workspace_file = next(tool for tool in native_tools if tool.__name__ == "read_workspace_file")
        write_submission = next(tool for tool in native_tools if tool.__name__ == "write_checkpoint_submission")
        execute_operation = next(tool for tool in native_tools if tool.__name__ == "execute_operation")
        submit_checkpoint = next(tool for tool in native_tools if tool.__name__ == "submit_checkpoint")
        registry = self

        class _SealedLifecycleAdapter:
            def execute(self, request: Any) -> SimpleNamespace:
                source_response = json.loads(read_workspace_file("hydraulics/current-source.json"))
                source = json.loads(source_response["content"])
                operation = json.loads(
                    execute_operation(
                        FIXTURE_CHECKPOINT_ID,
                        FIXTURE_OPERATION_ID,
                        source["visible_source_state_sha256"],
                        "Derive the declared deterministic observation.",
                    )
                )
                artifact_response = json.loads(read_workspace_file(operation["artifacts"][0]["path"]))
                artifact = json.loads(artifact_response["content"])
                written = json.loads(
                    write_submission(
                        FIXTURE_CHECKPOINT_ID,
                        json.dumps(
                            {
                                "checkpoint_id": FIXTURE_CHECKPOINT_ID,
                                "selected_action_id": operation["action_id"],
                                "observed_value": artifact["observed_value"] + registry.submission_offset,
                            }
                        ),
                    )
                )
                completed = json.loads(submit_checkpoint(FIXTURE_CHECKPOINT_ID))
                assert operation["status"] == "completed"
                assert written["status"] == "written"
                assert completed["status"] == "complete"
                return SimpleNamespace(
                    adapter_name=registry.resolved_adapter,
                    resolved_model=registry.resolved_model,
                    configuration_record={
                        "model": registry.resolved_model,
                        "max_turns": request.configuration["max_turns"],
                    },
                    agent_output=SimpleNamespace(status=SimpleNamespace(value="completed")),
                    transcript=[],
                    raw_output_text="Sealed lifecycle complete.",
                    provider_error=None,
                    failure_kind=None,
                    usage_input_tokens=10,
                    usage_output_tokens=2,
                    usage_cache_read_tokens=0,
                    usage_cache_write_tokens=0,
                )

        return _SealedLifecycleAdapter()


def _operation_tool_schema() -> list[dict[str, Any]]:
    return build_lifecycle_tool_schema(
        "persistent_context",
        supports_evidence_requests=False,
        supports_lifecycle_operations=True,
    )


def _copy_repository_source(output_dir: Path) -> Path:
    repository_root = Path(__file__).resolve().parents[2]
    output_dir.mkdir(mode=0o700)
    shutil.copytree(
        repository_root / "src" / "aec_bench",
        output_dir / "aec_bench",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    for name in ("pyproject.toml", "uv.lock"):
        shutil.copy2(repository_root / name, output_dir / name)
    subprocess.run(["git", "init"], cwd=output_dir, check=True, capture_output=True)
    subprocess.run(["git", "add", "aec_bench", "pyproject.toml", "uv.lock"], cwd=output_dir, check=True)
    environment = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Lifecycle Test",
        "GIT_AUTHOR_EMAIL": "lifecycle@example.invalid",
        "GIT_COMMITTER_NAME": "Lifecycle Test",
        "GIT_COMMITTER_EMAIL": "lifecycle@example.invalid",
    }
    subprocess.run(
        ["git", "commit", "-m", "Create sealed audit source fixture"],
        cwd=output_dir,
        check=True,
        capture_output=True,
        env=environment,
    )
    return output_dir


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
