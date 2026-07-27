# ABOUTME: Executes content-addressed blocked factorial plans through exact materialized RunBundles.
# ABOUTME: Enforces matched outer seeds, single-attempt Harbor runs, verified outcomes, and causal lineage.

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Any, Literal

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.run_bundle import TaskSnapshotRef
from aec_bench.contracts.trial_record import ArtifactReference, Completeness, TrialRecord
from aec_bench.harness.harbor_dispatch import HarborCommandExecutor
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.meta_harness.factorial_analysis import (
    FactorialAnalysis,
    FactorialOutcome,
    analyse_factorial,
)
from aec_bench.meta_harness.factorial_candidates import (
    MaterializedFactorialCandidate,
    MaterializedFactorialCandidateSet,
)
from aec_bench.meta_harness.factorial_plan import (
    FactorialCandidateReference,
    FactorialPlan,
    FactorialStudyManifest,
    FactorialTrial,
    build_factorial_plan,
)
from aec_bench.meta_harness.kernel_catalogue import KernelRuntimeRegistry
from aec_bench.meta_harness.program_runtime import ProgramExecutionStatus
from aec_bench.meta_harness.run_bundle_runtime import (
    MetaHarnessStudyContext,
    RunBundleExecution,
    execute_run_bundle,
)

StudySplit = Literal["discovery", "repair_gate", "calibration", "holdout"]


@dataclass(frozen=True)
class FactorialPlanArtifact:
    """Deterministic plan and seed schedule stored under their serialized content hash."""

    path: Path
    reference: ArtifactReference
    execution_seeds: tuple[int, ...]


@dataclass(frozen=True)
class FactorialTrialExecution:
    """One planned cell, its selected outer seed, runtime evidence, and verified records."""

    trial: FactorialTrial
    execution_seed: int
    candidate_reference: FactorialCandidateReference
    execution: RunBundleExecution
    records: tuple[TrialRecord, ...]


@dataclass(frozen=True)
class FactorialStudyExecution:
    """Complete plan, ordered executions, finite outcomes, and four-cell analysis."""

    manifest: FactorialStudyManifest
    plan: FactorialPlan
    plan_artifact: FactorialPlanArtifact
    trial_executions: tuple[FactorialTrialExecution, ...]
    outcomes: tuple[FactorialOutcome, ...]
    analysis: FactorialAnalysis


def execute_factorial_study(
    *,
    candidates: MaterializedFactorialCandidateSet | tuple[MaterializedFactorialCandidateSet, ...],
    manifest: FactorialStudyManifest,
    registry: KernelRuntimeRegistry,
    workflow: SynchronousHarborWorkflow,
    artifacts_root: Path,
    policy_id: str,
    harness_generator_sha256: str,
    program_generator_sha256: str,
    split: StudySplit,
    motif_ids: tuple[str, ...] = (),
    executor: HarborCommandExecutor | None = None,
    confidence_level: float = 0.95,
    bootstrap_replicates: int = 2_000,
    bootstrap_seed: int = 42,
) -> FactorialStudyExecution:
    """Execute a complete Williams-square study while preserving verifier-scored invalid outcomes."""
    materialized_sets = _normalize_materialized_sets(candidates)
    study_manifest, execution_seeds = _validate_study_inputs(
        materialized_sets=materialized_sets,
        manifest=manifest,
    )
    if any(
        candidate.bundle.kernel_ref != registry.manifest.ref
        for materialized in materialized_sets
        for candidate in materialized.candidates
    ):
        raise ValueError("factorial candidate bundle does not target the installed fixed kernel")

    plan = build_factorial_plan(study_manifest)
    plan_artifact = _write_factorial_plan_artifact(
        plan=plan,
        execution_seeds=execution_seeds,
        artifacts_root=artifacts_root,
    )
    candidates_by_reference = _candidate_map(materialized_sets, study_manifest)
    trial_executions: list[FactorialTrialExecution] = []
    outcomes: list[FactorialOutcome] = []

    for trial in plan.trials:
        candidate = candidates_by_reference.get(trial.candidate.reference_sha256)
        if candidate is None or candidate.reference != trial.candidate:
            raise ValueError("factorial plan candidate reference does not map to an exact RunBundle")
        execution_seed = _execution_seed(execution_seeds, trial)
        execution = execute_run_bundle(
            bundle=candidate.bundle,
            registry=registry,
            workflow=workflow,
            artifacts_root=artifacts_root,
            study=MetaHarnessStudyContext(
                run_id=trial.trial_id,
                policy_id=policy_id,
                harness_generator_sha256=harness_generator_sha256,
                program_generator_sha256=program_generator_sha256,
                split=split,
                factorial_cell=trial.cell.value,
                paired_block_id=trial.block_id,
                factorial_plan=plan_artifact.reference,
                execution_seed=execution_seed,
                motif_ids=motif_ids,
            ),
            executor=executor,
        )
        records = _validated_records(
            trial=trial,
            candidate=candidate,
            execution=execution,
            execution_seed=execution_seed,
            plan_artifact=plan_artifact.reference,
        )
        outcome = FactorialOutcome(
            trial_id=trial.trial_id,
            value=fmean(record.evaluation.reward for record in records),
        )
        trial_executions.append(
            FactorialTrialExecution(
                trial=trial,
                execution_seed=execution_seed,
                candidate_reference=candidate.reference,
                execution=execution,
                records=records,
            )
        )
        outcomes.append(outcome)

    analysis = analyse_factorial(
        plan,
        outcomes,
        confidence_level=confidence_level,
        bootstrap_replicates=bootstrap_replicates,
        bootstrap_seed=bootstrap_seed,
    )
    return FactorialStudyExecution(
        manifest=study_manifest,
        plan=plan,
        plan_artifact=plan_artifact,
        trial_executions=tuple(trial_executions),
        outcomes=tuple(outcomes),
        analysis=analysis,
    )


