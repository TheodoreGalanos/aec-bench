# ABOUTME: Finalizes one lifecycle invocation as the canonical TrialRecord and evidence set.
# ABOUTME: Validates compiled identity, recorded hashes, sessions, metrics, and retained artifacts in one path.

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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
from aec_bench.lifecycles.catalogue import lifecycle_package_variant, lifecycle_verifier
from aec_bench.lifecycles.compiled import CompiledLifecycle
from aec_bench.lifecycles.evidence_files import lifecycle_artifact_kind, safe_lifecycle_relative_path
from aec_bench.lifecycles.finalization_evidence import (
    file_sha256,
    validate_lifecycle_finalization_evidence,
    validate_lifecycle_sessions,
)
from aec_bench.lifecycles.invocation import (
    LifecycleCallableProvenance,
    LifecycleExperimentRecordingResult,
    LifecycleInvocationFinalizationAuthority,
    LifecycleInvocationPlanExpectation,
    LifecycleInvocationRecorderCapture,
    single_resolved_lifecycle_identity,
)
from aec_bench.lifecycles.provenance import callable_provenance
from aec_bench.lifecycles.values import LifecycleTrial

_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


@dataclass(frozen=True, slots=True)
class LifecycleArtifactSource:
    """Bind one retained logical artifact to the file that supplies its bytes."""

    kind: str
    logical_path: str
    path: Path
    media_type: str

    @property
    def reference(self) -> ArtifactReference:
        return ArtifactReference(
            kind=self.kind,
            path=self.logical_path,
            sha256=file_sha256(self.path),
            media_type=self.media_type,
        )


@dataclass(frozen=True, slots=True)
class LifecycleFinalizationSource:
    """Select the package, run, invocation, and study artifacts used for finalization."""

    compiled: CompiledLifecycle
    run_dir: Path
    recording: LifecycleExperimentRecordingResult
    logical_path_prefix: str = ""
    additional_artifacts: tuple[LifecycleArtifactSource, ...] = ()


def live_lifecycle_finalization_source(
    trial: LifecycleTrial,
    recording: LifecycleExperimentRecordingResult,
) -> LifecycleFinalizationSource:
    """Use the live package and run as the default finalization source."""
    return LifecycleFinalizationSource(
        compiled=trial.compiled,
        run_dir=trial.run_dir,
        recording=recording,
    )


