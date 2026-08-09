# ABOUTME: Provides the strict command-line entrypoint for one complete fixed-K adaptive cycle.
# ABOUTME: Uses the real synchronous Harbor subprocess path unless protocol executors are injected by tests.

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from aec_bench.experimentation.qualification.adaptive_cycle_runtime import (
    AdaptiveCycleExecutors,
    AdaptiveCycleResult,
    AdaptiveCycleSpec,
    run_adaptive_cycle,
)
from aec_bench.experimentation.qualification.harness_program_study_cli import (
    HarnessProgramStudySubprocessHarborExecutor,
    _preflight_harness_runtime,
    _preflight_runtime,
)
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.harness.kernel_catalogue import default_kernel_registry


def run_cli(
    argv: list[str] | None = None,
    *,
    executors: AdaptiveCycleExecutors | None = None,
) -> AdaptiveCycleResult:
    """Load one strict cycle spec, execute it, and print only the report path and hash."""

    arguments = _parser().parse_args(argv)
    spec = AdaptiveCycleSpec.model_validate_json(Path(arguments.spec).resolve().read_text(encoding="utf-8"))
    project_root = Path(arguments.project_root).resolve()
    repo_root = Path(arguments.repo_root).resolve()
    tasks_root = Path(arguments.tasks_root).resolve()
    env_file = Path(arguments.env_file).resolve() if arguments.env_file else project_root / ".env"
    load_dotenv(env_file)
    selected_executors = executors
    if selected_executors is None:
        _preflight_runtime(
            spec=spec.source_stage,
            project_root=project_root,
            repo_root=repo_root,
            tasks_root=tasks_root,
        )
        _preflight_harness_runtime(
            recipes=(
                spec.repair_parent.harness_request.recipe,
                spec.child_calibration.instantiation.fixed_harness_recipe,
                spec.transfer.instantiation.fixed_harness_recipe,
            ),
            project_root=project_root,
            repo_root=repo_root,
            tasks_root=tasks_root,
            surface_name="adaptive-cycle downstream stages",
        )
        subprocess_executor = HarnessProgramStudySubprocessHarborExecutor()
        selected_executors = AdaptiveCycleExecutors(
            source=subprocess_executor,
            repair=subprocess_executor,
            child_calibration=subprocess_executor,
        )
    workflow = SynchronousHarborWorkflow(
        project_root=project_root,
        repo_root=repo_root,
        tasks_root=tasks_root,
        ledger_root=Path(arguments.ledger_root).resolve(),
        jobs_root=Path(arguments.jobs_root).resolve(),
    )
    result = run_adaptive_cycle(
        spec=spec,
        registry=default_kernel_registry(),
        workflow=workflow,
        artifacts_root=Path(arguments.artifacts_root).resolve(),
        executors=selected_executors,
    )
    print(result.path)
    print(result.report.content_sha256)
    return result


def main() -> None:
    """Execute the production adaptive-cycle CLI through the real Harbor subprocess boundary."""

    run_cli()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a preregistered fixed-K adaptive meta-harness cycle.",
    )
    parser.add_argument("--spec", required=True, help="Strict AdaptiveCycleSpec JSON path")
    parser.add_argument("--project-root", default=".", help="Harbor command working directory")
    parser.add_argument("--env-file", default=None, help="Optional dotenv path; defaults to <project-root>/.env")
    parser.add_argument("--repo-root", default=".", help="Repository root used by Harbor import")
    parser.add_argument("--tasks-root", default="tasks", help="Task registry root")
    parser.add_argument("--ledger-root", default="artefacts/ledger", help="Append-only TrialRecord ledger root")
    parser.add_argument("--jobs-root", default="jobs", help="Harbor jobs root")
    parser.add_argument(
        "--artifacts-root",
        default="artefacts/adaptive-meta-harness",
        help="Content-addressed adaptive-cycle evidence root",
    )
    return parser


if __name__ == "__main__":
    main()
