# ABOUTME: Reconstructs schema-1 lifecycle study records from their immutable retained evidence.
# ABOUTME: Keeps the retired record format readable without creating a second current finalization path.

from __future__ import annotations

import hashlib
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
    LifecycleSessionRecord,
    LifecycleTrialProvenance,
    ProviderRoute,
    RunManifest,
    TimingRecord,
    TrialInput,
    TrialOutput,
    TrialRecord,
    UnresolvedSourceRef,
)
from aec_bench.experimentation.lifecycle_studies.ablation_plan import (
    LifecycleAblationManifest,
    LifecycleAblationPlan,
    LifecycleAblationTrial,
    LifecycleRuntimeProvenance,
)
from aec_bench.experimentation.lifecycle_studies.historical_evidence import (
    _artifact_media_type,
    _lifecycle_instruction,
    _media_type,
    _read_json,
    _sha256,
    _tree_hashes,
    _validate_artifact_hash,
    _validate_declared_run_artifacts,
    _validate_metrics_against_run,
    _validate_snapshotted_lifecycle_state,
)
from aec_bench.experimentation.lifecycle_studies.retained_record_identity import matches_retained_lifecycle_record
from aec_bench.experimentation.lifecycle_studies.retained_snapshot import LifecycleAblationSnapshot
from aec_bench.lifecycles.catalogue import lifecycle_package_variant
from aec_bench.lifecycles.evidence_files import lifecycle_artifact_kind
from aec_bench.lifecycles.invocation import (
    LifecycleExperimentMetrics,
    lifecycle_experiment_metrics_payload,
    single_resolved_lifecycle_identity,
)
from aec_bench.lifecycles.runtime.lifecycle import validate_lifecycle_verification
from aec_bench.lifecycles.session_records import parse_lifecycle_session_records


