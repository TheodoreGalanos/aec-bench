#!/usr/bin/env python3
# ABOUTME: Summarises Experiment 1 task-ecology evolution runs from arm workspaces.
# ABOUTME: Prints fixed/population and hill/QD scores once benchmark arms have run.

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from aec_bench.experiments.task_ecology_benchmark import summarise_benchmark_runs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare task-ecology Experiment 1 evolution arms."
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path("configs/task-ecology-exp1"),
        help="Directory containing Experiment 1 arm configs.",
    )
    args = parser.parse_args()

    rows = summarise_benchmark_runs(args.config_dir)
    print(yaml.safe_dump({"arms": rows}, sort_keys=False))


if __name__ == "__main__":
    main()
