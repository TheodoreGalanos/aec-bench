# ABOUTME: Runs one-pass local baselines over generated task-ecology suites.
# ABOUTME: Writes resumable JSONL rows and aggregate summaries for calibration.

from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from aec_bench.contracts.evolution import WorkspaceSnapshot
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evolution.backends.local import LocalSolver

DEFAULT_BASELINE_PROMPT = (
    "You are an expert engineering agent. Solve the task carefully, use the available "
    "tools when helpful, and verify your work before producing the final answer.\n"
)
DEFAULT_BASELINE_MODEL = "claude-sonnet-4-20250514"
DEFAULT_BASELINE_ADAPTER = "tool_loop"
DEFAULT_EXPERIMENT_ID = "task-ecology-exp1-baseline"
DEFAULT_SCORE_THRESHOLD = 0.85


@dataclass(frozen=True)
class BaselineTask:
    task_dir: Path
    task_id: str
    suite: str
    domain: str
    category: str
    template: str
    instance: str
    difficulty: str


def discover_baseline_tasks(
    *,
    tasks_root: Path,
    experiment: str,
    suites: tuple[str, ...] = ("fixed", "population"),
) -> list[BaselineTask]:
    """Find generated task directories and attach task-ecology metadata."""
    experiment_root = tasks_root / "generated" / experiment
    discovered: list[BaselineTask] = []
    for task_toml in sorted(experiment_root.rglob("task.toml")):
        task_dir = task_toml.parent
        relative_parts = task_dir.relative_to(experiment_root).parts
        if len(relative_parts) < 5:
            continue
        suite, domain, category, template = relative_parts[:4]
        if suite not in suites:
            continue
        metadata = _read_task_metadata(task_toml)
        discovered.append(
            BaselineTask(
                task_dir=task_dir,
                task_id=task_dir.relative_to(tasks_root).as_posix(),
                suite=suite,
                domain=str(metadata.get("domain") or domain),
                category=category,
                template=str(metadata.get("template") or template),
                instance=relative_parts[-1],
                difficulty=str(metadata.get("difficulty") or "unknown"),
            )
        )
    return discovered


def run_baseline_dataset(
    *,
    tasks: list[BaselineTask],
    output_dir: Path,
    model: str = DEFAULT_BASELINE_MODEL,
    adapter: str = DEFAULT_BASELINE_ADAPTER,
    experiment_id: str = DEFAULT_EXPERIMENT_ID,
    score_threshold: float = DEFAULT_SCORE_THRESHOLD,
    workspace_root: Path | None = None,
    prompt: str = DEFAULT_BASELINE_PROMPT,
    timeout: int = 1800,
) -> dict[str, Any]:
    """Run each task once and write a row immediately after completion."""
    validate_baseline_environment(model)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows_path = output_dir / "baseline.jsonl"
    summary_path = output_dir / "summary.yaml"
    snapshot = WorkspaceSnapshot(
        system_prompt=prompt,
        skills=[],
        workspace_version="baseline",
    )

    completed_ids = _completed_task_ids(rows_path)
    rows: list[dict[str, Any]] = []
    if rows_path.exists():
        rows.extend(_read_rows(rows_path))

    for index, task in enumerate(tasks, start=1):
        if task.task_id in completed_ids:
            continue
        print(f"[{index}/{len(tasks)}] {task.task_id}", flush=True)
        solver = LocalSolver(
            task_dirs=[task.task_dir],
            model=model,
            experiment_id=experiment_id,
            adapter=adapter,
            timeout=timeout,
            workspace_root=workspace_root,
        )
        try:
            records = solver(snapshot, batch_size=1)
            row = (
                baseline_row_from_record(
                    records[0],
                    task=task,
                    score_threshold=score_threshold,
                )
                if records
                else failed_row(task)
            )
        finally:
            solver.cleanup()
        rows.append(row)
        completed_ids.add(task.task_id)
        with rows_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
        summary = summarise_baseline_rows(rows, score_threshold=score_threshold)
        summary_path.write_text(yaml.safe_dump(summary, sort_keys=False), encoding="utf-8")
        print(
            f"  reward={row['reward']} status={row['agent_status']} below_threshold={row['below_threshold']}",
            flush=True,
        )

    return summarise_baseline_rows(rows, score_threshold=score_threshold)


