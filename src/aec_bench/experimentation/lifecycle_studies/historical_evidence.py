# ABOUTME: Validates schema-1 lifecycle evidence against its retained run and package artifacts.
# ABOUTME: Keeps retired evidence rules separate from current retention and finalization.

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, cast

from aec_bench.contracts.evidence_lifecycle import EvidenceLifecycleSpec
from aec_bench.contracts.trajectory import read_trajectory
from aec_bench.experimentation.lifecycle_studies.historical_operation import (
    validate_captured_lifecycle_operation_interaction,
)
from aec_bench.lifecycles.catalogue import lifecycle_operation_resolver
from aec_bench.lifecycles.runtime.episode import LifecycleOperationCurrentSource
from aec_bench.lifecycles.runtime.lifecycle import (
    evidence_request_catalog_payload,
    load_evidence_lifecycle_spec,
    validate_evidence_request_run_state,
)
from aec_bench.lifecycles.runtime.operation_snapshot import validate_lifecycle_operation_snapshot
from aec_bench.lifecycles.runtime.operation_store import (
    resolve_lifecycle_operation_current_source,
    validate_lifecycle_operation_resolver_replay,
)
from aec_bench.lifecycles.runtime.request_protocol import (
    expected_evidence_request_run_artifact_paths,
    is_evidence_request_run_artifact_path,
)
from aec_bench.lifecycles.runtime.state import EvidenceLifecycleRunState, EvidenceRequestActionRecord


def _validate_declared_run_artifacts(run_dir: Path, experiment: dict[str, Any]) -> None:
    outputs = experiment.get("outputs")
    declared = outputs.get("artifacts") if isinstance(outputs, dict) else None
    if not isinstance(declared, dict) or not declared:
        raise ValueError("canonical lifecycle manifest must declare run artifact hashes")
    required = {"lifecycle_ledger.jsonl", "metrics.json", "state.json", "verification.json"}
    missing = sorted(required - set(declared))
    if missing:
        raise ValueError(f"canonical lifecycle manifest is missing required run artifacts: {', '.join(missing)}")
    root = run_dir.resolve()
    for raw_relative, expected in sorted(declared.items()):
        relative = Path(str(raw_relative))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"canonical lifecycle manifest contains unsafe artifact path: {raw_relative}")
        path = (run_dir / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"canonical lifecycle manifest artifact escapes run root: {raw_relative}")
        if not path.is_file() or not isinstance(expected, str) or _sha256(path) != expected:
            raise ValueError(f"run artifact hash does not match canonical manifest: {raw_relative}")
    interaction = experiment.get("interaction")
    trajectories = interaction.get("trajectory_hashes") if isinstance(interaction, dict) else None
    if not isinstance(trajectories, dict):
        raise ValueError("canonical lifecycle manifest must declare trajectory hashes")
    for relative, digest in trajectories.items():
        if declared.get(relative) != digest:
            raise ValueError(f"trajectory hash does not match declared run artifact: {relative}")


def _validate_snapshotted_lifecycle_state(package_dir: Path, run_dir: Path) -> None:
    state = EvidenceLifecycleRunState.model_validate(_read_json(run_dir / "state.json"))
    spec = load_evidence_lifecycle_spec(package_dir)
    validate_evidence_request_run_state(state, spec)
    if state.schema_version == "7":
        resolver = lifecycle_operation_resolver(package_dir, run_dir)
        if resolver is None:
            raise ValueError("operation lifecycle snapshot has no task operation resolver")
        source = resolve_lifecycle_operation_current_source(state, resolver)
        validate_lifecycle_operation_resolver_replay(run_dir, state, spec, resolver)
        validate_lifecycle_operation_snapshot(
            run_dir,
            state,
            spec,
            expected_current_source=LifecycleOperationCurrentSource(
                revision_id=source.revision_id,
                physical_source_state_sha256=source.physical_source_state_sha256,
                visible_source_state_sha256=source.visible_source_state_sha256,
                source_state=source.source_state,
            ),
        )
    if state.branch is not None:
        raise ValueError("branched lifecycle snapshots are not supported by ablation finalization")
    for checkpoint in state.checkpoint_runs:
        checkpoint_spec = next(item for item in spec.checkpoints if item.checkpoint_id == checkpoint.checkpoint_id)
        expected_catalog = evidence_request_catalog_payload(checkpoint_spec, checkpoint)
        catalog_path = run_dir / "workspace" / "checkpoints" / checkpoint.checkpoint_id / "evidence-requests.json"
        released = expected_catalog is not None and checkpoint.status.value != "pending"
        if not released and catalog_path.exists():
            raise ValueError("snapshot contains an unreleased or undeclared evidence request catalogue")
        if released and (not catalog_path.is_file() or _read_json(catalog_path) != expected_catalog):
            raise ValueError("snapshotted evidence request catalogue does not match lifecycle state")
        for action in checkpoint.evidence_request_actions:
            transaction = run_dir / "evidence_requests" / action.action_id
            if EvidenceRequestActionRecord.model_validate(_read_json(transaction / "action.json")) != action:
                raise ValueError("snapshotted evidence request action does not match lifecycle state")
            if _read_json(transaction / "committed.json") != {"action_id": action.action_id, "status": "committed"}:
                raise ValueError("snapshotted evidence request transaction is not committed")
            for artifact in action.released_artifacts:
                canonical = run_dir / artifact.path
                workspace = run_dir / "workspace" / artifact.workspace_path
                if (
                    not canonical.is_file()
                    or _sha256(canonical) != artifact.sha256
                    or not workspace.is_file()
                    or _sha256(workspace) != artifact.sha256
                ):
                    raise ValueError("snapshotted requested evidence artifact hash mismatch")
        if checkpoint.status.value == "submitted":
            submission = run_dir / "episodes" / checkpoint.checkpoint_id / "submission.json"
            if (
                checkpoint.submission_sha256 is None
                or not submission.is_file()
                or _sha256(submission) != checkpoint.submission_sha256
            ):
                raise ValueError(f"snapshotted checkpoint submission hash mismatch: {checkpoint.checkpoint_id}")
    if any(checkpoint.conditional_evidence is not None for checkpoint in spec.checkpoints):
        _validate_evidence_request_artifact_inventory(run_dir, state, spec)


