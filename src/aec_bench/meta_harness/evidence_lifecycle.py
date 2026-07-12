# ABOUTME: Executes staged evidence lifecycles inside one existing meta-harness task-run boundary.
# ABOUTME: Controls release visibility, checkpoint persistence, tamper checks, and parent-run evidence.

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from aec_bench.meta_harness.evidence_lifecycle_state import (
    CheckpointAttemptRecord,
    CheckpointAttemptStatus,
    CheckpointRevisitRecord,
    CheckpointRunRecord,
    CheckpointRunStatus,
    EvidenceLifecycleRunState,
    LifecycleBranchRecord,
    LifecycleRunStatus,
    LifecycleTransitionKind,
    LifecycleTransitionRecord,
    LifecycleVerificationResult,
)
from aec_bench.meta_harness.ledger import append_ledger_entry, read_ledger
from aec_bench.task_world_templates.contracts import EvidenceCheckpointSpec, EvidenceLifecycleSpec

EpisodeResolver = Callable[[dict[str, Any]], dict[str, Any]]
LifecycleVerifier = Callable[[Path, Path], dict[str, Any] | LifecycleVerificationResult]


class EvidenceLifecycleError(RuntimeError):
    """Raised when a lifecycle package or checkpoint transition is invalid."""


def load_evidence_lifecycle_spec(package_dir: Path) -> EvidenceLifecycleSpec:
    """Load and validate one lifecycle package contract."""
    path = Path(package_dir) / "lifecycle.json"
    if not path.is_file():
        raise EvidenceLifecycleError(f"lifecycle contract not found: {path}")
    payload = _read_json(path)
    return EvidenceLifecycleSpec.model_validate(payload)


def prepare_evidence_checkpoint(package_dir: Path, run_dir: Path) -> dict[str, Any]:
    """Release exactly the next checkpoint into the persistent agent workspace."""
    package = Path(package_dir)
    run = Path(run_dir)
    spec = load_evidence_lifecycle_spec(package)
    if _state_path(run).exists():
        state = _load_state(package, run, spec)
    else:
        _preflight_checkpoint(package, spec.checkpoints[0])
        state = _initialize_state(package, run, spec)

    if state.status == LifecycleRunStatus.COMPLETE:
        return _result_context(run, state)
    if state.active_checkpoint_id:
        checkpoint = _checkpoint(spec, state.active_checkpoint_id)
        return _checkpoint_context(run, checkpoint, state)

    _assert_prior_submissions_unchanged(run, state)
    checkpoint_index = sum(checkpoint.status == CheckpointRunStatus.SUBMITTED for checkpoint in state.checkpoint_runs)
    checkpoint = spec.checkpoints[checkpoint_index]
    completed_ids = {
        item.checkpoint_id for item in state.checkpoint_runs if item.status == CheckpointRunStatus.SUBMITTED
    }
    if not set(checkpoint.depends_on).issubset(completed_ids):
        raise EvidenceLifecycleError(f"checkpoint dependencies are incomplete: {checkpoint.checkpoint_id}")

    instruction = _preflight_checkpoint(package, checkpoint)
    released_files = _materialize_checkpoint_release(package, run, checkpoint, instruction)

    checkpoint_run = state.checkpoint(checkpoint.checkpoint_id)
    checkpoint_run.status = CheckpointRunStatus.ACTIVE
    checkpoint_run.released_files = released_files
    previous_checkpoint_id = next(
        (
            item.checkpoint_id
            for item in reversed(state.checkpoint_runs)
            if item.status == CheckpointRunStatus.SUBMITTED
        ),
        None,
    )
    _append_transition(
        state,
        kind=LifecycleTransitionKind.RELEASE,
        from_checkpoint_id=previous_checkpoint_id,
        to_checkpoint_id=checkpoint.checkpoint_id,
        reason="Evidence released for active review.",
    )
    state.status = LifecycleRunStatus.AWAITING_CHECKPOINT_SUBMISSION
    state.active_checkpoint_id = checkpoint.checkpoint_id
    _write_state(run, state)
    _sync_transition_ledger(run, state)
    append_ledger_entry(
        _ledger_path(run),
        process_id=spec.lifecycle_id,
        stage="evidence_release",
        status="awaiting_checkpoint_submission",
        summary={"checkpoint_id": checkpoint.checkpoint_id, "released_files": released_files},
        artifact_refs=[str(_workspace(run) / "inbox" / checkpoint.checkpoint_id / path) for path in released_files],
    )
    return _checkpoint_context(run, checkpoint, state)


