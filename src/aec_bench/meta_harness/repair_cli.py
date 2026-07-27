# ABOUTME: Provides the strict JSON CLI for one generic verifier-guided paired repair attempt.
# ABOUTME: Uses the real synchronous Harbor subprocess path unless a protocol executor is injected by tests.

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from aec_bench.harness.harbor_dispatch import HarborCommandExecutor
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.meta_harness.factorial_experiment_cli import (
    FactorialExperimentSubprocessHarborExecutor,
    _preflight_harness_runtime,
)
from aec_bench.meta_harness.kernel_catalogue import default_kernel_registry
from aec_bench.meta_harness.repair_run import RepairRunSpec, run_repair
from aec_bench.meta_harness.repair_runtime import RepairRuntimeExecution


def run_cli(
    argv: list[str] | None = None,
    *,
    executor: HarborCommandExecutor | None = None,
) -> RepairRuntimeExecution:
    """Load one strict repair spec, execute it, and print only the terminal path and hash."""

    arguments = _parser().parse_args(argv)
    spec = RepairRunSpec.model_validate_json(Path(arguments.spec).resolve().read_text(encoding="utf-8"))
    project_root = Path(arguments.project_root).resolve()
    repo_root = Path(arguments.repo_root).resolve()
    tasks_root = Path(arguments.tasks_root).resolve()
    env_file = Path(arguments.env_file).resolve() if arguments.env_file else project_root / ".env"
    load_dotenv(env_file)
    selected_executor = executor
    if selected_executor is None:
        _preflight_repair_runtime(
            spec=spec,
            project_root=project_root,
            repo_root=repo_root,
            tasks_root=tasks_root,
        )
        selected_executor = FactorialExperimentSubprocessHarborExecutor()
    workflow = SynchronousHarborWorkflow(
        project_root=project_root,
        repo_root=repo_root,
        tasks_root=tasks_root,
        ledger_root=Path(arguments.ledger_root).resolve(),
        jobs_root=Path(arguments.jobs_root).resolve(),
    )
    result = run_repair(
        spec=spec,
        registry=default_kernel_registry(),
        workflow=workflow,
        artifacts_root=Path(arguments.artifacts_root).resolve(),
        executor=selected_executor,
    )
    print(result.terminal.path)
    print(result.terminal.reference.sha256)
    return result


def main() -> None:
    """Execute the production repair-only CLI through the real Harbor subprocess boundary."""

    run_cli()


def _preflight_repair_runtime(
    *,
    spec: RepairRunSpec,
    project_root: Path,
    repo_root: Path,
    tasks_root: Path,
) -> None:
    """Preflight the immutable parent surface because typed repair cannot change provider or backend."""

    _preflight_harness_runtime(
        recipes=(spec.parent.harness_request.recipe,),
        project_root=project_root,
        repo_root=repo_root,
        tasks_root=tasks_root,
        surface_name="repair",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one preregistered fixed-K paired repair attempt.")
    parser.add_argument("--spec", required=True, help="Strict RepairRunSpec JSON path")
    parser.add_argument("--project-root", default=".", help="Harbor command working directory")
    parser.add_argument("--env-file", default=None, help="Optional dotenv path; defaults to <project-root>/.env")
    parser.add_argument("--repo-root", default=".", help="Repository root used by Harbor import")
    parser.add_argument("--tasks-root", default="tasks", help="Task registry root")
    parser.add_argument("--ledger-root", default="artefacts/ledger", help="Append-only TrialRecord ledger root")
    parser.add_argument("--jobs-root", default="jobs", help="Harbor jobs root")
    parser.add_argument(
        "--artifacts-root",
        default="artefacts/adaptive-meta-harness",
        help="Content-addressed repair evidence root",
    )
    return parser


if __name__ == "__main__":
    main()
