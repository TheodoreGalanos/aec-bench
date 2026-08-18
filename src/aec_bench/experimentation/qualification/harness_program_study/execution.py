# ABOUTME: Executes content-addressed harness-program plans through exact materialized RunBundles.
# ABOUTME: Enforces matched outer seeds, single-attempt Harbor runs, verified outcomes, and causal lineage.

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Any, Literal

from aec_bench.contracts.harness_kernel import canonical_json_sha256
from aec_bench.contracts.run_bundle import TaskSnapshotRef
from aec_bench.contracts.trial_record import (
    ArtifactReference,
    TrialRecord,
)
from aec_bench.experimentation.qualification.harness_program_study.analysis import (
    HarnessProgramAnalysis,
    HarnessProgramOutcome,
    analyse_harness_program_study,
)
from aec_bench.experimentation.qualification.harness_program_study.candidates import (
    MaterializedHarnessProgramCandidate,
    MaterializedHarnessProgramCandidateSet,
)
from aec_bench.experimentation.qualification.harness_program_study.plan import (
    HarnessProgramCandidateReference,
    HarnessProgramPlan,
    HarnessProgramStudyManifest,
    HarnessProgramTrial,
    build_harness_program_plan,
)
from aec_bench.experimentation.qualification.run_bundle_runtime import (
    MetaHarnessStudyContext,
    RunBundleExecution,
    execute_run_bundle,
)
from aec_bench.harness.harbor_dispatch import HarborCommandExecutor
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.harness.kernel_catalogue import KernelRuntimeRegistry
from aec_bench.harness.program_execution import ProgramExecutionStatus
from aec_bench.ledger.reader import read_trial_record

StudySplit = Literal["discovery", "repair_gate", "calibration", "holdout"]


@dataclass(frozen=True)
class HarnessProgramPlanArtifact:
    """Deterministic plan and seed schedule stored under their serialized content hash."""

    path: Path
    reference: ArtifactReference
    execution_seeds: tuple[int, ...]


@dataclass(frozen=True)
class HarnessProgramTrialExecution:
    """One planned cell, its selected outer seed, runtime evidence, and verified records."""

    trial: HarnessProgramTrial
    execution_seed: int
    candidate_reference: HarnessProgramCandidateReference
    bundle_id: str
    execution: RunBundleExecution
    records: tuple[TrialRecord, ...]


@dataclass(frozen=True)
class HarnessProgramStudyExecution:
    """Complete plan, ordered executions, finite outcomes, and four-cell analysis."""

    manifest: HarnessProgramStudyManifest
    plan: HarnessProgramPlan
    plan_artifact: HarnessProgramPlanArtifact
    trial_executions: tuple[HarnessProgramTrialExecution, ...]
    outcomes: tuple[HarnessProgramOutcome, ...]
    analysis: HarnessProgramAnalysis


def execute_harness_program_study(
    *,
    candidates: MaterializedHarnessProgramCandidateSet | tuple[MaterializedHarnessProgramCandidateSet, ...],
    manifest: HarnessProgramStudyManifest,
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
) -> HarnessProgramStudyExecution:
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
        raise ValueError("harness-program candidate bundle does not target the installed fixed kernel")

    plan = build_harness_program_plan(study_manifest)
    plan_artifact = _write_harness_program_plan_artifact(
        plan=plan,
        execution_seeds=execution_seeds,
        artifacts_root=artifacts_root,
    )
    candidates_by_reference = _candidate_map(materialized_sets, study_manifest)
    trial_executions: list[HarnessProgramTrialExecution] = []
    outcomes: list[HarnessProgramOutcome] = []

    for trial in plan.trials:
        candidate = candidates_by_reference.get(trial.candidate.reference_sha256)
        if candidate is None or candidate.reference != trial.candidate:
            raise ValueError("harness-program plan candidate reference does not map to an exact RunBundle")
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
                harness_program_cell=trial.cell.value,
                paired_block_id=trial.block_id,
                harness_program_plan=plan_artifact.reference,
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
        outcome = HarnessProgramOutcome(
            trial_id=trial.trial_id,
            value=fmean(record.evaluation.reward for record in records),
        )
        trial_executions.append(
            HarnessProgramTrialExecution(
                trial=trial,
                execution_seed=execution_seed,
                candidate_reference=candidate.reference,
                bundle_id=candidate.bundle.bundle_id,
                execution=execution,
                records=records,
            )
        )
        outcomes.append(outcome)

    analysis = analyse_harness_program_study(
        plan,
        outcomes,
        confidence_level=confidence_level,
        bootstrap_replicates=bootstrap_replicates,
        bootstrap_seed=bootstrap_seed,
    )
    return HarnessProgramStudyExecution(
        manifest=study_manifest,
        plan=plan,
        plan_artifact=plan_artifact,
        trial_executions=tuple(trial_executions),
        outcomes=tuple(outcomes),
        analysis=analysis,
    )