def _write_factorial_plan_artifact(
    *,
    plan: FactorialPlan,
    execution_seeds: tuple[int, ...],
    artifacts_root: Path,
) -> FactorialPlanArtifact:
    payload = {
        "schema_version": "aecbench.meta-harness-factorial-plan.v1",
        "plan": plan.model_dump(mode="json"),
        "execution_seeds": list(execution_seeds),
    }
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    artifact_sha256 = hashlib.sha256(encoded).hexdigest()
    path = Path(artifacts_root) / "factorial-plans" / artifact_sha256 / "factorial-plan.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != encoded:
        raise ValueError("factorial plan artifact path already contains different content")
    if not path.exists():
        path.write_bytes(encoded)
    return FactorialPlanArtifact(
        path=path,
        reference=ArtifactReference(
            kind="factorial-plan",
            path=str(path),
            sha256=artifact_sha256,
            media_type="application/json",
        ),
        execution_seeds=execution_seeds,
    )


def _normalize_materialized_sets(
    candidates: MaterializedFactorialCandidateSet | tuple[MaterializedFactorialCandidateSet, ...],
) -> tuple[MaterializedFactorialCandidateSet, ...]:
    source = (candidates,) if isinstance(candidates, MaterializedFactorialCandidateSet) else candidates
    if not source:
        raise ValueError("factorial study requires at least one materialized candidate set")
    normalized = tuple(
        MaterializedFactorialCandidateSet.model_validate(candidate_set.model_dump(mode="python"))
        for candidate_set in source
    )
    world_ids = [candidate_set.request.world_id for candidate_set in normalized]
    if len(world_ids) != len(set(world_ids)):
        raise ValueError("materialized factorial world ids must be unique")
    return tuple(sorted(normalized, key=lambda candidate_set: candidate_set.request.world_id))


def _validate_study_inputs(
    *,
    materialized_sets: tuple[MaterializedFactorialCandidateSet, ...],
    manifest: FactorialStudyManifest,
) -> tuple[FactorialStudyManifest, tuple[int, ...]]:
    study_manifest = FactorialStudyManifest.model_validate(manifest.model_dump(mode="python"))
    materialized_by_world = {candidate_set.request.world_id: candidate_set for candidate_set in materialized_sets}
    manifest_by_world = {candidate_set.world_id: candidate_set for candidate_set in study_manifest.candidate_sets}
    missing_worlds = sorted(set(manifest_by_world) - set(materialized_by_world))
    if missing_worlds:
        raise ValueError("missing materialized factorial worlds: " + ", ".join(missing_worlds))
    extra_worlds = sorted(set(materialized_by_world) - set(manifest_by_world))
    if extra_worlds:
        raise ValueError("extra materialized factorial worlds: " + ", ".join(extra_worlds))
    for world_id, materialized in materialized_by_world.items():
        if materialized.references != manifest_by_world[world_id]:
            raise ValueError(f"factorial manifest references do not exactly match materialized world: {world_id}")

    experiment_ids = {candidate_set.request.experiment_id for candidate_set in materialized_sets}
    if experiment_ids != {study_manifest.experiment_id}:
        raise ValueError("materialized factorial worlds must share the manifest experiment identity")
    schedules = {
        (candidate_set.request.seeds, int(candidate_set.request.repetitions)) for candidate_set in materialized_sets
    }
    if len(schedules) != 1:
        raise ValueError("materialized factorial worlds must share one seed and repetition schedule")
    execution_seeds, repetitions = next(iter(schedules))
    if study_manifest.repetitions != repetitions or len(execution_seeds) != repetitions:
        raise ValueError("manifest repetitions must match the shared execution seed schedule")
    semantics = {_factor_semantics(candidate_set) for candidate_set in materialized_sets}
    if len(semantics) != 1:
        raise ValueError("materialized factorial worlds must share identical four-cell factor semantics")
    return study_manifest, execution_seeds


