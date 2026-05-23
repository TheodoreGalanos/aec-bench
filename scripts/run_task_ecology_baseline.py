#!/usr/bin/env python3
# ABOUTME: CLI wrapper for the task-ecology one-run baseline dataset.
# ABOUTME: Discovers generated tasks and writes JSONL plus YAML calibration summaries.

from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import yaml

from aec_bench.experiments.task_ecology_baseline import (
    DEFAULT_BASELINE_ADAPTER,
    DEFAULT_BASELINE_MODEL,
    DEFAULT_EXPERIMENT_ID,
    DEFAULT_SCORE_THRESHOLD,
    discover_baseline_tasks,
    run_baseline_dataset,
)


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Run a one-pass local baseline over generated task-ecology tasks."
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--experiment", default="task-ecology-exp1")
    parser.add_argument("--model", default=DEFAULT_BASELINE_MODEL)
    parser.add_argument("--adapter", default=DEFAULT_BASELINE_ADAPTER)
    parser.add_argument("--threshold", type=float, default=DEFAULT_SCORE_THRESHOLD)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--suite", action="append", choices=("fixed", "population"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Defaults to artefacts/task-ecology-exp1-baseline/<timestamp>.",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    suites = tuple(args.suite or ("fixed", "population"))
    tasks = discover_baseline_tasks(
        tasks_root=repo_root / "tasks",
        experiment=args.experiment,
        suites=suites,
    )
    if args.limit is not None:
        tasks = tasks[: args.limit]

    if args.dry_run:
        preview = {
            "selected_tasks": len(tasks),
            "by_suite": dict(sorted(Counter(task.suite for task in tasks).items())),
            "by_difficulty": dict(sorted(Counter(task.difficulty for task in tasks).items())),
            "by_domain": dict(sorted(Counter(task.domain for task in tasks).items())),
            "by_template": dict(sorted(Counter(task.template for task in tasks).items())),
        }
        print(yaml.safe_dump(preview, sort_keys=False))
        return

    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.output_dir or (
        repo_root / "artefacts" / DEFAULT_EXPERIMENT_ID / timestamp
    )
    try:
        summary = run_baseline_dataset(
            tasks=tasks,
            output_dir=output_dir,
            model=args.model,
            adapter=args.adapter,
            experiment_id=DEFAULT_EXPERIMENT_ID,
            score_threshold=args.threshold,
            workspace_root=repo_root,
            timeout=args.timeout,
        )
    except RuntimeError as exc:
        parser.exit(2, f"error: {exc}\n")
    print(yaml.safe_dump({"output_dir": str(output_dir), "summary": summary}, sort_keys=False))


if __name__ == "__main__":
    main()
