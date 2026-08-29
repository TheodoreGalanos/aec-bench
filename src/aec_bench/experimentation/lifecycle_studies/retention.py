# ABOUTME: Retains lifecycle ablation artifacts before the core finalizer creates the canonical TrialRecord.
# ABOUTME: Owns study snapshot layout, invocation-index repair, orphan recovery, and exact record persistence.

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Any, cast

from aec_bench.contracts.experiment_manifest import ComputeConfig
from aec_bench.contracts.trial_record import AdaptationProvenance, TrialRecord
from aec_bench.experimentation.lifecycle_studies.ablation_plan import (
    LifecycleAblationManifest,
    LifecycleAblationPlan,
    LifecycleAblationTrial,
    build_lifecycle_ablation_plan,
)
from aec_bench.experimentation.lifecycle_studies.retained_record_identity import matches_retained_lifecycle_record
from aec_bench.experimentation.lifecycle_studies.retained_snapshot import (
    LifecycleAblationInvocation,
    LifecycleAblationSnapshot,
)
from aec_bench.ledger.durability import fsync_directory, fsync_tree, mkdir_durable
from aec_bench.ledger.writer import DuplicateTrialRecordError, write_trial_record
from aec_bench.lifecycles.compiled import load_compiled_lifecycle
from aec_bench.lifecycles.finalization import (
    LifecycleArtifactSource,
    LifecycleFinalizationSource,
    finalize_lifecycle_trial,
)
from aec_bench.lifecycles.invocation import (
    LifecycleCallableProvenanceIdentity,
    LifecycleExperimentManifest,
    LifecycleExperimentRecordingResult,
    LifecycleExperimentSweepContext,
    LifecycleInvocationFinalizationAuthority,
    LifecycleInvocationPlanExpectation,
    LifecycleInvocationRecorderCapture,
    LifecycleRepositoryProvenanceIdentity,
    LifecycleRuntimeProvenance,
    LifecycleVerifierProvenanceExpectation,
)
from aec_bench.lifecycles.runtime.operation_snapshot import is_lifecycle_operation_run_artifact_path
from aec_bench.lifecycles.runtime.request_protocol import is_evidence_request_run_artifact_path
from aec_bench.lifecycles.values import LifecycleTrial
from aec_bench.trials import PlannedTrial

_INDEX_LOCKS_GUARD = Lock()
_INDEX_LOCKS: dict[str, Lock] = {}


def retain_lifecycle_ablation_snapshot(
    *,
    lifecycle_trial: LifecycleTrial,
    recording: LifecycleExperimentRecordingResult,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
) -> LifecycleFinalizationSource:
    """Retain one exact study snapshot before the core finalizer builds its record."""
    expected = _core_lifecycle_trial(
        manifest=manifest,
        trial=trial,
        package_dir=Path(trial.package_dir),
        run_dir=Path(trial.run_dir),
    )
    if lifecycle_trial != expected:
        raise ValueError("lifecycle finalization trial does not match the planned ablation trial")
    finalization_authority = recording.get("finalization_authority")
    if not isinstance(finalization_authority, LifecycleInvocationRecorderCapture):
        raise ValueError("live lifecycle retention requires the recorder finalization capture")
    record_path = Path(trial.ledger_path)
    if record_path.exists():
        raise DuplicateTrialRecordError(f"trial record already exists: {record_path}")
    artifact_dir = _artifact_dir(manifest, trial)
    if artifact_dir.exists():
        raise DuplicateTrialRecordError(f"lifecycle artifact snapshot already exists: {artifact_dir}")

    _repair_shared_invocation_index(lifecycle_trial.run_dir, manifest, trial)
    mkdir_durable(artifact_dir.parent)
    staging = artifact_dir.with_name(f".{trial.trial_id}.staging-{uuid.uuid4().hex}")
    try:
        _stage_authoritative_snapshot(
            manifest=manifest,
            trial=trial,
            package_dir=lifecycle_trial.package_dir,
            run_dir=lifecycle_trial.run_dir,
            staging=staging,
        )
        snapshot = _validate_snapshot_layout(staging, manifest, trial, plan=None)
        if (
            snapshot.invocation.manifest["experiment_id"] != recording["experiment_id"]
            or _sha256(snapshot.invocation.manifest_path) != recording["manifest_sha256"]
        ):
            raise ValueError("retained lifecycle invocation does not match the core recording result")
        _finalize_current_snapshot_at(
            staging,
            manifest,
            trial,
            plan=snapshot.plan,
            finalization_authority=finalization_authority,
        )
        fsync_tree(staging)
        staging.replace(artifact_dir)
        fsync_directory(artifact_dir.parent)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return _snapshot_finalization_source(
        manifest=manifest,
        trial=trial,
        artifact_dir=artifact_dir,
        plan=snapshot.plan,
        finalization_authority=finalization_authority,
    )


