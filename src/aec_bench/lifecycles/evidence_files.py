# ABOUTME: Enforces portable and contained filesystem paths for lifecycle evidence.
# ABOUTME: Rejects symlinks before recording or finalization can hash external bytes.

from __future__ import annotations

from pathlib import Path


def safe_lifecycle_relative_path(value: str) -> Path:
    """Return one portable relative path or reject unsafe lifecycle evidence input."""
    path = Path(value)
    if "\\" in value or "\0" in value or path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError(f"lifecycle manifest contains an unsafe artifact path: {value}")
    return path


def lifecycle_artifact_kind(relative: Path) -> str:
    """Return the semantic role of one lifecycle package or run artifact."""
    path = relative.as_posix()
    if path.startswith("run/experiments/") and path.endswith("/experiment-manifest.json"):
        return "lifecycle_manifest"
    if path.startswith("run/experiments/") and path.endswith("/index-entry.json"):
        return "lifecycle_invocation_seal"
    exact = {
        "experiment-index.jsonl": "lifecycle_invocation_index",
        "sweep/manifest.json": "lifecycle_ablation_manifest",
        "sweep/plan.json": "lifecycle_ablation_plan",
        "run/verification.json": "lifecycle_verification",
        "run/metrics.json": "lifecycle_metrics",
        "run/state.json": "lifecycle_state",
        "run/lifecycle_ledger.jsonl": "lifecycle_ledger",
    }
    if path in exact:
        return exact[path]
    suffixes = {
        "/trajectory.jsonl": "trajectory",
        "/conversation.jsonl": "conversation",
        "/episode_request.json": "lifecycle_episode_request",
        "/episode_result.json": "lifecycle_episode_result",
        "/environment_prepared_episode_request.json": "environment_prepared_lifecycle_episode_request",
        "/environment_prepared_episode_result.json": "environment_prepared_lifecycle_episode_result",
        "/environment_prepared_rejected_episode_result.json": "environment_prepared_lifecycle_episode_result",
        "/rejected_episode_result.json": "rejected_lifecycle_episode_result",
        "/raw_output.md": "raw_output",
        "/agent_result.json": "agent_result",
        "/agent_result.corrupt.json": "corrupt_agent_result",
        "/submission.json": "checkpoint_submission",
    }
    for suffix, kind in suffixes.items():
        if path.endswith(suffix):
            return kind
    if path.startswith("package/"):
        return "lifecycle_package"
    if path.startswith("run/evidence_requests/") and path.endswith("/action.json"):
        return "evidence_request_action"
    if path.startswith("run/evidence_requests/") and path.endswith("/committed.json"):
        return "evidence_request_commit"
    if path.startswith("run/evidence_requests/") and "/artifacts/" in path:
        return "requested_evidence"
    if path.endswith("/evidence-requests.json"):
        return "evidence_request_catalog"
    if path.startswith("run/workspace/inbox/") and "/requests/" in path:
        return "requested_evidence_projection"
    if "/lifecycle_operations/" in path and path.endswith("/request.json"):
        return "lifecycle_operation_request"
    if "/lifecycle_operations/" in path and path.endswith("/action.json"):
        return "lifecycle_operation_action"
    if "/lifecycle_operations/" in path and path.endswith("/result-manifest.json"):
        return "lifecycle_operation_result_manifest"
    if "/lifecycle_operations/" in path and path.endswith("/committed.json"):
        return "lifecycle_operation_commit"
    if "/lifecycle_operations/" in path and "/artifacts/" in path:
        return "lifecycle_operation_artifact"
    if path.endswith("/operations.json"):
        return "lifecycle_operation_catalog"
    if path == "run/workspace/operations/current-source.json":
        return "lifecycle_operation_current_source"
    if path.startswith("run/workspace/inbox/") and "/operations/" in path:
        return "lifecycle_operation_projection"
    if "/submissions/" in path:
        return "checkpoint_submission"
    return "lifecycle_run_artifact"


def require_lifecycle_regular_file(*, root: Path, path: Path, label: str) -> Path:
    """Require one non-symlink regular file whose resolved path stays inside root."""
    selected_root = Path(root)
    selected_path = Path(path)
    if selected_root.is_symlink() or not selected_root.is_dir():
        raise ValueError(f"{label} root must be a non-symlink directory")
    try:
        relative = selected_path.absolute().relative_to(selected_root.absolute())
    except ValueError as exc:
        raise ValueError(f"{label} must stay inside its lifecycle evidence root") from exc
    if not relative.parts:
        raise ValueError(f"{label} must be a regular file")
    current = selected_root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"{label} must not be a symlink")
    if not current.is_file():
        raise ValueError(f"{label} must be a regular file")
    try:
        contained = current.resolve(strict=True).is_relative_to(selected_root.resolve(strict=True))
    except OSError as exc:
        raise ValueError(f"{label} cannot be resolved") from exc
    if not contained:
        raise ValueError(f"{label} must stay inside its lifecycle evidence root")
    return current


def is_lifecycle_regular_file(*, root: Path, path: Path) -> bool:
    """Return whether one lifecycle evidence path passes the regular-file boundary."""
    try:
        require_lifecycle_regular_file(root=root, path=path, label="lifecycle artifact")
    except ValueError:
        return False
    return True


__all__ = (
    "is_lifecycle_regular_file",
    "lifecycle_artifact_kind",
    "require_lifecycle_regular_file",
    "safe_lifecycle_relative_path",
)