def submit_evidence_checkpoint(
    package_dir: Path,
    run_dir: Path,
    *,
    episode_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Accept one structurally valid submission and preserve it outside the workspace."""
    package = Path(package_dir)
    run = Path(run_dir)
    spec = load_evidence_lifecycle_spec(package)
    state = _load_state(package, run, spec)
    checkpoint_id = state.active_checkpoint_id
    if not checkpoint_id:
        raise EvidenceLifecycleError("no checkpoint is awaiting submission")

    _assert_prior_submissions_unchanged(run, state)
    checkpoint = _checkpoint(spec, checkpoint_id)
    submission_path = _workspace(run) / checkpoint.submission_path
    if not submission_path.is_file():
        raise EvidenceLifecycleError(f"checkpoint submission not found: {submission_path}")
    submission = _read_json(submission_path)
    if submission.get("checkpoint_id") != checkpoint_id:
        raise EvidenceLifecycleError(
            f"checkpoint submission id must be {checkpoint_id!r}, got {submission.get('checkpoint_id')!r}"
        )
    missing_fields = sorted(field for field in checkpoint.required_submission_fields if field not in submission)
    if missing_fields:
        raise EvidenceLifecycleError(f"checkpoint submission missing required fields: {', '.join(missing_fields)}")

    episode_dir = run / "episodes" / checkpoint_id
    episode_dir.mkdir(parents=True, exist_ok=True)
    archive_path = episode_dir / "submission.json"
    archive_temp = archive_path.with_suffix(".json.tmp")
    shutil.copy2(submission_path, archive_temp)
    archive_temp.replace(archive_path)
    submission_sha256 = _sha256(archive_path)
    _write_json(episode_dir / "result.json", copy.deepcopy(episode_result or {}))

    checkpoint_run = state.checkpoint(checkpoint_id)
    checkpoint_run.status = CheckpointRunStatus.SUBMITTED
    checkpoint_run.submission_path = checkpoint.submission_path
    checkpoint_run.submission_sha256 = submission_sha256
    if checkpoint_run.active_attempt is not None:
        checkpoint_run.active_attempt.status = CheckpointAttemptStatus.SUBMITTED
    _append_transition(
        state,
        kind=LifecycleTransitionKind.SUBMIT,
        from_checkpoint_id=checkpoint_id,
        to_checkpoint_id=None,
        reason="Checkpoint submission archived.",
    )
    state.active_checkpoint_id = None
    state.status = (
        LifecycleRunStatus.COMPLETE
        if all(item.status == CheckpointRunStatus.SUBMITTED for item in state.checkpoint_runs)
        else LifecycleRunStatus.AWAITING_EVIDENCE_RELEASE
    )
    _write_state(run, state)
    _sync_transition_ledger(run, state)
    append_ledger_entry(
        _ledger_path(run),
        process_id=spec.lifecycle_id,
        stage="checkpoint_submission",
        status=state.status.value,
        summary={
            "checkpoint_id": checkpoint_id,
            "submission_sha256": submission_sha256,
        },
        artifact_refs=[str(archive_path)],
    )
    return _result_context(run, state)


def branch_evidence_lifecycle(
    package_dir: Path,
    parent_run_dir: Path,
    branch_run_dir: Path,
    *,
    checkpoint_id: str,
    branch_id: str,
    reason: str,
) -> dict[str, Any]:
    """Create an isolated derived run that reopens one submitted checkpoint."""
    package = Path(package_dir)
    parent_run = Path(parent_run_dir)
    branch_run = Path(branch_run_dir)
    spec = load_evidence_lifecycle_spec(package)
    parent_state = _load_state(package, parent_run, spec)
    _assert_prior_submissions_unchanged(parent_run, parent_state)
    try:
        branch_index = next(
            index for index, checkpoint in enumerate(spec.checkpoints) if checkpoint.checkpoint_id == checkpoint_id
        )
    except StopIteration as exc:
        raise EvidenceLifecycleError(f"unknown checkpoint: {checkpoint_id}") from exc
    parent_checkpoint = parent_state.checkpoint(checkpoint_id)
    if parent_checkpoint.status != CheckpointRunStatus.SUBMITTED:
        raise EvidenceLifecycleError(f"checkpoint is not available for branching: {checkpoint_id}")
    if branch_run.exists():
        raise EvidenceLifecycleError(f"branch run directory already exists: {branch_run}")
    if parent_checkpoint.submission_sha256 is None:
        raise EvidenceLifecycleError(f"submitted checkpoint is missing its sha256: {checkpoint_id}")

    checkpoint_runs: list[CheckpointRunRecord] = []
    for index, checkpoint in enumerate(spec.checkpoints):
        if index < branch_index:
            inherited = parent_state.checkpoint(checkpoint.checkpoint_id)
            if inherited.status != CheckpointRunStatus.SUBMITTED:
                raise EvidenceLifecycleError(f"parent checkpoint dependency is incomplete: {checkpoint.checkpoint_id}")
            checkpoint_runs.append(
                CheckpointRunRecord(
                    checkpoint_id=checkpoint.checkpoint_id,
                    status=CheckpointRunStatus.SUBMITTED,
                    released_files=list(inherited.released_files),
                    submission_path=inherited.submission_path,
                    submission_sha256=inherited.submission_sha256,
                    inherited_from_parent=True,
                )
            )
        elif index == branch_index:
            checkpoint_runs.append(
                CheckpointRunRecord(
                    checkpoint_id=checkpoint.checkpoint_id,
                    status=CheckpointRunStatus.ACTIVE,
                    released_files=list(parent_checkpoint.released_files),
                )
            )
        else:
            checkpoint_runs.append(CheckpointRunRecord(checkpoint_id=checkpoint.checkpoint_id))

    state = EvidenceLifecycleRunState(
        lifecycle_id=spec.lifecycle_id,
        world_id=spec.world_id,
        lifecycle_spec_sha256=parent_state.lifecycle_spec_sha256,
        package_sha256=parent_state.package_sha256,
        status=LifecycleRunStatus.AWAITING_CHECKPOINT_SUBMISSION,
        active_checkpoint_id=checkpoint_id,
        checkpoint_runs=checkpoint_runs,
        branch=LifecycleBranchRecord(
            branch_id=branch_id,
            parent_run_dir=str(parent_run),
            branched_from_checkpoint_id=checkpoint_id,
            parent_submission_sha256=parent_checkpoint.submission_sha256,
            reason=reason,
        ),
    )
    _append_transition(
        state,
        kind=LifecycleTransitionKind.BRANCH,
        from_checkpoint_id=checkpoint_id,
        to_checkpoint_id=checkpoint_id,
        reason=reason,
    )

    branch_run.parent.mkdir(parents=True, exist_ok=True)
    staging_run = Path(tempfile.mkdtemp(prefix=f".{branch_run.name}.tmp-", dir=branch_run.parent))
    try:
        workspace = _workspace(staging_run)
        workspace.mkdir(parents=True)
        for index, checkpoint in enumerate(spec.checkpoints[: branch_index + 1]):
            _copy_release(
                _workspace(parent_run) / "inbox" / checkpoint.checkpoint_id,
                workspace / "inbox" / checkpoint.checkpoint_id,
            )
            _copy_file_atomic(
                _workspace(parent_run) / "checkpoints" / checkpoint.checkpoint_id / "instruction.md",
                workspace / "checkpoints" / checkpoint.checkpoint_id / "instruction.md",
            )
            if index < branch_index:
                _inherit_submission(parent_run, staging_run, checkpoint)

        parent_archive = parent_run / "episodes" / checkpoint_id / "submission.json"
        staged_origin = workspace / "branch_origin" / f"{checkpoint_id}.json"
        staged_submission = workspace / _checkpoint(spec, checkpoint_id).submission_path
        _copy_file_atomic(parent_archive, staged_origin)
        _copy_file_atomic(parent_archive, staged_submission)
        _write_text_atomic(
            workspace / "instruction.md",
            (workspace / "checkpoints" / checkpoint_id / "instruction.md").read_text(encoding="utf-8"),
        )
        _write_state(staging_run, state)
        _sync_transition_ledger(staging_run, state)
        final_origin = _workspace(branch_run) / "branch_origin" / f"{checkpoint_id}.json"
        final_submission = _workspace(branch_run) / _checkpoint(spec, checkpoint_id).submission_path
        append_ledger_entry(
            _ledger_path(staging_run),
            process_id=spec.lifecycle_id,
            stage="lifecycle_branch",
            status="awaiting_checkpoint_submission",
            summary=state.branch.model_dump(mode="json") if state.branch is not None else {},
            artifact_refs=[str(final_origin), str(final_submission)],
        )
        staging_run.replace(branch_run)
    except Exception:
        shutil.rmtree(staging_run, ignore_errors=True)
        raise
    return _checkpoint_context(branch_run, _checkpoint(spec, checkpoint_id), state)


def open_checkpoint_attempt(
    package_dir: Path,
    run_dir: Path,
    *,
    session_id: str,
    execution_mode: str,
) -> dict[str, Any]:
    """Open a checkpoint attempt, interrupting an abandoned active attempt."""
    package = Path(package_dir)
    run = Path(run_dir)
    spec = load_evidence_lifecycle_spec(package)
    state = _load_state(package, run, spec)
    checkpoint_id = state.active_checkpoint_id
    if checkpoint_id is None:
        raise EvidenceLifecycleError("no checkpoint is active")
    checkpoint_run = state.checkpoint(checkpoint_id)
    active_attempt = checkpoint_run.active_attempt
    if active_attempt is not None and active_attempt.session_id == session_id:
        return _attempt_context(active_attempt)
    if active_attempt is not None:
        active_attempt.status = CheckpointAttemptStatus.INTERRUPTED
    previous = checkpoint_run.last_attempt

    sequence = len(checkpoint_run.attempts) + 1
    attempt = CheckpointAttemptRecord(
        attempt_id=f"{checkpoint_id}.attempt-{sequence:03d}",
        session_id=session_id,
        sequence=sequence,
        execution_mode=execution_mode,
        status=CheckpointAttemptStatus.ACTIVE,
        resumed_from_attempt_id=previous.attempt_id if previous is not None else None,
    )
    checkpoint_run.attempts.append(attempt)
    _write_state(run, state)
    append_ledger_entry(
        _ledger_path(run),
        process_id=spec.lifecycle_id,
        stage="checkpoint_attempt",
        status="active",
        summary={
            "checkpoint_id": checkpoint_id,
            "attempt_id": attempt.attempt_id,
            "session_id": session_id,
            "resumed_from_attempt_id": attempt.resumed_from_attempt_id,
        },
        artifact_refs=[],
    )
    return _attempt_context(attempt)


def fail_checkpoint_attempt(
    package_dir: Path,
    run_dir: Path,
    *,
    session_id: str,
    failure_kind: str,
) -> dict[str, Any]:
    """Close the active checkpoint attempt after an execution failure."""
    package = Path(package_dir)
    run = Path(run_dir)
    spec = load_evidence_lifecycle_spec(package)
    state = _load_state(package, run, spec)
    checkpoint_id = state.active_checkpoint_id
    if checkpoint_id is None:
        raise EvidenceLifecycleError("no checkpoint is active")
    checkpoint_run = state.checkpoint(checkpoint_id)
    attempt = checkpoint_run.active_attempt
    if attempt is None:
        raise EvidenceLifecycleError("no checkpoint attempt is active")
    if attempt.session_id != session_id:
        raise EvidenceLifecycleError(
            f"active attempt belongs to {attempt.session_id}; cannot fail it from {session_id}"
        )

    attempt.status = CheckpointAttemptStatus.FAILED
    attempt.failure_kind = failure_kind
    _write_state(run, state)
    append_ledger_entry(
        _ledger_path(run),
        process_id=spec.lifecycle_id,
        stage="checkpoint_attempt",
        status="failed",
        summary={
            "checkpoint_id": checkpoint_id,
            "attempt_id": attempt.attempt_id,
            "session_id": session_id,
            "failure_kind": failure_kind,
        },
        artifact_refs=[],
    )
    return _attempt_context(attempt)


def revisit_evidence_checkpoint(
    package_dir: Path,
    run_dir: Path,
    *,
    checkpoint_id: str,
    reason: str,
) -> dict[str, Any]:
    """Return and log an immutable prior checkpoint without rewinding the run."""
    package = Path(package_dir)
    run = Path(run_dir)
    spec = load_evidence_lifecycle_spec(package)
    state = _load_state(package, run, spec)
    _assert_prior_submissions_unchanged(run, state)
    try:
        checkpoint_run = state.checkpoint(checkpoint_id)
    except KeyError as exc:
        raise EvidenceLifecycleError(f"unknown checkpoint: {checkpoint_id}") from exc
    if checkpoint_run.status != CheckpointRunStatus.SUBMITTED:
        raise EvidenceLifecycleError(f"checkpoint is not available for revisit: {checkpoint_id}")

    archive_path = run / "episodes" / checkpoint_id / "submission.json"
    instruction_path = _workspace(run) / "checkpoints" / checkpoint_id / "instruction.md"
    revisit = CheckpointRevisitRecord(
        revisit_id=f"revisit-{len(state.revisits) + 1:03d}",
        checkpoint_id=checkpoint_id,
        requested_from_checkpoint_id=state.active_checkpoint_id,
        reason=reason,
    )
    state.revisits.append(revisit)
    _append_transition(
        state,
        kind=LifecycleTransitionKind.REVISIT,
        from_checkpoint_id=revisit.requested_from_checkpoint_id,
        to_checkpoint_id=checkpoint_id,
        reason=reason,
    )
    _write_state(run, state)
    _sync_transition_ledger(run, state)
    append_ledger_entry(
        _ledger_path(run),
        process_id=spec.lifecycle_id,
        stage="checkpoint_revisit",
        status="recorded",
        summary=revisit.model_dump(mode="json"),
        artifact_refs=[str(archive_path), str(instruction_path)],
    )
    return {
        **revisit.model_dump(mode="json"),
        "instruction": instruction_path.read_text(encoding="utf-8"),
        "submission": _read_json(archive_path),
        "released_files": list(checkpoint_run.released_files),
    }


def run_evidence_lifecycle(
    package_dir: Path,
    run_dir: Path,
    *,
    episode_resolver: EpisodeResolver,
) -> dict[str, Any]:
    """Run every checkpoint with a fresh resolver call and one persistent workspace."""
    while True:
        context = prepare_evidence_checkpoint(package_dir, run_dir)
        if context["status"] == "complete":
            return context
        episode_result = episode_resolver(copy.deepcopy(context))
        result = submit_evidence_checkpoint(
            package_dir,
            run_dir,
            episode_result=episode_result,
        )
        if result["status"] == "complete":
            return result


def build_evidence_lifecycle_task_run_resolver(
    *,
    package_dir: Path,
    run_dir: Path,
    episode_resolver: EpisodeResolver,
    verifier: LifecycleVerifier,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Wrap a complete evidence lifecycle as one existing meta-harness task_run."""

    def resolve(runtime_result: dict[str, Any]) -> dict[str, Any]:
        lifecycle = run_evidence_lifecycle(
            package_dir,
            run_dir,
            episode_resolver=episode_resolver,
        )
        verification = validate_lifecycle_verification(verifier(Path(package_dir), Path(run_dir)))
        reward = float(verification["reward"])
        passed = bool(verification["passed"])
        process_id = runtime_result.get("process_id") or "process"
        spec = load_evidence_lifecycle_spec(Path(package_dir))
        return {
            "run_id": f"{process_id}.{spec.lifecycle_id}",
            "evidence": {
                "score": {"reward": reward, "passed": passed},
                "gates": copy.deepcopy(verification.get("gates", {})),
                "lifecycle": lifecycle,
                "verification": verification,
                "artifacts": {
                    "run_dir": str(Path(run_dir)),
                    "ledger": str(_ledger_path(Path(run_dir))),
                },
            },
        }

    return resolve


def read_evidence_lifecycle_state(package_dir: Path, run_dir: Path) -> dict[str, Any]:
    """Read current lifecycle state without releasing or accepting evidence."""
    package = Path(package_dir)
    run = Path(run_dir)
    spec = load_evidence_lifecycle_spec(package)
    state = _load_state(package, run, spec)
    _assert_prior_submissions_unchanged(run, state)
    return _result_context(run, state)


def load_validated_lifecycle_submissions(
    package_dir: Path,
    run_dir: Path,
    *,
    require_complete: bool = True,
) -> dict[str, dict[str, Any]]:
    """Load immutable checkpoint submissions after validating state and archive hashes."""
    package = Path(package_dir)
    run = Path(run_dir)
    spec = load_evidence_lifecycle_spec(package)
    state = _load_state(package, run, spec)
    _assert_prior_submissions_unchanged(run, state)
    if require_complete and state.status != LifecycleRunStatus.COMPLETE:
        raise EvidenceLifecycleError("lifecycle run is not complete")
    return {
        checkpoint.checkpoint_id: _read_json(run / "episodes" / checkpoint.checkpoint_id / "submission.json")
        for checkpoint in state.checkpoint_runs
        if checkpoint.status == CheckpointRunStatus.SUBMITTED
    }


def validate_lifecycle_verification(
    payload: dict[str, Any] | LifecycleVerificationResult,
) -> dict[str, Any]:
    """Validate the shared verifier-result boundary and return its JSON representation."""
    result = (
        payload
        if isinstance(payload, LifecycleVerificationResult)
        else LifecycleVerificationResult.model_validate(payload)
    )
    excluded = {"semantic_metrics"} if result.semantic_metrics is None else None
    return result.model_dump(mode="json", exclude=excluded)


def _initialize_state(
    package_dir: Path,
    run_dir: Path,
    spec: EvidenceLifecycleSpec,
) -> EvidenceLifecycleRunState:
    if _state_path(run_dir).exists():
        raise EvidenceLifecycleError(f"lifecycle state already exists: {_state_path(run_dir)}")
    _workspace(run_dir).mkdir(parents=True, exist_ok=True)
    state = EvidenceLifecycleRunState(
        lifecycle_id=spec.lifecycle_id,
        world_id=spec.world_id,
        lifecycle_spec_sha256=_spec_sha256(spec),
        package_sha256=_package_sha256(package_dir),
        checkpoint_runs=[CheckpointRunRecord(checkpoint_id=item.checkpoint_id) for item in spec.checkpoints],
    )
    _write_state(run_dir, state)
    return state


def _load_state(
    package_dir: Path,
    run_dir: Path,
    spec: EvidenceLifecycleSpec,
) -> EvidenceLifecycleRunState:
    path = _state_path(run_dir)
    if not path.is_file():
        raise EvidenceLifecycleError(f"lifecycle state not found: {path}")
    payload = _read_json(path)
    version = payload.get("schema_version")
    try:
        if version == "3":
            state = EvidenceLifecycleRunState.model_validate(payload)
            migrated = False
        elif version == "2":
            state = _migrate_v2_state(payload, package_dir, spec)
            migrated = True
        elif version in {None, "1"}:
            state = _migrate_legacy_state(payload, package_dir, spec)
            migrated = True
        else:
            raise EvidenceLifecycleError(f"unsupported lifecycle state schema version: {version}")
    except ValidationError as exc:
        raise EvidenceLifecycleError(f"invalid lifecycle state: {path}") from exc

    expected_ids = [checkpoint.checkpoint_id for checkpoint in spec.checkpoints]
    actual_ids = [checkpoint.checkpoint_id for checkpoint in state.checkpoint_runs]
    if state.lifecycle_id != spec.lifecycle_id or state.world_id != spec.world_id or actual_ids != expected_ids:
        raise EvidenceLifecycleError("run state does not match the lifecycle package")
    if state.lifecycle_spec_sha256 != _spec_sha256(spec):
        raise EvidenceLifecycleError("lifecycle contract does not match lifecycle run")
    if state.package_sha256 != _package_sha256(package_dir):
        raise EvidenceLifecycleError("package does not match lifecycle run")
    if migrated:
        _write_state(run_dir, state)
    _sync_transition_ledger(run_dir, state)
    return state


def _assert_prior_submissions_unchanged(run_dir: Path, state: EvidenceLifecycleRunState) -> None:
    if state.branch is not None:
        checkpoint_id = state.branch.branched_from_checkpoint_id
        branch_origin = _workspace(run_dir) / "branch_origin" / f"{checkpoint_id}.json"
        if not branch_origin.is_file() or _sha256(branch_origin) != state.branch.parent_submission_sha256:
            raise EvidenceLifecycleError(f"branch origin submission changed: {checkpoint_id}")
    for completed in state.checkpoint_runs:
        if completed.status != CheckpointRunStatus.SUBMITTED:
            continue
        if completed.submission_path is None or completed.submission_sha256 is None:
            raise EvidenceLifecycleError(
                f"submitted checkpoint is missing immutable metadata: {completed.checkpoint_id}"
            )
        archive_path = run_dir / "episodes" / completed.checkpoint_id / "submission.json"
        if not archive_path.is_file() or _sha256(archive_path) != completed.submission_sha256:
            checkpoint_id = completed.checkpoint_id
            raise EvidenceLifecycleError(f"archived checkpoint submission changed: {checkpoint_id}")
        workspace_path = _workspace(run_dir) / completed.submission_path
        if not workspace_path.is_file() or _sha256(workspace_path) != completed.submission_sha256:
            checkpoint_id = completed.checkpoint_id
            raise EvidenceLifecycleError(f"prior checkpoint submission changed: {checkpoint_id}")


def _preflight_checkpoint(package_dir: Path, checkpoint: EvidenceCheckpointSpec) -> str:
    release_source = package_dir / checkpoint.release_path
    instruction_source = package_dir / checkpoint.instruction_path
    if not release_source.is_dir() or release_source.is_symlink():
        raise EvidenceLifecycleError(f"checkpoint release not found: {release_source}")
    if not instruction_source.is_file() or instruction_source.is_symlink():
        raise EvidenceLifecycleError(f"checkpoint instruction not found: {instruction_source}")
    return instruction_source.read_text(encoding="utf-8")


def _materialize_checkpoint_release(
    package_dir: Path,
    run_dir: Path,
    checkpoint: EvidenceCheckpointSpec,
    instruction: str,
) -> list[str]:
    workspace = _workspace(run_dir)
    staging_root = workspace / ".staging" / checkpoint.checkpoint_id
    release_destination = workspace / "inbox" / checkpoint.checkpoint_id
    checkpoint_instruction = workspace / "checkpoints" / checkpoint.checkpoint_id / "instruction.md"
    if staging_root.exists():
        shutil.rmtree(staging_root)
    if release_destination.exists():
        shutil.rmtree(release_destination)
    staging_release = staging_root / "release"
    staging_instruction = staging_root / "instruction.md"
    try:
        released_files = _copy_release(package_dir / checkpoint.release_path, staging_release)
        _write_text_atomic(staging_instruction, instruction)
        release_destination.parent.mkdir(parents=True, exist_ok=True)
        staging_release.replace(release_destination)
        _copy_file_atomic(staging_instruction, checkpoint_instruction)
        _write_text_atomic(workspace / "instruction.md", instruction)
        return released_files
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)