def persist_finalized_lifecycle_ablation_record(
    *,
    record: TrialRecord,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
) -> Path:
    """Persist the exact record returned by the core lifecycle finalizer."""
    if record.experiment_id != manifest.experiment_id or record.trial_id != trial.trial_id:
        raise ValueError("core-finalized TrialRecord does not match the planned ablation trial")
    snapshot = _validate_snapshot_layout(_artifact_dir(manifest, trial), manifest, trial, plan=None)
    snapshot_root = snapshot.root.resolve()
    if any(
        not path.resolve().is_relative_to(snapshot_root)
        for path, _media_type, _logical_path in record.pending_artifacts.values()
    ):
        raise ValueError("core-finalized TrialRecord contains an artifact outside its retained study snapshot")
    return write_trial_record(ledger_root=Path(manifest.ledger_root), record=record)


def recover_lifecycle_ablation_record(
    *,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
    package_dir: Path,
    run_dir: Path,
) -> Path:
    """Finalize a current orphan snapshot, or retain a current completed invocation and finalize it."""
    package = Path(package_dir)
    run = Path(run_dir)
    if package.resolve() != Path(trial.package_dir).resolve():
        raise ValueError("supplied package directory does not match planned trial")
    if run.resolve() != Path(trial.run_dir).resolve():
        raise ValueError("supplied run directory does not match planned trial")
    record_path = Path(trial.ledger_path)
    if record_path.exists():
        raise DuplicateTrialRecordError(f"trial record already exists: {record_path}")
    artifact_dir = _artifact_dir(manifest, trial)
    if not artifact_dir.exists():
        _repair_shared_invocation_index(run, manifest, trial)
        mkdir_durable(artifact_dir.parent)
        staging = artifact_dir.with_name(f".{trial.trial_id}.staging-{uuid.uuid4().hex}")
        try:
            _stage_authoritative_snapshot(
                manifest=manifest,
                trial=trial,
                package_dir=package,
                run_dir=run,
                staging=staging,
            )
            snapshot = _validate_snapshot_layout(staging, manifest, trial, plan=None)
            _finalize_snapshot_for_recovery_at(staging, manifest, trial, plan=snapshot.plan)
            fsync_tree(staging)
            staging.replace(artifact_dir)
            fsync_directory(artifact_dir.parent)
        except Exception:
            if staging.exists():
                shutil.rmtree(staging)
            raise
    record = _finalize_snapshot_for_recovery_at(artifact_dir, manifest, trial, plan=None)
    return write_trial_record(ledger_root=Path(manifest.ledger_root), record=record)


def validate_lifecycle_ablation_record(
    record: TrialRecord,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
) -> None:
    """Compare a ledger record with the applicable finalizer for its retained snapshot."""
    if record.experiment_id != manifest.experiment_id or record.trial_id != trial.trial_id:
        raise ValueError("existing TrialRecord does not match the planned trial identity")
    snapshot = _validate_snapshot_layout(_artifact_dir(manifest, trial), manifest, trial, plan=None)
    if snapshot.invocation.manifest.get("schema_version") == "1":
        from aec_bench.experimentation.lifecycle_studies.historical_trial_record import (
            build_historical_lifecycle_trial_record,
            matches_historical_lifecycle_trial_record,
        )

        expected = build_historical_lifecycle_trial_record(
            manifest=manifest,
            trial=trial,
            snapshot=snapshot,
            plan=snapshot.plan,
        )
        if not matches_historical_lifecycle_trial_record(record, expected):
            raise ValueError("historical TrialRecord does not match its immutable lifecycle ablation snapshot")
        return
    expected = finalize_lifecycle_ablation_snapshot(manifest, trial)
    validate_record_matches_finalized_snapshot(record, expected)


def validate_lifecycle_ablation_snapshot(
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
) -> TrialRecord:
    """Validate and finalize an unpublished snapshot without writing a ledger record."""
    return _finalize_snapshot_for_recovery_at(_artifact_dir(manifest, trial), manifest, trial, plan=None)


