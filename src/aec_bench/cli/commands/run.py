# ABOUTME: CLI run command for Harbor experiments and portable run-package transfer.
# ABOUTME: Preserves config and inline invocation while adding explicit export and import modes.

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
import yaml

if TYPE_CHECKING:
    from aec_bench.contracts.experiment_manifest import ExperimentManifest

from aec_bench.cli.commands.config import resolve_path
from aec_bench.cli.optional_dependencies import require_optional_extra
from aec_bench.cli.output import console, emit, print_success
from aec_bench.harness.model_execution.llm_reviewer import (
    ReviewerEndpointConfig,
    ReviewerRunConfig,
    load_reviewer_config,
    reviewer_config_from_manifest,
)


def export_package(
    run_id: str = typer.Argument(help="Published run ID"),
    output: Path = typer.Option(..., "--output", "-o", help="Output .tar.zst path"),
    ledger_root: str | None = typer.Option(None, "--ledger-root", help="Ledger directory"),
) -> None:
    """Export one published run as exact portable archive bytes."""

    start = time.monotonic()
    from aec_bench.ledger.run_package import export_run_package

    resolved_ledger = resolve_path("ledger_root", cli_override=ledger_root)
    try:
        reference = export_run_package(ledger_root=resolved_ledger, run_id=run_id, output=output)
    except (FileNotFoundError, FileExistsError, ValueError) as error:
        emit("run export", data=None, errors=[str(error)], start_time=start)
        raise typer.Exit(1) from error
    emit(
        "run export",
        data={"run_id": run_id, "output": str(output), "artifact": reference.model_dump(mode="json")},
        start_time=start,
    )


def import_package(
    archive: Path = typer.Argument(help="Portable .tar.zst run package"),
    ledger_root: str | None = typer.Option(None, "--ledger-root", help="Ledger directory"),
) -> None:
    """Verify and import one portable run package."""

    start = time.monotonic()
    from aec_bench.ledger.run_package import import_run_package

    if not archive.is_file():
        emit("run import", data=None, errors=[f"run package not found: {archive}"], start_time=start)
        raise typer.Exit(1)
    resolved_ledger = resolve_path("ledger_root", cli_override=ledger_root)
    try:
        package, reference = import_run_package(ledger_root=resolved_ledger, data=archive.read_bytes())
    except ValueError as error:
        emit("run import", data=None, errors=[str(error)], start_time=start)
        raise typer.Exit(1) from error
    emit(
        "run import",
        data={
            "run_id": package.run_plan.run_manifest.run_id,
            "artifact": reference.model_dump(mode="json"),
        },
        start_time=start,
    )


