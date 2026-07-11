# ABOUTME: Orchestrates resumable model-by-variant evidence-lifecycle ablation experiments.
# ABOUTME: Classifies persisted state, dispatches trials, and publishes immutable records and summaries.

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.meta_harness.evidence_lifecycle import (
    evidence_lifecycle_package_identity,
    read_evidence_lifecycle_state,
    run_evidence_lifecycle,
)
from aec_bench.meta_harness.evidence_lifecycle_ablation_plan import (
    LifecycleAblationCondition,
    LifecycleAblationLimits,
    LifecycleAblationManifest,
    LifecycleAblationPlan,
    LifecycleAblationRunResult,
    LifecycleAblationStudyDesign,
    LifecycleAblationTrial,
    build_lifecycle_ablation_plan,
)
from aec_bench.meta_harness.evidence_lifecycle_episode import (
    InProcessLifecycleEpisodeEnvironment,
    LifecycleEpisodeRequest,
    LifecycleEpisodeResult,
    LifecycleEpisodeUsage,
    LifecycleExecutionMode,
)
from aec_bench.meta_harness.evidence_lifecycle_experiment import (
    LifecycleExperimentSweepContext,
)
from aec_bench.meta_harness.evidence_lifecycle_local import (
    recover_completed_persistent_lifecycle_session,
    run_local_evidence_lifecycle_fresh_context,
    run_local_evidence_lifecycle_session,
    validate_completed_persistent_lifecycle_recovery,
)
from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.lifecycles import (
    lifecycle_package_variant,
)
from aec_bench.task_world_templates.materializer import (
    materialize_template_lifecycle,
    verify_template_lifecycle,
)

__all__ = [
    "LifecycleAblationCondition",
    "LifecycleAblationLimits",
    "LifecycleAblationManifest",
    "LifecycleAblationPlan",
    "LifecycleAblationRunResult",
    "LifecycleAblationStudyDesign",
    "LifecycleAblationTrial",
    "LifecycleExecutionMode",
    "build_lifecycle_ablation_plan",
    "inspect_lifecycle_ablation_plan",
    "load_lifecycle_ablation_manifest",
    "run_lifecycle_ablation",
]

LifecycleRegistryFactory = Callable[[LifecycleAblationTrial, Path, Path], Any]


def load_lifecycle_ablation_manifest(path: Path) -> LifecycleAblationManifest:
    """Load YAML and resolve sweep storage paths relative to the manifest file."""
    source = Path(path)
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected lifecycle ablation YAML object: {source}")
    manifest = LifecycleAblationManifest.model_validate(payload)
    base = source.parent.resolve()

    def resolve(raw: str) -> str:
        candidate = Path(raw)
        return str(candidate.resolve() if candidate.is_absolute() else (base / candidate).resolve())

    normalized = manifest.model_dump(mode="json")
    normalized["output_root"] = resolve(manifest.output_root)
    normalized["ledger_root"] = resolve(manifest.ledger_root)
    return LifecycleAblationManifest.model_validate(normalized)