def finalize_lifecycle_trial(
    *,
    trial: LifecycleTrial,
    source: LifecycleFinalizationSource,
) -> TrialRecord:
    """Validate and finalize one lifecycle invocation exactly once."""
    recording = source.recording
    evidence = validate_lifecycle_finalization_evidence(
        trial=trial,
        compiled_source=source.compiled,
        run_dir=source.run_dir,
        recording=recording,
    )
    package = evidence.package_dir
    run = evidence.run_dir
    manifest_path = evidence.manifest_path
    manifest = evidence.manifest
    trial_context = evidence.trial_context
    experiment = evidence.experiment
    state = evidence.state
    verification = evidence.verification
    metrics = evidence.metrics
    execution_status = evidence.execution_status
    max_turns = evidence.max_turns_per_session
    finalization_authority = _recording_finalization_authority(recording)

    artifact_sources = _artifact_sources(
        package=package,
        run=run,
        manifest_path=manifest_path,
        index_path=Path(recording["index"]),
        package_files=evidence.package_files,
        run_files=evidence.run_files,
        logical_path_prefix=source.logical_path_prefix,
        additional=source.additional_artifacts,
    )
    artifact_references = [artifact.reference for artifact in artifact_sources]
    sessions = validate_lifecycle_sessions(
        trial=trial,
        evidence=evidence,
        artifact_references=artifact_references,
    )

    resolved_model = single_resolved_lifecycle_identity(
        (session.resolved_model for session in sessions),
        kind="model",
    )
    resolved_adapter = single_resolved_lifecycle_identity(
        (session.adapter for session in sessions),
        kind="adapter",
    )
    repository_value = experiment.get("repository")
    repository_commit, repository_kind, repository_dirty, repository_dirty_digest = _validated_repository_provenance(
        repository_value
    )
    _validate_repository_provenance_authority(repository_value, finalization_authority)
    environment_value = experiment.get("environment")
    if not isinstance(environment_value, dict):
        raise ValueError("lifecycle invocation environment is malformed")
    environment = cast(dict[str, Any], environment_value)
    runtime_value = environment.get("runtime_provenance")
    runtime_provider, runtime_distributions, runtime_dependency_sha256 = _validated_runtime_provenance(
        runtime_value,
        expected_adapter=trial.planned.agent.adapter,
    )
    _validate_runtime_provenance_authority(runtime_value, finalization_authority)
    verifier_value = experiment.get("verifier")
    verifier_qualified_name, verifier_source_sha256 = _validated_verifier_provenance(
        trial,
        verifier_value,
    )
    _validate_verifier_provenance_authority(verifier_value, finalization_authority)
    clean_git_source = repository_kind == "git" and not repository_dirty
    python_version = environment.get("python_version")
    if not isinstance(python_version, str) or not python_version.strip():
        raise ValueError("lifecycle invocation Python version is invalid")
    created_at_value = experiment.get("created_at")
    if not isinstance(created_at_value, str) or not created_at_value.strip():
        raise ValueError("lifecycle invocation creation time is invalid")
    try:
        created_at = datetime.fromisoformat(created_at_value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("lifecycle invocation creation time is invalid") from exc
    _validate_recorder_manifest_authority(recording, finalization_authority)
    run_manifest = RunManifest(
        run_id=trial_context.run_id,
        experiment_id=trial_context.planned_experiment_id,
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
                "variant_id": trial.compiled.envelope.variant_id,
                "execution_mode": trial.execution_mode.value,
                "memory_visibility_policy": trial.visibility_policy.value,
                "compiled": trial.compiled.envelope.model_dump(mode="json"),
            },
        ),
        execution_environment=ExecutionEnvironmentRef(
            runtime_image=f"python:{python_version}",
            compute_backend=trial.planned.compute.backend,
            tool_versions={"python": python_version},
        ),
        provider_route=ProviderRoute(provider=runtime_provider, route=resolved_adapter),
        expected_authorities=(
            AuthorityExpectation(
                authority_kind=AuthorityEvidenceKind.LIFECYCLE,
                protocol="aec-bench/lifecycle-evidence/1",
            ),
        ),
    )

    total_seconds = float(metrics.get("whole_run_seconds") or 0.0)
    completed = execution_status == "completed"
    verifier_completed = verification.get("overall") != "incomplete"
    structurally_valid = state.get("status") == "complete"
    invocation = _single_artifact(artifact_references, "lifecycle_manifest")
    invocation_index = _single_artifact(artifact_references, "lifecycle_invocation_index")
    run_logical_path = _prefixed_logical_path(source.logical_path_prefix, "run")
    verification_reference = _preferred_artifact(
        artifact_references,
        "lifecycle_verification",
        f"{run_logical_path}/verification.json",
    )
    metrics_reference = _preferred_artifact(
        artifact_references,
        "lifecycle_metrics",
        f"{run_logical_path}/metrics.json",
    )
    output = TrialOutput(
        agent_output=AgentOutput(
            status=AgentOutputStatus.COMPLETED if completed else AgentOutputStatus.FAILED,
            output_path=run_logical_path,
            output_format="evidence_lifecycle",
            error_message=None if completed else "lifecycle execution failed",
        ),
        agent_result={
            "lifecycle_experiment_id": manifest.experiment_id,
            "execution_status": execution_status,
            "verification_path": verification_reference.path,
            "metrics_path": metrics_reference.path,
            "manifest_path": invocation.path,
        },
        terminated=completed,
        truncated=not completed,
        final_reason=execution_status,
    ).bind_runtime_paths(
        raw_output_path=_one_logical_path(artifact_references, "raw_output"),
        conversation_path=_one_logical_path(artifact_references, "conversation"),
        trajectory_path=_one_logical_path(artifact_references, "trajectory"),
    )
    record = TrialRecord(
        trial_id=trial_context.trial_id,
        run_id=trial_context.run_id,
        task_id=trial_context.task_id,
        attempt=trial_context.repetition,
        execution_status=ExecutionStatus.COMPLETED if completed else ExecutionStatus.FAILED,
        evaluation_status=EvaluationStatus.COMPLETED,
        evidence_status=EvidenceStatus.PENDING,
        started_at=created_at,
        completed_at=created_at + timedelta(seconds=total_seconds),
        input=TrialInput(
            instruction=_lifecycle_instruction(package),
            task_revision=trial.compiled.envelope.package_sha256,
            task_kind="lifecycle",
            visibility=Visibility(trial.compiled.envelope.visibility),
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
    variant = lifecycle_package_variant(package)
    if variant is not None:
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
            lifecycle_id=trial.compiled.envelope.lifecycle_id,
            spec_sha256=trial.compiled.envelope.lifecycle_spec_sha256,
            package_sha256=trial.compiled.envelope.package_sha256,
            executable_artifact_sha256=trial.compiled.envelope.executable_artifact_sha256,
            operation_protocol_sha256=trial.compiled.envelope.operation_protocol_sha256,
            variant_id=trial.compiled.envelope.variant_id,
            repository_commit=repository_commit,
            repository_kind=repository_kind,
            repository_dirty=repository_dirty,
            repository_dirty_digest=repository_dirty_digest,
            runtime_provider=runtime_provider,
            runtime_distributions=runtime_distributions,
            runtime_dependency_sha256=runtime_dependency_sha256,
            verifier_qualified_name=verifier_qualified_name,
            verifier_source_sha256=verifier_source_sha256,
            invocation_manifest=invocation,
            invocation_index=invocation_index,
            ablation_manifest=_optional_single_artifact(artifact_references, "lifecycle_ablation_manifest"),
            ablation_plan=_optional_single_artifact(artifact_references, "lifecycle_ablation_plan"),
        ),
    )
    _attach_artifacts(record, artifact_sources, invocation)
    return record.bind_run_manifest(run_manifest)


