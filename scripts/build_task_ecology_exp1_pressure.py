#!/usr/bin/env python3
# ABOUTME: Builds pressure-only task-ecology evolution arm configs.
# ABOUTME: Reads baseline summary rows and writes four previous-style experiment arms.

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from aec_bench.experiments.task_ecology_benchmark import (
    DEFAULT_MAX_CYCLES,
    load_pressure_task_patterns,
    write_pressure_benchmark_configs,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build pressure-only task-ecology Experiment 1 configs."
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--source-experiment", default="task-ecology-exp1")
    parser.add_argument("--pressure-experiment", default="task-ecology-exp1-pressure")
    parser.add_argument(
        "--baseline-summary",
        type=Path,
        default=Path(
            "artefacts/task-ecology-exp1-baseline/20260515-simple-1run/summary.yaml"
        ),
    )
    parser.add_argument("--threshold", type=float, default=0.85)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--max-cycles", type=int, default=DEFAULT_MAX_CYCLES)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    summary_path = (repo_root / args.baseline_summary).resolve()
    pressure_patterns = load_pressure_task_patterns(
        summary_path,
        score_threshold=args.threshold,
    )
    config_paths = write_pressure_benchmark_configs(
        repo_root=repo_root,
        source_experiment_slug=args.source_experiment,
        pressure_experiment_slug=args.pressure_experiment,
        config_dir=repo_root / "configs" / args.pressure_experiment,
        workspace_root=repo_root / "workspaces",
        pressure_task_patterns=pressure_patterns,
        batch_size=args.batch_size,
        max_cycles=args.max_cycles,
    )
    run_commands = [
        f"uv run aec-bench evolve run --config {path.relative_to(repo_root)} --tasks-root tasks"
        for path in config_paths
    ]
    manifest = {
        "experiment": args.pressure_experiment,
        "source_experiment": args.source_experiment,
        "baseline_summary": str(summary_path.relative_to(repo_root)),
        "score_threshold": args.threshold,
        "task_counts": {
            suite: len(task_ids) for suite, task_ids in sorted(pressure_patterns.items())
        },
        "configs": [path.relative_to(repo_root).as_posix() for path in config_paths],
        "run_commands": run_commands,
    }
    manifest_path = repo_root / "configs" / args.pressure_experiment / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    print(yaml.safe_dump(manifest, sort_keys=False))


if __name__ == "__main__":
    main()