def _copy_release(source: Path, destination: Path) -> list[str]:
    if not source.is_dir() or source.is_symlink():
        raise EvidenceLifecycleError(f"checkpoint release not found: {source}")
    destination.mkdir(parents=True, exist_ok=False)
    released: list[str] = []
    for source_path in sorted(source.rglob("*")):
        if source_path.is_symlink():
            raise EvidenceLifecycleError(f"checkpoint releases may not contain symlinks: {source_path}")
        relative = source_path.relative_to(source)
        destination_path = destination / relative
        if source_path.is_dir():
            destination_path.mkdir(parents=True, exist_ok=True)
            continue
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)
        released.append(relative.as_posix())
    return released


def _copy_checkpoint_instruction(
    package_dir: Path,
    workspace: Path,
    checkpoint: EvidenceCheckpointSpec,
) -> None:
    source = package_dir / checkpoint.instruction_path
    destination = workspace / "checkpoints" / checkpoint.checkpoint_id / "instruction.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _inherit_submission(
    parent_run: Path,
    branch_run: Path,
    checkpoint: EvidenceCheckpointSpec,
) -> None:
    source = parent_run / "episodes" / checkpoint.checkpoint_id / "submission.json"
    archive = branch_run / "episodes" / checkpoint.checkpoint_id / "submission.json"
    workspace_submission = _workspace(branch_run) / checkpoint.submission_path
    _copy_file_atomic(source, archive)
    _copy_file_atomic(source, workspace_submission)
    _write_json(
        branch_run / "episodes" / checkpoint.checkpoint_id / "result.json",
        {"inherited_from_parent": str(parent_run)},
    )