def _write_harness_program_plan_artifact(
    *,
    plan: HarnessProgramPlan,
    execution_seeds: tuple[int, ...],
    artifacts_root: Path,
) -> HarnessProgramPlanArtifact:
    payload = {
        "schema_version": "aecbench.meta-harness-harness-program-plan.v1",
        "plan": plan.model_dump(mode="json"),
        "execution_seeds": list(execution_seeds),
    }
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    artifact_sha256 = hashlib.sha256(encoded).hexdigest()
    path = Path(artifacts_root) / "harness-program-plans" / artifact_sha256 / "harness-program-plan.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != encoded:
        raise ValueError("harness-program plan artifact path already contains different content")
    if not path.exists():
        path.write_bytes(encoded)
    return HarnessProgramPlanArtifact(
        path=path,
        reference=ArtifactReference(
            kind="harness-program-plan",
            path=str(path),
            sha256=artifact_sha256,
            media_type="application/json",
        ),
        execution_seeds=execution_seeds,
    )


def _normalize_materialized_sets(
    candidates: MaterializedHarnessProgramCandidateSet | tuple[MaterializedHarnessProgramCandidateSet, ...],
) -> tuple[MaterializedHarnessProgramCandidateSet, ...]:
    source = (candidates,) if isinstance(candidates, MaterializedHarnessProgramCandidateSet) else candidates
    if not source:
        raise ValueError("harness-program study requires at least one materialized candidate set")
    normalized = tuple(
        MaterializedHarnessProgramCandidateSet.model_validate(candidate_set.model_dump(mode="python"))
        for candidate_set in source
    )
    task_set_ids = [candidate_set.request.task_set_id for candidate_set in normalized]
    if len(task_set_ids) != len(set(task_set_ids)):
        raise ValueError("materialized harness-program task-set ids must be unique")
    return tuple(sorted(normalized, key=lambda candidate_set: candidate_set.request.task_set_id))


def _validate_study_inputs(
    *,
    materialized_sets: tuple[MaterializedHarnessProgramCandidateSet, ...],
    manifest: HarnessProgramStudyManifest,
) -> tuple[HarnessProgramStudyManifest, tuple[int, ...]]:
    study_manifest = HarnessProgramStudyManifest.model_validate(manifest.model_dump(mode="python"))
    materialized_by_task_set = {candidate_set.request.task_set_id: candidate_set for candidate_set in materialized_sets}
    manifest_by_task_set = {candidate_set.task_set_id: candidate_set for candidate_set in study_manifest.candidate_sets}
    missing_task_sets = sorted(set(manifest_by_task_set) - set(materialized_by_task_set))
    if missing_task_sets:
        raise ValueError("missing materialized harness-program task sets: " + ", ".join(missing_task_sets))
    extra_task_sets = sorted(set(materialized_by_task_set) - set(manifest_by_task_set))
    if extra_task_sets:
        raise ValueError("extra materialized harness-program task sets: " + ", ".join(extra_task_sets))
    for task_set_id, materialized in materialized_by_task_set.items():
        if materialized.references != manifest_by_task_set[task_set_id]:
            raise ValueError(
                f"harness-program manifest references do not exactly match materialized task set: {task_set_id}"
            )

    experiment_ids = {candidate_set.request.experiment_id for candidate_set in materialized_sets}
    if experiment_ids != {study_manifest.experiment_id}:
        raise ValueError("materialized harness-program task sets must share the manifest experiment identity")
    schedules = {
        (candidate_set.request.seeds, int(candidate_set.request.repetitions)) for candidate_set in materialized_sets
    }
    if len(schedules) != 1:
        raise ValueError("materialized harness-program task sets must share one seed and repetition schedule")
    execution_seeds, repetitions = next(iter(schedules))
    if study_manifest.repetitions != repetitions or len(execution_seeds) != repetitions:
        raise ValueError("manifest repetitions must match the shared execution seed schedule")
    semantics = {_factor_semantics(candidate_set) for candidate_set in materialized_sets}
    if len(semantics) != 1:
        raise ValueError("materialized harness-program task sets must share identical four-cell factor semantics")
    return study_manifest, execution_seeds