def _validated_repository_provenance(
    value: object,
) -> tuple[str, Literal["git", "source_tree"], bool, str]:
    fields = {
        "root",
        "commit",
        "dirty",
        "dirty_digest",
        "source_inventory_sha256",
        "repository_kind",
    }
    if not isinstance(value, dict):
        raise ValueError("lifecycle repository provenance is malformed")
    repository = cast(dict[str, Any], value)
    root = repository.get("root")
    if not isinstance(root, str) or not root.strip():
        raise ValueError("lifecycle repository root is invalid")
    commit = repository.get("commit")
    if not isinstance(commit, str):
        if commit is None:
            raise ValueError("lifecycle repository commit is missing")
        raise ValueError("lifecycle repository commit is invalid")
    if not commit.strip():
        raise ValueError("lifecycle repository commit is missing")
    repository_kind = repository.get("repository_kind")
    if repository_kind not in {"git", "source_tree"}:
        raise ValueError("lifecycle repository provenance kind is invalid")
    source_inventory_sha256 = _validated_lifecycle_sha256(
        repository.get("source_inventory_sha256"),
        label="lifecycle repository source inventory hash",
    )
    if repository_kind == "git":
        valid_commit = len(commit) == 40 and all(character in "0123456789abcdef" for character in commit)
        if not valid_commit:
            raise ValueError("lifecycle repository commit is invalid")
    elif commit != f"source-sha256:{source_inventory_sha256}":
        raise ValueError("lifecycle source-tree commit does not match its source inventory")
    dirty = repository.get("dirty")
    if not isinstance(dirty, bool):
        raise ValueError("lifecycle repository dirty flag is invalid")
    dirty_digest = _validated_lifecycle_sha256(
        repository.get("dirty_digest"),
        label="lifecycle repository dirty digest",
    )
    if repository_kind == "source_tree" and dirty:
        raise ValueError("lifecycle source-tree repository dirty flag is invalid")
    if not dirty and dirty_digest != _EMPTY_SHA256:
        raise ValueError("clean lifecycle repository dirty digest is invalid")
    if dirty and dirty_digest == _EMPTY_SHA256:
        raise ValueError("dirty lifecycle repository dirty digest is invalid")
    if set(repository) != fields:
        raise ValueError("lifecycle repository provenance is malformed")
    return commit, cast(Literal["git", "source_tree"], repository_kind), dirty, dirty_digest


