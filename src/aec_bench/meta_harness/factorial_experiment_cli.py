# ABOUTME: Provides the strict JSON command-line entrypoint for fixed-K factorial candidate searches.
# ABOUTME: Uses the installed kernel and real synchronous Harbor workflow unless a test executor is injected.

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from aec_bench.adapters.rlm.providers import preflight_pydantic_model_configuration
from aec_bench.contracts.harness_instance import AgentBindingConfig, ComputeBindingConfig, HarnessRecipe
from aec_bench.harness.harbor_dispatch import HarborCommandExecutor
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.meta_harness.factorial_experiment import (
    FactorialExperimentRunResult,
    FactorialExperimentSpec,
    run_factorial_experiment,
)
from aec_bench.meta_harness.kernel_catalogue import AgentAdapterRuntime, default_kernel_registry


class FactorialExperimentSubprocessHarborExecutor:
    """Execute real Harbor while keeping machine-readable success output isolated on stdout."""

    def execute(self, *, command: list[str], cwd: Path) -> int:
        env = dict(os.environ)
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(cwd) if not existing_pythonpath else f"{cwd}{os.pathsep}{existing_pythonpath}"
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            env=env,
            stdout=sys.stderr,
        )
        return int(completed.returncode)


def run_factorial_experiment_cli(
    argv: list[str] | None = None,
    *,
    executor: HarborCommandExecutor | None = None,
) -> FactorialExperimentRunResult:
    """Load one strict spec, run the real workflow surface, and print only report path/hash."""
    arguments = _parser().parse_args(argv)
    spec_path = Path(arguments.spec).resolve()
    spec = FactorialExperimentSpec.model_validate_json(
        spec_path.read_text(encoding="utf-8"),
    )
    project_root = Path(arguments.project_root).resolve()
    repo_root = Path(arguments.repo_root).resolve()
    tasks_root = Path(arguments.tasks_root).resolve()
    env_file = Path(arguments.env_file).resolve() if arguments.env_file else project_root / ".env"
    load_dotenv(env_file)
    if executor is None:
        _preflight_runtime(spec=spec, project_root=project_root, repo_root=repo_root, tasks_root=tasks_root)
    workflow = SynchronousHarborWorkflow(
        project_root=project_root,
        repo_root=repo_root,
        tasks_root=tasks_root,
        ledger_root=Path(arguments.ledger_root).resolve(),
        jobs_root=Path(arguments.jobs_root).resolve(),
    )
    result = run_factorial_experiment(
        spec=spec,
        registry=default_kernel_registry(),
        workflow=workflow,
        artifacts_root=Path(arguments.artifacts_root).resolve(),
        executor=(executor if executor is not None else FactorialExperimentSubprocessHarborExecutor()),
    )
    print(result.path)
    print(result.report.content_sha256)
    return result


def main() -> None:
    """Execute a factorial experiment with Harbor's subprocess executor."""
    run_factorial_experiment_cli()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a preregistered fixed-K adaptive-harness candidate search.",
    )
    parser.add_argument(
        "--spec",
        required=True,
        help="Strict FactorialExperimentSpec JSON path",
    )
    parser.add_argument("--project-root", default=".", help="Harbor command working directory")
    parser.add_argument(
        "--env-file",
        default=None,
        help="Optional dotenv path; defaults to <project-root>/.env",
    )
    parser.add_argument("--repo-root", default=".", help="Repository root used by Harbor import")
    parser.add_argument("--tasks-root", default="tasks", help="Task registry root")
    parser.add_argument("--ledger-root", default="artefacts/ledger", help="Append-only TrialRecord ledger root")
    parser.add_argument("--jobs-root", default="jobs", help="Harbor jobs root")
    parser.add_argument(
        "--artifacts-root",
        default="artefacts/adaptive-meta-harness",
        help="Content-addressed factorial-experiment evidence root",
    )
    return parser


def _preflight_runtime(
    *,
    spec: FactorialExperimentSpec,
    project_root: Path,
    repo_root: Path,
    tasks_root: Path,
) -> None:
    recipes = tuple(
        recipe
        for request in spec.candidate_requests
        for recipe in (request.fixed_harness_recipe, request.learned_harness_recipe)
    )
    _preflight_harness_runtime(
        recipes=recipes,
        project_root=project_root,
        repo_root=repo_root,
        tasks_root=tasks_root,
        surface_name="factorial experiment",
    )


def _preflight_harness_runtime(
    *,
    recipes: tuple[HarnessRecipe, ...],
    project_root: Path,
    repo_root: Path,
    tasks_root: Path,
    surface_name: str,
) -> None:
    """Validate shared filesystem, executable, backend, and provider prerequisites without network calls."""

    missing_roots = [path for path in (project_root, repo_root, tasks_root) if not path.is_dir()]
    if missing_roots:
        raise RuntimeError(
            f"{surface_name} runtime directories are missing: " + ", ".join(str(path) for path in missing_roots)
        )
    if shutil.which("uv") is None:
        raise RuntimeError(f"{surface_name} requires the uv executable used to launch the real Harbor CLI")

    agent_models, uses_morph = _preflight_runtime_requirements(recipes)
    if uses_morph and not os.environ.get("MORPH_API_KEY", "").strip():
        raise RuntimeError(f"{surface_name} Morph execution requires MORPH_API_KEY")
    _preflight_runtime_models(agent_models, surface_name=surface_name)


def _preflight_runtime_requirements(
    recipes: tuple[HarnessRecipe, ...],
) -> tuple[set[str], bool]:
    agent_models: set[str] = set()
    uses_morph = False
    registry = default_kernel_registry()
    for recipe in recipes:
        for binding in recipe.bindings:
            if isinstance(binding.configuration, AgentBindingConfig):
                runtime = registry.resolve(binding.capability_ref).runtime
                if isinstance(runtime, AgentAdapterRuntime) and runtime.adapter_kind in {
                    "direct",
                    "tool_loop",
                    "rlm",
                    "lambda-rlm",
                }:
                    agent_models.add(binding.configuration.model)
            elif isinstance(binding.configuration, ComputeBindingConfig):
                uses_morph = uses_morph or (binding.capability_ref.capability_id == "aecbench.backend.harbor.morph")
    return agent_models, uses_morph


def _preflight_runtime_models(
    agent_models: set[str],
    *,
    surface_name: str,
) -> None:
    for model in sorted(agent_models):
        try:
            preflight_pydantic_model_configuration(model)
        except Exception as error:
            raise RuntimeError(f"{surface_name} model provider preflight failed for {model!r}: {error}") from error


if __name__ == "__main__":
    main()
