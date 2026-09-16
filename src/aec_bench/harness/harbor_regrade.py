# ABOUTME: Runs Harbor verifier-only assessments against retained local trial artifacts.
# ABOUTME: Copies and hashes assessment inputs without changing source trials or the execution ledger.

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import tomllib
from pathlib import Path

from harbor.models.task.task import Task  # type: ignore[import-untyped]
from harbor.models.trial.config import (  # type: ignore[import-untyped]
    EnvironmentConfig,
    SourceTrialConfig,
    TaskConfig,
    TrialConfig,
)
from harbor.models.trial.result import TrialResult  # type: ignore[import-untyped]
from harbor.trial.regrade import check_task_regradable, read_artifact_manifest  # type: ignore[import-untyped]
from harbor.trial.trial import Trial  # type: ignore[import-untyped]


def plan_regrade(
    *,
    source_trial: Path,
    task_dir: Path,
    output_dir: Path,
    environment: EnvironmentConfig | None = None,
) -> TrialConfig:
    """Validate local input structure without creating files or environments.

    Harbor checks complete artifact coverage before it starts verification.
    The revised task declares the required inputs; the original execution's
    optional diagnostic artifacts do not become regrade requirements.
    """
    source_trial = source_trial.expanduser().resolve()
    task_dir = task_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    for root in (source_trial, task_dir):
        if output_dir.is_relative_to(root) or root.is_relative_to(output_dir):
            raise ValueError("Regrade output must be separate from the source trial and revised task.")
    if output_dir.exists():
        raise FileExistsError(f"Regrade output already exists: {output_dir}")

    # Inspect metadata before reading or copying task-owned private material.
    metadata = tomllib.loads((task_dir / "task.toml").read_text(encoding="utf-8")).get("metadata", {})
    if metadata.get("visibility") != "public":
        raise ValueError("Regrading currently requires a task with metadata.visibility = 'public'.")
    task = Task(task_dir)
    source = TrialResult.model_validate_json((source_trial / "result.json").read_text(encoding="utf-8"))
    if source.finished_at is None:
        raise ValueError("The source trial is not finished.")
    if source.config.source_trial is not None:
        raise ValueError("Select the original execution trial, not an earlier regrade.")
    if source.task_name != task.name:
        raise ValueError(f"Task name mismatch: source ran {source.task_name!r}; revised task is {task.name!r}.")
    if source.step_results or task.has_steps or (source_trial / "steps").exists():
        raise ValueError("Regrading currently supports single-step artifact trials only.")
    task_error = check_task_regradable(task_dir)
    if task_error:
        raise ValueError(task_error)
    read_artifact_manifest(source_trial)
    _input_digest(task_dir)
    for path in _source_paths(source_trial):
        _input_digest(path)

    return TrialConfig(
        task=TaskConfig(path=task_dir, source=source.source),
        trials_dir=output_dir,
        trial_name="verification",
        agent=source.config.agent,
        environment=environment or EnvironmentConfig(type="docker"),
        source_trial=SourceTrialConfig(action="regrade", type="local", path=source_trial, trial_id=source.id),
    )


async def run_regrade(config: TrialConfig) -> TrialResult:
    """Run a planned assessment with Harbor's native regrade lifecycle.

    A fresh output directory holds the input copies and Harbor's result,
    lock, verifier logs, and replayed artifacts. Nothing is imported into
    the execution ledger. Failed verification remains a failed assessment.
    """
    if config.source_trial is None or config.source_trial.path is None or config.task.path is None:
        raise ValueError("Regrade requires local source and task paths.")
    source_dir = config.source_trial.path
    task_dir = config.task.path
    output_dir = config.trials_dir
    output_dir.mkdir(parents=True, exist_ok=False)
    retained_source = output_dir / "source"
    retained_source.mkdir()
    retained_task = output_dir / "task" / task_dir.name
    source_digests: dict[str, str] = {}
    for path in _source_paths(source_dir):
        source_digests[path.name] = _copy_input(path, retained_source / path.name)
    task_digest = _copy_input(task_dir, retained_task)
    (output_dir / "inputs.json").write_text(
        json.dumps(
            {
                "source_trial_id": str(config.source_trial.trial_id),
                "source_path": str(source_dir),
                "source_sha256": source_digests,
                "task_path": str(task_dir),
                "task_sha256": task_digest,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    retained_config = config.model_copy(
        deep=True,
        update={
            "task": config.task.model_copy(update={"path": retained_task}),
            "source_trial": config.source_trial.model_copy(update={"path": retained_source}),
        },
    )
    trial = await Trial.create(retained_config)
    return await trial.run()


def _source_paths(root: Path) -> list[Path]:
    # Do not retain backend work directories or provisioned environment state.
    return [
        root / name
        for name in ("result.json", "config.json", "lock.json", "agent", "artifacts")
        if (root / name).exists() or (root / name).is_symlink()
    ]


def _copy_input(source: Path, target: Path) -> str:
    digest = _input_digest(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target, symlinks=True)
    else:
        shutil.copy2(source, target, follow_symlinks=False)
    if _input_digest(target) != digest or _input_digest(source) != digest:
        raise ValueError(f"Regrade input changed during retention: {source}")
    return digest


def _input_digest(root: Path) -> str:
    """Hash names, file bytes, empty directories, and permissions; reject links."""
    entries: dict[str, tuple[int, str | None]] = {}
    for path in [root, *sorted(root.rglob("*"))] if root.is_dir() else [root]:
        mode = path.lstat().st_mode
        if stat.S_ISREG(mode):
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
        elif stat.S_ISDIR(mode):
            digest = None
        else:
            raise ValueError(f"Regrade inputs must contain regular files and directories only: {path}")
        entries[path.relative_to(root).as_posix()] = (stat.S_IMODE(mode), digest)
    return hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
