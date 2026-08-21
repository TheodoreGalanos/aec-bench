# ABOUTME: Builds normal core TrialRecord values from recorded lifecycle execution evidence.
# ABOUTME: Keeps lifecycle trial construction independent from study and provider policy.

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, cast

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.authority_evidence import AuthorityEvidenceKind
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trial_record import (
    AdaptationProvenance,
    AgentConfiguration,
    ArtifactReference,
    AuthorityExpectation,
    CostRecord,
    EvaluationStatus,
    EvidenceStatus,
    ExecutionEnvironmentRef,
    ExecutionStatus,
    GitSourceRef,
    LifecycleExecutionRecord,
    LifecycleTrialProvenance,
    ProviderRoute,
    RunManifest,
    TimingRecord,
    TrialInput,
    TrialOutput,
    TrialRecord,
    UnresolvedSourceRef,
)
from aec_bench.lifecycles.catalogue import lifecycle_package_variant
from aec_bench.lifecycles.recording import (
    LifecycleExperimentManifest,
    LifecycleExperimentMetrics,
    LifecycleExperimentRecordingResult,
    lifecycle_experiment_metrics_payload,
)
from aec_bench.lifecycles.runtime.lifecycle import validate_lifecycle_verification
from aec_bench.lifecycles.session_records import parse_lifecycle_session_records
from aec_bench.lifecycles.values import LifecycleTrial


