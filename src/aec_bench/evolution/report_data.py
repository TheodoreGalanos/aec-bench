# ABOUTME: Data layer for the evolution report — extracts cycle diffs from git history.
# ABOUTME: Produces typed dataclasses consumed by the HTML renderer or future web UI.

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

import yaml

from aec_bench.contracts.evolution import WorkspaceCandidateVersion
from aec_bench.evolution.workspace import Workspace


@dataclass(frozen=True)
class CycleReport:
    """Data for one evolution cycle's changes."""

    cycle: int
    candidate_id: str
    label: str | None
    source_revision: str
    score: float
    prompt_diff: str
    skills_added: list[str] = field(default_factory=list)
    skills_modified: list[str] = field(default_factory=list)
    skills_removed: list[str] = field(default_factory=list)
    skill_diffs: dict[str, str] = field(default_factory=dict)
    evolver_reasoning: str | None = None


@dataclass(frozen=True)
class EvolutionReportData:
    """Aggregated data for the full evolution report."""

    workspace_name: str
    model: str
    total_cycles: int
    converged: bool
    best_score: float
    final_score: float
    baseline_candidate_id: str | None
    baseline_label: str | None
    baseline_source_revision: str | None
    cycles: list[CycleReport] = field(default_factory=list)


class EvolutionRunSummary(TypedDict):
    """Summary of one tagged evolution run."""

    run_id: str
    cycles: int
    best_score: float
    final_score: float
    strategy: str


class FileTreeNode(TypedDict):
    """Recursive file-tree node returned by evolution report APIs."""

    name: str
    type: Literal["directory", "file"]
    status: str
    children: NotRequired[list[FileTreeNode]]


class CandidateFile(TypedDict):
    """File content read from one registered workspace candidate."""

    path: str
    candidate_id: str
    label: str | None
    source_revision: str
    content: str
    language: str


class CandidateFileDiff(TypedDict):
    """File diff between adjacent registered workspace candidates."""

    path: str
    from_candidate_id: str | None
    to_candidate_id: str
    diff: str


class WorkspaceRunSummary(TypedDict):
    """Evolution run card shown by workspace discovery."""

    name: str
    path: str
    run_id: str
    strategy: str
    cycles: int
    best_score: float
    final_score: float
    model: str


def build_evolution_report_data(
    workspace_path: Path,
    run_id: str | None = None,
) -> EvolutionReportData:
    """Build report data from registered candidates and exact source revisions."""
    workspace_name = _read_workspace_name(workspace_path)
    model = _read_model(workspace_path)
    all_candidates = Workspace(workspace_path).list_candidates()
    candidates = _report_candidates(all_candidates, run_id)
    baseline = next((candidate for candidate in all_candidates if candidate.candidate_id == "baseline"), None)
    baseline_candidate_id = baseline.candidate_id if baseline is not None else None
    baseline_label = baseline.label if baseline is not None else None
    baseline_source_revision = baseline.source_revision if baseline is not None else None

    if len(candidates) < 2:
        return EvolutionReportData(
            workspace_name=workspace_name,
            model=model,
            total_cycles=0,
            converged=False,
            best_score=0.0,
            final_score=0.0,
            baseline_candidate_id=baseline_candidate_id,
            baseline_label=baseline_label,
            baseline_source_revision=baseline_source_revision,
        )

    cycles: list[CycleReport] = []
    candidates_by_id = {candidate.candidate_id: candidate for candidate in all_candidates}
    for i, candidate in enumerate(candidates[1:], 1):
        parent = candidates_by_id.get(candidate.parent_candidate_id or "")
        if parent is None:
            continue
        cycle_num = i

        score = candidate.score or 0.0
        prompt_diff = _get_file_diff(
            workspace_path,
            parent.source_revision,
            candidate.source_revision,
            "prompts/system.md",
        )

        added, modified, removed, skill_diffs = _classify_skill_changes(
            workspace_path,
            parent.source_revision,
            candidate.source_revision,
        )

        cycles.append(
            CycleReport(
                cycle=cycle_num,
                candidate_id=candidate.candidate_id,
                label=candidate.label,
                source_revision=candidate.source_revision,
                score=score,
                prompt_diff=prompt_diff,
                skills_added=added,
                skills_modified=modified,
                skills_removed=removed,
                skill_diffs=skill_diffs,
            )
        )

    scores = [c.score for c in cycles]
    return EvolutionReportData(
        workspace_name=workspace_name,
        model=model,
        total_cycles=len(cycles),
        converged=False,
        best_score=max(scores) if scores else 0.0,
        final_score=scores[-1] if scores else 0.0,
        baseline_candidate_id=baseline_candidate_id,
        baseline_label=baseline_label,
        baseline_source_revision=baseline_source_revision,
        cycles=cycles,
    )


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _candidate_run_id(candidate_id: str) -> str | None:
    run_id, separator, cycle = candidate_id.rpartition(":")
    if not separator or not cycle.isdigit():
        return None
    return run_id


