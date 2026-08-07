# ABOUTME: Local run import logic for building TrialRecords without Harbor.
# ABOUTME: Constructs validated records from local run artifacts and task definitions.

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.pricing import estimate_cost_usd
from aec_bench.contracts.trial_record import (
    AgentReference,
    Completeness,
    CostRecord,
    EnvironmentSnapshot,
    InputRecord,
    OutputRecord,
    TaskReference,
    TimingRecord,
    TrialRecord,
)
from aec_bench.tasks.loader import load_task_definition

# Artifact filenames we look for when copying from a local run directory.
ARTIFACT_FILENAMES: list[str] = [
    "agent_result.json",
    "output.md",
    "trajectory.jsonl",
    "conversation.jsonl",
    "symbolic_state.json",
    ".scratchpad.json",
    "model_reasoning.jsonl",
    "prime-events.jsonl",
    "prime-stderr.log",
    "prime-run.json",
]

ARTIFACT_DIRECTORIES: tuple[Path, ...] = (Path("logs/prime/sessions"),)


def _optional_non_negative_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _estimated_cost_if_usage_known(
    model: str,
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    cache_read_tokens: int | None,
    cache_write_tokens: int | None,
) -> float | None:
    if None in (input_tokens, output_tokens, cache_read_tokens, cache_write_tokens):
        return None
    assert input_tokens is not None
    assert output_tokens is not None
    assert cache_read_tokens is not None
    assert cache_write_tokens is not None
    return estimate_cost_usd(
        model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
    )


def build_trial_record_from_workspace(
    *,
    workspace_dir: Path,
    trial_id: str,
    experiment_id: str,
    task_id: str,
    model: str,
    adapter: str,
    instruction: str,
    timing: TimingRecord | None = None,
) -> TrialRecord:
    """Build a TrialRecord from workspace artifacts after an adapter run.

    Reads agent_result.json, verifier outputs (reward.json / details.json),
    and optional conversation/trajectory files from the workspace directory.
    Missing verifier artifacts are handled gracefully by setting reward=0.0
    and verifier_completed=False.
    """
    # --- agent_result.json ---------------------------------------------------
    agent_result_path = workspace_dir / "agent_result.json"
    agent_result: dict[str, Any] | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cache_read: int | None = None
    cache_write: int | None = None
    status_str: str = "error"

    if agent_result_path.exists():
        agent_result = json.loads(agent_result_path.read_text(encoding="utf-8"))
        tokens_in = _optional_non_negative_int(agent_result, "input_tokens")
        tokens_out = _optional_non_negative_int(agent_result, "output_tokens")
        cache_read = _optional_non_negative_int(agent_result, "cache_read_tokens")
        cache_write = _optional_non_negative_int(agent_result, "cache_write_tokens")
        status_str = agent_result.get("status", "error")

    # Legacy rlm_script.py writes "ok"; library adapters write AgentOutputStatus enum values.
    agent_status = (
        AgentOutputStatus.COMPLETED
        if status_str in ("ok", AgentOutputStatus.COMPLETED.value)
        else AgentOutputStatus.FAILED
    )

    # --- verifier outputs ----------------------------------------------------
    reward_path = workspace_dir / "logs" / "verifier" / "reward.json"
    details_path = workspace_dir / "logs" / "verifier" / "details.json"

    verifier_completed = reward_path.exists()
    reward = 0.0
    breakdown: dict[str, Any] | None = None

    if verifier_completed:
        reward_data = json.loads(reward_path.read_text(encoding="utf-8"))
        reward = float(reward_data["reward"])
        if details_path.exists():
            breakdown = json.loads(details_path.read_text(encoding="utf-8"))
    reviewer_summary = _read_reviewer_summary(workspace_dir / "logs" / "reviewer" / "summary.json")
    if reviewer_summary is not None:
        breakdown = dict(breakdown or {})
        breakdown["llm_reviewer"] = reviewer_summary

    validity = ValidityCheck(
        output_parseable=agent_status == AgentOutputStatus.COMPLETED,
        schema_valid=agent_status == AgentOutputStatus.COMPLETED,
        verifier_completed=verifier_completed,
    )
    evaluation = EvaluationResult(reward=reward, validity=validity, breakdown=breakdown)

    # --- optional artifact paths ---------------------------------------------
    conversation_path_val: str | None = None
    conversation_file = workspace_dir / "conversation.jsonl"
    if conversation_file.exists():
        conversation_path_val = str(conversation_file)

    trajectory_path_val: str | None = None
    trajectory_file = workspace_dir / "trajectory.jsonl"
    if trajectory_file.exists():
        trajectory_path_val = str(trajectory_file)

    # --- cost record ---------------------------------------------------------
    recorded_model = (
        str(agent_result.get("resolved_model") or agent_result.get("model") or model)
        if agent_result is not None
        else model
    )
    cost_usd = _estimated_cost_if_usage_known(
        recorded_model,
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
    )

    cost: CostRecord | None = None
    model_calls = _optional_non_negative_int(agent_result, "model_calls") if agent_result is not None else None
    if any(value is not None for value in (model_calls, tokens_in, tokens_out, cache_read, cache_write)):
        cost = CostRecord(
            model_calls=model_calls,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            estimated_cost_usd=cost_usd,
        )

    # --- timing --------------------------------------------------------------
    effective_timing = timing if timing is not None else TimingRecord(total_seconds=0.0)

    adapter_configuration = agent_result.get("adapter_configuration", {}) if agent_result is not None else {}
    safe_adapter_configuration = dict(adapter_configuration) if isinstance(adapter_configuration, dict) else {}
    safe_adapter_configuration.update({"source": "run-local", "model_requested": model})

    return TrialRecord(
        trial_id=trial_id,
        experiment_id=experiment_id,
        timestamp=datetime.now(UTC),
        task=TaskReference(task_id=task_id, task_revision="local"),
        agent=AgentReference(
            adapter=adapter,
            model=recorded_model,
            configuration=safe_adapter_configuration,
        ),
        environment=EnvironmentSnapshot(
            runtime_image="local",
            compute_backend="local",
        ),
        inputs=InputRecord(instruction=instruction),
        outputs=OutputRecord(
            agent_output=AgentOutput(
                status=agent_status,
                output_path="output.md",
                output_format="markdown",
                error_message=None if agent_status == AgentOutputStatus.COMPLETED else status_str,
            ),
            conversation_path=conversation_path_val,
            trajectory_path=trajectory_path_val,
            agent_result=(
                None
                if agent_result is None
                else {
                    "status": status_str,
                    "failure_kind": agent_result.get("failure_kind"),
                    "provider_error": agent_result.get("provider_error"),
                    "output_source": agent_result.get("output_source"),
                }
            ),
            terminated=agent_status is AgentOutputStatus.COMPLETED,
        ),
        evaluation=evaluation,
        timing=effective_timing,
        cost=cost,
        completeness=Completeness.PARTIAL,
    )