def build_historical_lifecycle_trial_record(
    *,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
    snapshot: LifecycleAblationSnapshot,
    plan: LifecycleAblationPlan,
) -> TrialRecord:
    """Rebuild one schema-1 record from its retained package, run, invocation, and study plan."""
    package = snapshot.package_dir
    run = snapshot.run_dir
    experiment = snapshot.invocation.manifest
    if experiment.get("schema_version") != "1":
        raise ValueError("historical lifecycle builder accepts only schema version 1")
    _validate_snapshotted_lifecycle_state(package, run)
    state = _read_json(run / "state.json")
    variant = lifecycle_package_variant(package)
    if variant is None or variant.get("variant_id") != trial.variant_id:
        raise ValueError("historical lifecycle package variant does not match planned trial")
    if AdaptationProvenance.model_validate(variant.get("adaptation")) != trial.adaptation:
        raise ValueError("historical lifecycle package adaptation does not match planned trial")

    verification = validate_lifecycle_verification(_read_json(snapshot.invocation.verification_path))
    metrics = lifecycle_experiment_metrics_payload(
        LifecycleExperimentMetrics.model_validate(_read_json(snapshot.invocation.metrics_path))
    )
    outputs = cast(dict[str, Any], experiment.get("outputs", {}))
    _validate_artifact_hash(
        snapshot.invocation.verification_path,
        outputs.get("verification.json"),
        "historical lifecycle verification",
    )
    _validate_artifact_hash(
        snapshot.invocation.metrics_path,
        outputs.get("metrics.json"),
        "historical lifecycle metrics",
    )
    _validate_artifact_hash(run / "verification.json", outputs.get("verification.json"), "run verification")
    _validate_artifact_hash(run / "metrics.json", outputs.get("metrics.json"), "run metrics")
    _validate_declared_run_artifacts(run, experiment)
    _validate_metrics_against_run(run, state, experiment, metrics, verification)
    lifecycle, repository, runtime_environment, execution = _validate_historical_invocation_identity(
        manifest=manifest,
        plan=plan,
        trial=trial,
        package=package,
        state=state,
        experiment=experiment,
        verification=verification,
        variant=variant,
    )
    python_version = str(runtime_environment["python_version"])
    repository_commit = cast(str, repository["commit"])
    repository_kind = cast(Literal["git", "source_tree"], repository["repository_kind"])
    repository_dirty = cast(bool, repository["dirty"])
    repository_dirty_digest = cast(str, repository["dirty_digest"])

    artifacts = _snapshot_references(snapshot, Path(manifest.ledger_root))
    sessions = _lifecycle_sessions(
        run,
        artifacts,
        state=state,
        experiment=experiment,
        metrics=metrics,
        verification=verification,
    )
    resolved_model = single_resolved_lifecycle_identity(
        (session.resolved_model for session in sessions),
        kind="model",
    )
    resolved_adapter = single_resolved_lifecycle_identity(
        (session.adapter for session in sessions),
        kind="adapter",
    )
    verifier = cast(dict[str, Any], experiment["verifier"])
    verifier_source_sha256 = verifier.get("source_sha256")
    if not isinstance(verifier_source_sha256, str):
        raise ValueError("historical lifecycle verifier source hash is missing")

    invocation_manifest = _single_artifact_or_default(
        artifacts,
        kind="lifecycle_manifest",
        default=ArtifactReference(
            kind="lifecycle_manifest",
            path=str(snapshot.invocation.manifest_path),
            sha256=_sha256(snapshot.invocation.manifest_path),
            media_type="application/json",
        ),
    )
    execution_status = _execution_status(execution.get("status"))
    max_turns_per_session = _positive_int(
        execution.get("max_turns_per_session"),
        "historical lifecycle max_turns_per_session",
    )
    execution_record = LifecycleExecutionRecord(
        execution_mode=trial.execution_mode.value,
        memory_visibility_policy=trial.memory_visibility_policy.value,
        max_turns_per_session=max_turns_per_session,
        status=execution_status,
        sessions=sessions,
    )
    lifecycle_provenance = LifecycleTrialProvenance(
        lifecycle_id=str(lifecycle["lifecycle_id"]),
        spec_sha256=str(lifecycle["spec_sha256"]),
        package_sha256=str(lifecycle["package_sha256"]),
        repository_commit=repository_commit,
        repository_kind=repository_kind,
        repository_dirty=repository_dirty,
        repository_dirty_digest=repository_dirty_digest,
        runtime_provider=trial.runtime_provenance.provider,
        runtime_distributions=trial.runtime_provenance.distributions,
        runtime_dependency_sha256=trial.runtime_provenance.dependency_inventory_sha256,
        verifier_qualified_name=str(verifier["qualified_name"]),
        verifier_source_sha256=verifier_source_sha256,
        invocation_manifest=invocation_manifest,
        invocation_index=_artifact_by_kind(artifacts, "lifecycle_invocation_index"),
        ablation_manifest=_artifact_by_kind(artifacts, "lifecycle_ablation_manifest"),
        ablation_plan=_artifact_by_kind(artifacts, "lifecycle_ablation_plan"),
    )

    run_id = ":".join(
        (
            manifest.experiment_id,
            resolved_adapter,
            resolved_model,
            trial.execution_mode.value,
            trial.memory_visibility_policy.value,
            trial.variant_id,
        )
    )
    clean_git_source = (
        repository_kind == "git"
        and not repository_dirty
        and len(repository_commit) == 40
        and all(character in "0123456789abcdef" for character in repository_commit)
    )
    run_manifest = RunManifest(
        run_id=run_id,
        experiment_id=manifest.experiment_id,
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
                "agent_name": trial.agent.name,
                "requested_model": trial.agent.model,
                "requested_adapter": trial.agent.adapter,
                "parameters": trial.agent.parameters,
                "variant_id": trial.variant_id,
                "execution_mode": trial.execution_mode.value,
                "memory_visibility_policy": trial.memory_visibility_policy.value,
                "plan_sha256": plan.plan_sha256,
            },
        ),
        execution_environment=ExecutionEnvironmentRef(
            runtime_image=f"python:{python_version}",
            compute_backend="local",
            tool_versions={"python": python_version},
        ),
        provider_route=ProviderRoute(provider=trial.runtime_provenance.provider, route=resolved_adapter),
        expected_authorities=(
            AuthorityExpectation(
                authority_kind=AuthorityEvidenceKind.LIFECYCLE,
                protocol="aec-bench/lifecycle-evidence/1",
            ),
        ),
    )

    agent_status = AgentOutputStatus.COMPLETED if execution_status == "completed" else AgentOutputStatus.FAILED
    verification_reference = _artifact_by_kind(artifacts, "lifecycle_verification")
    metrics_reference = _artifact_by_kind(artifacts, "lifecycle_metrics")
    raw_output_refs = [artifact.path for artifact in artifacts if artifact.kind == "raw_output"]
    conversation_refs = [artifact.path for artifact in artifacts if artifact.kind == "conversation"]
    trajectory_refs = [artifact.path for artifact in artifacts if artifact.kind == "trajectory"]
    output = TrialOutput(
        agent_output=AgentOutput(
            status=agent_status,
            output_path=_artifact_output_root(trial),
            output_format="evidence_lifecycle",
            error_message=None if agent_status is AgentOutputStatus.COMPLETED else "lifecycle execution failed",
        ),
        agent_result={
            "lifecycle_experiment_id": experiment.get("experiment_id"),
            "execution_status": execution_status,
            "verification_path": (
                verification_reference.path
                if verification_reference is not None
                else str(snapshot.invocation.verification_path)
            ),
            "metrics_path": (
                metrics_reference.path if metrics_reference is not None else str(snapshot.invocation.metrics_path)
            ),
            "manifest_path": invocation_manifest.path,
        },
        terminated=agent_status is AgentOutputStatus.COMPLETED,
        truncated=agent_status is not AgentOutputStatus.COMPLETED,
        final_reason=execution_status,
    ).bind_runtime_paths(
        raw_output_path=_single_path(raw_output_refs),
        conversation_path=_single_path(conversation_refs),
        trajectory_path=_single_path(trajectory_refs),
    )
    total_seconds = float(metrics.get("whole_run_seconds") or 0.0)
    created_at = datetime.fromisoformat(str(experiment.get("created_at")).replace("Z", "+00:00"))
    verifier_completed = verification.get("overall") != "incomplete"
    output_structurally_valid = state.get("status") == "complete"
    record = TrialRecord(
        trial_id=trial.trial_id,
        run_id=run_id,
        task_id=manifest.lifecycle_template_id,
        attempt=trial.repetition,
        execution_status=(
            ExecutionStatus.COMPLETED if agent_status is AgentOutputStatus.COMPLETED else ExecutionStatus.FAILED
        ),
        evaluation_status=EvaluationStatus.COMPLETED,
        evidence_status=EvidenceStatus.PENDING,
        started_at=created_at,
        completed_at=created_at + timedelta(seconds=total_seconds),
        input=TrialInput(
            instruction=_lifecycle_instruction(package),
            task_revision=str(state["package_sha256"]),
            task_kind="lifecycle",
            visibility=Visibility(str(variant["visibility"])),
        ),
        output=output,
        evaluation=EvaluationResult(
            reward=float(verification["reward"]),
            validity=ValidityCheck(
                output_parseable=output_structurally_valid,
                schema_valid=output_structurally_valid and verifier_completed,
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
    record.attach_extension("adaptation", trial.adaptation)
    record.attach_extension("lifecycle_execution", execution_record)
    record.attach_extension("lifecycle_provenance", lifecycle_provenance)
    _attach_snapshot_artifacts(record, artifacts, invocation_manifest, Path(manifest.ledger_root), package)
    return record.bind_run_manifest(run_manifest)


def matches_historical_lifecycle_trial_record(record: TrialRecord, expected: TrialRecord) -> bool:
    """Allow only the omitted visibility field used by records written before that field existed."""
    return matches_retained_lifecycle_record(record, expected, allow_omitted_visibility=True)


def _validate_historical_invocation_identity(
    *,
    manifest: LifecycleAblationManifest,
    plan: LifecycleAblationPlan,
    trial: LifecycleAblationTrial,
    package: Path,
    state: dict[str, Any],
    experiment: dict[str, Any],
    verification: dict[str, Any],
    variant: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    lifecycle = cast(dict[str, Any], experiment.get("lifecycle", {}))
    expected_lifecycle = {
        "lifecycle_id": trial.lifecycle_id,
        "spec_sha256": trial.spec_sha256,
        "package_sha256": trial.package_sha256,
    }
    if any(lifecycle.get(key) != value for key, value in expected_lifecycle.items()):
        raise ValueError("historical lifecycle invocation does not match planned package revision")
    expected_state = {
        "lifecycle_id": trial.lifecycle_id,
        "lifecycle_spec_sha256": trial.spec_sha256,
        "package_sha256": trial.package_sha256,
    }
    if any(state.get(key) != value for key, value in expected_state.items()):
        raise ValueError("historical lifecycle state does not match planned package revision")
    if verification.get("lifecycle_id") != trial.lifecycle_id or lifecycle.get("variant") != variant:
        raise ValueError("historical lifecycle evidence does not match planned lifecycle")
    try:
        Visibility(str(variant["visibility"]))
    except (KeyError, ValueError) as exc:
        raise ValueError("historical lifecycle package visibility is invalid") from exc
    model = cast(dict[str, Any], experiment.get("model", {}))
    execution = cast(dict[str, Any], experiment.get("execution", {}))
    if model.get("requested_model") != trial.agent.model:
        raise ValueError("historical lifecycle model does not match planned trial")
    if model.get("requested_adapter") != trial.agent.adapter or model.get("adapter") != trial.agent.adapter:
        raise ValueError("historical lifecycle adapter does not match planned trial")
    recorded_max_turns = _positive_int(
        execution.get("max_turns_per_session"),
        "historical lifecycle max_turns_per_session",
    )
    if (
        execution.get("mode") != trial.execution_mode.value
        or execution.get("memory_visibility_policy") != trial.memory_visibility_policy.value
        or recorded_max_turns != trial.max_turns_per_session
    ):
        raise ValueError("historical lifecycle execution does not match planned trial")
    expected_sweep = {
        "schema_version": "1",
        "sweep_experiment_id": manifest.experiment_id,
        "planned_trial_id": trial.trial_id,
        "plan_sha256": plan.plan_sha256,
        "condition_id": f"{trial.execution_mode.value}__{trial.memory_visibility_policy.value}",
        "repetition": trial.repetition,
    }
    if experiment.get("sweep") != expected_sweep:
        raise ValueError("historical lifecycle sweep context does not match its snapshotted plan")
    raw_repository = experiment.get("repository")
    if not isinstance(raw_repository, dict):
        raise ValueError("historical lifecycle repository provenance is invalid")
    repository = cast(dict[str, Any], raw_repository)
    repository_kind = repository.get("repository_kind")
    if repository_kind not in {"git", "source_tree"}:
        raise ValueError("historical lifecycle repository provenance kind is invalid")
    repository_commit = repository.get("commit")
    source_inventory_sha256 = repository.get("source_inventory_sha256")
    if (
        not isinstance(repository_commit, str)
        or repository_commit != plan.code_provenance.repository_commit
        or source_inventory_sha256 != plan.code_provenance.source_inventory_sha256
    ):
        raise ValueError("historical lifecycle repository does not match its snapshotted plan")
    if repository_kind == "git":
        if len(repository_commit) != 40 or any(character not in "0123456789abcdef" for character in repository_commit):
            raise ValueError("historical lifecycle Git repository commit is invalid")
    elif repository_commit != f"source-sha256:{source_inventory_sha256}":
        raise ValueError("historical lifecycle source-tree commit does not match its source inventory")
    if type(repository.get("dirty")) is not bool:
        raise ValueError("historical lifecycle repository dirty state is invalid")
    dirty_digest = repository.get("dirty_digest")
    if not isinstance(dirty_digest, str):
        raise ValueError("historical lifecycle repository dirty digest is invalid")
    try:
        ArtifactReference.validate_sha256(dirty_digest)
    except ValueError as exc:
        raise ValueError("historical lifecycle repository dirty digest is invalid") from exc
    repository_dirty = cast(bool, repository["dirty"])
    empty_digest = hashlib.sha256(b"").hexdigest()
    if (not repository_dirty and dirty_digest != empty_digest) or (repository_dirty and dirty_digest == empty_digest):
        raise ValueError("historical lifecycle repository dirty state and digest are inconsistent")
    if repository_kind == "source_tree" and repository_dirty:
        raise ValueError("historical lifecycle source-tree repository must be clean")
    raw_runtime_environment = experiment.get("environment")
    if not isinstance(raw_runtime_environment, dict):
        raise ValueError("historical lifecycle runtime environment is invalid")
    runtime_environment = cast(dict[str, Any], raw_runtime_environment)
    try:
        runtime_provenance = LifecycleRuntimeProvenance.model_validate(runtime_environment.get("runtime_provenance"))
    except (TypeError, ValueError) as exc:
        raise ValueError("historical lifecycle runtime provenance is invalid") from exc
    if runtime_provenance != trial.runtime_provenance:
        raise ValueError("historical lifecycle runtime dependencies do not match planned trial")
    if not isinstance(runtime_environment.get("python_version"), str) or not runtime_environment["python_version"]:
        raise ValueError("historical lifecycle Python version is missing")
    verifier = cast(dict[str, Any], experiment.get("verifier", {}))
    entrypoint = verifier.get("entrypoint")
    if (
        verifier.get("qualified_name") != plan.code_provenance.verifier_qualified_name
        or verifier.get("source_sha256") != plan.code_provenance.verifier_source_sha256
        or not isinstance(entrypoint, dict)
        or entrypoint.get("qualified_name") != plan.code_provenance.verifier_entrypoint_qualified_name
        or entrypoint.get("source_sha256") != plan.code_provenance.verifier_entrypoint_source_sha256
    ):
        raise ValueError("historical lifecycle verifier does not match its snapshotted plan")
    package_files = lifecycle.get("package_files")
    if not isinstance(package_files, dict) or not package_files or package_files != _tree_hashes(package):
        raise ValueError("historical lifecycle package files do not match its canonical manifest")
    return lifecycle, repository, runtime_environment, execution


def _snapshot_references(snapshot: LifecycleAblationSnapshot, ledger_root: Path) -> list[ArtifactReference]:
    references = [
        ArtifactReference(
            kind=lifecycle_artifact_kind(path.relative_to(snapshot.root)),
            path=path.relative_to(ledger_root).as_posix(),
            sha256=_sha256(path),
            media_type=_media_type(path),
        )
        for path in sorted(snapshot.root.rglob("*"))
        if path.is_file()
    ]
    if not references:
        raise ValueError("historical lifecycle artifact snapshot is empty")
    return references


def _lifecycle_sessions(
    run_dir: Path,
    artifacts: list[ArtifactReference],
    *,
    state: dict[str, Any],
    experiment: dict[str, Any],
    metrics: dict[str, Any],
    verification: dict[str, Any],
) -> list[LifecycleSessionRecord]:
    outputs = cast(dict[str, Any], experiment["outputs"])
    execution = cast(dict[str, Any], experiment["execution"])
    model = cast(dict[str, Any], experiment["model"])
    sessions = parse_lifecycle_session_records(
        run_dir=run_dir,
        artifact_references=artifacts,
        state=state,
        declared_run_artifacts=cast(dict[str, str], outputs["artifacts"]),
        requested_model=str(model.get("requested_model") or ""),
        requested_adapter=str(model.get("requested_adapter") or ""),
        execution_mode=cast(Literal["persistent_context", "fresh_context"], execution.get("mode")),
        memory_visibility_policy=cast(
            Literal["persistent_context", "artifact_memory", "raw_evidence_only", "current_release_only"],
            execution.get("memory_visibility_policy"),
        ),
        max_turns_per_session=_positive_int(
            execution.get("max_turns_per_session"),
            "historical lifecycle max_turns_per_session",
        ),
        execution_status=_execution_status(execution.get("status")),
        verification=verification,
    )
    session_count = _non_negative_int(
        execution.get("session_count"),
        "historical lifecycle session_count",
    )
    if session_count != len(sessions):
        raise ValueError("historical lifecycle session_count does not match session artifacts")
    declared = cast(dict[str, str], outputs["artifacts"])
    configurations = [
        _read_json(run_dir / relative).get("configuration_record")
        for relative in sorted(Path(relative) for relative in declared if Path(relative).name == "agent_result.json")
    ]
    if model.get("session_configurations") != configurations:
        raise ValueError("historical lifecycle model session configurations do not match session artifacts")
    if model.get("resolved_models") != sorted({session.resolved_model for session in sessions}):
        raise ValueError("historical lifecycle resolved models do not match session artifacts")
    if model.get("resolved_adapters") != sorted({session.adapter for session in sessions}):
        raise ValueError("historical lifecycle resolved adapters do not match session artifacts")
    for metric_field, session_field in {
        "input_tokens": "input_tokens",
        "output_tokens": "output_tokens",
        "cache_read_tokens": "cache_read_tokens",
        "cache_write_tokens": "cache_write_tokens",
    }.items():
        if metrics.get(metric_field) != sum(getattr(session, session_field) for session in sessions):
            raise ValueError(f"historical lifecycle {metric_field} does not match session artifacts")
    return sessions


def _attach_snapshot_artifacts(
    record: TrialRecord,
    artifacts: list[ArtifactReference],
    invocation_manifest: ArtifactReference,
    ledger_root: Path,
    package: Path,
) -> None:
    for index, artifact in enumerate(artifacts):
        if artifact.path == invocation_manifest.path:
            continue
        path = Path(artifact.path)
        if not path.is_absolute():
            path = ledger_root / path
        record.attach_artifact(
            f"output:{artifact.kind}:{index}",
            path,
            media_type=artifact.media_type,
            logical_path=artifact.path,
        )
    invocation_path = Path(invocation_manifest.path)
    if not invocation_path.is_absolute():
        invocation_path = ledger_root / invocation_path
    record.attach_artifact(
        f"authority:{AuthorityEvidenceKind.LIFECYCLE.value}:aec-bench/lifecycle-evidence/1",
        invocation_path,
        media_type=invocation_manifest.media_type,
    )
    for index, path in enumerate(sorted(item for item in package.rglob("*") if item.is_file())):
        record.attach_artifact(
            f"input:lifecycle_package:{index}",
            path,
            media_type=_artifact_media_type(path),
        )


def _execution_status(status: object) -> Literal["completed", "failed", "partial"]:
    if status not in {"completed", "failed", "partial"}:
        raise ValueError("historical lifecycle execution status is invalid")
    return cast(Literal["completed", "failed", "partial"], status)


def _positive_int(value: object, label: str) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _non_negative_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _artifact_output_root(trial: LifecycleAblationTrial) -> str:
    experiment_id = Path(trial.ledger_path).parent.name
    return (Path(experiment_id) / "_artifacts" / trial.trial_id / "run").as_posix()


def _single_path(paths: list[str]) -> str | None:
    return paths[0] if len(paths) == 1 else None


def _artifact_by_kind(artifacts: list[ArtifactReference], kind: str) -> ArtifactReference | None:
    matches = [artifact for artifact in artifacts if artifact.kind == kind]
    if len(matches) > 1:
        raise ValueError(f"historical snapshot contains duplicate {kind} records")
    return matches[0] if matches else None


def _single_artifact_or_default(
    artifacts: list[ArtifactReference],
    *,
    kind: str,
    default: ArtifactReference,
) -> ArtifactReference:
    return _artifact_by_kind(artifacts, kind) or default


def _verification_failures(verification: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    gates = verification.get("gates", {})
    if not isinstance(gates, dict):
        return ["verification gates are malformed"]
    for gate_id, gate in gates.items():
        if not isinstance(gate, dict):
            failures.append(f"{gate_id}:malformed")
            continue
        for failure in gate.get("failures", []):
            failures.append(f"{gate_id}:{failure}")
    return failures