def validate_lifecycle_ablation_working_trial(
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
    *,
    package_dir: Path,
    run_dir: Path,
) -> None:
    """Validate a current completed invocation through the canonical core finalizer."""
    plan = build_lifecycle_ablation_plan(manifest)
    if {item.trial_id: item for item in plan.trials}.get(trial.trial_id) != trial:
        raise ValueError("working lifecycle trial does not match the deterministic ablation plan")
    package = Path(package_dir)
    run = Path(run_dir)
    if package.resolve() != Path(trial.package_dir).resolve() or run.resolve() != Path(trial.run_dir).resolve():
        raise ValueError("working lifecycle paths do not match the planned ablation trial")
    invocation = _canonical_invocation(run, manifest, trial)
    lifecycle_trial = _core_lifecycle_trial(
        manifest=manifest,
        trial=trial,
        package_dir=package,
        run_dir=run,
        plan=plan,
    )

    def validate(index_path: Path) -> None:
        finalize_lifecycle_trial(
            trial=lifecycle_trial,
            source=LifecycleFinalizationSource(
                compiled=lifecycle_trial.compiled,
                run_dir=run,
                recording=_recording_result(
                    invocation,
                    index_path,
                    finalization_authority=_planned_finalization_expectation(plan, trial),
                ),
            ),
        )

    shared_index = run.parent / "experiment-index.jsonl"
    shared_entry: dict[str, Any] | None = None
    if shared_index.is_file():
        try:
            matching = [
                entry
                for entry in _read_jsonl(shared_index)
                if entry.get("experiment_id") == invocation.manifest["experiment_id"]
            ]
        except (json.JSONDecodeError, ValueError):
            matching = []
        if len(matching) == 1 and _equivalent_index_entries(matching[0], invocation.index_entry):
            shared_entry = matching[0]
    if shared_entry is not None:
        validate(shared_index)
        return
    with TemporaryDirectory(prefix="aec-bench-lifecycle-index-") as temporary:
        normalized = dict(invocation.index_entry)
        normalized["manifest_path"] = str(invocation.manifest_path)
        temporary_index = Path(temporary) / "experiment-index.jsonl"
        _write_jsonl(temporary_index, [normalized])
        validate(temporary_index)


def finalize_lifecycle_ablation_snapshot(
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
    *,
    plan: LifecycleAblationPlan | None = None,
) -> TrialRecord:
    """Build the canonical core record from one immutable current study snapshot."""
    return _finalize_current_snapshot_at(_artifact_dir(manifest, trial), manifest, trial, plan=plan)


def _finalize_current_snapshot_at(
    artifact_dir: Path,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
    *,
    plan: LifecycleAblationPlan | None,
    finalization_authority: LifecycleInvocationFinalizationAuthority | None = None,
) -> TrialRecord:
    snapshot = _validate_snapshot_layout(artifact_dir, manifest, trial, plan=plan)
    if snapshot.invocation.manifest.get("schema_version") != "2":
        raise ValueError("canonical core finalization requires lifecycle invocation schema version 2")
    lifecycle_trial = _core_lifecycle_trial(
        manifest=manifest,
        trial=trial,
        package_dir=snapshot.package_dir,
        run_dir=snapshot.run_dir,
        plan=plan or snapshot.plan,
    )
    return finalize_lifecycle_trial(
        trial=lifecycle_trial,
        source=_snapshot_finalization_source(
            manifest=manifest,
            trial=trial,
            artifact_dir=snapshot.root,
            plan=plan or snapshot.plan,
            finalization_authority=finalization_authority,
        ),
    )


def _finalize_snapshot_for_recovery_at(
    artifact_dir: Path,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
    *,
    plan: LifecycleAblationPlan | None,
) -> TrialRecord:
    snapshot = _validate_snapshot_layout(artifact_dir, manifest, trial, plan=plan)
    if snapshot.invocation.manifest.get("schema_version") == "2":
        return _finalize_current_snapshot_at(artifact_dir, manifest, trial, plan=snapshot.plan)
    from aec_bench.experimentation.lifecycle_studies.historical_trial_record import (
        build_historical_lifecycle_trial_record,
    )

    return build_historical_lifecycle_trial_record(
        manifest=manifest,
        trial=trial,
        snapshot=snapshot,
        plan=snapshot.plan,
    )


def validate_lifecycle_ablation_snapshot_layout(
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
    *,
    plan: LifecycleAblationPlan | None = None,
) -> LifecycleAblationSnapshot:
    """Validate the retained study file set and return its resolved roots."""
    return _validate_snapshot_layout(_artifact_dir(manifest, trial), manifest, trial, plan=plan)