def _validate_evidence_request_artifact_inventory(
    run_dir: Path,
    state: EvidenceLifecycleRunState,
    spec: EvidenceLifecycleSpec,
) -> None:
    expected = expected_evidence_request_run_artifact_paths(state, spec)
    actual = {
        path.relative_to(run_dir).as_posix()
        for path in sorted(run_dir.rglob("*"))
        if path.is_file() and is_evidence_request_run_artifact_path(path.relative_to(run_dir).as_posix())
    }
    if actual != expected:
        raise ValueError(
            "snapshotted evidence request artifact inventory does not match lifecycle state: "
            f"missing={sorted(expected - actual)}; unexpected={sorted(actual - expected)}"
        )


def _validate_metrics_against_run(
    run_dir: Path,
    state: dict[str, Any],
    experiment: dict[str, Any],
    metrics: dict[str, Any],
    verification: dict[str, Any],
) -> None:
    checkpoint_runs = state.get("checkpoint_runs")
    if not isinstance(checkpoint_runs, list):
        raise ValueError("lifecycle state checkpoint_runs are malformed")
    attempts = [
        attempt
        for checkpoint in checkpoint_runs
        if isinstance(checkpoint, dict)
        for attempt in checkpoint.get("attempts", [])
        if isinstance(attempt, dict)
    ]
    request_actions = [
        action
        for checkpoint in checkpoint_runs
        if isinstance(checkpoint, dict)
        for action in checkpoint.get("evidence_request_actions", [])
        if isinstance(action, dict)
    ]
    operation_actions = [
        action
        for checkpoint in checkpoint_runs
        if isinstance(checkpoint, dict)
        for action in checkpoint.get("operation_actions", [])
        if isinstance(action, dict)
    ]
    expected = {
        "checkpoint_count": sum(
            isinstance(checkpoint, dict) and checkpoint.get("status") == "submitted" for checkpoint in checkpoint_runs
        ),
        "retries": sum(
            max(0, len(checkpoint.get("attempts", [])) - 1)
            for checkpoint in checkpoint_runs
            if isinstance(checkpoint, dict)
        ),
        "failures": sum(attempt.get("status") == "failed" for attempt in attempts),
    }
    if state.get("schema_version") == "6":
        expected.update(
            {
                "evidence_request_calls": len(request_actions),
                "accepted_evidence_requests": sum(action.get("outcome") == "released" for action in request_actions),
                "already_released_evidence_requests": sum(
                    action.get("outcome") == "already_released" for action in request_actions
                ),
                "rejected_evidence_requests": sum(action.get("outcome") == "rejected" for action in request_actions),
                "evidence_request_budget_consumed": sum(
                    _non_negative_int(
                        action.get("budget_consumed", 0),
                        "historical lifecycle evidence request budget_consumed",
                    )
                    for action in request_actions
                ),
                "evidence_request_artifacts_released": sum(
                    len(action.get("released_artifacts", []))
                    for action in request_actions
                    if action.get("outcome") == "released"
                ),
            }
        )
    if state.get("schema_version") == "7":
        if metrics.get("schema_version") != "3":
            raise ValueError("operation lifecycle metrics require schema version 3")
        expected.update(
            {
                "operation_calls": len(operation_actions),
                "completed_operations": sum(action.get("outcome") == "completed" for action in operation_actions),
                "already_current_operations": sum(
                    action.get("outcome") == "already_current" for action in operation_actions
                ),
                "rejected_operations": sum(action.get("outcome") == "rejected" for action in operation_actions),
                "operation_budget_consumed": sum(
                    _non_negative_int(
                        action.get("budget_consumed", 0),
                        "historical lifecycle operation budget_consumed",
                    )
                    for action in operation_actions
                ),
                "operation_artifacts_produced": sum(
                    len(action.get("artifacts", []))
                    for action in operation_actions
                    if action.get("outcome") == "completed"
                ),
            }
        )
    for field, value in expected.items():
        if metrics.get(field) != value:
            raise ValueError(f"lifecycle {field} does not match run state")
    interaction = experiment.get("interaction")
    if not isinstance(interaction, dict) or not isinstance(interaction.get("trajectory_hashes"), dict):
        raise ValueError("lifecycle invocation interaction is malformed")
    if state.get("schema_version") == "7":
        protocol = interaction.get("lifecycle_operation_protocol")
        tool_schema = interaction.get("tool_schema")
        if not isinstance(protocol, dict) or not isinstance(tool_schema, list):
            raise ValueError("lifecycle invocation operation protocol is missing")
        validate_captured_lifecycle_operation_interaction(protocol, tool_schema)
    trajectory_hashes = cast(dict[str, str], interaction["trajectory_hashes"])
    trajectories = [read_trajectory(run_dir / relative) for relative in sorted(trajectory_hashes)]
    entries = [entry for trajectory in trajectories for entry in trajectory]
    tool_calls = [entry for entry in entries if entry.role == "tool_call"]
    trajectory_metrics = {
        "requests": sum(len({entry.step for entry in trajectory if entry.step > 0}) for trajectory in trajectories),
        "tool_calls": len(tool_calls),
        "reads": sum(entry.tool_name == "read_workspace_file" for entry in tool_calls),
        "revisits": sum(entry.tool_name == "revisit_checkpoint" for entry in tool_calls),
    }
    for field, value in trajectory_metrics.items():
        if metrics.get(field) != value:
            raise ValueError(f"lifecycle {field} does not match trajectories")
    if metrics.get("semantic_transition") != verification.get("semantic_metrics"):
        raise ValueError("lifecycle semantic metrics do not match verification")
    execution = experiment.get("execution")
    if not isinstance(execution, dict):
        raise ValueError("lifecycle execution timing does not match metrics")
    raw_checkpoint_seconds = execution.get("checkpoint_seconds")
    if not isinstance(raw_checkpoint_seconds, dict):
        raise ValueError("lifecycle execution timing does not match metrics")
    checkpoint_seconds = {
        str(checkpoint_id): _non_negative_number(seconds, "historical lifecycle checkpoint timing")
        for checkpoint_id, seconds in raw_checkpoint_seconds.items()
    }
    whole_run_seconds = execution.get("whole_run_seconds")
    normalized_whole_run_seconds = (
        None
        if whole_run_seconds is None
        else _non_negative_number(whole_run_seconds, "historical lifecycle whole-run timing")
    )
    if checkpoint_seconds != metrics.get("checkpoint_seconds") or normalized_whole_run_seconds != metrics.get(
        "whole_run_seconds"
    ):
        raise ValueError("lifecycle execution timing does not match metrics")