def baseline_row_from_record(
    record: TrialRecord,
    *,
    task: BaselineTask,
    score_threshold: float = DEFAULT_SCORE_THRESHOLD,
) -> dict[str, Any]:
    """Convert a local TrialRecord into a compact calibration dataset row."""
    agent_result = record.outputs.agent_result or {}
    reward = record.evaluation.reward
    breakdown = record.evaluation.breakdown or {}
    return {
        "task_id": task.task_id,
        "suite": task.suite,
        "domain": task.domain,
        "category": task.category,
        "template": task.template,
        "instance": task.instance,
        "difficulty": task.difficulty,
        "trial_id": record.trial_id,
        "reward": reward,
        "below_threshold": reward < score_threshold,
        "field_scores": breakdown,
        "verifier_completed": record.evaluation.validity.verifier_completed,
        "agent_status": agent_result.get("status"),
        "model": record.agent.model,
        "adapter": record.agent.adapter,
        "input_tokens": record.cost.tokens_in if record.cost else None,
        "output_tokens": record.cost.tokens_out if record.cost else None,
        "cache_read_tokens": record.cost.cache_read_tokens if record.cost else None,
        "cache_write_tokens": record.cost.cache_write_tokens if record.cost else None,
        "timestamp": record.timestamp.isoformat(),
    }


def failed_row(task: BaselineTask) -> dict[str, Any]:
    """Record a solver-level failure that did not produce a TrialRecord."""
    return {
        "task_id": task.task_id,
        "suite": task.suite,
        "domain": task.domain,
        "category": task.category,
        "template": task.template,
        "instance": task.instance,
        "difficulty": task.difficulty,
        "trial_id": None,
        "reward": 0.0,
        "below_threshold": True,
        "field_scores": {},
        "verifier_completed": False,
        "agent_status": "missing-trial-record",
        "model": None,
        "adapter": None,
        "input_tokens": None,
        "output_tokens": None,
        "cache_read_tokens": None,
        "cache_write_tokens": None,
        "timestamp": datetime.now(tz=UTC).isoformat(),
    }


def summarise_baseline_rows(
    rows: list[dict[str, Any]],
    *,
    score_threshold: float = DEFAULT_SCORE_THRESHOLD,
) -> dict[str, Any]:
    """Aggregate baseline rows by suite, difficulty, template, and domain."""
    summary: dict[str, Any] = {
        "total_tasks": len(rows),
        "score_threshold": score_threshold,
        "mean_reward": _mean(row["reward"] for row in rows),
        "below_threshold_count": sum(1 for row in rows if row["reward"] < score_threshold),
        "by_suite": {},
        "by_difficulty": {},
        "by_domain": {},
        "by_template": {},
        "below_threshold_tasks": [
            {
                "task_id": row["task_id"],
                "reward": row["reward"],
                "suite": row["suite"],
                "difficulty": row["difficulty"],
                "template": row["template"],
            }
            for row in sorted(rows, key=lambda item: (item["reward"], item["task_id"]))
            if row["reward"] < score_threshold
        ],
    }
    for key in ("suite", "difficulty", "domain", "template"):
        bucket_name = f"by_{key}"
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            groups.setdefault(str(row[key]), []).append(row)
        summary[bucket_name] = {
            name: {
                "count": len(group_rows),
                "mean_reward": _mean(row["reward"] for row in group_rows),
                "below_threshold_count": sum(1 for row in group_rows if row["reward"] < score_threshold),
            }
            for name, group_rows in sorted(groups.items())
        }
    return summary


def validate_baseline_environment(model: str) -> None:
    """Fail early when the selected model provider has no local credentials."""
    required_env = _required_api_key_env(model)
    if required_env is not None and not os.environ.get(required_env):
        msg = f"Model {model!r} requires {required_env} in the environment. Set it before running the baseline dataset."
        raise RuntimeError(msg)


def _read_task_metadata(task_toml: Path) -> dict[str, Any]:
    raw = tomllib.loads(task_toml.read_text(encoding="utf-8"))
    metadata = raw.get("metadata", {})
    generation = raw.get("generation", {})
    return {
        "domain": metadata.get("domain"),
        "difficulty": generation.get("difficulty") or metadata.get("difficulty"),
        "template": generation.get("template"),
    }


def _required_api_key_env(model: str) -> str | None:
    provider_hint = model.lower()
    if "claude" in provider_hint or "anthropic" in provider_hint:
        return "ANTHROPIC_API_KEY"
    if "gpt" in provider_hint or "openai" in provider_hint:
        return "OPENAI_API_KEY"
    return None


def _completed_task_ids(rows_path: Path) -> set[str]:
    return {str(row["task_id"]) for row in _read_rows(rows_path)}


def _read_rows(rows_path: Path) -> list[dict[str, Any]]:
    if not rows_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in rows_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _mean(values: Any) -> float | None:
    concrete = [float(value) for value in values]
    if not concrete:
        return None
    return round(sum(concrete) / len(concrete), 4)