def _copy_file_atomic(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise EvidenceLifecycleError(f"branch source artifact not found: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    shutil.copy2(source, temporary)
    temporary.replace(destination)


def _write_text_atomic(destination: Path, content: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(destination)


def _checkpoint(spec: EvidenceLifecycleSpec, checkpoint_id: str) -> EvidenceCheckpointSpec:
    for checkpoint in spec.checkpoints:
        if checkpoint.checkpoint_id == checkpoint_id:
            return checkpoint
    raise EvidenceLifecycleError(f"unknown checkpoint in lifecycle state: {checkpoint_id}")


def _checkpoint_context(
    run_dir: Path,
    checkpoint: EvidenceCheckpointSpec,
    state: EvidenceLifecycleRunState,
) -> dict[str, Any]:
    workspace = _workspace(run_dir)
    checkpoint_run = state.checkpoint(checkpoint.checkpoint_id)
    return {
        "lifecycle_id": state.lifecycle_id,
        "world_id": state.world_id,
        "status": state.status.value,
        "active_checkpoint_id": state.active_checkpoint_id,
        "checkpoint_id": checkpoint.checkpoint_id,
        "title": checkpoint.title,
        "workspace": str(workspace),
        "run_dir": str(run_dir),
        "instruction": (workspace / "instruction.md").read_text(encoding="utf-8"),
        "instruction_path": str(workspace / "instruction.md"),
        "submission_path": str(workspace / checkpoint.submission_path),
        "released_files": list(checkpoint_run.released_files),
        "completed_checkpoints": _completed_checkpoints(state),
        "checkpoint_runs": [item.model_dump(mode="json") for item in state.checkpoint_runs],
        "revisits": [item.model_dump(mode="json") for item in state.revisits],
        "transitions": [item.model_dump(mode="json") for item in state.transitions],
        "branch": state.branch.model_dump(mode="json") if state.branch is not None else None,
    }


def _result_context(run_dir: Path, state: EvidenceLifecycleRunState) -> dict[str, Any]:
    return {
        "lifecycle_id": state.lifecycle_id,
        "world_id": state.world_id,
        "status": state.status.value,
        "workspace": str(_workspace(run_dir)),
        "run_dir": str(run_dir),
        "active_checkpoint_id": state.active_checkpoint_id,
        "completed_checkpoints": _completed_checkpoints(state),
        "checkpoint_runs": [item.model_dump(mode="json") for item in state.checkpoint_runs],
        "revisits": [item.model_dump(mode="json") for item in state.revisits],
        "transitions": [item.model_dump(mode="json") for item in state.transitions],
        "branch": state.branch.model_dump(mode="json") if state.branch is not None else None,
    }


def _completed_checkpoints(state: EvidenceLifecycleRunState) -> list[dict[str, Any]]:
    return [
        {
            "checkpoint_id": item.checkpoint_id,
            "submission_path": item.submission_path,
            "submission_sha256": item.submission_sha256,
            "released_files": list(item.released_files),
        }
        for item in state.checkpoint_runs
        if item.status == CheckpointRunStatus.SUBMITTED
    ]


def _attempt_context(attempt: CheckpointAttemptRecord) -> dict[str, Any]:
    return attempt.model_dump(mode="json")


def _append_transition(
    state: EvidenceLifecycleRunState,
    *,
    kind: LifecycleTransitionKind,
    from_checkpoint_id: str | None,
    to_checkpoint_id: str | None,
    reason: str,
) -> None:
    state.transitions.append(
        LifecycleTransitionRecord(
            transition_id=f"transition-{len(state.transitions) + 1:03d}",
            kind=kind,
            from_checkpoint_id=from_checkpoint_id,
            to_checkpoint_id=to_checkpoint_id,
            reason=reason,
        )
    )


def _sync_transition_ledger(run_dir: Path, state: EvidenceLifecycleRunState) -> None:
    ledger_path = _ledger_path(run_dir)
    recorded = {
        str(entry.get("summary", {}).get("transition_id"))
        for entry in read_ledger(ledger_path)
        if entry.get("stage") == "lifecycle_transition"
    }
    for transition in state.transitions:
        if transition.transition_id in recorded:
            continue
        append_ledger_entry(
            ledger_path,
            process_id=state.lifecycle_id,
            stage="lifecycle_transition",
            status=transition.kind.value,
            summary=transition.model_dump(mode="json"),
            artifact_refs=[],
        )


def _migrate_v2_state(
    payload: dict[str, Any],
    package_dir: Path,
    spec: EvidenceLifecycleSpec,
) -> EvidenceLifecycleRunState:
    migrated = copy.deepcopy(payload)
    migrated["schema_version"] = "3"
    migrated["lifecycle_spec_sha256"] = _spec_sha256(spec)
    migrated["package_sha256"] = _package_sha256(package_dir)
    return EvidenceLifecycleRunState.model_validate(migrated)


def _migrate_legacy_state(
    payload: dict[str, Any],
    package_dir: Path,
    spec: EvidenceLifecycleSpec,
) -> EvidenceLifecycleRunState:
    completed = {item["checkpoint_id"]: item for item in payload.get("completed_checkpoints", [])}
    active_checkpoint_id = payload.get("active_checkpoint_id")
    checkpoint_runs = []
    for checkpoint in spec.checkpoints:
        legacy = completed.get(checkpoint.checkpoint_id)
        if legacy is not None:
            checkpoint_runs.append(
                CheckpointRunRecord(
                    checkpoint_id=checkpoint.checkpoint_id,
                    status=CheckpointRunStatus.SUBMITTED,
                    released_files=list(legacy.get("released_files", [])),
                    submission_path=legacy.get("submission_path"),
                    submission_sha256=legacy.get("submission_sha256"),
                )
            )
        elif checkpoint.checkpoint_id == active_checkpoint_id:
            checkpoint_runs.append(
                CheckpointRunRecord(
                    checkpoint_id=checkpoint.checkpoint_id,
                    status=CheckpointRunStatus.ACTIVE,
                    released_files=list(payload.get("active_released_files", [])),
                )
            )
        else:
            checkpoint_runs.append(CheckpointRunRecord(checkpoint_id=checkpoint.checkpoint_id))
    return EvidenceLifecycleRunState(
        lifecycle_id=str(payload["lifecycle_id"]),
        world_id=str(payload["world_id"]),
        lifecycle_spec_sha256=_spec_sha256(spec),
        package_sha256=_package_sha256(package_dir),
        status=LifecycleRunStatus(str(payload.get("status", "awaiting_evidence_release"))),
        active_checkpoint_id=active_checkpoint_id,
        checkpoint_runs=checkpoint_runs,
    )


def _workspace(run_dir: Path) -> Path:
    return run_dir / "workspace"


def _state_path(run_dir: Path) -> Path:
    return run_dir / "state.json"


def _ledger_path(run_dir: Path) -> Path:
    return run_dir / "lifecycle_ledger.jsonl"


def _write_state(run_dir: Path, state: EvidenceLifecycleRunState) -> None:
    path = _state_path(run_dir)
    temporary = path.with_suffix(".json.tmp")
    _write_json(temporary, state.model_dump(mode="json"))
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceLifecycleError(f"invalid JSON artifact: {path}") from exc
    if not isinstance(payload, dict):
        raise EvidenceLifecycleError(f"JSON artifact must contain an object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _spec_sha256(spec: EvidenceLifecycleSpec) -> str:
    payload = json.dumps(
        spec.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _package_sha256(package_dir: Path) -> str:
    package = Path(package_dir)
    if not package.is_dir():
        raise EvidenceLifecycleError(f"lifecycle package not found: {package}")
    digest = hashlib.sha256()
    files = sorted(path for path in package.rglob("*") if path.is_file() or path.is_symlink())
    for path in files:
        if path.is_symlink():
            raise EvidenceLifecycleError(f"lifecycle packages may not contain symlinks: {path}")
        relative = path.relative_to(package).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(64 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()
