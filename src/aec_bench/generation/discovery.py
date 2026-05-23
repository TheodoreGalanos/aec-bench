# ABOUTME: Discovery utilities for scanning template and seed directories.
# ABOUTME: Enumerates built-in templates (engine.py + params.toml) and seeds (source_task.json).

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LibrarySeed:
    """A seed task from source_task.json."""

    discipline: str
    category: str
    task_id: str
    task_name: str
    description: str
    complexity: str
    standards: tuple[str, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    path: Path


@dataclass(frozen=True)
class LibraryTemplate:
    """A built template with engine.py and params.toml."""

    discipline: str
    task_id: str
    path: Path
    params_raw: dict  # parsed params.toml content


def scan_seeds(tasks_root: Path) -> list[LibrarySeed]:
    """Scan all source_task.json files under tasks_root."""
    if not tasks_root.is_dir():
        return []
    seeds: list[LibrarySeed] = []
    for path in sorted(tasks_root.rglob("source_task.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            src = data.get("source", {})
            seeds.append(
                LibrarySeed(
                    discipline=src.get("discipline", "unknown"),
                    category=src.get("category_id", path.parent.parent.name),
                    task_id=src.get("task_id", path.parent.name),
                    task_name=src.get("task_name", path.parent.name),
                    description=src.get("description", ""),
                    complexity=src.get("complexity", "unknown"),
                    standards=tuple(src.get("standards", [])),
                    inputs=tuple(src.get("inputs", [])),
                    outputs=tuple(src.get("outputs", [])),
                    path=path.parent,
                )
            )
        except (json.JSONDecodeError, KeyError):
            continue
    return seeds


def scan_templates(templates_root: Path) -> list[LibraryTemplate]:
    """Scan built-in templates that have engine.py + params.toml."""
    if not templates_root.is_dir():
        return []
    templates: list[LibraryTemplate] = []
    for params_path in sorted(templates_root.rglob("params.toml")):
        engine_path = params_path.parent / "engine.py"
        if not engine_path.exists():
            continue
        try:
            params_raw = tomllib.loads(params_path.read_text(encoding="utf-8"))
            meta = params_raw.get("meta", {})
            discipline = meta.get("discipline", params_path.parent.parent.name)
            task_id = meta.get("name", params_path.parent.name.replace("_", "-"))
            templates.append(
                LibraryTemplate(
                    discipline=discipline,
                    task_id=task_id,
                    path=params_path.parent,
                    params_raw=params_raw,
                )
            )
        except (tomllib.TOMLDecodeError, KeyError):
            continue
    return templates