def inspect_lifecycle_ablation_plan(manifest: LifecycleAblationManifest) -> dict[str, Any]:
    """Report deterministic trial status without creating files or invoking adapters."""
    from aec_bench.meta_harness.evidence_lifecycle_trial_record import (
        build_lifecycle_trial_record,
        validate_lifecycle_ablation_snapshot,
    )

    plan = build_lifecycle_ablation_plan(manifest)
    mutable_trials = [
        trial
        for trial in plan.trials
        if not Path(trial.ledger_path).is_file()
        and not (Path(manifest.ledger_root) / manifest.experiment_id / "_artifacts" / trial.trial_id).is_dir()
    ]
    contract_error: str | None = None
    smoke_error: str | None = None
    if mutable_trials:
        try:
            contract_error = _persisted_contract_error(
                Path(manifest.output_root) / "manifest.json",
                manifest.model_dump(mode="json"),
                label="lifecycle ablation manifest",
            ) or _persisted_contract_error(
                Path(manifest.output_root) / "plan.json",
                plan.model_dump(mode="json"),
                label="lifecycle ablation plan",
            )
        except (OSError, ValueError) as exc:
            contract_error = str(exc)
        if contract_error is None:
            smoke_error = _dry_run_smoke_error(manifest, plan)
    statuses: list[dict[str, Any]] = []
    for trial in plan.trials:
        status = "pending"
        reason: str | None = None
        record_path = Path(trial.ledger_path)
        package = Path(trial.package_dir)
        run_dir = Path(trial.run_dir)
        artifact_dir = Path(manifest.ledger_root) / manifest.experiment_id / "_artifacts" / trial.trial_id
        if record_path.is_file():
            try:
                record = TrialRecord.model_validate_json(record_path.read_text(encoding="utf-8"))
                _validate_existing_record(record, manifest, trial)
            except (OSError, RuntimeError, ValueError) as exc:
                status = "conflict"
                reason = str(exc)
            else:
                status = "complete"
        elif artifact_dir.is_dir():
            try:
                validate_lifecycle_ablation_snapshot(manifest, trial)
            except (OSError, RuntimeError, ValueError) as exc:
                status = "conflict"
                reason = str(exc)
            else:
                status = "finalizable"
        else:
            reason = contract_error or smoke_error
            if reason is None and package.exists():
                try:
                    _validate_variant_package(package, trial)
                except (OSError, RuntimeError, ValueError) as exc:
                    reason = str(exc)
            if reason is not None:
                status = "conflict"
            elif _trial_has_finalizable_state(manifest, trial):
                try:
                    if (run_dir / "state.json").is_file():
                        _validate_ablation_runtime_state(package, run_dir, trial)
                    build_lifecycle_trial_record(
                        manifest=manifest,
                        trial=trial,
                        package_dir=package,
                        run_dir=run_dir,
                    )
                except (OSError, RuntimeError, ValueError) as exc:
                    status = "conflict"
                    reason = str(exc)
                else:
                    status = "finalizable"
            elif (run_dir / "state.json").is_file():
                try:
                    _validate_ablation_runtime_state(package, run_dir, trial)
                    state = read_evidence_lifecycle_state(package, run_dir)
                    if (
                        state["status"] == "complete"
                        and trial.execution_mode is LifecycleExecutionMode.PERSISTENT_CONTEXT
                    ):
                        validate_completed_persistent_lifecycle_recovery(package, run_dir)
                except (OSError, RuntimeError, ValueError) as exc:
                    status = "conflict"
                    reason = str(exc)
                else:
                    status = (
                        "finalizable"
                        if state["status"] == "complete"
                        and trial.execution_mode is LifecycleExecutionMode.PERSISTENT_CONTEXT
                        else "resumable"
                    )
        item = {
            "trial_id": trial.trial_id,
            "variant_id": trial.variant_id,
            "agent_name": trial.agent.name,
            "adapter": trial.agent.adapter,
            "model": trial.agent.model,
            "execution_mode": trial.execution_mode.value,
            "memory_visibility_policy": trial.memory_visibility_policy.value,
            "repetition": trial.repetition,
            "package_dir": trial.package_dir,
            "run_dir": trial.run_dir,
            "ledger_path": trial.ledger_path,
            "status": status,
        }
        if reason is not None:
            item["reason"] = reason
        statuses.append(item)
    return {
        "plan": plan.model_dump(mode="json"),
        "trial_statuses": statuses,
    }