def validate_record_matches_finalized_snapshot(record: TrialRecord, expected: TrialRecord) -> None:
    """Require a persisted record to match the exact core-finalized snapshot record."""
    if not matches_retained_lifecycle_record(record, expected):
        raise ValueError("existing TrialRecord does not match its immutable lifecycle ablation snapshot")


def _snapshot_finalization_source(
    *,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
    artifact_dir: Path,
    plan: LifecycleAblationPlan,
    finalization_authority: LifecycleInvocationFinalizationAuthority | None = None,
) -> LifecycleFinalizationSource:
    ledger_root = Path(manifest.ledger_root)
    invocation = _canonical_invocation(artifact_dir / "run", manifest, trial)
    logical_prefix = artifact_dir.resolve().relative_to(ledger_root.resolve()).as_posix()
    return LifecycleFinalizationSource(
        compiled=load_compiled_lifecycle(artifact_dir / "package"),
        run_dir=artifact_dir / "run",
        recording=_recording_result(
            invocation,
            artifact_dir / "experiment-index.jsonl",
            finalization_authority=(finalization_authority or _planned_finalization_expectation(plan, trial)),
        ),
        logical_path_prefix=logical_prefix,
        additional_artifacts=(
            LifecycleArtifactSource(
                kind="lifecycle_ablation_manifest",
                logical_path="sweep/manifest.json",
                path=artifact_dir / "sweep" / "manifest.json",
                media_type="application/json",
            ),
            LifecycleArtifactSource(
                kind="lifecycle_ablation_plan",
                logical_path="sweep/plan.json",
                path=artifact_dir / "sweep" / "plan.json",
                media_type="application/json",
            ),
        ),
    )


def _core_lifecycle_trial(
    *,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
    package_dir: Path,
    run_dir: Path,
    plan: LifecycleAblationPlan | None = None,
) -> LifecycleTrial:
    selected_plan = plan or build_lifecycle_ablation_plan(manifest)
    compiled = load_compiled_lifecycle(package_dir)
    _validate_planned_compiled_lifecycle(
        compiled=compiled.envelope.model_dump(mode="json"),
        manifest=manifest,
        trial=trial,
    )
    return LifecycleTrial(
        planned=PlannedTrial(
            trial_id=trial.trial_id,
            experiment_id=manifest.experiment_id,
            task_id=manifest.lifecycle_template_id,
            agent=trial.agent,
            compute=ComputeConfig(backend="local"),
            repetition=trial.repetition,
        ),
        compiled=compiled,
        run_dir=run_dir,
        execution_mode=trial.execution_mode,
        visibility_policy=trial.memory_visibility_policy,
        sweep_context=LifecycleExperimentSweepContext(
            sweep_experiment_id=manifest.experiment_id,
            planned_trial_id=trial.trial_id,
            plan_sha256=selected_plan.plan_sha256,
            condition_id=f"{trial.execution_mode.value}__{trial.memory_visibility_policy.value}",
            repetition=trial.repetition,
        ),
    )


def _recording_result(
    invocation: LifecycleAblationInvocation,
    index_path: Path,
    *,
    finalization_authority: LifecycleInvocationFinalizationAuthority,
) -> LifecycleExperimentRecordingResult:
    return {
        "experiment_id": str(invocation.manifest["experiment_id"]),
        "manifest": str(invocation.manifest_path),
        "canonical_manifest": str(invocation.manifest_path),
        "manifest_sha256": _sha256(invocation.manifest_path),
        "metrics": str(invocation.manifest_path.parents[2] / "metrics.json"),
        "verification": str(invocation.manifest_path.parents[2] / "verification.json"),
        "index": str(index_path),
        "finalization_authority": finalization_authority,
    }


def _planned_finalization_expectation(
    plan: LifecycleAblationPlan,
    trial: LifecycleAblationTrial,
) -> LifecycleInvocationPlanExpectation:
    code = plan.code_provenance
    return LifecycleInvocationPlanExpectation(
        repository=LifecycleRepositoryProvenanceIdentity(
            commit=code.repository_commit,
            source_inventory_sha256=code.source_inventory_sha256,
        ),
        runtime=LifecycleRuntimeProvenance.model_validate(trial.runtime_provenance.model_dump(mode="json")),
        verifier=LifecycleVerifierProvenanceExpectation(
            registered=LifecycleCallableProvenanceIdentity(
                qualified_name=code.verifier_qualified_name,
                source_sha256=code.verifier_source_sha256,
            ),
            entrypoint=LifecycleCallableProvenanceIdentity(
                qualified_name=code.verifier_entrypoint_qualified_name,
                source_sha256=code.verifier_entrypoint_source_sha256,
            ),
        ),
    )


