#!/usr/bin/env python3
# ABOUTME: Materialises Experiment 1 fixed and population task-ecology benchmark suites.
# ABOUTME: Writes generated tasks, evolution configs, workspaces, and a suite manifest.

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from aec_bench.experiments.task_ecology_benchmark import (
    DEFAULT_EXPERIMENT_SLUG,
    DEFAULT_MAX_CYCLES,
    DEFAULT_SEED,
    build_benchmark,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build task-ecology Experiment 1 benchmark suites."
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--index",
        type=Path,
        default=Path("task_genomes/templates/index.yaml"),
        help="Template genome catalogue index.",
    )
    parser.add_argument("--experiment", default=DEFAULT_EXPERIMENT_SLUG)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--population-per-domain", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--max-cycles", type=int, default=DEFAULT_MAX_CYCLES)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    output_root = repo_root / "tasks" / "generated" / args.experiment
    manifest = build_benchmark(
        repo_root=repo_root,
        index_path=(repo_root / args.index).resolve(),
        output_root=output_root,
        config_dir=repo_root / "configs" / args.experiment,
        workspace_root=repo_root / "workspaces",
        seed=args.seed,
        population_per_domain=args.population_per_domain,
        batch_size=args.batch_size,
        max_cycles=args.max_cycles,
    )

    print(yaml.safe_dump(manifest, sort_keys=False))


if __name__ == "__main__":
    main()