def find_tasks_root(task_dir: Path) -> Path:
    """Walk upward from *task_dir* to find the nearest ``tasks/`` ancestor."""
    candidate = task_dir
    while candidate != candidate.parent:
        if candidate.name == "tasks":
            return candidate
        candidate = candidate.parent
    # Fallback: treat the parent as tasks root (task_dir is one level inside)
    return task_dir.parent


def copy_artifacts(
    run_path: Path,
    artifact_dir: Path,
) -> list[str]:
    """Copy recognised artifact files from *run_path* into *artifact_dir*.

    Returns the list of filenames that were successfully copied.
    """
    artifact_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for fname in ARTIFACT_FILENAMES:
        src = run_path / fname
        if src.exists():
            shutil.copy2(src, artifact_dir / fname)
            copied.append(fname)
    for relative_dir in ARTIFACT_DIRECTORIES:
        source_dir = run_path / relative_dir
        if not source_dir.exists():
            continue
        for src in sorted(source_dir.rglob("*")):
            if not src.is_file():
                continue
            relative_file = src.relative_to(run_path)
            dest = artifact_dir / relative_file
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            copied.append(relative_file.as_posix())
    return copied


def _read_reviewer_summary(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def build_trial_record(
    *,
    run_path: Path,
    task_dir: Path,
    experiment_id: str,
    trial_id: str,
    artifact_dir: Path,
    repo_root: Path,
) -> TrialRecord:
    """Construct a TrialRecord from a local run directory and task definition.

    This is the pure-logic core, kept separate from CLI/IO concerns so that
    tests can exercise it directly.
    """
    agent_result_file = run_path / "agent_result.json"
    agent_result: dict[str, Any] = json.loads(agent_result_file.read_text(encoding="utf-8"))

    tasks_root = find_tasks_root(task_dir)
    task = load_task_definition(task_dir, tasks_root)

    requested_model: str = agent_result.get("model", "unknown")
    model: str = agent_result.get("resolved_model") or requested_model
    adapter_kind: str = agent_result.get("adapter", "rlm")
    input_tokens = _optional_non_negative_int(agent_result, "input_tokens")
    output_tokens = _optional_non_negative_int(agent_result, "output_tokens")
    cache_read = _optional_non_negative_int(agent_result, "cache_read_tokens")
    cache_write = _optional_non_negative_int(agent_result, "cache_write_tokens")

    cost = _estimated_cost_if_usage_known(
        model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
    )

    status_str: str = agent_result.get("status", "error")
    # Legacy rlm_script.py writes "ok"; library adapters write AgentOutputStatus enum values.
    agent_status = (
        AgentOutputStatus.COMPLETED
        if status_str in ("ok", AgentOutputStatus.COMPLETED.value)
        else AgentOutputStatus.FAILED
    )

    # Build repo-root-relative POSIX paths for portability (same convention
    # as the Harbor import).
    def _rel_posix(p: Path) -> str | None:
        if not p.exists():
            return None
        try:
            return p.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            return str(p)

    output_md = artifact_dir / "output.md"
    trajectory = artifact_dir / "trajectory.jsonl"
    conversation = artifact_dir / "conversation.jsonl"

    adapter_configuration = agent_result.get("adapter_configuration", {})
    safe_adapter_configuration = dict(adapter_configuration) if isinstance(adapter_configuration, dict) else {}
    safe_adapter_configuration.update(
        {
            "source": "import-local",
            "run_dir": str(run_path),
            "model_requested": requested_model,
            "output_source": agent_result.get("output_source"),
            "compaction_count": agent_result.get("compaction_count", 0),
        }
    )
    model_calls = _optional_non_negative_int(agent_result, "model_calls")
    has_usage = any(value is not None for value in (model_calls, input_tokens, output_tokens, cache_read, cache_write))

    return TrialRecord(
        trial_id=trial_id,
        experiment_id=experiment_id,
        dataset_id=None,
        timestamp=datetime.now(UTC),
        task=TaskReference(
            task_id=task.task_id,
            task_revision="local",
            visibility=task.visibility,
        ),
        agent=AgentReference(
            adapter=adapter_kind,
            model=model,
            adapter_revision=None,
            configuration=safe_adapter_configuration,
        ),
        environment=EnvironmentSnapshot(
            runtime_image="local",
            compute_backend="local",
            tool_versions=None,
        ),
        inputs=InputRecord(
            instruction=task.instruction,
            system_prompt=None,
            input_files=None,
        ),
        outputs=OutputRecord(
            agent_output=AgentOutput(
                status=agent_status,
                output_path="output.md",
                output_format="markdown",
                error_message=None if agent_status == AgentOutputStatus.COMPLETED else status_str,
            ),
            raw_output_path=_rel_posix(output_md),
            conversation_path=_rel_posix(conversation),
            trajectory_path=_rel_posix(trajectory),
            agent_result={
                "turns_used": agent_result.get("turns_used"),
                "max_turns": agent_result.get("max_turns"),
                "harbor_status": status_str,
                "output_source": agent_result.get("output_source"),
                "compaction_count": agent_result.get("compaction_count", 0),
                "failure_kind": agent_result.get("failure_kind"),
                "provider_error": agent_result.get("provider_error"),
            },
            terminated=agent_status is AgentOutputStatus.COMPLETED,
        ),
        evaluation=EvaluationResult(
            reward=0.0,
            validity=ValidityCheck(
                output_parseable=agent_status == AgentOutputStatus.COMPLETED,
                schema_valid=agent_status == AgentOutputStatus.COMPLETED,
                verifier_completed=False,
                errors=["local run — not verified"],
            ),
        ),
        timing=TimingRecord(
            total_seconds=0.0,
            agent_seconds=None,
            setup_seconds=None,
            verification_seconds=None,
        ),
        cost=(
            CostRecord(
                model_calls=model_calls,
                tokens_in=input_tokens,
                tokens_out=output_tokens,
                cache_read_tokens=cache_read,
                cache_write_tokens=cache_write,
                estimated_cost_usd=cost,
            )
            if has_usage
            else None
        ),
        completeness=Completeness.PARTIAL,
    )