def run_lifecycle_ablation(
    manifest: LifecycleAblationManifest,
    *,
    registry_factory: LifecycleRegistryFactory | None = None,
) -> LifecycleAblationRunResult:
    """Execute or resume a sequential sweep and finalize each invocation once."""
    from aec_bench.meta_harness.evidence_lifecycle_trial_record import finalize_lifecycle_trial_record

    plan = build_lifecycle_ablation_plan(manifest)
    output_root = Path(manifest.output_root)

    executed = 0
    imported_orphans = 0
    skipped = 0
    failed = 0
    trial_ids = [trial.trial_id for trial in plan.trials]
    record_paths_by_trial: dict[str, str] = {}
    remaining: list[LifecycleAblationTrial] = []
    for trial in plan.trials:
        record_path = Path(trial.ledger_path)
        if record_path.is_file():
            record = TrialRecord.model_validate_json(record_path.read_text(encoding="utf-8"))
            _validate_existing_record(record, manifest, trial)
            skipped += 1
            record_paths_by_trial[trial.trial_id] = str(record_path)
            continue
        artifact_dir = Path(manifest.ledger_root) / manifest.experiment_id / "_artifacts" / trial.trial_id
        if artifact_dir.is_dir():
            finalized = finalize_lifecycle_trial_record(
                manifest=manifest,
                trial=trial,
                package_dir=Path(trial.package_dir),
                run_dir=Path(trial.run_dir),
            )
            imported_orphans += 1
            record_paths_by_trial[trial.trial_id] = str(finalized)
            record = TrialRecord.model_validate_json(finalized.read_text(encoding="utf-8"))
            failed += int(_record_execution_failed(record))
            continue
        remaining.append(trial)

    if remaining:
        _write_or_validate_json(
            output_root / "manifest.json",
            manifest.model_dump(mode="json"),
            label="lifecycle ablation manifest",
        )
        _write_or_validate_json(
            output_root / "plan.json",
            plan.model_dump(mode="json"),
            label="lifecycle ablation plan",
        )

    planned_by_variant = {trial.variant_id: trial for trial in remaining}
    packages = {
        variant_id: _ensure_variant_package(manifest, planned_by_variant[variant_id])
        for variant_id in sorted(planned_by_variant)
    }
    if packages:
        _smoke_lifecycle_packages(packages)

    for trial in remaining:
        package = packages[trial.variant_id]
        run_dir = Path(trial.run_dir)
        if (run_dir / "state.json").is_file():
            _validate_ablation_runtime_state(package, run_dir, trial)

        if _trial_has_finalizable_state(manifest, trial):
            finalized = finalize_lifecycle_trial_record(
                manifest=manifest,
                trial=trial,
                package_dir=package,
                run_dir=run_dir,
            )
            imported_orphans += 1
            record_paths_by_trial[trial.trial_id] = str(finalized)
            record = TrialRecord.model_validate_json(finalized.read_text(encoding="utf-8"))
            failed += int(_record_execution_failed(record))
            continue

        sweep_context = LifecycleExperimentSweepContext(
            sweep_experiment_id=manifest.experiment_id,
            planned_trial_id=trial.trial_id,
            plan_sha256=plan.plan_sha256,
            condition_id=f"{trial.execution_mode.value}__{trial.memory_visibility_policy.value}",
            repetition=trial.repetition,
        )
        max_turns = trial.max_turns_per_session
        state = read_evidence_lifecycle_state(package, run_dir) if (run_dir / "state.json").is_file() else None
        if (
            state is not None
            and state["status"] == "complete"
            and trial.execution_mode is LifecycleExecutionMode.PERSISTENT_CONTEXT
        ):
            recover_completed_persistent_lifecycle_session(
                package_dir=package,
                run_dir=run_dir,
                model=trial.agent.model,
                verifier=verify_template_lifecycle,
                adapter_kind=trial.agent.adapter,
                max_turns=max_turns,
                process_id=f"process.lifecycle.{trial.trial_id}",
                visibility_policy=trial.memory_visibility_policy,
                sweep_context=sweep_context,
                repository_dir=Path(__file__).resolve().parent,
            )
            finalized = finalize_lifecycle_trial_record(
                manifest=manifest,
                trial=trial,
                package_dir=package,
                run_dir=run_dir,
            )
            imported_orphans += 1
            record_paths_by_trial[trial.trial_id] = str(finalized)
            record = TrialRecord.model_validate_json(finalized.read_text(encoding="utf-8"))
            failed += int(_record_execution_failed(record))
            continue

        registry = registry_factory(trial, package, run_dir) if registry_factory is not None else None
        try:
            if trial.execution_mode is LifecycleExecutionMode.PERSISTENT_CONTEXT:
                run_local_evidence_lifecycle_session(
                    package_dir=package,
                    run_dir=run_dir,
                    model=trial.agent.model,
                    verifier=verify_template_lifecycle,
                    adapter_kind=trial.agent.adapter,
                    max_turns=max_turns,
                    process_id=f"process.lifecycle.{trial.trial_id}",
                    registry=registry,
                    visibility_policy=trial.memory_visibility_policy,
                    sweep_context=sweep_context,
                    repository_dir=Path(__file__).resolve().parent,
                    require_adapter_identity_match=True,
                )
            else:
                run_local_evidence_lifecycle_fresh_context(
                    package_dir=package,
                    run_dir=run_dir,
                    model=trial.agent.model,
                    verifier=verify_template_lifecycle,
                    adapter_kind=trial.agent.adapter,
                    max_turns=max_turns,
                    process_id=f"process.lifecycle.{trial.trial_id}",
                    registry=registry,
                    visibility_policy=trial.memory_visibility_policy,
                    sweep_context=sweep_context,
                    repository_dir=Path(__file__).resolve().parent,
                    require_adapter_identity_match=True,
                )
        except Exception:
            if not (run_dir / "experiment-manifest.json").is_file():
                raise
        executed += 1
        finalized = finalize_lifecycle_trial_record(
            manifest=manifest,
            trial=trial,
            package_dir=package,
            run_dir=run_dir,
        )
        record_paths_by_trial[trial.trial_id] = str(finalized)
        record = TrialRecord.model_validate_json(finalized.read_text(encoding="utf-8"))
        failed += int(_record_execution_failed(record))

    from aec_bench.meta_harness.evidence_lifecycle_evaluation import write_lifecycle_ablation_evaluation

    summary_path = write_lifecycle_ablation_evaluation(manifest)
    record_paths = [record_paths_by_trial[trial_id] for trial_id in trial_ids]
    return LifecycleAblationRunResult(
        experiment_id=manifest.experiment_id,
        plan_sha256=plan.plan_sha256,
        run_root=manifest.output_root,
        ledger_root=manifest.ledger_root,
        planned_trials=plan.trial_count,
        executed_trials=executed,
        imported_orphans=imported_orphans,
        skipped_trials=skipped,
        failed_trials=failed,
        trial_ids=trial_ids,
        record_paths=record_paths,
        summary_path=str(summary_path),
    )