def _report_candidates(
    candidates: list[WorkspaceCandidateVersion],
    run_id: str | None,
) -> list[WorkspaceCandidateVersion]:
    baseline = next((candidate for candidate in candidates if candidate.candidate_id == "baseline"), None)
    grouped: dict[str, list[WorkspaceCandidateVersion]] = {}
    for candidate in candidates:
        candidate_run_id = _candidate_run_id(candidate.candidate_id)
        if candidate_run_id is not None:
            grouped.setdefault(candidate_run_id, []).append(candidate)
    selected_run_id = run_id or (sorted(grouped)[-1] if grouped else None)
    if selected_run_id is None:
        return [baseline] if baseline is not None else []
    selected = grouped.get(selected_run_id, [])
    return ([baseline] if baseline is not None else []) + selected


# Pattern for strategy in tag messages: [hill_climb] or [qd]
_STRATEGY_PATTERN = re.compile(r"\[(hill_climb|qd)\]")


def _parse_strategy(summary: str | None) -> str | None:
    """Extract a strategy name from a candidate summary."""
    match = _STRATEGY_PATTERN.search(summary or "")
    if match:
        return match.group(1)
    return None


def list_runs(workspace_path: Path) -> list[EvolutionRunSummary]:
    """List all evolution runs in a workspace, grouped by run_id.

    Returns a list of dicts sorted most-recent-first, each containing:
    run_id, cycles, best_score, final_score, strategy.
    """
    candidates = Workspace(workspace_path).list_candidates()
    runs: dict[str, list[WorkspaceCandidateVersion]] = {}
    for candidate in candidates:
        run_id = _candidate_run_id(candidate.candidate_id)
        if run_id is not None:
            runs.setdefault(run_id, []).append(candidate)

    # Parse scores and strategy per run
    config_strategy = _read_strategy(workspace_path)
    result: list[EvolutionRunSummary] = []
    for run_id, run_candidates in runs.items():
        scores = [candidate.score or 0.0 for candidate in run_candidates]

        strategy = _parse_strategy(run_candidates[0].summary)
        if strategy is None:
            strategy = config_strategy

        result.append(
            {
                "run_id": run_id,
                "cycles": len(run_candidates),
                "best_score": max(scores) if scores else 0.0,
                "final_score": scores[-1] if scores else 0.0,
                "strategy": strategy,
            }
        )

    # Engine run IDs are sortable UTC event times.
    result.sort(key=lambda r: r["run_id"], reverse=True)
    return result


def _read_strategy(workspace_path: Path) -> str:
    """Read the strategy field from evolution YAML config files in a workspace."""
    for config_name in ("evolution-debug.yaml", "evolution-quick.yaml", "evolution.yaml"):
        config_path = workspace_path / config_name
        if config_path.exists():
            data = yaml.safe_load(config_path.read_text())
            if isinstance(data, dict):
                strategy = data.get("strategy")
                if isinstance(strategy, str):
                    return strategy
    return "unknown"


def _get_file_diff(cwd: Path, from_tag: str, to_tag: str, filepath: str) -> str:
    """Get the unified diff for a single file between two tags."""
    return _git(cwd, "diff", f"{from_tag}..{to_tag}", "--", filepath)


def _classify_skill_changes(
    cwd: Path,
    from_tag: str,
    to_tag: str,
) -> tuple[list[str], list[str], list[str], dict[str, str]]:
    """Classify skill changes between two tags.

    Returns (added, modified, removed, skill_diffs).
    """
    raw = _git(cwd, "diff", "--name-status", f"{from_tag}..{to_tag}", "--", "skills/")
    if not raw:
        return [], [], [], {}

    added: list[str] = []
    modified: list[str] = []
    removed: list[str] = []
    seen_skills: set[str] = set()

    for line in raw.splitlines():
        parts = line.split("\t", 1)
        if len(parts) < 2:
            continue
        status, filepath = parts[0], parts[1]
        # Extract skill name from path like "skills/ac-circuit-analysis/SKILL.md"
        path_parts = filepath.split("/")
        if len(path_parts) < 2:
            continue
        skill_name = path_parts[1]
        if skill_name in seen_skills:
            continue
        seen_skills.add(skill_name)

        if status.startswith("A"):
            added.append(skill_name)
        elif status.startswith("M"):
            modified.append(skill_name)
        elif status.startswith("D"):
            removed.append(skill_name)

    # Collect diffs for modified and added skills
    skill_diffs: dict[str, str] = {}
    for name in added + modified:
        diff = _git(cwd, "diff", f"{from_tag}..{to_tag}", "--", f"skills/{name}/")
        if diff:
            skill_diffs[name] = diff

    return sorted(added), sorted(modified), sorted(removed), skill_diffs