def _stage_authoritative_snapshot(
    *,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
    package_dir: Path,
    run_dir: Path,
    staging: Path,
) -> None:
    invocation = _canonical_invocation(run_dir, manifest, trial)
    lifecycle = cast(dict[str, Any], invocation.manifest["lifecycle"])
    outputs = cast(dict[str, Any], invocation.manifest["outputs"])
    _validate_reserved_source_artifact_declarations(
        run_dir,
        cast(dict[str, str], outputs["artifacts"]),
    )
    for relative in sorted(cast(dict[str, str], lifecycle["package_files"])):
        _copy_declared_file(package_dir, staging / "package", relative)
    for relative in sorted(cast(dict[str, str], outputs["artifacts"])):
        _copy_declared_file(run_dir, staging / "run", relative)

    experiment_id = str(invocation.manifest["experiment_id"])
    canonical_dir = staging / "run" / "experiments" / experiment_id
    canonical_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(invocation.manifest_path, canonical_dir / "experiment-manifest.json")
    shutil.copy2(invocation.metrics_path, canonical_dir / "metrics.json")
    shutil.copy2(invocation.verification_path, canonical_dir / "verification.json")
    normalized_seal = dict(invocation.index_entry)
    normalized_seal["manifest_path"] = "experiment-manifest.json"
    _write_json(canonical_dir / "index-entry.json", normalized_seal)
    normalized_index = dict(invocation.index_entry)
    normalized_index["manifest_path"] = f"run/experiments/{experiment_id}/experiment-manifest.json"
    _write_jsonl(staging / "experiment-index.jsonl", [normalized_index])

    persisted_manifest = Path(manifest.output_root) / "manifest.json"
    if persisted_manifest.is_file() and _read_json(persisted_manifest) != manifest.model_dump(mode="json"):
        raise ValueError("persisted ablation manifest does not match planned sweep")
    persisted_plan = Path(manifest.output_root) / "plan.json"
    plan = (
        LifecycleAblationPlan.model_validate(_read_json(persisted_plan))
        if persisted_plan.is_file()
        else build_lifecycle_ablation_plan(manifest)
    )
    if {item.trial_id: item for item in plan.trials}.get(trial.trial_id) != trial:
        raise ValueError("persisted ablation plan does not contain the retained trial")
    _write_json(staging / "sweep" / "manifest.json", manifest.model_dump(mode="json"))
    _write_json(staging / "sweep" / "plan.json", plan.model_dump(mode="json"))


def _validate_reserved_source_artifact_declarations(
    run_dir: Path,
    declared_run_artifacts: dict[str, str],
) -> None:
    selectors = (is_evidence_request_run_artifact_path, is_lifecycle_operation_run_artifact_path)
    actual: set[str] = set()
    for path in sorted(run_dir.rglob("*")):
        relative = path.relative_to(run_dir).as_posix()
        if not any(selects(relative) for selects in selectors):
            continue
        if path.is_symlink():
            raise ValueError(f"reserved lifecycle run artifact is a symlink: {relative}")
        if path.is_file():
            actual.add(relative)
    declared = {relative for relative in declared_run_artifacts if any(selects(relative) for selects in selectors)}
    if actual != declared:
        raise ValueError(
            "source lifecycle run reserved artifact inventory does not match its canonical invocation; "
            f"undeclared={sorted(actual - declared)}; missing={sorted(declared - actual)}"
        )


