# ABOUTME: Classifies aec-bench tasks by the Prime/verifiers harness they need.
# ABOUTME: Keeps exporter mode selection explicit before generating environment code.

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from aec_bench.contracts.task_definition import TaskDefinition


class PrimeHarnessKind(StrEnum):
    SINGLE_TURN = "single_turn"
    STATEFUL_WORKSPACE = "stateful_workspace"


def classify_prime_harness(task: TaskDefinition, task_dir: Path) -> PrimeHarnessKind:
    """Select the smallest Prime harness that can represent a task."""
    policy_files = (task_dir / "rlm.toml", task_dir / "lambda-rlm.toml")
    if (
        any(path.is_file() for path in policy_files)
        or bool(task.environment.tools)
        or task.environment.compose_file is not None
        or task.environment.manifest is not None
    ):
        return PrimeHarnessKind.STATEFUL_WORKSPACE
    return PrimeHarnessKind.SINGLE_TURN