def _factor_semantics(materialized: MaterializedHarnessProgramCandidateSet) -> str:
    request = materialized.request
    return canonical_json_sha256(
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
            configuration["task_refs"] = ["<task-set-refs>"]
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
    materialized_sets: tuple[MaterializedHarnessProgramCandidateSet, ...],
    manifest: HarnessProgramStudyManifest,
) -> dict[str, MaterializedHarnessProgramCandidate]:
    materialized_candidates = tuple(
        candidate for materialized in materialized_sets for candidate in materialized.candidates
    )
    candidates_by_reference = {candidate.reference.reference_sha256: candidate for candidate in materialized_candidates}
    if len(candidates_by_reference) != len(materialized_candidates):
        raise ValueError("harness-program candidate references must be unique")
    manifest_references = {
        reference.reference_sha256
        for candidate_set in manifest.candidate_sets
        for reference in candidate_set.candidates
    }
    if set(candidates_by_reference) != manifest_references:
        raise ValueError("harness-program candidate references do not map to the materialized RunBundles")
    return candidates_by_reference


def _execution_seed(execution_seeds: tuple[int, ...], trial: HarnessProgramTrial) -> int:
    seed_index = trial.repetition - 1
    if not 0 <= seed_index < len(execution_seeds):
        raise ValueError("harness-program trial repetition does not map to an execution seed")
    return execution_seeds[seed_index]


def _validated_records(
    *,
    trial: HarnessProgramTrial,
    candidate: MaterializedHarnessProgramCandidate,
    execution: RunBundleExecution,
    execution_seed: int,
    plan_artifact: ArtifactReference,
) -> tuple[TrialRecord, ...]:
    paths = _validated_harness_program_execution_paths(
        trial=trial,
        candidate=candidate,
        execution=execution,
    )
    records = _load_harness_program_trial_records(paths)
    _validate_harness_program_record_coverage(records=records, candidate=candidate)
    _validate_harness_program_record_outcomes(
        records=records,
        trial=trial,
        candidate=candidate,
        execution_seed=execution_seed,
        plan_artifact=plan_artifact,
    )
    return records


def _validated_harness_program_execution_paths(
    *,
    trial: HarnessProgramTrial,
    candidate: MaterializedHarnessProgramCandidate,
    execution: RunBundleExecution,
) -> tuple[Path, ...]:
    if execution.program.status is not ProgramExecutionStatus.SUCCEEDED:
        detail = execution.program.error_message or execution.program.message or "unknown program failure"
        raise ValueError(f"harness-program trial execution failed: {trial.trial_id}: {detail}")
    if not execution.harbor_invocations:
        raise ValueError("harness-program trial produced no Harbor invocations")
    if candidate.bundle.harbor.repetitions != 1:
        raise ValueError("harness-program trial Harbor invocations must each use exactly one attempt")
    if any(not invocation.imported_trial_paths for invocation in execution.harbor_invocations):
        raise ValueError("harness-program trial Harbor invocation produced no imported TrialRecords")
    paths = tuple(path for invocation in execution.harbor_invocations for path in invocation.imported_trial_paths)
    if len(paths) != len(set(paths)):
        raise ValueError("harness-program trial contains duplicate imported TrialRecord paths")
    return paths


