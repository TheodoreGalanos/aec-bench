# ABOUTME: Enforces path-safe proposal Harbor identities, roots, and symlink boundaries.
# ABOUTME: Keeps proposal confinement helpers separate from provider-operation policy.

from __future__ import annotations

import json
import os
import re
from pathlib import Path, PurePosixPath

from aec_bench.experimentation.proposals.proposal_dispatch import (
    GovernedProposalDispatch,
)


def safe_segment(value: str) -> str:
    """Return one path-safe dispatch segment or fail closed."""

    if re.fullmatch(r"[A-Za-z0-9._-]+", value) is None:
        raise ValueError("proposal Harbor dispatch id is not path-safe")
    return value


def reject_symlink_components(path: Path, *, label: str) -> None:
    """Reject any existing symbolic-link component in a proposed path."""

    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if os.path.lexists(current) and current.is_symlink():
            raise ValueError(f"{label} cannot traverse symlinks")


def paths_overlap(left: Path, right: Path) -> bool:
    """Return whether either path contains the other."""

    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def authorized_jobs_root(
    *,
    dispatch: GovernedProposalDispatch,
    project_root: Path,
) -> Path:
    """Resolve the jobs root asserted by one canonical Harbor dispatch."""

    try:
        configured = json.loads(dispatch.harbor_job_config_json)["jobs_dir"]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            "authorized Harbor dispatch has no valid jobs root",
        ) from error
    if not isinstance(configured, str) or not configured.strip():
        raise ValueError(
            "authorized Harbor jobs root must be a non-empty string",
        )
    path = Path(configured)
    return path.resolve() if path.is_absolute() else (Path(project_root) / path).resolve()


def authorized_project_root(
    *,
    dispatch: GovernedProposalDispatch,
    project_root: Path,
) -> Path:
    """Resolve and confine the project root implied by a derived task."""

    task_path = PurePosixPath(dispatch.task_id)
    if task_path.is_absolute() or not task_path.parts or any(part in {"", ".", ".."} for part in task_path.parts):
        raise ValueError(
            "authorized Harbor dispatch has an invalid task identity",
        )
    derived_task = Path(dispatch.derived_task_path).resolve()
    expected_relative = Path("tasks", *task_path.parts)
    try:
        selected = derived_task.parents[len(expected_relative.parts) - 1]
    except IndexError as error:
        raise ValueError(
            "authorized derived task cannot identify its project root",
        ) from error
    allowed = Path(project_root).resolve()
    if (
        selected / expected_relative != derived_task
        or (selected != allowed and not selected.is_relative_to(allowed))
        or not selected.is_dir()
    ):
        raise ValueError(
            "authorized dispatch project root escapes its declared root",
        )
    return selected
