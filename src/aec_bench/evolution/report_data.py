# ABOUTME: Data layer for the evolution report — extracts cycle diffs from git history.
# ABOUTME: Produces typed dataclasses consumed by the HTML renderer or future web UI.

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class CycleReport:
    """Data for one evolution cycle's changes."""

    cycle: int
    version_tag: str
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
    cycles: list[CycleReport] = field(default_factory=list)


_SCORE_PATTERN = re.compile(r"score\s+([\d.]+)")


def build_evolution_report_data(
    workspace_path: Path,
    run_id: str | None = None,
) -> EvolutionReportData:
    """Build report data by reading git tags and diffs from a workspace.

    Walks ``evo-0``, ``evo-1``, ... tags and extracts diffs between
    consecutive pairs.  Scores are parsed from tag messages.
    """
    workspace_name = _read_workspace_name(workspace_path)
    model = _read_model(workspace_path)
    tags = _list_evo_tags(workspace_path, run_id=run_id)

    if len(tags) < 2:
        return EvolutionReportData(
            workspace_name=workspace_name,
            model=model,
            total_cycles=0,
            converged=False,
            best_score=0.0,
            final_score=0.0,
        )

    cycles: list[CycleReport] = []
    for i in range(1, len(tags)):
        prev_tag = tags[i - 1]
        curr_tag = tags[i]
        cycle_num = i

        score = _parse_score_from_tag(workspace_path, curr_tag)
        prompt_diff = _get_file_diff(workspace_path, prev_tag, curr_tag, "prompts/system.md")

        added, modified, removed, skill_diffs = _classify_skill_changes(
            workspace_path,
            prev_tag,
            curr_tag,
        )

        cycles.append(
            CycleReport(
                cycle=cycle_num,
                version_tag=curr_tag,
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


def _list_evo_tags(cwd: Path, run_id: str | None = None) -> list[str]:
    """List evo tags sorted by cycle number, optionally filtered to a specific run.

    Supports both legacy ``evo-N`` tags and run-scoped ``evo-{run_id}-N`` tags.
    When *run_id* is None, auto-detects the latest run by finding the most
    recent run prefix. ``evo-0`` (the workspace baseline) is always included.
    """
    raw = _git(cwd, "tag", "-l", "evo-*")
    if not raw:
        return []
    all_tags = [t.strip() for t in raw.splitlines() if t.strip()]

    if run_id == "legacy":
        # Legacy runs use evo-N format (no run prefix)
        legacy_re = re.compile(r"^evo-\d+$")
        tags = [t for t in all_tags if legacy_re.match(t)]
    elif run_id:
        # Filter to specific run + evo-0
        prefix = f"evo-{run_id}-"
        tags = [t for t in all_tags if t.startswith(prefix) or t == "evo-0"]
    else:
        # Auto-detect: find the latest run prefix
        tags = _filter_latest_run(all_tags)

    # Sort by numeric suffix (cycle number)
    def _sort_key(tag: str) -> int:
        try:
            return int(tag.split("-")[-1])
        except ValueError:
            return 0

    return sorted(tags, key=_sort_key)


def _filter_latest_run(tags: list[str]) -> list[str]:
    """Given all evo-* tags, return only evo-0 + the most recent run's tags.

    Run-scoped tags have format ``evo-{YYYYMMDD}-{HHMM}-{cycle}``.
    Legacy tags have format ``evo-{cycle}``. If only legacy tags exist,
    returns all of them for backwards compatibility.
    """
    import re

    run_prefix_pattern = re.compile(r"^evo-(\d{8}-\d{4})-\d+$")
    run_prefixes: set[str] = set()
    legacy_tags: list[str] = []

    for tag in tags:
        m = run_prefix_pattern.match(tag)
        if m:
            run_prefixes.add(m.group(1))
        elif tag == "evo-0":
            pass  # always include
        else:
            legacy_tags.append(tag)

    if not run_prefixes:
        # Only legacy tags — return all for backwards compatibility
        return tags

    # Pick the latest run prefix (lexicographic sort on YYYYMMDD-HHMM works)
    latest = sorted(run_prefixes)[-1]
    prefix = f"evo-{latest}-"
    return ["evo-0"] + [t for t in tags if t.startswith(prefix)]


def _parse_score_from_tag(cwd: Path, tag: str) -> float:
    """Extract score from a tag's annotation message."""
    msg = _git(cwd, "tag", "-l", tag, "-n1")
    match = _SCORE_PATTERN.search(msg)
    if match:
        return float(match.group(1))
    return 0.0


# Pattern for strategy in tag messages: [hill_climb] or [qd]
_STRATEGY_PATTERN = re.compile(r"\[(hill_climb|qd)\]")


def _parse_strategy_from_tag(cwd: Path, tag: str) -> str | None:
    """Extract strategy name from a tag's annotation message, if present."""
    msg = _git(cwd, "tag", "-l", tag, "-n1")
    match = _STRATEGY_PATTERN.search(msg)
    if match:
        return match.group(1)
    return None


def list_runs(workspace_path: Path) -> list[dict]:
    """List all evolution runs in a workspace, grouped by run_id.

    Returns a list of dicts sorted most-recent-first, each containing:
    run_id, cycles, best_score, final_score, strategy.
    """
    raw = _git(workspace_path, "tag", "-l", "evo-*")
    if not raw:
        return []
    all_tags = [t.strip() for t in raw.splitlines() if t.strip()]

    run_prefix_pattern = re.compile(r"^evo-(\d{8}-\d{4})-(\d+)$")
    legacy_pattern = re.compile(r"^evo-(\d+)$")

    # Group tags by run_id
    runs: dict[str, list[tuple[str, int]]] = {}  # run_id -> [(tag, cycle)]
    for tag in all_tags:
        if tag == "evo-0":
            continue
        m = run_prefix_pattern.match(tag)
        if m:
            run_id = m.group(1)
            cycle = int(m.group(2))
            runs.setdefault(run_id, []).append((tag, cycle))
            continue
        m = legacy_pattern.match(tag)
        if m:
            cycle = int(m.group(1))
            runs.setdefault("legacy", []).append((tag, cycle))

    # Parse scores and strategy per run
    config_strategy = _read_strategy(workspace_path)
    result: list[dict] = []
    for run_id, tag_cycles in runs.items():
        tag_cycles.sort(key=lambda tc: tc[1])
        scores: list[float] = []
        for tag, _cycle in tag_cycles:
            score = _parse_score_from_tag(workspace_path, tag)
            scores.append(score)

        # Try to read strategy from the first tag's message; fall back to config
        strategy = _parse_strategy_from_tag(workspace_path, tag_cycles[0][0])
        if strategy is None:
            strategy = config_strategy

        result.append(
            {
                "run_id": run_id,
                "cycles": len(tag_cycles),
                "best_score": max(scores) if scores else 0.0,
                "final_score": scores[-1] if scores else 0.0,
                "strategy": strategy,
            }
        )

    # Sort most-recent-first (lexicographic on YYYYMMDD-HHMM; "legacy" sorts first)
    result.sort(key=lambda r: r["run_id"], reverse=True)
    return result


def _read_strategy(workspace_path: Path) -> str:
    """Read the strategy field from evolution YAML config files in a workspace."""
    for config_name in ("evolution-debug.yaml", "evolution-quick.yaml", "evolution.yaml"):
        config_path = workspace_path / config_name
        if config_path.exists():
            data = yaml.safe_load(config_path.read_text())
            if data and "strategy" in data:
                return data["strategy"]
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
        return data.get("name", "unknown")
    return "unknown"


def _read_model(workspace_path: Path) -> str:
    config = workspace_path / "evolution.yaml"
    if config.exists():
        data = yaml.safe_load(config.read_text())
        models = data.get("models", {})
        return models.get("evolver", "unknown")
    return "unknown"


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------


def _previous_version(version: str) -> str | None:
    """Return the previous evo tag for both legacy and run-scoped formats.

    Legacy: evo-N → evo-(N-1), evo-0 → None.
    Run-scoped: evo-{run_id}-N → evo-{run_id}-(N-1), evo-{run_id}-1 → evo-0,
    evo-{run_id}-0 → None.
    """
    # Run-scoped: evo-YYYYMMDD-HHMM-N
    run_match = re.match(r"^evo-(\d{8}-\d{4})-(\d+)$", version)
    if run_match:
        run_id = run_match.group(1)
        cycle = int(run_match.group(2))
        if cycle == 0:
            return None
        if cycle == 1:
            return "evo-0"
        return f"evo-{run_id}-{cycle - 1}"

    # Legacy: evo-N
    legacy_match = re.match(r"^evo-(\d+)$", version)
    if legacy_match:
        n = int(legacy_match.group(1))
        if n == 0:
            return None
        return f"evo-{n - 1}"

    return None


def _status_char_to_label(char: str) -> str:
    """Map git status character to human-readable label."""
    mapping = {"A": "added", "M": "modified", "D": "removed"}
    return mapping.get(char, "unchanged")


_STATUS_SEVERITY = {"unchanged": 0, "modified": 1, "added": 2, "removed": 3}


def _aggregate_status(children: list[dict]) -> str:
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


def _get_changed_files(cwd: Path, from_version: str, to_version: str) -> dict[str, str]:
    """Return {filepath: status_char} for changes between two versions."""
    raw = _git(cwd, "diff", "--name-status", f"{from_version}..{to_version}")
    result: dict[str, str] = {}
    for line in raw.splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2:
            result[parts[1]] = parts[0][0]
    return result


def _get_changed_files_initial(cwd: Path, version: str) -> dict[str, str]:
    """Return {filepath: 'A'} for all files at an initial commit (evo-0).

    Uses --root to diff against the empty tree so the root commit's files
    appear as additions.
    """
    raw = _git(cwd, "diff-tree", "-r", "--root", "--no-commit-id", "--name-status", version)
    result: dict[str, str] = {}
    for line in raw.splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2:
            result[parts[1].strip()] = parts[0][0]
    return result


def _build_tree_nodes(
    files: list[str],
    changed_files: dict[str, str],
) -> dict:
    """Build a nested tree structure from a flat list of file paths.

    Returns the root node dict with nested children.
    """
    root: dict = {
        "name": ".",
        "type": "directory",
        "children": [],
        "status": "unchanged",
    }
    # Map directory path -> node for quick lookup
    dir_nodes: dict[str, dict] = {"": root}

    for filepath in sorted(files):
        parts = filepath.split("/")
        # Ensure all parent directories exist
        for i in range(len(parts) - 1):
            dir_path = "/".join(parts[: i + 1])
            if dir_path not in dir_nodes:
                dir_node: dict = {
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
        file_node: dict = {
            "name": parts[-1],
            "type": "file",
            "status": status,
        }
        parent_path = "/".join(parts[:-1]) if len(parts) > 1 else ""
        dir_nodes[parent_path]["children"].append(file_node)

    # Propagate status up to directories (post-order)
    _propagate_status(root)
    return root


def _propagate_status(node: dict) -> None:
    """Recursively set directory status from children (most severe wins)."""
    if node["type"] == "file":
        return
    for child in node.get("children", []):
        _propagate_status(child)
    node["status"] = _aggregate_status(node.get("children", []))


def get_file_tree_at_version(workspace_path: Path, version: str) -> dict:
    """Return the file tree at a specific evo-N version.

    Uses git ls-tree to list files and git diff to determine change status.
    For evo-0 all files are marked as "added".
    """
    # List all files at this version
    raw_files = _git(workspace_path, "ls-tree", "-r", "--name-only", version)
    if not raw_files:
        return {
            "name": ".",
            "type": "directory",
            "children": [],
            "status": "unchanged",
        }
    files = raw_files.splitlines()

    # Determine changed files
    prev = _previous_version(version)
    if prev is None:
        changed_files = _get_changed_files_initial(workspace_path, version)
    else:
        changed_files = _get_changed_files(workspace_path, prev, version)

    return _build_tree_nodes(files, changed_files)


def get_file_at_version(workspace_path: Path, version: str, filepath: str) -> dict:
    """Return file content at a specific version.

    Returns dict with path, version, content, and language (detected from
    file extension).
    """
    content = _git(workspace_path, "show", f"{version}:{filepath}")
    ext = Path(filepath).suffix.lower()
    language = _EXTENSION_LANGUAGE.get(ext, "text")
    return {
        "path": filepath,
        "version": version,
        "content": content,
        "language": language,
    }


def get_file_diff_at_version(
    workspace_path: Path,
    version: str,
    filepath: str,
) -> dict:
    """Return unified diff for a file between the previous version and this one.

    For evo-0, the entire file content is shown as additions (diff against
    empty tree).
    """
    prev = _previous_version(version)
    if prev is None:
        # evo-0: show everything as additions
        content = _git(workspace_path, "show", f"{version}:{filepath}")
        lines = content.splitlines()
        diff_lines = [f"+{line}" for line in lines]
        diff_text = "\n".join(diff_lines)
    else:
        diff_text = _get_file_diff(workspace_path, prev, version, filepath)

    return {
        "path": filepath,
        "from_version": prev,
        "to_version": version,
        "diff": diff_text,
    }


# ---------------------------------------------------------------------------
# Workspace discovery
# ---------------------------------------------------------------------------


def discover_workspaces(search_root: Path) -> list[dict]:
    """Scan search_root for directories containing both manifest.yaml and evolution.yaml.

    Returns one entry per **run** (not per workspace directory). Each entry
    contains: name, path (relative to search_root), run_id, strategy,
    cycles, best_score, final_score, model.
    """
    results: list[dict] = []
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