def _copy_declared_file(source_root: Path, destination_root: Path, raw_relative: str) -> None:
    relative = Path(raw_relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"declared artifact path is unsafe: {raw_relative}")
    source = source_root / relative
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"declared artifact source is not a regular file: {source}")
    destination = destination_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _validate_snapshot_layout(
    artifact_dir: Path,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
    *,
    plan: LifecycleAblationPlan | None,
) -> LifecycleAblationSnapshot:
    if artifact_dir.is_symlink():
        raise ValueError("lifecycle artifact snapshot root must not be a symlink")
    symlinks = sorted(path for path in artifact_dir.rglob("*") if path.is_symlink())
    if symlinks:
        relative = symlinks[0].relative_to(artifact_dir).as_posix()
        raise ValueError(f"lifecycle artifact snapshot must not contain symlinks: {relative}")
    snapshot_manifest = LifecycleAblationManifest.model_validate(_read_json(artifact_dir / "sweep" / "manifest.json"))
    if snapshot_manifest != manifest:
        raise ValueError("artifact snapshot ablation manifest does not match requested sweep")
    snapshot_plan = LifecycleAblationPlan.model_validate(_read_json(artifact_dir / "sweep" / "plan.json"))
    if plan is not None and snapshot_plan != plan:
        raise ValueError("artifact snapshot ablation plan does not match requested sweep")
    if {item.trial_id: item for item in snapshot_plan.trials}.get(trial.trial_id) != trial:
        raise ValueError("artifact snapshot trial does not match its retained ablation plan")
    invocation = _canonical_invocation(artifact_dir / "run", manifest, trial)
    _validate_study_invocation(invocation.manifest, manifest, snapshot_plan, trial)
    lifecycle = cast(dict[str, Any], invocation.manifest["lifecycle"])
    outputs = cast(dict[str, Any], invocation.manifest["outputs"])
    expected = {
        *(f"package/{relative}" for relative in cast(dict[str, str], lifecycle["package_files"])),
        *(f"run/{relative}" for relative in cast(dict[str, str], outputs["artifacts"])),
        f"run/experiments/{invocation.manifest['experiment_id']}/experiment-manifest.json",
        f"run/experiments/{invocation.manifest['experiment_id']}/metrics.json",
        f"run/experiments/{invocation.manifest['experiment_id']}/verification.json",
        f"run/experiments/{invocation.manifest['experiment_id']}/index-entry.json",
        "experiment-index.jsonl",
        "sweep/manifest.json",
        "sweep/plan.json",
    }
    actual = {path.relative_to(artifact_dir).as_posix() for path in artifact_dir.rglob("*") if path.is_file()}
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise ValueError(f"artifact snapshot file set mismatch; missing={missing}, unexpected={unexpected}")
    return LifecycleAblationSnapshot(
        root=artifact_dir,
        package_dir=artifact_dir / "package",
        run_dir=artifact_dir / "run",
        invocation=invocation,
        plan=snapshot_plan,
    )


def _validate_study_invocation(
    experiment: dict[str, Any],
    manifest: LifecycleAblationManifest,
    plan: LifecycleAblationPlan,
    trial: LifecycleAblationTrial,
) -> None:
    """Reconcile recorded execution provenance with the preregistered study plan."""
    lifecycle = cast(dict[str, Any], experiment.get("lifecycle", {}))
    if experiment.get("schema_version") == "2":
        _validate_schema_two_planned_lifecycle(
            experiment=experiment,
            lifecycle=lifecycle,
            manifest=manifest,
            trial=trial,
        )
    variant = lifecycle.get("variant")
    if not isinstance(variant, dict) or variant.get("variant_id") != trial.variant_id:
        raise ValueError("lifecycle invocation variant does not match its planned study trial")
    try:
        adaptation = AdaptationProvenance.model_validate(variant.get("adaptation"))
    except ValueError as exc:
        raise ValueError("lifecycle invocation adaptation is malformed") from exc
    if adaptation != trial.adaptation:
        raise ValueError("lifecycle invocation adaptation does not match its planned study trial")

    environment = cast(dict[str, Any], experiment.get("environment", {}))
    if environment.get("runtime_provenance") != trial.runtime_provenance.model_dump(mode="json"):
        raise ValueError("lifecycle invocation runtime dependencies do not match its planned study trial")
    repository = cast(dict[str, Any], experiment.get("repository", {}))
    provenance = plan.code_provenance
    if (
        repository.get("commit") != provenance.repository_commit
        or repository.get("source_inventory_sha256") != provenance.source_inventory_sha256
    ):
        raise ValueError("lifecycle invocation repository does not match its planned study provenance")
    verifier = cast(dict[str, Any], experiment.get("verifier", {}))
    entrypoint = verifier.get("entrypoint")
    if (
        verifier.get("qualified_name") != provenance.verifier_qualified_name
        or verifier.get("source_sha256") != provenance.verifier_source_sha256
        or not isinstance(entrypoint, dict)
        or entrypoint.get("qualified_name") != provenance.verifier_entrypoint_qualified_name
        or entrypoint.get("source_sha256") != provenance.verifier_entrypoint_source_sha256
    ):
        raise ValueError("lifecycle invocation verifier does not match its planned study provenance")


