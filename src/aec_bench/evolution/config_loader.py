# ABOUTME: Loads evolution experiment configuration from YAML files.
# ABOUTME: Provides config loading, harness manifest merging, and task directory resolution.

from fnmatch import fnmatch
from pathlib import Path

import yaml

from aec_bench.contracts.evolution import EvolutionConfig
from aec_bench.contracts.experiment_manifest import ExperimentManifest, TaskSelector

# Markers that identify a directory as a task instance.
_TASK_MARKERS = ("instruction.md", "task.toml")

# Default value for the timeout field — used to detect whether the user
# explicitly set a different value versus leaving it at the default.
_DEFAULT_TIMEOUT = 1800


def merge_harness_config(
    config: EvolutionConfig,
    config_dir: Path,
) -> EvolutionConfig:
    """Merge fields from a referenced ExperimentManifest into an EvolutionConfig.

    When harness_config is set, the manifest file is loaded and its values are
    used to fill in fields that still hold their defaults. Explicitly-set values
    in the EvolutionConfig are never overridden.

    Merge rules:
    - solver:  populated from manifest.agents[0] if config.solver is None
    - backend: upgraded from manifest.compute.backend if config.backend == "local"
    - timeout: taken from manifest.compute.timeout_override if config.timeout is
               still the default (1800) and the manifest has a timeout
    """
    if config.harness_config is None:
        return config

    manifest_path = config_dir / config.harness_config
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest = ExperimentManifest.model_validate(raw)

    updates: dict = {}

    if config.solver is None and manifest.agents:
        updates["solver"] = manifest.agents[0]

    if config.backend == "local":
        updates["backend"] = manifest.compute.backend

    if config.timeout == _DEFAULT_TIMEOUT and manifest.compute.timeout_override is not None:
        updates["timeout"] = manifest.compute.timeout_override

    if not updates:
        return config

    return config.model_copy(update=updates)


def load_evolution_config(path: Path) -> EvolutionConfig:
    """Read a YAML file and return a validated EvolutionConfig.

    The YAML `tasks` key is mapped to `task_selector` before validation so
    that the user-facing field name matches convention while the Pydantic model
    uses the canonical internal name.

    If harness_config is set, an ExperimentManifest is loaded from that path
    and its values are merged into the config for any fields still at defaults.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    # Remap the user-friendly key to the Pydantic field name.
    if "tasks" in raw and "task_selector" not in raw:
        raw["task_selector"] = raw.pop("tasks")

    config = EvolutionConfig.model_validate(raw)
    return merge_harness_config(config, config_dir=path.parent)


def resolve_task_dirs(task_selector: TaskSelector, tasks_root: Path) -> list[Path]:
    """Resolve a TaskSelector into concrete task directory paths under tasks_root.

    A directory is considered a task instance if it contains `instruction.md`
    or `task.toml`. Filtering is applied in order: domain, include patterns,
    exclude patterns. Returns a sorted list of absolute Paths.
    """
    if not tasks_root.exists():
        return []

    # Collect all task instance directories.
    candidates: list[Path] = []
    for marker in _TASK_MARKERS:
        for marker_path in tasks_root.rglob(marker):
            task_dir = marker_path.parent
            if task_dir not in candidates:
                candidates.append(task_dir)

    # Filter by domain (first path component relative to tasks_root).
    if task_selector.domains:
        domains = set(task_selector.domains)
        candidates = [p for p in candidates if p.relative_to(tasks_root).parts[0] in domains]

    # Filter by include patterns against the relative path string.
    if task_selector.include_patterns:
        candidates = [
            p
            for p in candidates
            if any(fnmatch(str(p.relative_to(tasks_root)), pattern) for pattern in task_selector.include_patterns)
        ]

    # Exclude by exclude patterns against the relative path string.
    if task_selector.exclude_patterns:
        candidates = [
            p
            for p in candidates
            if not any(fnmatch(str(p.relative_to(tasks_root)), pattern) for pattern in task_selector.exclude_patterns)
        ]

    return sorted(candidates)
