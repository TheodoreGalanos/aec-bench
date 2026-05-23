# ABOUTME: Configuration helpers with layered resolution for aec-bench projects.
# ABOUTME: Discovers aec-bench.toml, merges project TOML > global JSON > defaults.

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

_CONFIG_FILENAME = "aec-bench.toml"

_TOML_KEY_MAP: dict[str, str] = {
    "tasks": "tasks_root",
    "seeds": "seeds_root",
    "ledger": "ledger_root",
    "feedback": "feedback_root",
    "jobs": "jobs_root",
    "templates": "templates_root",
    "datasets": "datasets_root",
}

_PATH_DEFAULTS: dict[str, str] = {
    "tasks_root": "tasks",
    "seeds_root": "seeds",
    "ledger_root": "artefacts/ledger",
    "feedback_root": "artefacts/feedback",
    "jobs_root": "jobs",
    "templates_root": "templates",
    "datasets_root": "artefacts/datasets",
}

_DEFAULTS: dict[str, str] = {
    **_PATH_DEFAULTS,
    "default_compute_backend": "modal",
    "project_name": "",
}


@dataclass(frozen=True)
class AppConfig:
    project_root: Path
    tasks_root: Path
    ledger_root: Path
    seeds_root: Path
    jobs_root: Path
    templates_root: Path
    feedback_root: Path
    datasets_root: Path
    default_compute_backend: str
    project_name: str


def find_project_config() -> Path | None:
    """Walk from cwd upward looking for an aec-bench.toml file.

    Returns the resolved path to the config file, or None if not found.
    """
    current = Path.cwd().resolve()
    while True:
        candidate = current / _CONFIG_FILENAME
        if candidate.is_file():
            return candidate
        parent = current.parent
        if parent == current:
            # Reached filesystem root
            return None
        current = parent


def _load_project_toml(path: Path) -> dict[str, str]:
    """Parse an aec-bench.toml and return a flat dict with internal key names.

    Maps short TOML path names (e.g. ``tasks``) to internal field names
    (e.g. ``tasks_root``) via ``_TOML_KEY_MAP``.
    """
    with open(path, "rb") as f:
        data = tomllib.load(f)

    result: dict[str, str] = {}

    # [project] section
    project = data.get("project", {})
    if "name" in project:
        result["project_name"] = project["name"]

    # [paths] section
    paths = data.get("paths", {})
    for toml_key, internal_key in _TOML_KEY_MAP.items():
        if toml_key in paths:
            result[internal_key] = paths[toml_key]

    # [compute] section
    compute = data.get("compute", {})
    if "backend" in compute:
        result["default_compute_backend"] = compute["backend"]

    return result


def _load_global_json() -> dict[str, str]:
    """Load global config from ``~/.config/aec-bench/config.json`` if it exists.

    Returns a flat dict with internal key names, or an empty dict if the
    file does not exist or cannot be parsed.
    """
    global_config = Path.home() / ".config" / "aec-bench" / "config.json"
    if not global_config.is_file():
        return {}
    try:
        with open(global_config, encoding="utf-8") as f:
            data = json.load(f)
        result: dict[str, str] = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = value
        return result
    except (json.JSONDecodeError, OSError):
        return {}


def load_config(project_root: Path | None = None) -> AppConfig:
    """Build an AppConfig by merging project TOML > global JSON > defaults.

    Resolution order:
    1. If ``project_root`` is explicitly passed, use it directly.
    2. Otherwise, try ``find_project_config()`` to discover a project root.
    3. If no TOML found and no explicit root, fall back to the package root
       (``Path(__file__).resolve().parents[2]``) -- preserving existing behavior.

    Values are merged: project TOML > global JSON > defaults.
    All relative paths are resolved against the project root.
    """
    toml_values: dict[str, str] = {}

    if project_root is not None:
        # Explicit project root -- skip TOML discovery
        resolved_root = project_root.resolve()
    else:
        config_file = find_project_config()
        if config_file is not None:
            resolved_root = config_file.parent.resolve()
            toml_values = _load_project_toml(config_file)
        else:
            # Fall back to package root (existing behavior)
            resolved_root = Path(__file__).resolve().parents[2]

    # Layer: project TOML > global JSON > defaults
    global_values = _load_global_json()
    merged: dict[str, str] = {**_DEFAULTS, **global_values, **toml_values}

    # Resolve path fields against project root
    path_values: dict[str, Path] = {}
    for key in _PATH_DEFAULTS:
        raw = merged[key]
        path = Path(raw)
        if not path.is_absolute():
            path = resolved_root / path
        path_values[key] = path

    return AppConfig(
        project_root=resolved_root,
        tasks_root=path_values["tasks_root"],
        ledger_root=path_values["ledger_root"],
        seeds_root=path_values["seeds_root"],
        jobs_root=path_values["jobs_root"],
        templates_root=path_values["templates_root"],
        feedback_root=path_values["feedback_root"],
        datasets_root=path_values["datasets_root"],
        default_compute_backend=merged["default_compute_backend"],
        project_name=merged["project_name"],
    )


def resolve_artifact_path(stored_path: str, project_root: Path | None = None) -> Path | None:
    """Resolve an artifact path, falling back to jobs/ at project root.

    Stored paths in trial records may contain leading ``../`` segments from
    older repo layouts. When the literal path does not exist on disk, this
    helper extracts the ``jobs/...`` suffix and resolves it relative to the
    project root.
    """
    direct = Path(stored_path)
    if direct.exists():
        return direct
    root = project_root or load_config().project_root
    parts = direct.parts
    for i, part in enumerate(parts):
        if part == "jobs":
            candidate = root / Path(*parts[i:])
            if candidate.exists():
                return candidate
    return None
