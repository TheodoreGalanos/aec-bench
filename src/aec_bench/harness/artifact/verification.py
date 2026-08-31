# ABOUTME: Runs task-owned artifact verification and maps process truth to evaluation.
# ABOUTME: Keeps verifier staging, receipts, feedback, and redacted execution evidence at one boundary.

from __future__ import annotations

import json
import shutil
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.trial_extensions import VerifierExecutionReceipt
from aec_bench.contracts.trial_record import EvaluationStatus
from aec_bench.evaluation.verifier_outcome import map_verifier_execution
from aec_bench.harness.artifact.values import TaskAttempt
from aec_bench.harness.artifact.workspace_port import resolve_workspace_path
from aec_bench.harness.local_runtime import stage_verifier_assets
from aec_bench.harness.verifier_execution import (
    VERIFIER_PROTOCOL_VERSION,
    execute_verifier,
    localise_staged_verifier_paths,
)
from aec_bench.tasks.instance import ResolvedTaskInstance

_VERIFIER_RETRY_PROMPT = "verifier_retry_prompt.md"
DEFAULT_VERIFIER_RETRY_TARGET_REWARD = 1.0
_VERIFIER_RETRY_ARTIFACT_SUFFIXES = (
    "_record.json",
    "_decision.json",
    "_readback_check.json",
    "_notice.json",
    "_report.json",
    "_marker.json",
)
_VERIFIER_RETRY_EXCLUDED_PREFIXES = ("expected_", "input_", "prior_", "source_")


def _read_optional_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def should_run_verifier_feedback_retry(
    workspace: Path,
    *,
    reward: float | None,
    target_reward: float,
) -> bool:
    return reward is not None and reward < target_reward and (workspace / _VERIFIER_RETRY_PROMPT).is_file()


def build_verifier_retry_instruction(
    *, workspace: Path, output_path: Path, base_instruction: str, reward: float
) -> str:
    verifier_dir = workspace / "logs" / "verifier"
    retry_instruction = _read_optional_text(workspace / "verifier_retry_instruction.md").strip()
    governing_instruction = retry_instruction or base_instruction.strip()
    parts = [
        governing_instruction,
        "---",
        "# Verifier Feedback Retry",
        _read_optional_text(workspace / _VERIFIER_RETRY_PROMPT).strip(),
        f"Previous verifier reward: `{reward:.4f}`.",
        "The previous output was:",
        "```markdown",
        _read_optional_text(output_path).strip(),
        "```",
    ]
    feedback = _read_optional_text(verifier_dir / "feedback.md").strip()
    details = _read_optional_text(verifier_dir / "details.json").strip()
    if feedback:
        parts.extend(("The verifier feedback was:", "```markdown", feedback, "```"))
    if details:
        parts.extend(("The verifier detail scores were:", "```json", details, "```"))
    parts.append(
        "Repair the workspace now. You may overwrite the required output and any required side-effect files. "
        "Do not merely describe files that should be written."
    )
    return "\n\n".join(part for part in parts if part)


def _is_verifier_retry_side_effect(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix == ".json"
        and not path.name.startswith(_VERIFIER_RETRY_EXCLUDED_PREFIXES)
        and path.name.endswith(_VERIFIER_RETRY_ARTIFACT_SUFFIXES)
    )


def _archive_verifier_retry_attempt(workspace: Path, output_path: Path, attempt_name: str) -> Path:
    archive_dir = workspace / "logs" / "verifier" / "attempts" / attempt_name
    archive_dir.mkdir(parents=True, exist_ok=True)
    for relative in (
        "agent_result.json",
        "trajectory.jsonl",
        "conversation.jsonl",
        "prime-events.jsonl",
        "prime-stderr.log",
        "prime-run.json",
        "logs/verifier/reward.json",
        "logs/verifier/details.json",
        "logs/verifier/feedback.md",
    ):
        source = workspace / relative
        if source.is_file():
            shutil.copy2(source, archive_dir / source.name)
    if output_path.is_file():
        shutil.copy2(output_path, archive_dir / output_path.name)
    prime_sessions = workspace / "logs" / "prime" / "sessions"
    if prime_sessions.is_dir():
        shutil.copytree(prime_sessions, archive_dir / "prime-sessions", dirs_exist_ok=True)
    for source in sorted(workspace.iterdir()):
        if _is_verifier_retry_side_effect(source):
            artifact_dir = archive_dir / "artifacts"
            artifact_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, artifact_dir / source.name)
    return archive_dir