def _validated_runtime_provenance(
    value: object,
    *,
    expected_adapter: str,
) -> tuple[str, tuple[str, ...], str]:
    fields = {"adapter", "provider", "distributions", "dependency_inventory_sha256"}
    if not isinstance(value, dict):
        raise ValueError("lifecycle runtime dependency provenance is malformed")
    runtime = cast(dict[str, Any], value)
    if runtime.get("adapter") != expected_adapter:
        raise ValueError("lifecycle runtime adapter does not match the planned trial")
    provider = runtime.get("provider")
    if not isinstance(provider, str):
        if provider is None:
            raise ValueError("lifecycle runtime provider is missing")
        raise ValueError("lifecycle runtime provider is invalid")
    if not provider.strip():
        raise ValueError("lifecycle runtime provider is missing")
    raw_distributions = runtime.get("distributions")
    if (
        not isinstance(raw_distributions, list)
        or not raw_distributions
        or any(not isinstance(item, str) or not item.strip() for item in raw_distributions)
    ):
        raise ValueError("lifecycle runtime distributions are invalid")
    distributions = tuple(raw_distributions)
    if distributions != tuple(sorted(set(distributions))):
        raise ValueError("lifecycle runtime distributions are invalid")
    dependency_sha256 = _validated_lifecycle_sha256(
        runtime.get("dependency_inventory_sha256"),
        label="lifecycle runtime dependency hash",
    )
    if set(runtime) != fields:
        raise ValueError("lifecycle runtime dependency provenance is malformed")
    return provider, distributions, dependency_sha256