def _validate_schema_two_planned_lifecycle(
    *,
    experiment: dict[str, Any],
    lifecycle: dict[str, Any],
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
) -> None:
    context = experiment.get("trial")
    compiled = context.get("compiled") if isinstance(context, dict) else None
    expected_lifecycle = {
        "lifecycle_id": trial.lifecycle_id,
        "spec_sha256": trial.spec_sha256,
        "package_sha256": trial.package_sha256,
    }
    expected_compiled = {
        "template_id": manifest.lifecycle_template_id,
        "lifecycle_id": trial.lifecycle_id,
        "lifecycle_spec_sha256": trial.spec_sha256,
        "package_sha256": trial.package_sha256,
        "variant_id": trial.variant_id,
    }
    if (
        any(lifecycle.get(key) != value for key, value in expected_lifecycle.items())
        or not isinstance(context, dict)
        or context.get("task_id") != manifest.lifecycle_template_id
        or not isinstance(compiled, dict)
        or any(compiled.get(key) != value for key, value in expected_compiled.items())
    ):
        raise ValueError("schema-2 lifecycle invocation does not match its planned lifecycle identity")


def _validate_planned_compiled_lifecycle(
    *,
    compiled: dict[str, Any],
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
) -> None:
    expected = {
        "template_id": manifest.lifecycle_template_id,
        "lifecycle_id": trial.lifecycle_id,
        "lifecycle_spec_sha256": trial.spec_sha256,
        "package_sha256": trial.package_sha256,
        "variant_id": trial.variant_id,
    }
    if any(compiled.get(key) != value for key, value in expected.items()):
        raise ValueError("compiled lifecycle does not match its planned lifecycle identity")


def _canonical_invocation(
    run_dir: Path,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
) -> LifecycleAblationInvocation:
    candidates: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted((run_dir / "experiments").glob("*/experiment-manifest.json")):
        if path.parent.name.startswith("."):
            continue
        payload = LifecycleExperimentManifest.model_validate(_read_json(path)).model_dump(mode="json")
        sweep = payload.get("sweep")
        if isinstance(sweep, dict) and (
            sweep.get("sweep_experiment_id") == manifest.experiment_id
            and sweep.get("planned_trial_id") == trial.trial_id
        ):
            candidates.append((path, payload))
    if len(candidates) != 1:
        raise ValueError("expected exactly one canonical lifecycle invocation for planned trial")
    manifest_path, payload = candidates[0]
    experiment_id = str(payload["experiment_id"])
    seal_path = manifest_path.parent / "index-entry.json"
    index_path = run_dir.parent / "experiment-index.jsonl"
    seal_entry = _read_json(seal_path) if seal_path.is_file() else None
    if seal_entry is not None:
        _validate_invocation_index_entry(
            seal_entry,
            entry_path=seal_path,
            manifest_path=manifest_path,
            manifest=payload,
        )
    shared_entries: list[dict[str, Any]] | None = None
    if index_path.is_file():
        try:
            shared_entries = [entry for entry in _read_jsonl(index_path) if entry.get("experiment_id") == experiment_id]
        except (json.JSONDecodeError, ValueError):
            if seal_entry is None:
                raise
    if shared_entries is not None and len(shared_entries) > 1:
        raise ValueError("canonical lifecycle invocation must have at most one shared index entry")
    shared_entry = shared_entries[0] if shared_entries else None
    if shared_entry is not None:
        _validate_invocation_index_entry(
            shared_entry,
            entry_path=index_path,
            manifest_path=manifest_path,
            manifest=payload,
        )
    if seal_entry is not None and shared_entry is not None and not _equivalent_index_entries(seal_entry, shared_entry):
        raise ValueError("canonical lifecycle invocation seal conflicts with shared index entry")
    index_entry = seal_entry or shared_entry
    if index_entry is None:
        raise ValueError("canonical lifecycle invocation has no sealed or shared index entry")
    return LifecycleAblationInvocation(
        manifest_path=manifest_path,
        manifest=payload,
        metrics_path=manifest_path.parent / "metrics.json",
        verification_path=manifest_path.parent / "verification.json",
        index_entry=index_entry,
    )