def prepare_verifier_retry_workspace(*, workspace: Path, output_path: Path, attempt_name: str) -> Path:
    archive_dir = _archive_verifier_retry_attempt(workspace, output_path, attempt_name)
    output_path.unlink(missing_ok=True)
    return archive_dir


def write_verifier_retry_summary(workspace: Path, payload: Mapping[str, object]) -> None:
    retry_path = workspace / "logs" / "verifier" / "retry.json"
    retry_path.parent.mkdir(parents=True, exist_ok=True)
    retry_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def evaluate_selected_attempt(
    *, task: ResolvedTaskInstance, attempt: TaskAttempt, verify: bool
) -> tuple[EvaluationResult, float | None, VerifierExecutionReceipt | None, EvaluationStatus | None]:
    output_path = resolve_workspace_path(attempt.workspace, task.task.verifier.expected_output_path)
    verifier_seconds = None
    verifier_receipt = None
    reward_payload: dict[str, Any] | None = None
    details_payload: dict[str, Any] | None = None
    if verify:
        stage_verifier_assets(task.instance_dir, attempt.workspace)
        started = time.monotonic()
        transform_version = localise_staged_verifier_paths(
            workspace=attempt.workspace,
            verifier_root=attempt.workspace / "tests",
        )
        execution = execute_verifier(
            verifier_path=attempt.workspace / task.task.verifier.script,
            workspace=attempt.workspace,
            output_path=output_path,
            reward_path=resolve_workspace_path(attempt.workspace, task.task.verifier.reward_path),
            details_path=(
                None
                if task.task.verifier.details_path is None
                else resolve_workspace_path(attempt.workspace, task.task.verifier.details_path)
            ),
            verifier_key=f"{task.task.task_id}/verifier",
            verifier_version=VERIFIER_PROTOCOL_VERSION,
            runtime_transform_version=transform_version,
        )
        verifier_seconds = time.monotonic() - started
        verifier_receipt = execution.receipt
        reward_payload = execution.reward_payload
        details_payload = execution.details_payload
    verifier_completed = verifier_receipt is not None and verifier_receipt.completed
    output_present = output_path.is_file()
    valid_output = attempt.status is AgentOutputStatus.COMPLETED and output_present
    reward = 0.0
    breakdown = details_payload
    errors: list[str] = []
    if verifier_completed and reward_payload is not None:
        reward = float(reward_payload["reward"])
    elif not verify:
        errors.append("verification was disabled")
    elif verifier_receipt is not None:
        errors.append(verifier_receipt.failure_message or "verifier did not complete successfully")
    else:
        errors.append("verifier did not run")
    if not valid_output and reward != 0.0:
        errors.append("verifier reward was ignored because the selected attempt has no valid output")
        reward = 0.0
    evaluation = EvaluationResult(
        reward=reward,
        validity=ValidityCheck(
            output_parseable=valid_output,
            schema_valid=valid_output,
            verifier_completed=verifier_completed,
            errors=errors,
        ),
        breakdown=breakdown,
    )
    if verifier_receipt is not None:
        mapped = map_verifier_execution(
            receipt=verifier_receipt,
            evaluation=evaluation,
            expected_verifier_key=f"{task.task.task_id}/verifier",
            expected_verifier_version=VERIFIER_PROTOCOL_VERSION,
        )
        return mapped.evaluation, verifier_seconds, verifier_receipt, mapped.status
    return evaluation, verifier_seconds, verifier_receipt, None


def with_reviewer_summary(evaluation: EvaluationResult, workspace: Path) -> EvaluationResult:
    summary_path = workspace / "logs" / "reviewer" / "summary.json"
    if not summary_path.is_file():
        return evaluation
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    breakdown = dict(evaluation.breakdown or {})
    breakdown["llm_reviewer"] = payload
    return evaluation.model_copy(update={"breakdown": breakdown})


__all__ = (
    "DEFAULT_VERIFIER_RETRY_TARGET_REWARD",
    "build_verifier_retry_instruction",
    "evaluate_selected_attempt",
    "prepare_verifier_retry_workspace",
    "should_run_verifier_feedback_retry",
    "with_reviewer_summary",
    "write_verifier_retry_summary",
)