def run_experiment(
    config: Path | None = typer.Option(None, "--config", "-c", help="Experiment config YAML"),
    tasks_root: str | None = typer.Option(None, "--tasks-root", help="Tasks directory"),
    tasks_path: str | None = typer.Argument(None, help="Task path (simple invocation)"),
    package_value: str | None = typer.Argument(None, help="Run ID or archive path for export/import"),
    model: str | None = typer.Option(None, "--model", help="Model name"),
    adapter: str = typer.Option(
        "tool_loop",
        "--adapter",
        "--harness",
        help="Agent harness: tool_loop, pydantic_ai, direct, rlm, lambda-rlm, deepseek_harness",
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
    reviewer: bool = typer.Option(False, "--reviewer", help="Run the post-verifier LLM reviewer stage"),
    reviewer_model: str | None = typer.Option(None, "--reviewer-model", help="Single reviewer model name"),
    reviewer_models_config: Path | None = typer.Option(
        None,
        "--reviewer-models-config",
        help="JSON/YAML reviewer model endpoint config",
    ),
    fail_on_reviewer_error: bool = typer.Option(
        False,
        "--fail-on-reviewer-error",
        help="Fail the run when the reviewer stage cannot complete",
    ),
    output: Path | None = typer.Option(None, "--output", "-o", help="Exported .tar.zst path"),
    ledger_root: str | None = typer.Option(None, "--ledger-root", help="Ledger directory"),
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
      aec-bench run export run-001 --output run-package.tar.zst
      aec-bench run import run-package.tar.zst
      aec-bench --json run --config experiment.yaml | jq '.data.experiment_id'
    """
    if tasks_path == "export":
        if package_value is None or output is None:
            raise typer.BadParameter("run export requires <run-id> and --output <path>")
        export_package(run_id=package_value, output=output, ledger_root=ledger_root)
        return
    if tasks_path == "import":
        if package_value is None:
            raise typer.BadParameter("run import requires <archive-path>")
        import_package(archive=Path(package_value), ledger_root=ledger_root)
        return
    if package_value is not None:
        raise typer.BadParameter(f"unexpected run argument: {package_value}")
    start = time.monotonic()
    reviewer_config = _reviewer_config_from_cli(
        enabled=reviewer,
        model=reviewer_model,
        models_config=reviewer_models_config,
        fail_on_error=fail_on_reviewer_error,
    )

    if config is not None:
        _run_from_config(
            config,
            tasks_root=tasks_root,
            dry_run=dry_run,
            start=start,
            no_verify=no_verify,
            reviewer_config=reviewer_config,
        )
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
            reviewer_config=reviewer_config,
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
    reviewer_config: ReviewerRunConfig | None = None,
) -> None:
    if not config_path.exists():
        emit("run", data=None, errors=[f"config file not found: {config_path}"], start_time=start)
        return

    config_dir = config_path.parent.resolve()
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    resolved_tasks = resolve_path("tasks_root", cli_override=tasks_root)
    raw = _resolve_interactive_dataset_alias(raw, project_root=resolved_tasks.parent)

    from aec_bench.contracts.experiment_manifest import ExperimentManifest

    manifest = ExperimentManifest.model_validate(raw)
    if no_verify:
        manifest = manifest.model_copy(update={"disable_verification": True})

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

    _execute_manifest(
        manifest,
        tasks_root=resolved_tasks,
        dry_run=dry_run,
        start=start,
        reviewer_config=reviewer_config,
    )


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
    reviewer_config: ReviewerRunConfig | None = None,
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
    _execute_manifest(
        manifest,
        tasks_root=resolved_tasks,
        dry_run=dry_run,
        start=start,
        reviewer_config=reviewer_config,
    )


def _execute_manifest(
    manifest: ExperimentManifest,
    *,
    tasks_root: Path,
    dry_run: bool,
    start: float,
    reviewer_config: ReviewerRunConfig | None = None,
) -> None:
    effective_reviewer_config = reviewer_config or reviewer_config_from_manifest(manifest.reviewer)
    morph = manifest.compute.backend == "morph"
    modules = ("harbor", "morphcloud") if morph else ("harbor",)
    extras = "execution,morph" if morph else "execution"
    if effective_reviewer_config is not None and effective_reviewer_config.enabled:
        modules = (*modules, "pydantic_ai")
        extras += ",local-agents"
    require_optional_extra("Experiment execution support", extras, modules)

    from aec_bench.cli.harbor_environment import HARBOR_RUN_BACKENDS, resolve_harbor_environment_binding
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
    project_root = tasks_root.parent
    selected_tasks = select_manifest_tasks(
        registry.all(),
        manifest,
        project_root=project_root,
    )

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
            "reviewer": _reviewer_plan(effective_reviewer_config),
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
        reviewer_config=reviewer_config,
        environment_binding=resolve_harbor_environment_binding(manifest.compute.backend),
    )

    result_data = {
        "experiment_id": manifest.experiment_id,
        "job_dir": str(result.job_dir) if result.job_dir else None,
        "imported": result.import_result.imported_trials if result.import_result else 0,
        "duplicates": result.import_result.duplicate_trials if result.import_result else 0,
        "reviewer": _reviewer_result_data(result.reviewer_result),
    }

    def _render_result(d: dict[str, Any]) -> None:
        print_success(f"Completed: {d['imported']} trials imported into ledger")

    emit("run", result_data, start_time=start, human_renderer=_render_result)


def _resolve_interactive_dataset_alias(raw: object, *, project_root: Path) -> object:
    """Replace one user-facing dataset selector with its exact reference before validation."""

    if not isinstance(raw, dict):
        return raw
    tasks = raw.get("tasks")
    if not isinstance(tasks, dict):
        return raw
    selector = tasks.get("dataset")
    if not isinstance(selector, str):
        return raw

    from aec_bench.config import load_config
    from aec_bench.dataset.publication import resolve_dataset

    config = load_config(project_root)
    resolved = resolve_dataset(
        datasets_root=config.datasets_root,
        selector=selector,
        project_root=project_root,
    )
    if resolved is None:
        raise ValueError(f"dataset selector did not resolve to a publication: {selector}")
    resolved_tasks = dict(tasks)
    resolved_tasks["dataset"] = resolved.reference.model_dump(mode="json")
    resolved_raw = dict(raw)
    resolved_raw["tasks"] = resolved_tasks
    return resolved_raw


def _reviewer_config_from_cli(
    *,
    enabled: bool,
    model: str | None,
    models_config: Path | None,
    fail_on_error: bool,
) -> ReviewerRunConfig | None:
    if models_config is not None:
        config = load_reviewer_config(models_config)
        return config.model_copy(update={"enabled": True, "fail_on_error": fail_on_error or config.fail_on_error})
    if model is not None:
        return ReviewerRunConfig(
            enabled=True,
            fail_on_error=fail_on_error,
            models=[
                ReviewerEndpointConfig(
                    name=model,
                    model=model,
                )
            ],
        )
    if enabled:
        return ReviewerRunConfig(enabled=True, fail_on_error=fail_on_error)
    return None


def _reviewer_plan(config: ReviewerRunConfig | None) -> dict[str, Any]:
    if config is None:
        return {"enabled": False, "required": False, "models": []}
    return {
        "enabled": config.enabled,
        "required": config.required,
        "models": [model.name for model in config.models],
        "fail_on_error": config.fail_on_error,
    }


def _reviewer_result_data(result: Any | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "trial_count": result.trial_count,
        "complete_count": result.complete_count,
        "error_count": result.error_count,
        "skipped_count": result.skipped_count,
    }