def _ensure_variant_package(manifest: LifecycleAblationManifest, trial: LifecycleAblationTrial) -> Path:
    variant_id = trial.variant_id
    package = Path(manifest.output_root) / "packages" / variant_id
    if not package.exists():
        materialize_template_lifecycle(
            get_template(manifest.lifecycle_template_id),
            package,
            variant_id=variant_id,
        )
    _validate_variant_package(package, trial)
    return package


def _validate_variant_package(package: Path, trial: LifecycleAblationTrial) -> None:
    variant_id = trial.variant_id
    identity = lifecycle_package_variant(package)
    if identity is None or identity.get("variant_id") != variant_id:
        raise ValueError(f"materialized lifecycle package does not match planned variant {variant_id!r}")
    package_identity = evidence_lifecycle_package_identity(package)
    expected_identity = {
        "lifecycle_id": trial.lifecycle_id,
        "world_id": trial.world_id,
        "spec_sha256": trial.spec_sha256,
        "package_sha256": trial.package_sha256,
    }
    if package_identity != expected_identity:
        raise ValueError("variant identity does not match materialized package content")


def _smoke_lifecycle_packages(packages: dict[str, Path]) -> None:
    with tempfile.TemporaryDirectory(prefix="aec-bench-lifecycle-smoke-") as temporary:
        smoke_root = Path(temporary)
        for variant_id, package in sorted(packages.items()):
            gold_path = package / "hidden" / "gold-submissions.json"
            if not gold_path.is_file():
                raise ValueError(f"lifecycle package lacks deterministic smoke submissions: {variant_id}")
            gold = _read_json(gold_path)

            run_dir = smoke_root / variant_id
            run_evidence_lifecycle(
                package,
                run_dir,
                episode_environment=_gold_smoke_environment(gold),
            )
            verification = verify_template_lifecycle(package, run_dir)
            if not verification.get("passed") or float(verification.get("reward", 0.0)) != 1.0:
                raise ValueError(f"lifecycle package failed deterministic smoke verification: {variant_id}")