def _validate_invocation_index_entry(
    entry: dict[str, Any],
    *,
    entry_path: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
) -> None:
    if entry.get("experiment_id") != manifest.get("experiment_id"):
        raise ValueError("canonical lifecycle invocation id does not match index entry")
    indexed_path = Path(str(entry.get("manifest_path", "")))
    if not indexed_path.is_absolute():
        indexed_path = entry_path.parent / indexed_path
    if indexed_path.resolve() != manifest_path.resolve():
        raise ValueError("canonical lifecycle invocation path does not match index entry")
    if entry.get("manifest_sha256") != _sha256(manifest_path):
        raise ValueError("canonical lifecycle invocation hash does not match index entry")
    if entry.get("sweep") != manifest.get("sweep"):
        raise ValueError("canonical lifecycle invocation sweep does not match index entry")


def _equivalent_index_entries(first: dict[str, Any], second: dict[str, Any]) -> bool:
    return {key: value for key, value in first.items() if key != "manifest_path"} == {
        key: value for key, value in second.items() if key != "manifest_path"
    }


def _repair_shared_invocation_index(
    run_dir: Path,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
) -> None:
    invocation = _canonical_invocation(run_dir, manifest, trial)
    index_path = run_dir.parent / "experiment-index.jsonl"
    normalized = dict(invocation.index_entry)
    normalized["manifest_path"] = str(invocation.manifest_path)
    with _exclusive_index_lock(index_path):
        needs_rewrite = not index_path.is_file()
        try:
            entries = (
                _read_jsonl(index_path)
                if index_path.is_file()
                else _recover_index_entries_from_seals(index_path.parent)
            )
        except (json.JSONDecodeError, ValueError):
            entries = _recover_index_entries_from_seals(index_path.parent)
            needs_rewrite = True
        matching = [entry for entry in entries if entry.get("experiment_id") == normalized["experiment_id"]]
        if len(matching) > 1:
            raise ValueError("canonical lifecycle invocation has duplicate shared index entries")
        if matching:
            if not _equivalent_index_entries(matching[0], normalized):
                raise ValueError("canonical lifecycle invocation seal conflicts with shared index entry")
            if needs_rewrite:
                _write_jsonl_atomic(index_path, sorted(entries, key=lambda entry: str(entry.get("experiment_id", ""))))
            return
        entries.append(normalized)
        _write_jsonl_atomic(index_path, sorted(entries, key=lambda entry: str(entry.get("experiment_id", ""))))


@contextmanager
def _exclusive_index_lock(index_path: Path) -> Iterator[None]:
    mkdir_durable(index_path.parent)
    lock_path = index_path.with_name(f".{index_path.name}.lock")
    key = str(lock_path.resolve())
    with _INDEX_LOCKS_GUARD:
        thread_lock = _INDEX_LOCKS.setdefault(key, Lock())
    with thread_lock:
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


def _recover_index_entries_from_seals(index_root: Path) -> list[dict[str, Any]]:
    recovered: dict[str, dict[str, Any]] = {}
    for seal_path in sorted(index_root.glob("*/experiments/*/index-entry.json")):
        if seal_path.parent.name.startswith("."):
            continue
        entry = _read_json(seal_path)
        manifest_path = seal_path.parent / "experiment-manifest.json"
        manifest = LifecycleExperimentManifest.model_validate(_read_json(manifest_path)).model_dump(mode="json")
        _validate_invocation_index_entry(
            entry,
            entry_path=seal_path,
            manifest_path=manifest_path,
            manifest=manifest,
        )
        normalized = dict(entry)
        normalized["manifest_path"] = str(manifest_path)
        experiment_id = str(normalized["experiment_id"])
        if experiment_id in recovered and not _equivalent_index_entries(recovered[experiment_id], normalized):
            raise ValueError(f"conflicting canonical invocation seals: {experiment_id}")
        recovered[experiment_id] = normalized
    return list(recovered.values())


def _artifact_dir(manifest: LifecycleAblationManifest, trial: LifecycleAblationTrial) -> Path:
    return Path(manifest.ledger_root) / manifest.experiment_id / "_artifacts" / trial.trial_id


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, payloads: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(payload, sort_keys=True) + "\n" for payload in payloads),
        encoding="utf-8",
    )


def _write_jsonl_atomic(path: Path, payloads: list[dict[str, Any]]) -> None:
    mkdir_durable(path.parent)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write("".join(json.dumps(payload, sort_keys=True) + "\n" for payload in payloads))
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError(f"expected JSONL file: {path}")
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"expected JSON object at {path}:{line_number}")
        records.append(cast(dict[str, Any], payload))
    return records


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