def _load_harness_program_trial_records(paths: tuple[Path, ...]) -> tuple[TrialRecord, ...]:
    records: list[TrialRecord] = []
    for path in paths:
        try:
            record = read_trial_record(path)
        except Exception as error:
            raise ValueError(f"invalid harness-program trial record: {path}") from error
        records.append(record)
    return tuple(records)


def _validate_harness_program_record_coverage(
    *,
    records: tuple[TrialRecord, ...],
    candidate: MaterializedHarnessProgramCandidate,
) -> None:
    record_ids = [record.trial_id for record in records]
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("duplicate harness-program TrialRecord ids")
    task_ids = [record.task.task_id for record in records]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("duplicate harness-program TrialRecords for one task")
    expected_task_ids = set(candidate.bundle.harbor.task_refs)
    if set(task_ids) != expected_task_ids:
        missing = sorted(expected_task_ids - set(task_ids))
        unexpected = sorted(set(task_ids) - expected_task_ids)
        raise ValueError(
            "harness-program TrialRecords do not exactly cover the candidate tasks; "
            f"missing={missing}, unexpected={unexpected}"
        )


def _validate_harness_program_record_outcomes(
    *,
    records: tuple[TrialRecord, ...],
    trial: HarnessProgramTrial,
    candidate: MaterializedHarnessProgramCandidate,
    execution_seed: int,
    plan_artifact: ArtifactReference,
) -> None:
    for record in records:
        validate_harness_program_record_lineage(
            record=record,
            trial=trial,
            candidate=candidate,
            execution_seed=execution_seed,
            plan_artifact=plan_artifact,
        )
        validity = record.evaluation.validity
        if not validity.verifier_completed:
            raise ValueError(f"unverified harness-program trial record: {record.trial_id}")
        if not math.isfinite(record.evaluation.reward):
            raise ValueError(f"non-finite harness-program trial reward: {record.trial_id}")


def validate_harness_program_record_lineage(
    *,
    record: TrialRecord,
    trial: HarnessProgramTrial,
    candidate: MaterializedHarnessProgramCandidate,
    execution_seed: int,
    plan_artifact: ArtifactReference,
) -> None:
    provenance = record.meta_harness_provenance
    if provenance is None:
        raise ValueError(f"harness-program trial record lacks meta-harness provenance: {record.trial_id}")
    snapshot = next(
        (item for item in candidate.bundle.task_snapshots if item.task_id == record.task.task_id),
        None,
    )
    if snapshot is None:
        raise ValueError(f"harness-program trial task has no compiled snapshot: {record.trial_id}")
    expected_review_sidecar, expected_declared_surface = _snapshot_review_lineage(snapshot)
    if (
        provenance.run_id != trial.trial_id
        or provenance.execution_seed != execution_seed
        or provenance.harness_program_cell != trial.cell.value
        or provenance.paired_block_id != trial.block_id
        or provenance.harness_program_plan != plan_artifact
        or provenance.bundle_id != candidate.bundle.bundle_id
        or provenance.kernel_id != candidate.bundle.kernel_ref.kernel_id
        or provenance.harness_id != candidate.reference.harness_ref.instance_id
        or provenance.harness_id != candidate.bundle.harness.instance_id
        or provenance.program_id != candidate.bundle.program.program_id
        or provenance.review_sidecar_sha256 != expected_review_sidecar
        or provenance.declared_surface_sha256 != expected_declared_surface
        or provenance.repetition != 1
    ):
        raise ValueError(
            f"harness-program trial record lineage does not match its planned candidate: {record.trial_id}"
        )


def _snapshot_review_lineage(snapshot: TaskSnapshotRef) -> tuple[str, str]:
    if snapshot.task_review is not None:
        return snapshot.task_review.review_sidecar_sha256, snapshot.task_review.declared_surface_sha256
    return (
        snapshot.package_sha256,
        canonical_json_sha256(
            {
                "kind": "atomic-task",
                "task_id": snapshot.task_id,
                "task_package_sha256": snapshot.package_sha256,
            }
        ),
    )
