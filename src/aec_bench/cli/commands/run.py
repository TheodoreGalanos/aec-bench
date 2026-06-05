# ABOUTME: CLI run command for executing experiments via Harbor.
# ABOUTME: Supports both config-file and inline argument invocation.

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
import yaml  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from aec_bench.contracts.experiment_manifest import ExperimentManifest

from aec_bench.cli.commands.config import resolve_path
from aec_bench.cli.output import console, emit, print_success


def run_experiment(
    config: Path | None = typer.Option(None, "--config", "-c", help="Experiment config YAML"),
    tasks_root: str | None = typer.Option(None, "--tasks-root", help="Tasks directory"),
    tasks_path: str | None = typer.Argument(None, help="Task path (simple invocation)"),
    model: str | None = typer.Option(None, "--model", help="Model name"),
    adapter: str = typer.Option(
        "tool_loop",
        "--adapter",
        "--harness",
        help="Agent harness: tool_loop, pydantic_ai, direct, rlm, lambda-rlm",
    ),
    backend: str = typer.Option(
        "modal",
        "--backend",
        "-b",
        help="Harbor execution backend: modal, morph, e2b, daytona, docker.",
    ),
    repetitions: int = typer.Option(1, "--repetitions", "-n", help="Repetitions"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show plan without executing"),
    no_verify: bool = typer.Option(False, "--no-verify", help="Skip verification (agent-only run)"),
) -> None:
    """Run an experiment.

    Two invocation styles:

      aec-bench run --config experiment.yaml --tasks-root ../tasks

      aec-bench run ../tasks/mechanical/heat-load --model claude-sonnet-4-20250514

    Returns (dry-run): experiment_id, selected_tasks, planned_trials, agents,
    repetitions, trials list (trial_id, task_id, agent per trial).

    Returns (live run): experiment_id, job_dir, imported, duplicates.

    Examples:
      aec-bench run tasks/electrical/voltage-drop --model gpt-4.1-mini --dry-run
      aec-bench --json run --config experiment.yaml | jq '.data.experiment_id'
    """
    start = time.monotonic()

    if config is not None:
        _run_from_config(config, tasks_root=tasks_root, dry_run=dry_run, start=start, no_verify=no_verify)
    elif tasks_path is not None and model is not None:
        _run_inline(
            tasks_path=tasks_path,
            model=model,
            adapter=adapter,
            backend=backend,
            repetitions=repetitions,
            tasks_root=tasks_root,
            dry_run=dry_run,
            start=start,
            no_verify=no_verify,
        )
    else:
        emit(
            "run",
            data=None,
            errors=["provide --config <file> or <tasks-path> --model <name>"],
            start_time=start,
        )
        return


def _run_from_config(
    config_path: Path,
    *,
    tasks_root: str | None,
    dry_run: bool,
    start: float,
    no_verify: bool = False,
) -> None:
    if not config_path.exists():
        emit("run", data=None, errors=[f"config file not found: {config_path}"], start_time=start)
        return

    config_dir = config_path.parent.resolve()
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    from aec_bench.contracts.experiment_manifest import ExperimentManifest

    manifest = ExperimentManifest.model_validate(raw)
    if no_verify:
        manifest = manifest.model_copy(update={"disable_verification": True})

    resolved_tasks = resolve_path("tasks_root", cli_override=tasks_root)

    for agent in manifest.agents:
        if agent.system_prompt_file is not None:
            prompt_path = config_dir / agent.system_prompt_file
            if not prompt_path.exists():
                emit(
                    "run",
                    data=None,
                    errors=[f"system prompt not found: {prompt_path}"],
                    start_time=start,
                )
                return

    _execute_manifest(manifest, tasks_root=resolved_tasks, dry_run=dry_run, start=start)


def _run_inline(
    *,
    tasks_path: str,
    model: str,
    adapter: str,
    backend: str = "modal",
    repetitions: int,
    tasks_root: str | None,
    dry_run: bool,
    start: float,
    no_verify: bool = False,
) -> None:
    from aec_bench.contracts.experiment_manifest import (
        AgentConfig,
        ComputeConfig,
        ExperimentManifest,
        TaskSelector,
    )

    resolved_tasks = resolve_path("tasks_root", cli_override=tasks_root)
    tasks_abs = Path(tasks_path).resolve()
    try:
        relative = tasks_abs.relative_to(resolved_tasks).as_posix()
    except ValueError:
        relative = tasks_path.rstrip("/")
    # Match both leaf tasks (exact path) and parent dirs (with sub-instances)
    task_patterns = [relative, relative + "/*"]

    manifest = ExperimentManifest(
        experiment_id=f"inline-{model.split('/')[-1].split('-')[0]}",
        name=f"Inline run: {model}",
        tasks=TaskSelector(include_patterns=task_patterns),
        agents=[
            AgentConfig(
                name=f"{adapter}-{model.split('-')[0]}",
                adapter=adapter,
                model=model,
            )
        ],
        compute=ComputeConfig(backend=backend),
        repetitions=repetitions,
        disable_verification=no_verify,
    )

    resolved_tasks = resolve_path("tasks_root", cli_override=tasks_root)
    _execute_manifest(manifest, tasks_root=resolved_tasks, dry_run=dry_run, start=start)


def _execute_manifest(
    manifest: ExperimentManifest,
    *,
    tasks_root: Path,
    dry_run: bool,
    start: float,
) -> None:
    from aec_bench.harness.harbor_dispatch import HARBOR_RUN_BACKENDS
    from aec_bench.harness.scheduler import build_trial_plan, select_manifest_tasks
    from aec_bench.tasks.registry import TaskRegistry

    if manifest.compute.backend not in HARBOR_RUN_BACKENDS:
        supported = ", ".join(HARBOR_RUN_BACKENDS)
        emit(
            "run",
            data=None,
            errors=[
                f"backend '{manifest.compute.backend}' is not supported by 'aec-bench run'; "
                f"or choose one of: {supported}"
            ],
            start_time=start,
        )
        return

    registry = TaskRegistry(tasks_root=tasks_root)
    registry.reload()
    selected_tasks = select_manifest_tasks(registry.all(), manifest)

    if not selected_tasks:
        emit(
            "run",
            data=None,
            errors=["no tasks matched the manifest selector"],
            start_time=start,
        )
        return

    plan = build_trial_plan(manifest, selected_tasks)

    if dry_run:
        plan_data = {
            "experiment_id": manifest.experiment_id,
            "backend": manifest.compute.backend,
            "selected_tasks": len(selected_tasks),
            "planned_trials": len(plan),
            "agents": [a.name for a in manifest.agents],
            "repetitions": manifest.repetitions,
            "trials": [{"trial_id": t.trial_id, "task_id": t.task_id, "agent": t.agent.name} for t in plan],
        }

        def _render_dry_run(d: dict[str, Any]) -> None:
            console.print(f"[bold]Dry Run: {d['experiment_id']}[/bold]")
            console.print(f"  Backend:    {d['backend']}")
            console.print(f"  Tasks:      {d['selected_tasks']}")
            console.print(f"  Agents:     {', '.join(d['agents'])}")
            console.print(f"  Repetitions: {d['repetitions']}")
            console.print(f"  Total trials: [bold]{d['planned_trials']}[/bold]")

            from rich.table import Table

            table = Table(title="Planned Trials")
            table.add_column("Trial ID", style="dim")
            table.add_column("Task")
            table.add_column("Agent")

            for trial in d["trials"][:20]:
                table.add_row(trial["trial_id"], trial["task_id"], trial["agent"])

            if len(d["trials"]) > 20:
                table.add_row("...", f"({len(d['trials']) - 20} more)", "...")

            console.print(table)

        emit("run", plan_data, start_time=start, human_renderer=_render_dry_run)
        return

    console.print(f"[bold]Running: {manifest.name}[/bold]")
    console.print(f"  {len(plan)} trials across {len(selected_tasks)} tasks")

    from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow

    resolved_ledger = resolve_path("ledger_root")
    project_root = tasks_root.parent
    jobs_root = project_root / "jobs"

    workflow = SynchronousHarborWorkflow(
        project_root=project_root,
        repo_root=project_root,
        tasks_root=tasks_root,
        ledger_root=resolved_ledger,
        jobs_root=jobs_root,
    )

    def _progress(snapshot: object) -> None:
        console.print(f"  [dim]{snapshot}[/dim]")

    result = workflow.run(
        manifest=manifest,
        config_path=project_root / f".aec-bench-{manifest.experiment_id}.yaml",
        progress_callback=_progress,
    )

    result_data = {
        "experiment_id": manifest.experiment_id,
        "job_dir": str(result.job_dir) if result.job_dir else None,
        "imported": result.import_result.imported_trials if result.import_result else 0,
        "duplicates": result.import_result.duplicate_trials if result.import_result else 0,
    }

    def _render_result(d: dict[str, Any]) -> None:
        print_success(f"Completed: {d['imported']} trials imported into ledger")

    emit("run", result_data, start_time=start, human_renderer=_render_result)