# ---------------------------------------------------------------------------
# Workspace metadata
# ---------------------------------------------------------------------------


def _read_workspace_name(workspace_path: Path) -> str:
    manifest = workspace_path / "manifest.yaml"
    if manifest.exists():
        data = yaml.safe_load(manifest.read_text())
        if isinstance(data, dict):
            name = data.get("name")
            if isinstance(name, str):
                return name
    return "unknown"


def _read_model(workspace_path: Path) -> str:
    config = workspace_path / "evolution.yaml"
    if config.exists():
        data = yaml.safe_load(config.read_text())
        if isinstance(data, dict):
            models = data.get("models")
            if isinstance(models, dict):
                evolver = models.get("evolver")
                if isinstance(evolver, str):
                    return evolver
    return "unknown"


# ---------------------------------------------------------------------------
# Candidate helpers
# ---------------------------------------------------------------------------


def _candidate_and_parent(
    workspace_path: Path,
    candidate_id: str,
) -> tuple[WorkspaceCandidateVersion, WorkspaceCandidateVersion | None]:
    workspace = Workspace(workspace_path)
    candidate = workspace.require_candidate(candidate_id)
    parent = (
        workspace.require_candidate(candidate.parent_candidate_id)
        if candidate.parent_candidate_id is not None
        else None
    )
    return candidate, parent


def _status_char_to_label(char: str) -> str:
    """Map git status character to human-readable label."""
    mapping = {"A": "added", "M": "modified", "D": "removed"}
    return mapping.get(char, "unchanged")


_STATUS_SEVERITY = {"unchanged": 0, "modified": 1, "added": 2, "removed": 3}


def _aggregate_status(children: list[FileTreeNode]) -> str:
    """Return the most severe status among children nodes."""
    if not children:
        return "unchanged"
    worst = "unchanged"
    worst_rank = 0
    for child in children:
        rank = _STATUS_SEVERITY.get(child.get("status", "unchanged"), 0)
        if rank > worst_rank:
            worst_rank = rank
            worst = child["status"]
    return worst


# ---------------------------------------------------------------------------
# File tree and content retrieval
# ---------------------------------------------------------------------------


_EXTENSION_LANGUAGE = {
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".py": "python",
}


def _get_changed_files(cwd: Path, from_revision: str, to_revision: str) -> dict[str, str]:
    """Return {filepath: status_char} for changes between two source revisions."""
    raw = _git(cwd, "diff", "--name-status", f"{from_revision}..{to_revision}")
    result: dict[str, str] = {}
    for line in raw.splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2:
            result[parts[1]] = parts[0][0]
    return result


def _get_changed_files_initial(cwd: Path, source_revision: str) -> dict[str, str]:
    """Return {filepath: 'A'} for all files at an initial commit (evo-0).

    Uses --root to diff against the empty tree so the root commit's files
    appear as additions.
    """
    raw = _git(cwd, "diff-tree", "-r", "--root", "--no-commit-id", "--name-status", source_revision)
    result: dict[str, str] = {}
    for line in raw.splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2:
            result[parts[1].strip()] = parts[0][0]
    return result


def _build_tree_nodes(
    files: list[str],
    changed_files: dict[str, str],
) -> FileTreeNode:
    """Build a nested tree structure from a flat list of file paths.

    Returns the root node dict with nested children.
    """
    root: FileTreeNode = {
        "name": ".",
        "type": "directory",
        "children": [],
        "status": "unchanged",
    }
    # Map directory path -> node for quick lookup
    dir_nodes: dict[str, FileTreeNode] = {"": root}

    for filepath in sorted(files):
        parts = filepath.split("/")
        # Ensure all parent directories exist
        for i in range(len(parts) - 1):
            dir_path = "/".join(parts[: i + 1])
            if dir_path not in dir_nodes:
                dir_node: FileTreeNode = {
                    "name": parts[i],
                    "type": "directory",
                    "children": [],
                    "status": "unchanged",
                }
                parent_path = "/".join(parts[:i]) if i > 0 else ""
                dir_nodes[parent_path]["children"].append(dir_node)
                dir_nodes[dir_path] = dir_node

        # Add the file node
        status_char = changed_files.get(filepath, "")
        status = _status_char_to_label(status_char) if status_char else "unchanged"
        file_node: FileTreeNode = {
            "name": parts[-1],
            "type": "file",
            "status": status,
        }
        parent_path = "/".join(parts[:-1]) if len(parts) > 1 else ""
        dir_nodes[parent_path]["children"].append(file_node)

    # Propagate status up to directories (post-order)
    _propagate_status(root)
    return root


