# ABOUTME: Classifies aec-bench tasks by the Prime/verifiers harness they need.
# ABOUTME: Keeps exporter mode selection explicit before generating environment code.

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from aec_bench.contracts.task_definition import TaskDefinition


class PrimeHarnessKind(StrEnum):
    SINGLE_TURN = "single_turn"
    TOOL = "tool"
    STATEFUL_WORKSPACE = "stateful_workspace"
    RLM_POLICY = "rlm_policy"
    LAMBDA_RLM_POLICY = "lambda_rlm_policy"


@dataclass(frozen=True)
class PrimeHarnessClassification:
    kind: PrimeHarnessKind
    reasons: list[str]


def classify_prime_harness(task: TaskDefinition, task_dir: Path) -> PrimeHarnessClassification:
    """Select the smallest Prime harness that can represent a task."""
    if (task_dir / "lambda-rlm.toml").exists():
        return PrimeHarnessClassification(
            kind=PrimeHarnessKind.LAMBDA_RLM_POLICY,
            reasons=["lambda-rlm.toml present"],
        )

    if (task_dir / "rlm.toml").exists():
        return PrimeHarnessClassification(
            kind=PrimeHarnessKind.RLM_POLICY,
            reasons=["rlm.toml present"],
        )

    workspace_reasons = _workspace_reasons(task)
    if workspace_reasons:
        return PrimeHarnessClassification(
            kind=PrimeHarnessKind.STATEFUL_WORKSPACE,
            reasons=workspace_reasons,
        )

    if task.environment.tools:
        return PrimeHarnessClassification(
            kind=PrimeHarnessKind.TOOL,
            reasons=["task declares tool: " + tool.name for tool in task.environment.tools],
        )

    return PrimeHarnessClassification(
        kind=PrimeHarnessKind.SINGLE_TURN,
        reasons=["no task tools or workspace policy detected"],
    )


def _workspace_reasons(task: TaskDefinition) -> list[str]:
    reasons: list[str] = []
    workspace_tool_names = {"bash"}
    for tool in task.environment.tools:
        if tool.name in workspace_tool_names:
            reasons.append(f"workspace-affecting tool declared: {tool.name}")

    if task.environment.compose_file is not None:
        reasons.append(f"compose file declared: {task.environment.compose_file}")
    if task.environment.manifest is not None:
        reasons.append(f"environment manifest declared: {task.environment.manifest}")
    return reasons