def _dry_run_smoke_error(
    manifest: LifecycleAblationManifest,
    plan: LifecycleAblationPlan,
) -> str | None:
    try:
        with tempfile.TemporaryDirectory(prefix="aec-bench-lifecycle-inspect-") as temporary:
            temporary_root = Path(temporary)
            trials_by_variant = {trial.variant_id: trial for trial in plan.trials}
            packages: dict[str, Path] = {}
            for variant_id in sorted(manifest.variants):
                planned = Path(trials_by_variant[variant_id].package_dir)
                if planned.exists():
                    packages[variant_id] = planned
                    continue
                packages[variant_id] = materialize_template_lifecycle(
                    get_template(manifest.lifecycle_template_id),
                    temporary_root / variant_id,
                    variant_id=variant_id,
                )
            _smoke_lifecycle_packages(packages)
    except (OSError, RuntimeError, ValueError) as exc:
        return str(exc)
    return None


def _validate_ablation_runtime_state(
    package: Path,
    run_dir: Path,
    trial: LifecycleAblationTrial,
) -> None:
    state = read_evidence_lifecycle_state(package, run_dir)
    checkpoint_runs = state.get("checkpoint_runs")
    if not isinstance(checkpoint_runs, list):
        raise ValueError("lifecycle state checkpoint_runs are malformed")
    session_attempts: dict[str, list[str]] = {}
    for checkpoint in checkpoint_runs:
        if not isinstance(checkpoint, dict):
            raise ValueError("lifecycle checkpoint state is malformed")
        checkpoint_id = str(checkpoint.get("checkpoint_id") or "")
        attempts = checkpoint.get("attempts")
        if not isinstance(attempts, list):
            raise ValueError(f"lifecycle checkpoint attempts are malformed: {checkpoint_id}")
        for attempt in attempts:
            if not isinstance(attempt, dict):
                raise ValueError(f"lifecycle checkpoint attempt is malformed: {checkpoint_id}")
            if attempt.get("execution_mode") != trial.execution_mode.value:
                raise ValueError(f"attempt execution mode does not match planned trial: {checkpoint_id}")
            session_id = str(attempt.get("session_id") or "")
            session_attempts.setdefault(session_id, []).append(checkpoint_id)
        if checkpoint.get("status") != "submitted":
            continue
        if not attempts:
            raise ValueError(f"submitted checkpoint has no adapter attempt owner: {checkpoint_id}")
        submitted = [attempt for attempt in attempts if attempt.get("status") == "submitted"]
        if len(submitted) != 1 or attempts[-1] != submitted[0]:
            raise ValueError(f"submitted checkpoint has ambiguous adapter attempt ownership: {checkpoint_id}")

    if trial.execution_mode is LifecycleExecutionMode.FRESH_CONTEXT and any(
        len(checkpoint_ids) != 1 for checkpoint_ids in session_attempts.values()
    ):
        raise ValueError("fresh session must own exactly one checkpoint attempt")

    for path in sorted(run_dir.glob("**/agent_result.json")):
        if "experiments" in path.relative_to(run_dir).parts:
            continue
        try:
            payload = _read_json(path)
        except (OSError, ValueError) as exc:
            relative = path.relative_to(run_dir)
            session_id = relative.parts[1] if len(relative.parts) == 3 else ""
            session_attempt_statuses = [
                str(attempt.get("status") or "")
                for checkpoint in checkpoint_runs
                for attempt in checkpoint.get("attempts", [])
                if isinstance(attempt, dict) and attempt.get("session_id") == session_id
            ]
            terminal_persistent_result = (
                path.is_file()
                and trial.execution_mode is LifecycleExecutionMode.PERSISTENT_CONTEXT
                and state.get("status") == "complete"
                and relative.parts == ("sessions", session_id, "agent_result.json")
                and bool(session_attempt_statuses)
                and all(status == "submitted" for status in session_attempt_statuses)
            )
            if not terminal_persistent_result:
                raise ValueError(f"lifecycle session result is malformed: {path}") from exc
            validate_completed_persistent_lifecycle_recovery(package, run_dir)
            continue
        if payload.get("model") != trial.agent.model:
            raise ValueError(f"lifecycle session requested model does not match planned trial: {path}")
        if payload.get("adapter") != trial.agent.adapter:
            raise ValueError(f"lifecycle session requested adapter does not match planned trial: {path}")
        if payload.get("max_turns") != trial.max_turns_per_session:
            raise ValueError(f"lifecycle session turn limit does not match planned trial: {path}")
        expected_session_mode = (
            "persistent" if trial.execution_mode is LifecycleExecutionMode.PERSISTENT_CONTEXT else "fresh"
        )
        if payload.get("session_mode") != expected_session_mode:
            raise ValueError(f"session execution mode does not match planned trial: {path}")
        if payload.get("memory_visibility_policy") != trial.memory_visibility_policy.value:
            raise ValueError(f"session visibility policy does not match planned trial: {path}")
        relative = path.relative_to(run_dir)
        session_id = str(payload.get("session_id") or "")
        if expected_session_mode == "persistent" and relative.parts[:2] != ("sessions", session_id):
            raise ValueError(f"persistent session artifact path does not match planned trial: {path}")
        if expected_session_mode == "fresh" and (
            len(relative.parts) < 4 or relative.parts[0] != "episodes" or relative.parts[2] != session_id
        ):
            raise ValueError(f"fresh session artifact path does not match planned trial: {path}")
        resolved_adapter = payload.get("adapter_name")
        if not isinstance(resolved_adapter, str) or not resolved_adapter:
            raise ValueError(f"lifecycle session resolved adapter is missing: {path}")
        allowed_mismatch = payload.get("status") == "failed" and (
            payload.get("failure_kind") == "adapter_identity_mismatch"
            or (
                resolved_adapter == "unresolved"
                and payload.get("failure_kind") in {"interrupted", "interrupted_after_completion"}
            )
        )
        if resolved_adapter != trial.agent.adapter and not allowed_mismatch:
            raise ValueError(f"lifecycle session resolved adapter does not match planned trial: {path}")