def build_lifecycle_trial_record(
    *,
    trial: LifecycleTrial,
    recording: LifecycleExperimentRecordingResult,
) -> TrialRecord:
    """Build one core trial record from canonical lifecycle invocation files."""
    package = trial.package_dir
    run = trial.run_dir
    state = _read_json(run / "state.json")
    manifest_path = Path(str(recording["canonical_manifest"]))
    experiment = LifecycleExperimentManifest.model_validate(_read_json(manifest_path)).model_dump(mode="json")
    verification_path = manifest_path.with_name("verification.json")
    metrics_path = manifest_path.with_name("metrics.json")
    verification = validate_lifecycle_verification(_read_json(verification_path))
    metrics = lifecycle_experiment_metrics_payload(LifecycleExperimentMetrics.model_validate(_read_json(metrics_path)))
    lifecycle = cast(dict[str, Any], experiment["lifecycle"])
    execution = cast(dict[str, Any], experiment["execution"])
    model = cast(dict[str, Any], experiment["model"])
    repository = cast(dict[str, Any], experiment["repository"])
    environment = cast(dict[str, Any], experiment["environment"])
    outputs = cast(dict[str, Any], experiment["outputs"])
    variant = lifecycle_package_variant(package)
    if variant is None or not isinstance(variant.get("visibility"), str):
        raise ValueError("lifecycle package variant visibility is missing")
    visibility = Visibility(str(variant["visibility"]))
    if lifecycle.get("lifecycle_id") != state.get("lifecycle_id"):
        raise ValueError("lifecycle recording does not match canonical run state")
    if model.get("requested_model") != trial.planned.agent.model:
        raise ValueError("lifecycle run model does not match planned trial")
    if model.get("requested_adapter", model.get("adapter")) != trial.planned.agent.adapter:
        raise ValueError("lifecycle run adapter does not match planned trial")
    if execution.get("mode") != trial.execution_mode.value:
        raise ValueError("lifecycle run execution mode does not match planned trial")
    if execution.get("memory_visibility_policy") != trial.visibility_policy.value:
        raise ValueError("lifecycle run visibility policy does not match planned trial")
    max_turns = int(execution.get("max_turns_per_session") or 1)
    execution_status = _execution_status(str(execution.get("status") or "failed"))
    sessions = parse_lifecycle_session_records(
        run_dir=run,
        artifact_references=(),
        state=state,
        declared_run_artifacts=cast(dict[str, str], outputs.get("artifacts", {})),
        requested_model=trial.planned.agent.model,
        requested_adapter=trial.planned.agent.adapter,
        execution_mode=trial.execution_mode.value,
        memory_visibility_policy=trial.visibility_policy.value,
        max_turns_per_session=max_turns,
        execution_status=execution_status,
        verification=verification,
    )
    resolved_model = next(
        (item.resolved_model for item in sessions if item.resolved_model != "unresolved"),
        "unresolved",
    )
    resolved_adapter = next((item.adapter for item in sessions if item.adapter != "unresolved"), "unresolved")
    runtime = cast(dict[str, Any], environment.get("runtime_provenance", {}))
    distributions = tuple(sorted(str(item) for item in runtime.get("distributions", ())))
    if not distributions:
        raise ValueError("lifecycle runtime dependency provenance is missing")
    invocation = ArtifactReference(
        kind="lifecycle_manifest",
        path=str(manifest_path),
        sha256=_sha256(manifest_path),
        media_type="application/json",
    )
    verifier = cast(dict[str, Any], experiment["verifier"])
    repository_commit = str(repository.get("commit") or "unknown")
    repository_kind = str(repository.get("repository_kind", "git"))
    clean_git_source = (
        repository_kind == "git"
        and not bool(repository.get("dirty"))
        and len(repository_commit) == 40
        and all(character in "0123456789abcdef" for character in repository_commit)
    )
    run_id = ":".join(
        (
            trial.planned.experiment_id,
            resolved_adapter,
            resolved_model,
            trial.execution_mode.value,
            trial.visibility_policy.value,
            str(variant.get("variant_id") or "default"),
        )
    )
    python_version = str(environment.get("python_version") or "unknown")
    run_manifest = RunManifest(
        run_id=run_id,
        experiment_id=trial.planned.experiment_id,
        source=(
            GitSourceRef(revision=repository_commit)
            if clean_git_source
            else UnresolvedSourceRef(reason="lifecycle source is dirty, non-Git, or lacks a full retained revision")
        ),
        agent=AgentConfiguration(
            adapter=resolved_adapter,
            model=resolved_model,
            adapter_revision=repository_commit if clean_git_source else None,
            configuration={
                "agent_name": trial.planned.agent.name,
                "requested_model": trial.planned.agent.model,
                "requested_adapter": trial.planned.agent.adapter,
                "parameters": trial.planned.agent.parameters,
                "variant_id": variant.get("variant_id"),
                "execution_mode": trial.execution_mode.value,
                "memory_visibility_policy": trial.visibility_policy.value,
            },
        ),
        execution_environment=ExecutionEnvironmentRef(
            runtime_image=f"python:{python_version}",
            compute_backend=trial.planned.compute.backend,
            tool_versions={"python": python_version},
        ),
        provider_route=ProviderRoute(provider=str(runtime.get("provider") or "unknown"), route=resolved_adapter),
        expected_authorities=(
            AuthorityExpectation(
                authority_kind=AuthorityEvidenceKind.LIFECYCLE,
                protocol="aec-bench/lifecycle-evidence/1",
            ),
        ),
    )
    created_at = datetime.fromisoformat(str(experiment["created_at"]).replace("Z", "+00:00"))
    total_seconds = float(metrics.get("whole_run_seconds") or 0.0)
    completed = execution_status == "completed"
    verifier_completed = verification.get("overall") != "incomplete"
    structurally_valid = state.get("status") == "complete"
    output = TrialOutput(
        agent_output=AgentOutput(
            status=AgentOutputStatus.COMPLETED if completed else AgentOutputStatus.FAILED,
            output_path=str(run),
            output_format="evidence_lifecycle",
            error_message=None if completed else "lifecycle execution failed",
        ),
        agent_result={
            "lifecycle_experiment_id": experiment.get("experiment_id"),
            "execution_status": execution_status,
            "verification_path": str(verification_path),
            "metrics_path": str(metrics_path),
            "manifest_path": str(manifest_path),
        },
        terminated=completed,
        truncated=not completed,
        final_reason=execution_status,
    )
    record = TrialRecord(
        trial_id=trial.planned.trial_id,
        run_id=run_id,
        task_id=trial.planned.task_id,
        attempt=trial.planned.repetition,
        execution_status=ExecutionStatus.COMPLETED if completed else ExecutionStatus.FAILED,
        evaluation_status=EvaluationStatus.COMPLETED,
        evidence_status=EvidenceStatus.PENDING,
        started_at=created_at,
        completed_at=created_at + timedelta(seconds=total_seconds),
        input=TrialInput(
            instruction=_lifecycle_instruction(package),
            task_revision=str(state["package_sha256"]),
            task_kind="lifecycle",
            visibility=visibility,
        ),
        output=output,
        evaluation=EvaluationResult(
            reward=float(verification["reward"]),
            validity=ValidityCheck(
                output_parseable=structurally_valid,
                schema_valid=structurally_valid and verifier_completed,
                verifier_completed=verifier_completed,
                errors=_verification_failures(verification),
            ),
            breakdown={
                "lifecycle_gates": verification.get("gates", {}),
                "semantic_transition": metrics.get("semantic_transition"),
                "operational_metrics": {key: value for key, value in metrics.items() if key != "semantic_transition"},
            },
        ),
        timing=TimingRecord(total_seconds=total_seconds, agent_seconds=total_seconds),
        cost=CostRecord(
            tokens_in=int(metrics.get("input_tokens", 0)),
            tokens_out=int(metrics.get("output_tokens", 0)),
            cache_read_tokens=int(metrics.get("cache_read_tokens", 0)),
            cache_write_tokens=int(metrics.get("cache_write_tokens", 0)),
            estimated_cost_usd=metrics.get("estimated_cost_usd"),
        ),
    )
    record.attach_extension("adaptation", AdaptationProvenance.model_validate(variant["adaptation"]))
    record.attach_extension(
        "lifecycle_execution",
        LifecycleExecutionRecord(
            execution_mode=trial.execution_mode.value,
            memory_visibility_policy=trial.visibility_policy.value,
            max_turns_per_session=max_turns,
            status=execution_status,
            sessions=sessions,
        ),
    )
    record.attach_extension(
        "lifecycle_provenance",
        LifecycleTrialProvenance(
            lifecycle_id=str(lifecycle["lifecycle_id"]),
            spec_sha256=str(lifecycle["spec_sha256"]),
            package_sha256=str(lifecycle["package_sha256"]),
            repository_commit=repository_commit,
            repository_kind=cast(Literal["git", "source_tree"], repository_kind),
            repository_dirty=bool(repository.get("dirty")),
            repository_dirty_digest=str(repository["dirty_digest"]),
            runtime_provider=str(runtime.get("provider") or "unknown"),
            runtime_distributions=distributions,
            runtime_dependency_sha256=str(runtime["dependency_inventory_sha256"]),
            verifier_qualified_name=str(verifier["qualified_name"]),
            verifier_source_sha256=str(verifier["source_sha256"]),
            invocation_manifest=invocation,
        ),
    )
    record.attach_artifact(
        f"authority:{AuthorityEvidenceKind.LIFECYCLE.value}:aec-bench/lifecycle-evidence/1",
        manifest_path,
        media_type="application/json",
    )
    return record.bind_run_manifest(run_manifest)


def _execution_status(value: str) -> Literal["completed", "failed", "partial"]:
    accepted = value if value in {"completed", "failed", "partial"} else "failed"
    return cast(Literal["completed", "failed", "partial"], accepted)


def _lifecycle_instruction(package_dir: Path) -> str:
    instruction_paths = sorted((package_dir / "instructions").glob("*.md"))
    instructions = [path.read_text(encoding="utf-8").strip() for path in instruction_paths]
    return "\n\n".join(item for item in instructions if item) or "Complete the lifecycle."


def _verification_failures(verification: dict[str, Any]) -> list[str]:
    return [
        str(failure)
        for gate in verification.get("gates", {}).values()
        if isinstance(gate, dict)
        for failure in gate.get("failures", [])
    ]


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = ("build_lifecycle_trial_record",)
