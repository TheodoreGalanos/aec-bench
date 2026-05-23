# ABOUTME: Promotion-gate helpers for deciding whether a task is ready to move toward active use.
# ABOUTME: Reports unresolved placeholders, contract mismatches, and missing execution assets.

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.contracts.validators import normalize_workspace_path
from aec_bench.tasks.loader import extract_workspace_output_paths


class PromotionCheckResult(StrEnum):
    READY = "ready"
    UNRESOLVED_INSTRUCTION = "unresolved_instruction"
    OUTPUT_PATH_MISMATCH = "output_path_mismatch"
    MISSING_DOCKERFILE = "missing_dockerfile"
    MISSING_COMPOSE_FILE = "missing_compose_file"
    MISSING_MANIFEST = "missing_manifest"
    MISSING_TOOL_SOURCE = "missing_tool_source"
    MISSING_VERIFIER_SCRIPT = "missing_verifier_script"


@dataclass(frozen=True)
class PromotionReadinessReport:
    issues: list[PromotionCheckResult]

    @property
    def ready(self) -> bool:
        return not self.issues


def evaluate_promotion_readiness(
    task: TaskDefinition,
    instance_dir: Path | None = None,
) -> PromotionReadinessReport:
    issues: list[PromotionCheckResult] = []

    if "{" in task.instruction and "}" in task.instruction:
        issues.append(PromotionCheckResult.UNRESOLVED_INSTRUCTION)

    if not _instruction_matches_expected_output(task):
        issues.append(PromotionCheckResult.OUTPUT_PATH_MISMATCH)

    if instance_dir is not None:
        _append_missing_asset_issues(issues, task, instance_dir)

    return PromotionReadinessReport(issues=issues)


def _instruction_matches_expected_output(task: TaskDefinition) -> bool:
    output_paths = extract_workspace_output_paths(task.instruction)
    if not output_paths:
        return False

    return normalize_workspace_path(output_paths[-1]) == normalize_workspace_path(task.verifier.expected_output_path)


def _append_missing_asset_issues(
    issues: list[PromotionCheckResult],
    task: TaskDefinition,
    instance_dir: Path,
) -> None:
    if not (instance_dir / task.environment.dockerfile).exists():
        issues.append(PromotionCheckResult.MISSING_DOCKERFILE)

    if task.environment.compose_file is not None and not (instance_dir / task.environment.compose_file).exists():
        issues.append(PromotionCheckResult.MISSING_COMPOSE_FILE)

    if task.environment.manifest is not None and not (instance_dir / task.environment.manifest).exists():
        issues.append(PromotionCheckResult.MISSING_MANIFEST)

    if any(not (instance_dir / tool.source).exists() for tool in task.environment.tools):
        issues.append(PromotionCheckResult.MISSING_TOOL_SOURCE)

    if not (instance_dir / task.verifier.script).exists():
        issues.append(PromotionCheckResult.MISSING_VERIFIER_SCRIPT)
