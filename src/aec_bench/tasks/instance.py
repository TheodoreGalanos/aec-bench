# ABOUTME: Execution-ready task-instance resolution helpers for aec-bench Python.
# ABOUTME: Converts a task definition plus an instance directory into harness-facing paths.

from dataclasses import dataclass
from pathlib import Path

from aec_bench.contracts.task_definition import TaskDefinition


@dataclass(frozen=True)
class ResolvedTaskInstance:
    task: TaskDefinition
    instance_dir: Path
    environment_dockerfile: Path
    environment_compose_file: Path | None
    environment_manifest: Path | None
    verifier_script: Path


def resolve_instance_paths(task: TaskDefinition, instance_dir: Path) -> ResolvedTaskInstance:
    compose_file = task.environment.compose_file
    manifest = task.environment.manifest

    return ResolvedTaskInstance(
        task=task,
        instance_dir=instance_dir,
        environment_dockerfile=instance_dir / task.environment.dockerfile,
        environment_compose_file=instance_dir / compose_file if compose_file is not None else None,
        environment_manifest=instance_dir / manifest if manifest is not None else None,
        verifier_script=instance_dir / task.verifier.script,
    )