def _validated_verifier_provenance(trial: LifecycleTrial, value: object) -> tuple[str, str]:
    fields = {"qualified_name", "source_path", "source_sha256", "entrypoint", "chain"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("lifecycle verifier provenance is malformed")
    verifier = cast(dict[str, Any], value)
    recorded_registered = _validated_callable_provenance(
        {field: verifier.get(field) for field in ("qualified_name", "source_path", "source_sha256")},
        label="lifecycle verifier",
    )
    registered = _validated_callable_provenance(
        callable_provenance(lifecycle_verifier(trial.compiled.envelope.template_id)),
        label="registered lifecycle verifier",
    )
    if (
        recorded_registered.qualified_name != registered.qualified_name
        or recorded_registered.source_sha256 != registered.source_sha256
    ):
        raise ValueError("lifecycle verifier does not match the registered verifier")
    entrypoint = _validated_callable_provenance(
        verifier.get("entrypoint"),
        label="lifecycle verifier entrypoint",
    )
    entrypoint_payload = entrypoint.model_dump(mode="json")
    registered_payload = recorded_registered.model_dump(mode="json")
    expected_chain = (
        [entrypoint_payload] if entrypoint_payload == registered_payload else [entrypoint_payload, registered_payload]
    )
    if verifier.get("chain") != expected_chain:
        raise ValueError("lifecycle verifier chain does not match the recorded entrypoint and registered verifier")
    return recorded_registered.qualified_name, recorded_registered.source_sha256


def _recording_finalization_authority(
    recording: LifecycleExperimentRecordingResult,
) -> LifecycleInvocationFinalizationAuthority:
    authority = recording.get("finalization_authority")
    if not isinstance(authority, LifecycleInvocationRecorderCapture | LifecycleInvocationPlanExpectation):
        raise ValueError("lifecycle recording finalization authority is missing")
    return authority


def _validate_repository_provenance_authority(
    value: object,
    authority: LifecycleInvocationFinalizationAuthority,
) -> None:
    repository = cast(dict[str, Any], value)
    if isinstance(authority, LifecycleInvocationRecorderCapture):
        return
    expected = authority.repository
    if (
        repository.get("commit") != expected.commit
        or repository.get("source_inventory_sha256") != expected.source_inventory_sha256
        or repository.get("repository_kind") != expected.expected_repository_kind
    ):
        raise ValueError("lifecycle repository provenance does not match its planned expectation")


def _validate_runtime_provenance_authority(
    value: object,
    authority: LifecycleInvocationFinalizationAuthority,
) -> None:
    if isinstance(authority, LifecycleInvocationRecorderCapture):
        return
    runtime = cast(dict[str, Any], value)
    if runtime != authority.runtime.model_dump(mode="json"):
        raise ValueError("lifecycle runtime provenance does not match its planned expectation")


def _validate_verifier_provenance_authority(
    value: object,
    authority: LifecycleInvocationFinalizationAuthority,
) -> None:
    verifier = cast(dict[str, Any], value)
    if isinstance(authority, LifecycleInvocationRecorderCapture):
        return
    entrypoint = cast(dict[str, Any], verifier["entrypoint"])
    expected = authority.verifier
    if (
        verifier.get("qualified_name") != expected.registered.qualified_name
        or verifier.get("source_sha256") != expected.registered.source_sha256
        or entrypoint.get("qualified_name") != expected.entrypoint.qualified_name
        or entrypoint.get("source_sha256") != expected.entrypoint.source_sha256
    ):
        raise ValueError("lifecycle verifier provenance does not match its planned expectation")


def _validate_recorder_manifest_authority(
    recording: LifecycleExperimentRecordingResult,
    authority: LifecycleInvocationFinalizationAuthority,
) -> None:
    if (
        isinstance(authority, LifecycleInvocationRecorderCapture)
        and recording["manifest_sha256"] != authority.manifest_sha256
    ):
        raise ValueError("lifecycle invocation manifest does not match its recorder capture")


def _validated_callable_provenance(value: object, *, label: str) -> LifecycleCallableProvenance:
    fields = {"qualified_name", "source_path", "source_sha256"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} provenance is malformed")
    qualified_name = value.get("qualified_name")
    source_path = value.get("source_path")
    if not isinstance(qualified_name, str) or not qualified_name.strip():
        raise ValueError(f"{label} qualified name is invalid")
    if not isinstance(source_path, str) or not source_path.strip():
        raise ValueError(f"{label} source path is invalid")
    source_sha256 = _validated_lifecycle_sha256(value.get("source_sha256"), label=f"{label} source hash")
    return LifecycleCallableProvenance(
        qualified_name=qualified_name,
        source_path=source_path,
        source_sha256=source_sha256,
    )


def _validated_lifecycle_sha256(value: object, *, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} is invalid")
    try:
        return ArtifactReference.validate_sha256(value)
    except ValueError as exc:
        raise ValueError(f"{label} is invalid") from exc


def _artifact_sources(
    *,
    package: Path,
    run: Path,
    manifest_path: Path,
    index_path: Path,
    package_files: Mapping[str, str],
    run_files: Mapping[str, str],
    logical_path_prefix: str,
    additional: Sequence[LifecycleArtifactSource],
) -> list[LifecycleArtifactSource]:
    prefix = _normalized_logical_prefix(logical_path_prefix)
    sources = [
        LifecycleArtifactSource(
            kind="lifecycle_package",
            logical_path=_prefixed_logical_path(prefix, f"package/{relative}"),
            path=package / relative,
            media_type=_media_type(package / relative),
        )
        for relative in sorted(package_files)
    ]
    sources.extend(
        LifecycleArtifactSource(
            kind=lifecycle_artifact_kind(Path("run") / relative),
            logical_path=_prefixed_logical_path(prefix, f"run/{relative}"),
            path=run / relative,
            media_type=_media_type(run / relative),
        )
        for relative in sorted(run_files)
    )
    canonical_root = Path("run") / "experiments" / manifest_path.parent.name
    for name in ("experiment-manifest.json", "metrics.json", "verification.json", "index-entry.json"):
        path = manifest_path.parent / name
        sources.append(
            LifecycleArtifactSource(
                kind=lifecycle_artifact_kind(canonical_root / name),
                logical_path=_prefixed_logical_path(prefix, (canonical_root / name).as_posix()),
                path=path,
                media_type=_media_type(path),
            )
        )
    sources.append(
        LifecycleArtifactSource(
            kind="lifecycle_invocation_index",
            logical_path=_prefixed_logical_path(prefix, "experiment-index.jsonl"),
            path=index_path,
            media_type="application/x-ndjson",
        )
    )
    sources.extend(
        LifecycleArtifactSource(
            kind=item.kind,
            logical_path=_prefixed_logical_path(prefix, item.logical_path),
            path=item.path,
            media_type=item.media_type,
        )
        for item in additional
    )
    logical_paths = [item.logical_path for item in sources]
    if len(logical_paths) != len(set(logical_paths)):
        raise ValueError("lifecycle finalization contains duplicate logical artifact paths")
    for item in sources:
        if not item.path.is_file():
            raise ValueError(f"lifecycle finalization artifact is unavailable: {item.logical_path}")
    return sources


def _attach_artifacts(
    record: TrialRecord,
    sources: Sequence[LifecycleArtifactSource],
    invocation: ArtifactReference,
) -> None:
    output_index = 0
    input_index = 0
    for artifact in sources:
        reference = artifact.reference
        if reference.path == invocation.path:
            record.attach_artifact(
                f"authority:{AuthorityEvidenceKind.LIFECYCLE.value}:aec-bench/lifecycle-evidence/1",
                artifact.path,
                media_type=artifact.media_type,
                expected_sha256=reference.sha256,
            )
        elif artifact.kind == "lifecycle_package":
            record.attach_artifact(
                f"input:lifecycle_package:{input_index}",
                artifact.path,
                media_type=artifact.media_type,
                logical_path=artifact.logical_path,
                expected_sha256=reference.sha256,
            )
            input_index += 1
        else:
            record.attach_artifact(
                f"output:{artifact.kind}:{output_index}",
                artifact.path,
                media_type=artifact.media_type,
                logical_path=artifact.logical_path,
                expected_sha256=reference.sha256,
            )
            output_index += 1


def _media_type(path: Path) -> str:
    return {
        ".json": "application/json",
        ".jsonl": "application/x-ndjson",
        ".md": "text/markdown",
        ".txt": "text/plain",
    }.get(path.suffix.lower(), "application/octet-stream")


def _single_artifact(artifacts: Sequence[ArtifactReference], kind: str) -> ArtifactReference:
    matches = [artifact for artifact in artifacts if artifact.kind == kind]
    if len(matches) != 1:
        raise ValueError(f"lifecycle finalization requires exactly one {kind} artifact")
    return matches[0]


def _preferred_artifact(
    artifacts: Sequence[ArtifactReference],
    kind: str,
    logical_path: str,
) -> ArtifactReference:
    matches = [artifact for artifact in artifacts if artifact.kind == kind and artifact.path == logical_path]
    if len(matches) != 1:
        raise ValueError(f"lifecycle finalization requires {logical_path}")
    return matches[0]


def _optional_single_artifact(
    artifacts: Sequence[ArtifactReference],
    kind: str,
) -> ArtifactReference | None:
    matches = [artifact for artifact in artifacts if artifact.kind == kind]
    if len(matches) > 1:
        raise ValueError(f"lifecycle finalization contains duplicate {kind} artifacts")
    return matches[0] if matches else None


def _one_logical_path(artifacts: Sequence[ArtifactReference], kind: str) -> str | None:
    matches = [artifact.path for artifact in artifacts if artifact.kind == kind]
    return matches[0] if len(matches) == 1 else None


def _normalized_logical_prefix(value: str) -> str:
    if not value:
        return ""
    return safe_lifecycle_relative_path(value.strip("/")).as_posix()


def _prefixed_logical_path(prefix: str, relative: str) -> str:
    normalized_relative = safe_lifecycle_relative_path(relative).as_posix()
    normalized_prefix = _normalized_logical_prefix(prefix)
    return f"{normalized_prefix}/{normalized_relative}" if normalized_prefix else normalized_relative


def _lifecycle_instruction(package_dir: Path) -> str:
    instruction_paths = sorted((package_dir / "instructions").glob("*.md"))
    instructions = [path.read_text(encoding="utf-8").strip() for path in instruction_paths]
    instruction = "\n\n".join(item for item in instructions if item)
    if not instruction:
        raise ValueError("lifecycle package instructions are empty")
    return instruction


def _verification_failures(verification: Mapping[str, Any]) -> list[str]:
    gates = verification.get("gates")
    if not isinstance(gates, dict):
        return ["verification gates are malformed"]
    return [
        f"{gate_id}:{failure}"
        for gate_id, gate in gates.items()
        if isinstance(gate, dict)
        for failure in gate.get("failures", [])
    ]


__all__ = (
    "LifecycleArtifactSource",
    "LifecycleFinalizationSource",
    "finalize_lifecycle_trial",
    "live_lifecycle_finalization_source",
)