def _factor_semantics(materialized: MaterializedFactorialCandidateSet) -> str:
    request = materialized.request
    return canonical_content_sha256(
        {
            "schema_version": "1",
            "kernel_ref": request.kernel_ref.model_dump(mode="json"),
            "model": request.model,
            "harness_budget": request.harness_budget.model_dump(mode="json"),
            "program_limits": request.program_limits.model_dump(mode="json"),
            "fixed_harness": _harness_semantics(request.fixed_harness_recipe.model_dump(mode="json")),
            "learned_harness": _harness_semantics(request.learned_harness_recipe.model_dump(mode="json")),
            "fixed_program": _program_semantics(request.fixed_program.model_dump(mode="json")),
            "learned_program": _program_semantics(request.learned_program.model_dump(mode="json")),
        }
    )


def _harness_semantics(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized.pop("content_sha256", None)
    normalized.pop("recipe_id", None)
    normalized.pop("summary", None)
    bindings = []
    for source_binding in normalized["bindings"]:
        binding = dict(source_binding)
        configuration = dict(binding["configuration"])
        if configuration.get("kind") == "task_source":
            configuration["task_refs"] = ["<world-task-refs>"]
        binding["configuration"] = configuration
        bindings.append(binding)
    normalized["bindings"] = bindings
    return normalized


def _program_semantics(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized.pop("content_sha256", None)
    normalized.pop("factor_id", None)
    return normalized


def _candidate_map(
    materialized_sets: tuple[MaterializedFactorialCandidateSet, ...],
    manifest: FactorialStudyManifest,
) -> dict[str, MaterializedFactorialCandidate]:
    materialized_candidates = tuple(
        candidate for materialized in materialized_sets for candidate in materialized.candidates
    )
    candidates_by_reference = {candidate.reference.reference_sha256: candidate for candidate in materialized_candidates}
    if len(candidates_by_reference) != len(materialized_candidates):
        raise ValueError("factorial candidate references must be unique")
    manifest_references = {
        reference.reference_sha256
        for candidate_set in manifest.candidate_sets
        for reference in candidate_set.candidates
    }
    if set(candidates_by_reference) != manifest_references:
        raise ValueError("factorial candidate references do not map to the materialized RunBundles")
    return candidates_by_reference


def _execution_seed(execution_seeds: tuple[int, ...], trial: FactorialTrial) -> int:
    seed_index = trial.repetition - 1
    if not 0 <= seed_index < len(execution_seeds):
        raise ValueError("factorial trial repetition does not map to an execution seed")
    return execution_seeds[seed_index]


def _validated_records(
    *,
    trial: FactorialTrial,
    candidate: MaterializedFactorialCandidate,
    execution: RunBundleExecution,
    execution_seed: int,
    plan_artifact: ArtifactReference,
) -> tuple[TrialRecord, ...]:
    paths = _validated_factorial_execution_paths(
        trial=trial,
        candidate=candidate,
        execution=execution,
    )
    records = _load_factorial_trial_records(paths)
    _validate_factorial_record_coverage(records=records, candidate=candidate)
    _validate_factorial_record_outcomes(
        records=records,
        trial=trial,
        candidate=candidate,
        execution_seed=execution_seed,
        plan_artifact=plan_artifact,
    )
    return records


def _validated_factorial_execution_paths(
    *,
    trial: FactorialTrial,
    candidate: MaterializedFactorialCandidate,
    execution: RunBundleExecution,
) -> tuple[Path, ...]:
    if execution.program.status is not ProgramExecutionStatus.SUCCEEDED:
        detail = execution.program.error_message or execution.program.message or "unknown program failure"
        raise ValueError(f"factorial trial execution failed: {trial.trial_id}: {detail}")
    if not execution.harbor_invocations:
        raise ValueError("factorial trial produced no Harbor invocations")
    if candidate.bundle.harbor.repetitions != 1:
        raise ValueError("factorial trial Harbor invocations must each use exactly one attempt")
    if any(not invocation.imported_trial_paths for invocation in execution.harbor_invocations):
        raise ValueError("factorial trial Harbor invocation produced no imported TrialRecords")
    paths = tuple(path for invocation in execution.harbor_invocations for path in invocation.imported_trial_paths)
    if len(paths) != len(set(paths)):
        raise ValueError("factorial trial contains duplicate imported TrialRecord paths")
    return paths


def _load_factorial_trial_records(paths: tuple[Path, ...]) -> tuple[TrialRecord, ...]:
    records: list[TrialRecord] = []
    for path in paths:
        try:
            record = TrialRecord.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as error:
            raise ValueError(f"invalid factorial trial record: {path}") from error
        records.append(record)
    return tuple(records)


def _validate_factorial_record_coverage(
    *,
    records: tuple[TrialRecord, ...],
    candidate: MaterializedFactorialCandidate,
) -> None:
    record_ids = [record.trial_id for record in records]
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("duplicate factorial TrialRecord ids")
    task_ids = [record.task.task_id for record in records]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("duplicate factorial TrialRecords for one task")
    expected_task_ids = set(candidate.bundle.harbor.task_refs)
    if set(task_ids) != expected_task_ids:
        missing = sorted(expected_task_ids - set(task_ids))
        unexpected = sorted(set(task_ids) - expected_task_ids)
        raise ValueError(
            "factorial TrialRecords do not exactly cover the candidate tasks; "
            f"missing={missing}, unexpected={unexpected}"
        )


def _validate_factorial_record_outcomes(
    *,
    records: tuple[TrialRecord, ...],
    trial: FactorialTrial,
    candidate: MaterializedFactorialCandidate,
    execution_seed: int,
    plan_artifact: ArtifactReference,
) -> None:
    for record in records:
        validate_factorial_record_lineage(
            record=record,
            trial=trial,
            candidate=candidate,
            execution_seed=execution_seed,
            plan_artifact=plan_artifact,
        )
        validity = record.evaluation.validity
        if not validity.verifier_completed:
            raise ValueError(f"unverified factorial trial record: {record.trial_id}")
        if not math.isfinite(record.evaluation.reward):
            raise ValueError(f"non-finite factorial trial reward: {record.trial_id}")


def validate_factorial_record_lineage(
    *,
    record: TrialRecord,
    trial: FactorialTrial,
    candidate: MaterializedFactorialCandidate,
    execution_seed: int,
    plan_artifact: ArtifactReference,
) -> None:
    provenance = record.meta_harness_provenance
    if provenance is None:
        raise ValueError(f"factorial trial record lacks meta-harness provenance: {record.trial_id}")
    snapshot = next(
        (item for item in candidate.bundle.task_snapshots if item.task_id == record.task.task_id),
        None,
    )
    if snapshot is None:
        raise ValueError(f"factorial trial task has no compiled snapshot: {record.trial_id}")
    expected_world_package, expected_topology = _snapshot_world_lineage(snapshot)
    if (
        provenance.run_id != trial.trial_id
        or provenance.execution_seed != execution_seed
        or provenance.factorial_cell != trial.cell.value
        or provenance.paired_block_id != trial.block_id
        or provenance.factorial_plan != plan_artifact
        or provenance.bundle_id != candidate.bundle.bundle_id
        or provenance.bundle_sha256 != candidate.bundle.content_sha256
        or provenance.kernel_id != candidate.bundle.kernel_ref.kernel_id
        or provenance.harness_sha256 != candidate.reference.harness_sha256
        or provenance.harness_id != candidate.bundle.harness.instance_id
        or provenance.kernel_sha256 != candidate.reference.kernel_sha256
        or provenance.program_id != candidate.bundle.program.program_id
        or provenance.program_sha256 != candidate.bundle.program.content_sha256
        or provenance.world_package_sha256 != expected_world_package
        or provenance.topology_signature_sha256 != expected_topology
        or provenance.repetition != 1
        or record.completeness is not Completeness.COMPLETE
    ):
        raise ValueError(f"factorial trial record lineage does not match its planned candidate: {record.trial_id}")
    if record.outputs.artifacts is None or plan_artifact not in record.outputs.artifacts:
        raise ValueError(f"factorial trial record does not bind its plan artifact: {record.trial_id}")


def _snapshot_world_lineage(snapshot: TaskSnapshotRef) -> tuple[str, str]:
    if snapshot.world is not None:
        return snapshot.world.world_package_sha256, snapshot.world.topology_signature_sha256
    return (
        snapshot.package_sha256,
        canonical_content_sha256(
            {
                "kind": "atomic-task-world",
                "task_id": snapshot.task_id,
                "task_package_sha256": snapshot.package_sha256,
            }
        ),
    )