def _propagate_status(node: FileTreeNode) -> None:
    """Recursively set directory status from children (most severe wins)."""
    if node["type"] == "file":
        return
    for child in node.get("children", []):
        _propagate_status(child)
    node["status"] = _aggregate_status(node.get("children", []))


def get_file_tree_at_candidate(workspace_path: Path, candidate_id: str) -> FileTreeNode:
    """Return the file tree for an exact candidate ID.

    Uses git ls-tree to list files and git diff to determine change status.
    For evo-0 all files are marked as "added".
    """
    candidate, parent = _candidate_and_parent(workspace_path, candidate_id)
    raw_files = _git(workspace_path, "ls-tree", "-r", "--name-only", candidate.source_revision)
    if not raw_files:
        return {
            "name": ".",
            "type": "directory",
            "children": [],
            "status": "unchanged",
        }
    files = raw_files.splitlines()

    # Determine changed files
    if parent is None:
        changed_files = _get_changed_files_initial(workspace_path, candidate.source_revision)
    else:
        changed_files = _get_changed_files(workspace_path, parent.source_revision, candidate.source_revision)

    return _build_tree_nodes(files, changed_files)


def get_file_at_candidate(
    workspace_path: Path,
    candidate_id: str,
    filepath: str,
) -> CandidateFile:
    """Return file content for an exact candidate ID."""
    candidate, _ = _candidate_and_parent(workspace_path, candidate_id)
    content = _git(workspace_path, "show", f"{candidate.source_revision}:{filepath}")
    ext = Path(filepath).suffix.lower()
    language = _EXTENSION_LANGUAGE.get(ext, "text")
    return {
        "path": filepath,
        "candidate_id": candidate.candidate_id,
        "label": candidate.label,
        "source_revision": candidate.source_revision,
        "content": content,
        "language": language,
    }


def get_file_diff_at_candidate(
    workspace_path: Path,
    candidate_id: str,
    filepath: str,
) -> CandidateFileDiff:
    """Return a unified diff between one candidate and its parent.

    For evo-0, the entire file content is shown as additions (diff against
    empty tree).
    """
    candidate, parent = _candidate_and_parent(workspace_path, candidate_id)
    if parent is None:
        # evo-0: show everything as additions
        content = _git(workspace_path, "show", f"{candidate.source_revision}:{filepath}")
        lines = content.splitlines()
        diff_lines = [f"+{line}" for line in lines]
        diff_text = "\n".join(diff_lines)
    else:
        diff_text = _get_file_diff(
            workspace_path,
            parent.source_revision,
            candidate.source_revision,
            filepath,
        )

    return {
        "path": filepath,
        "from_candidate_id": parent.candidate_id if parent is not None else None,
        "to_candidate_id": candidate.candidate_id,
        "diff": diff_text,
    }


# ---------------------------------------------------------------------------
# Workspace discovery
# ---------------------------------------------------------------------------


def discover_workspaces(search_root: Path) -> list[WorkspaceRunSummary]:
    """Scan search_root for directories containing both manifest.yaml and evolution.yaml.

    Returns one entry per **run** (not per workspace directory). Each entry
    contains: name, path (relative to search_root), run_id, strategy,
    cycles, best_score, final_score, model.
    """
    results: list[WorkspaceRunSummary] = []
    if not search_root.exists():
        return results

    for entry in sorted(search_root.iterdir()):
        if not entry.is_dir():
            continue
        manifest = entry / "manifest.yaml"
        evolution = entry / "evolution.yaml"
        if not manifest.exists() or not evolution.exists():
            continue

        ws_name = _read_workspace_name(entry)
        model = _read_model(entry)
        rel_path = str(entry.relative_to(search_root))

        runs = list_runs(entry)
        if not runs:
            # Workspace exists but no runs yet — show a placeholder card
            results.append(
                {
                    "name": ws_name,
                    "path": rel_path,
                    "run_id": "",
                    "strategy": _read_strategy(entry),
                    "cycles": 0,
                    "best_score": 0.0,
                    "final_score": 0.0,
                    "model": model,
                }
            )
        else:
            for run in runs:
                results.append(
                    {
                        "name": ws_name,
                        "path": rel_path,
                        "run_id": run["run_id"],
                        "strategy": run["strategy"],
                        "cycles": run["cycles"],
                        "best_score": run["best_score"],
                        "final_score": run["final_score"],
                        "model": model,
                    }
                )

    return results