def _non_negative_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _non_negative_number(value: object, label: str) -> int | float:
    if type(value) not in {int, float}:
        raise ValueError(f"{label} must be a finite non-negative number")
    number = cast(int | float, value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{label} must be a finite non-negative number")
    return number


def _lifecycle_instruction(package_dir: Path) -> str:
    parts = [path.read_text(encoding="utf-8").strip() for path in sorted((package_dir / "instructions").glob("*.md"))]
    instruction = "\n\n".join(part for part in parts if part)
    if not instruction:
        raise ValueError("lifecycle package instructions are empty")
    return instruction


def _validate_artifact_hash(path: Path, expected: object, label: str) -> None:
    if not isinstance(expected, str) or _sha256(path) != expected:
        raise ValueError(f"{label} hash does not match manifest")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _media_type(path: Path) -> str:
    return {
        ".json": "application/json",
        ".jsonl": "application/x-ndjson",
        ".md": "text/markdown",
        ".txt": "text/plain",
    }.get(path.suffix.lower(), "application/octet-stream")


def _artifact_media_type(path: Path) -> str:
    if path.suffix == ".json":
        return "application/json"
    if path.suffix == ".jsonl":
        return "application/x-ndjson"
    if path.suffix in {".md", ".txt"}:
        return "text/plain"
    return "application/octet-stream"
