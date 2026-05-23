# ABOUTME: Task-level remediation configuration read from [remediation] table in task.toml.
# ABOUTME: Lets tasks opt out of remediation or declare their own iteration/target defaults.

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RemediationTaskConfig:
    """Per-task remediation settings from task.toml."""

    enabled: bool = True
    max_iterations: int | None = None
    target_reward: float | None = None


def parse_remediation_config(task_toml_dict: Mapping[str, Any]) -> RemediationTaskConfig:
    """Parse [remediation] table from a task.toml dict.

    Returns default (enabled=True, overrides None) when the table is absent
    or empty. An explicit `enabled = false` disables remediation for the task.
    """
    rem = task_toml_dict.get("remediation", {})
    if not isinstance(rem, Mapping):
        return RemediationTaskConfig()
    return RemediationTaskConfig(
        enabled=bool(rem.get("enabled", True)),
        max_iterations=rem.get("max_iterations"),
        target_reward=rem.get("target_reward"),
    )
