# ABOUTME: Parses lifecycle session records from canonical on-disk adapter results and attempt state.
# ABOUTME: Shares session lineage, identity, status, and artifact validation across record finalizers.

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from aec_bench.contracts.trial_record import ArtifactReference, LifecycleSessionRecord
from aec_bench.meta_harness.evidence_lifecycle_episode import LifecycleEpisodeRequest


def parse_lifecycle_session_records(
    *,
    run_dir: Path,
    artifact_references: Sequence[ArtifactReference],
    state: Mapping[str, Any],
    declared_run_artifacts: Mapping[str, str],
    requested_model: str,
    requested_adapter: str,
    execution_mode: Literal["persistent_context", "fresh_context"],
    memory_visibility_policy: Literal[
        "persistent_context",
        "artifact_memory",
        "raw_evidence_only",
        "current_release_only",
    ],
    max_turns_per_session: int,
    execution_status: Literal["completed", "failed", "partial"],
    verification: Mapping[str, Any],
) -> list[LifecycleSessionRecord]:
    """Derive sessions from durable results and reconcile them with host attempt authority."""
    expected_session_mode = "persistent" if execution_mode == "persistent_context" else "fresh"
    result_paths = sorted(
        Path(relative) for relative in declared_run_artifacts if Path(relative).name == "agent_result.json"
    )
    payloads: dict[str, tuple[Path, dict[str, Any]]] = {}
    for relative in result_paths:
        payload = _read_json(Path(run_dir) / relative)
        session_id = str(payload.get("session_id") or "")
        if not session_id:
            raise ValueError(f"lifecycle session is missing session_id: {relative}")
        if session_id in payloads:
            raise ValueError(f"lifecycle run contains duplicate session_id: {session_id}")
        payloads[session_id] = (relative, payload)

    ordered_session_ids: list[str] = []
    expected_checkpoints: dict[str, list[str]] = {}
    expected_attempt_statuses: dict[str, list[str]] = {}
    checkpoint_runs = state.get("checkpoint_runs")
    if not isinstance(checkpoint_runs, list):
        raise ValueError("lifecycle state checkpoint_runs are malformed")
    for checkpoint in checkpoint_runs:
        if not isinstance(checkpoint, dict):
            raise ValueError("lifecycle state checkpoint record is malformed")
        checkpoint_id = str(checkpoint.get("checkpoint_id") or "")
        attempts = checkpoint.get("attempts")
        if not isinstance(attempts, list):
            raise ValueError(f"lifecycle checkpoint attempts are malformed: {checkpoint_id}")
        if any(not isinstance(attempt, dict) for attempt in attempts):
            raise ValueError(f"lifecycle checkpoint attempt is malformed: {checkpoint_id}")
        checkpoint_status = str(checkpoint.get("status") or "")
        if checkpoint_status == "submitted":
            if not attempts:
                raise ValueError(f"submitted checkpoint has no adapter attempt owner: {checkpoint_id}")
            submitted_attempts = [attempt for attempt in attempts if attempt.get("status") == "submitted"]
            if len(submitted_attempts) != 1 or attempts[-1] != submitted_attempts[0]:
                raise ValueError(f"submitted checkpoint has ambiguous adapter attempt ownership: {checkpoint_id}")
        elif any(attempt.get("status") == "submitted" for attempt in attempts):
            raise ValueError(f"unsubmitted checkpoint contains submitted adapter attempt: {checkpoint_id}")
        for attempt in attempts:
            session_id = str(attempt.get("session_id") or "")
            if not session_id:
                raise ValueError(f"lifecycle checkpoint attempt has no session owner: {checkpoint_id}")
            if attempt.get("execution_mode") != execution_mode:
                raise ValueError(f"lifecycle checkpoint attempt execution mode mismatch: {checkpoint_id}")
            request_relative = Path("episodes") / checkpoint_id / session_id / "episode_request.json"
            request_hash = attempt.get("episode_request_sha256")
            declared_request_hash = declared_run_artifacts.get(request_relative.as_posix())
            if request_hash is not None:
                if execution_mode != "fresh_context":
                    raise ValueError(f"persistent lifecycle attempt cannot own a fresh request: {session_id}")
                if request_hash != declared_request_hash:
                    raise ValueError(f"lifecycle episode request hash does not match attempt state: {session_id}")
                request = LifecycleEpisodeRequest.model_validate(_read_json(Path(run_dir) / request_relative))
                expected_request_identity = {
                    "episode_id": f"{state.get('lifecycle_id')}.{attempt.get('attempt_id')}",
                    "lifecycle_id": state.get("lifecycle_id"),
                    "world_id": state.get("world_id"),
                    "lifecycle_spec_sha256": state.get("lifecycle_spec_sha256"),
                    "package_sha256": state.get("package_sha256"),
                    "checkpoint_id": checkpoint_id,
                    "checkpoint_ids": (checkpoint_id,),
                    "attempt_id": attempt.get("attempt_id"),
                    "session_id": session_id,
                    "execution_mode": execution_mode,
                    "memory_visibility_policy": memory_visibility_policy,
                    "requested_adapter": requested_adapter,
                    "requested_model": requested_model,
                    "max_turns_per_session": max_turns_per_session,
                }
                actual_request_identity = {key: getattr(request, key) for key in expected_request_identity}
                if actual_request_identity != expected_request_identity:
                    raise ValueError(f"lifecycle episode request identity mismatch: {session_id}")
            elif declared_request_hash is not None:
                raise ValueError(f"lifecycle episode request lacks attempt-state hash: {session_id}")
            if session_id not in ordered_session_ids:
                ordered_session_ids.append(session_id)
            expected_checkpoints.setdefault(session_id, []).append(checkpoint_id)
            expected_attempt_statuses.setdefault(session_id, []).append(str(attempt.get("status") or ""))
    if set(payloads) != set(ordered_session_ids):
        raise ValueError("lifecycle session artifacts do not match checkpoint attempt lineage")
    if execution_mode == "fresh_context" and any(
        len(checkpoint_ids) != 1 for checkpoint_ids in expected_checkpoints.values()
    ):
        raise ValueError("fresh lifecycle session must own exactly one checkpoint attempt")

    sessions: list[LifecycleSessionRecord] = []
    for session_id in ordered_session_ids:
        relative, payload = payloads[session_id]
        checkpoint_ids = payload.get("checkpoint_ids", [])
        if not isinstance(checkpoint_ids, list):
            raise ValueError(f"lifecycle session checkpoint_ids are malformed: {session_id}")
        expected_ids = list(dict.fromkeys(expected_checkpoints[session_id]))
        if checkpoint_ids != expected_ids:
            raise ValueError(f"lifecycle session checkpoint coverage does not match state: {session_id}")
        payload_model = str(payload.get("model") or "")
        requested_session_adapter = str(payload.get("adapter") or "")
        resolved_adapter = str(payload.get("adapter_name") or "")
        if payload_model != requested_model:
            raise ValueError(f"lifecycle session requested model does not match invocation: {session_id}")
        if payload.get("session_mode") != expected_session_mode:
            raise ValueError(f"lifecycle session execution mode does not match invocation: {session_id}")
        if payload.get("memory_visibility_policy") != memory_visibility_policy:
            raise ValueError(f"lifecycle session visibility policy does not match invocation: {session_id}")
        parts = relative.parts
        if expected_session_mode == "persistent" and parts != (
            "sessions",
            session_id,
            "agent_result.json",
        ):
            raise ValueError(f"persistent lifecycle session artifact path is invalid: {session_id}")
        if expected_session_mode == "fresh" and (
            parts
            != (
                "episodes",
                expected_ids[0],
                session_id,
                "agent_result.json",
            )
        ):
            raise ValueError(f"fresh lifecycle session artifact path is invalid: {session_id}")
        if requested_session_adapter != requested_adapter:
            raise ValueError(f"lifecycle session requested adapter does not match invocation: {session_id}")
        if not resolved_adapter:
            raise ValueError(f"lifecycle session resolved adapter is missing: {session_id}")
        if payload.get("max_turns") != max_turns_per_session:
            raise ValueError(f"lifecycle session max_turns does not match invocation: {session_id}")
        resolved_model = str(payload.get("resolved_model") or payload.get("model") or "")
        if not resolved_model:
            raise ValueError(f"lifecycle session resolved model is missing: {session_id}")
        session_status = _session_status(str(payload.get("status") or "failed"))
        attempts_submitted = all(status == "submitted" for status in expected_attempt_statuses[session_id])
        identity_mismatch = (
            resolved_adapter != requested_session_adapter
            and session_status == "failed"
            and payload.get("failure_kind") == "adapter_identity_mismatch"
        )
        unresolved_interruption = (
            resolved_adapter == "unresolved"
            and session_status == "failed"
            and payload.get("failure_kind") in {"interrupted", "interrupted_after_completion"}
        )
        failure_kind = payload.get("failure_kind")
        terminal_failure = (
            attempts_submitted and session_status == "failed" and isinstance(failure_kind, str) and bool(failure_kind)
        )
        if resolved_adapter != requested_session_adapter and not (identity_mismatch or unresolved_interruption):
            raise ValueError(f"lifecycle session resolved adapter does not match invocation: {session_id}")
        if attempts_submitted != (session_status == "completed") and not (
            attempts_submitted and (identity_mismatch or unresolved_interruption or terminal_failure)
        ):
            raise ValueError(f"lifecycle session status does not match checkpoint attempts: {session_id}")
        session_artifacts = [
            artifact for artifact in artifact_references if f"/run/{relative.parent.as_posix()}/" in f"/{artifact.path}"
        ]
        configuration = payload.get("configuration_record")
        if not isinstance(configuration, dict):
            raise ValueError(f"lifecycle session configuration is malformed: {session_id}")
        sessions.append(
            LifecycleSessionRecord(
                session_id=session_id,
                checkpoint_ids=expected_ids,
                requested_adapter=requested_session_adapter,
                adapter=resolved_adapter,
                resolved_model=resolved_model,
                execution_mode=execution_mode,
                memory_visibility_policy=memory_visibility_policy,
                configuration=cast(dict[str, Any], configuration),
                status=session_status,
                input_tokens=int(payload.get("input_tokens", 0)),
                output_tokens=int(payload.get("output_tokens", 0)),
                cache_read_tokens=int(payload.get("cache_read_tokens", 0)),
                cache_write_tokens=int(payload.get("cache_write_tokens", 0)),
                failure_kind=(str(payload["failure_kind"]) if payload.get("failure_kind") is not None else None),
                provider_error=(str(payload["provider_error"]) if payload.get("provider_error") is not None else None),
                artifacts=session_artifacts,
            )
        )
    if any(session.status != "completed" for session in sessions) and (
        execution_status != "failed"
        or verification.get("overall") != "incomplete"
        or float(verification.get("reward", 0.0)) != 0.0
    ):
        raise ValueError("failed lifecycle sessions must remain an unscored failed execution")
    if execution_status == "completed" and (
        state.get("status") != "complete" or any(session.status != "completed" for session in sessions)
    ):
        raise ValueError("completed lifecycle execution contradicts state or session status")
    return sessions


def _session_status(status: str) -> Literal["completed", "failed", "partial"]:
    if status in {"completed", "ok"}:
        return "completed"
    if status == "partial":
        return "partial"
    return "failed"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)
