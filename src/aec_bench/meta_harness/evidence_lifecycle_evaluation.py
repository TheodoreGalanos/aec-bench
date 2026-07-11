# ABOUTME: Builds lifecycle-ablation summaries exclusively from append-only core TrialRecords.
# ABOUTME: Keeps sweep-specific evaluation beside its meta-harness plan and immutable snapshot boundary.

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aec_bench.contracts.trial_record import ArtifactReference, TrialRecord
from aec_bench.evaluation.artifact import (
    EvaluationArtifact,
    EvaluationFilters,
    write_evaluation_artifact,
)
from aec_bench.meta_harness.evidence_lifecycle_ablation_plan import (
    LifecycleAblationManifest,
    LifecycleAblationPlan,
    LifecycleAblationTrial,
    build_lifecycle_ablation_plan,
)
from aec_bench.meta_harness.evidence_lifecycle_trial_record import (
    validate_historical_lifecycle_ablation_record,
)


def build_lifecycle_ablation_evaluation(
    manifest: LifecycleAblationManifest,
) -> EvaluationArtifact:
    """Build one deterministic summary from the experiment's core ledger records."""
    paths = _trial_record_paths(manifest)
    if paths:
        first = TrialRecord.model_validate_json(paths[0].read_text(encoding="utf-8"))
        historical_manifest, plan = _load_historical_sweep_contract(manifest, first)
    else:
        historical_manifest = manifest
        plan = build_lifecycle_ablation_plan(manifest)
    planned = {trial.trial_id: trial for trial in plan.trials}
    records = _read_validated_records(historical_manifest, plan, planned, paths)

    completed = sum(_record_completed(record) for record in records)
    failed = len(records) - completed
    passed = sum(record.evaluation.reward >= 1.0 for record in records)
    rewards = [record.evaluation.reward for record in records]
    summary = {
        "study_design": plan.study_design.model_dump(mode="json"),
        "planned_trials": plan.trial_count,
        "invocation_records": len(records),
        "completed_trials": completed,
        "failed_trials": failed,
        "passed_trials": passed,
        "mean_reward": _mean(rewards),
        "total_cost_usd": sum(record.cost.estimated_cost_usd or 0.0 for record in records if record.cost is not None),
        "groups": _group_records(records, planned),
    }
    record_digest = hashlib.sha256(
        json.dumps(
            [record.model_dump(mode="json") for record in sorted(records, key=lambda item: item.trial_id)],
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    timestamp = max((record.timestamp for record in records), default=datetime.fromtimestamp(0, tz=UTC))
    return EvaluationArtifact(
        evaluation_id=f"lifecycle-ablation-{record_digest}",
        experiment_id=manifest.experiment_id,
        timestamp=timestamp,
        filters=EvaluationFilters(),
        summary=summary,
        framework_version="1",
    )


def write_lifecycle_ablation_evaluation(manifest: LifecycleAblationManifest) -> Path:
    """Persist the deterministic ledger-derived summary as an EvaluationArtifact."""
    return write_evaluation_artifact(
        Path(manifest.ledger_root),
        build_lifecycle_ablation_evaluation(manifest),
    )


def _group_records(
    records: list[TrialRecord],
    planned: dict[str, LifecycleAblationTrial],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str, str, str], list[TrialRecord]] = defaultdict(list)
    for record in records:
        trial = planned[record.trial_id]
        key = (
            trial.agent.name,
            trial.agent.adapter,
            trial.agent.model,
            trial.variant_id,
            trial.execution_mode.value,
            trial.memory_visibility_policy.value,
        )
        grouped[key].append(record)

    result: list[dict[str, Any]] = []
    for key, group in sorted(grouped.items()):
        rewards = [record.evaluation.reward for record in group]
        retentions = [retention for record in group if (retention := _retention(record)) is not None]
        completed = sum(_record_completed(record) for record in group)
        executions = [record.lifecycle_execution for record in group]
        if any(execution is None for execution in executions):
            raise ValueError("lifecycle calibration group contains a record without execution provenance")
        turn_limits = {execution.max_turns_per_session for execution in executions if execution is not None}
        if len(turn_limits) != 1:
            raise ValueError("lifecycle calibration group mixes per-session turn limits")
        max_turns_per_session = next(iter(turn_limits))
        session_counts = [len(execution.sessions) for execution in executions if execution is not None]
        configured_capacities = [max_turns_per_session * count for count in session_counts]
        requests = [_operational_metric(record, "requests") for record in group]
        tool_calls = [_operational_metric(record, "tool_calls") for record in group]
        token_values = {
            "input": [
                record.cost.tokens_in if record.cost and record.cost.tokens_in is not None else 0 for record in group
            ],
            "output": [
                record.cost.tokens_out if record.cost and record.cost.tokens_out is not None else 0 for record in group
            ],
            "cache_read": [
                record.cost.cache_read_tokens if record.cost and record.cost.cache_read_tokens is not None else 0
                for record in group
            ],
            "cache_write": [
                record.cost.cache_write_tokens if record.cost and record.cost.cache_write_tokens is not None else 0
                for record in group
            ],
        }
        result.append(
            {
                "agent_name": key[0],
                "adapter": key[1],
                "requested_adapter": key[1],
                "resolved_adapters": sorted(
                    {
                        session.adapter
                        for execution in executions
                        if execution is not None
                        for session in execution.sessions
                    }
                ),
                "requested_model": key[2],
                "resolved_models": sorted(
                    {
                        session.resolved_model
                        for execution in executions
                        if execution is not None
                        for session in execution.sessions
                    }
                ),
                "variant_id": key[3],
                "execution_mode": key[4],
                "memory_visibility_policy": key[5],
                "trials": len(group),
                "completed": completed,
                "failed": len(group) - completed,
                "passed": sum(reward >= 1.0 for reward in rewards),
                "mean_reward": _mean(rewards),
                "mean_retention": _mean(retentions) if retentions else None,
                "total_cost_usd": sum(
                    record.cost.estimated_cost_usd or 0.0 for record in group if record.cost is not None
                ),
                "turn_budget_scope": "per_session",
                "max_turns_per_session": max_turns_per_session,
                "total_sessions": sum(session_counts),
                "mean_sessions_per_trial": _mean(session_counts),
                "total_configured_turn_capacity": sum(configured_capacities),
                "mean_configured_turn_capacity": _mean(configured_capacities),
                "total_requests": sum(requests),
                "mean_requests": _mean(requests),
                "total_tool_calls": sum(tool_calls),
                "mean_tool_calls": _mean(tool_calls),
                "total_input_tokens": sum(token_values["input"]),
                "mean_input_tokens": _mean(token_values["input"]),
                "total_output_tokens": sum(token_values["output"]),
                "mean_output_tokens": _mean(token_values["output"]),
                "total_cache_read_tokens": sum(token_values["cache_read"]),
                "mean_cache_read_tokens": _mean(token_values["cache_read"]),
                "total_cache_write_tokens": sum(token_values["cache_write"]),
                "mean_cache_write_tokens": _mean(token_values["cache_write"]),
            }
        )
    return result


def _read_validated_records(
    manifest: LifecycleAblationManifest,
    plan: LifecycleAblationPlan,
    planned: dict[str, LifecycleAblationTrial],
    paths: list[Path],
) -> list[TrialRecord]:
    records: list[TrialRecord] = []
    seen: set[str] = set()
    for path in paths:
        record = TrialRecord.model_validate_json(path.read_text(encoding="utf-8"))
        trial = planned.get(record.trial_id)
        if trial is None:
            raise ValueError(f"ledger contains trial outside the ablation plan: {record.trial_id}")
        if record.trial_id in seen:
            raise ValueError(f"ledger contains duplicate planned trial id: {record.trial_id}")
        if path.resolve() != Path(trial.ledger_path).resolve():
            raise ValueError(f"TrialRecord is not stored at its canonical ledger path: {record.trial_id}")
        validate_historical_lifecycle_ablation_record(record, manifest, plan, trial)
        seen.add(record.trial_id)
        records.append(record)
    return records


def _trial_record_paths(manifest: LifecycleAblationManifest) -> list[Path]:
    experiment_root = Path(manifest.ledger_root) / manifest.experiment_id
    if not experiment_root.exists():
        return []
    return sorted(
        path
        for path in experiment_root.rglob("*.json")
        if not any(part.startswith("_") for part in path.relative_to(experiment_root).parts)
    )


def _load_historical_sweep_contract(
    requested_manifest: LifecycleAblationManifest,
    record: TrialRecord,
) -> tuple[LifecycleAblationManifest, LifecycleAblationPlan]:
    provenance = record.lifecycle_provenance
    if provenance is None or provenance.ablation_manifest is None or provenance.ablation_plan is None:
        raise ValueError("historical TrialRecord is missing snapshotted ablation contract references")
    manifest_payload = _read_artifact_json(
        Path(requested_manifest.ledger_root),
        provenance.ablation_manifest,
        expected_kind="lifecycle_ablation_manifest",
    )
    plan_payload = _read_artifact_json(
        Path(requested_manifest.ledger_root),
        provenance.ablation_plan,
        expected_kind="lifecycle_ablation_plan",
    )
    historical_manifest = LifecycleAblationManifest.model_validate(manifest_payload)
    plan = LifecycleAblationPlan.model_validate(plan_payload)
    if historical_manifest != requested_manifest:
        raise ValueError("requested ablation manifest does not match the snapshotted historical manifest")
    manifest_sha256 = hashlib.sha256(
        json.dumps(
            historical_manifest.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()
    if plan.experiment_id != historical_manifest.experiment_id or plan.manifest_sha256 != manifest_sha256:
        raise ValueError("snapshotted historical plan does not bind the ablation manifest")
    return historical_manifest, plan


def _read_artifact_json(
    ledger_root: Path,
    artifact: ArtifactReference,
    *,
    expected_kind: str,
) -> dict[str, Any]:
    if artifact.kind != expected_kind:
        raise ValueError(f"historical sweep artifact kind must be {expected_kind}")
    root = ledger_root.resolve()
    path = (ledger_root / artifact.path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("historical sweep artifact escapes the ledger root") from exc
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != artifact.sha256:
        raise ValueError("historical sweep artifact hash does not match its TrialRecord")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("historical sweep artifact must contain a JSON object")
    return payload


def _retention(record: TrialRecord) -> float | None:
    breakdown = record.evaluation.breakdown
    if not isinstance(breakdown, dict):
        return None
    semantic = breakdown.get("semantic_transition")
    if not isinstance(semantic, dict):
        return None
    aggregate = semantic.get("aggregate")
    if not isinstance(aggregate, dict):
        return None
    value = aggregate.get("retention")
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _record_completed(record: TrialRecord) -> bool:
    return bool(
        record.lifecycle_execution is not None
        and record.lifecycle_execution.status == "completed"
        and record.evaluation.validity.verifier_completed
    )


def _operational_metric(record: TrialRecord, name: str) -> int:
    breakdown = record.evaluation.breakdown
    operational = breakdown.get("operational_metrics") if isinstance(breakdown, dict) else None
    value = operational.get(name) if isinstance(operational, dict) else None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"lifecycle operational metric must be a non-negative integer: {name}")
    return value


def _mean(values: Sequence[float | int]) -> float:
    return sum(values) / len(values) if values else 0.0