def _write_or_validate_json(path: Path, payload: dict[str, Any], *, label: str) -> None:
    if path.is_file():
        if _read_json(path) != payload:
            raise ValueError(f"{label} conflicts with the persisted sweep contract")
        return
    if path.exists():
        raise ValueError(f"{label} path is not a file: {path}")
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    _write_json(temporary, payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.replace(path)


def _persisted_contract_error(path: Path, payload: dict[str, Any], *, label: str) -> str | None:
    if path.is_file():
        if _read_json(path) != payload:
            return f"{label} conflicts with the persisted sweep contract"
        return None
    if path.exists():
        return f"{label} path is not a file: {path}"
    return None


def _gold_smoke_environment(
    gold: dict[str, Any],
) -> InProcessLifecycleEpisodeEnvironment:
    def execute(request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
        submission = Path(request.submission_path)
        _write_json(
            submission,
            cast(dict[str, Any], gold[request.checkpoint_id]),
        )
        return LifecycleEpisodeResult(
            episode_id=request.episode_id,
            attempt_id=request.attempt_id,
            session_id=request.session_id,
            checkpoint_ids=request.checkpoint_ids,
            execution_mode=request.execution_mode,
            memory_visibility_policy=request.memory_visibility_policy,
            status="completed",
            requested_adapter="deterministic",
            requested_model="gold",
            max_turns_per_session=request.max_turns_per_session,
            adapter="in_process",
            resolved_model="gold",
            configuration={"source": "hidden_gold_smoke"},
            usage=LifecycleEpisodeUsage(),
        )

    return InProcessLifecycleEpisodeEnvironment(executor=execute)


def _trial_has_finalizable_state(
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
) -> bool:
    artifact_dir = Path(manifest.ledger_root) / manifest.experiment_id / "_artifacts" / trial.trial_id
    canonical_invocations = Path(trial.run_dir) / "experiments"
    return artifact_dir.is_dir() or any(
        not path.parent.name.startswith(".") for path in canonical_invocations.glob("*/experiment-manifest.json")
    )


def _validate_existing_record(
    record: TrialRecord,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
) -> None:
    from aec_bench.meta_harness.evidence_lifecycle_trial_record import validate_lifecycle_ablation_record

    validate_lifecycle_ablation_record(record, manifest, trial)


def _record_execution_failed(record: TrialRecord) -> bool:
    return (
        record.lifecycle_execution is None
        or record.lifecycle_execution.status != "completed"
        or not record.evaluation.validity.verifier_completed
    )


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
