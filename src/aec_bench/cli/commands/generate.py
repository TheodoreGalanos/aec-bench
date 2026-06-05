# ABOUTME: CLI generate subcommand group for producing task instances from templates.
# ABOUTME: Provides task, suite, list-templates, and validate-template subcommands.

# ruff: noqa: B008

from pathlib import Path

import typer
from rich.table import Table

from aec_bench.cli.commands.generate_dockerfiles import generate_dockerfiles_command
from aec_bench.cli.output import console, emit, print_success, print_warning
from aec_bench.templates.registry import discover_templates, load_template, validate_template

app = typer.Typer(help="Generate task instances from templates.", no_args_is_help=True)

# Register the dockerfiles subcommand from its own module
app.command("dockerfiles")(generate_dockerfiles_command)


def _find_named_template(name: str) -> Path | None:
    """Search built-in templates for one matching the given name.

    Returns the template directory path, or None if not found.
    """
    templates = discover_templates()
    for config, path in templates:
        if config.meta.name == name:
            return path
    return None


@app.command("task")
def generate_task(
    name: str | None = typer.Argument(None, help="Built-in template name"),
    template: Path | None = typer.Option(None, "--template", help="Path to a local template directory"),
    instances: int = typer.Option(3, "--instances", help="Number of instances to generate"),
    difficulty: str | None = typer.Option(
        None,
        "--difficulty",
        help="Comma-separated difficulty names (e.g. easy,medium). Defaults to all presets.",
    ),
    seed: int = typer.Option(42, "--seed", help="Random seed for reproducibility"),
    output: Path = typer.Option(Path("./tasks/"), "--output", help="Output directory for instances"),
    tool_mode: str | None = typer.Option(None, "--tool-mode", help="Override template tool_mode"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print plan without writing files"),
) -> None:
    """Generate task instances from a named built-in or local template.

    Returns (dry-run): dry_run, template, output, seed, instances list
    (instance number and difficulty per entry).

    Returns (live): dry_run, template, output, count, instances list
    (index, instance name, difficulty, path per entry).

    Examples:
      aec-bench generate task voltage-drop --instances 5 --difficulty easy,medium
      aec-bench --json generate task voltage-drop --dry-run | jq '.data.instances'
    """
    import time

    start = time.monotonic()

    # Resolve template directory
    if name is not None and template is not None:
        emit(
            "generate task",
            data=None,
            errors=["specify either a template name or --template, not both"],
            start_time=start,
        )
        return

    if name is None and template is None:
        emit(
            "generate task",
            data=None,
            errors=["provide a template name or --template <path>"],
            start_time=start,
        )
        return

    if template is not None:
        template_dir = template.resolve()
    else:
        assert name is not None
        template_dir = _find_named_template(name)
        if template_dir is None:
            emit(
                "generate task",
                data=None,
                errors=[f"template '{name}' not found in built-in templates"],
                start_time=start,
            )
            return

    # Load the template
    try:
        config, resolved_dir = load_template(template_dir)
    except (FileNotFoundError, ValueError) as exc:
        emit(
            "generate task",
            data=None,
            errors=[f"failed to load template: {exc}"],
            start_time=start,
        )
        return

    # Resolve difficulty list
    available_difficulties = list(config.difficulty.keys())
    if difficulty is not None:
        requested = [d.strip() for d in difficulty.split(",") if d.strip()]
        unknown = [d for d in requested if d not in available_difficulties]
        if unknown:
            emit(
                "generate task",
                data=None,
                errors=[
                    f"unknown difficulty preset(s): {', '.join(unknown)}. "
                    f"Available: {', '.join(available_difficulties)}"
                ],
                start_time=start,
            )
            return
        difficulty_cycle = requested
    else:
        difficulty_cycle = available_difficulties

    if dry_run:
        plan_list = [
            {
                "instance": i + 1,
                "difficulty": difficulty_cycle[i % len(difficulty_cycle)],
            }
            for i in range(instances)
        ]
        plan_data: dict[str, object] = {
            "dry_run": True,
            "template": resolved_dir.name,
            "output": str(output.resolve()),
            "seed": seed,
            "instances": plan_list,
        }

        def _render_plan(data: dict) -> None:
            console.print(f"[bold]Dry run:[/bold] would generate {len(data['instances'])} instance(s)")
            console.print(f"  Template:  {data['template']}")
            console.print(f"  Output:    {data['output']}")
            console.print(f"  Seed:      {data['seed']}")
            for inst in data["instances"]:
                console.print(f"  Instance {inst['instance']}: difficulty={inst['difficulty']}")

        emit(
            "generate task",
            plan_data,
            start_time=start,
            human_renderer=_render_plan,
        )
        return

    # Import generation modules lazily to keep startup fast
    from aec_bench.generation.sampler import sample_instance
    from aec_bench.generation.scaffolder import scaffold_task_instance
    from aec_bench.templates.registry import load_engine_module

    engine_module = load_engine_module(resolved_dir)
    engine_source = (resolved_dir / "engine.py").read_text(encoding="utf-8")

    created_paths: list[Path] = []

    for i in range(instances):
        diff = difficulty_cycle[i % len(difficulty_cycle)]
        instance = sample_instance(
            config=config,
            engine_compute=engine_module.compute,
            difficulty_name=diff,
            seed=seed,
            instance_index=i,
        )
        instance_dir = scaffold_task_instance(
            config=config,
            engine_source=engine_source,
            template_dir=resolved_dir,
            instance=instance,
            output_dir=output.resolve(),
            tool_mode_override=tool_mode,
        )
        created_paths.append(instance_dir)

    results_list = [
        {
            "index": idx + 1,
            "instance": instance_path.name,
            "difficulty": difficulty_cycle[i % len(difficulty_cycle)],
            "path": str(instance_path),
        }
        for idx, (instance_path, i) in enumerate(zip(created_paths, range(instances), strict=True))
    ]
    results_data: dict[str, object] = {
        "dry_run": False,
        "template": resolved_dir.name,
        "output": str(output.resolve()),
        "count": len(created_paths),
        "instances": results_list,
    }

    def _render_results(data: dict) -> None:
        table = Table(title=f"Generated {data['count']} instance(s)")
        table.add_column("#", justify="right", style="dim")
        table.add_column("Instance")
        table.add_column("Difficulty")
        table.add_column("Path")

        for inst in data["instances"]:
            table.add_row(
                str(inst["index"]),
                inst["instance"],
                inst["difficulty"],
                inst["path"],
            )

        console.print(table)
        print_success(f"Generated {data['count']} instance(s) in {data['output']}")

    emit(
        "generate task",
        results_data,
        start_time=start,
        human_renderer=_render_results,
    )


@app.command("list-templates")
def list_templates(
    discipline: str | None = typer.Option(None, "--discipline", help="Filter by discipline"),
    user_dir: Path | None = typer.Option(None, "--user-dir", help="Additional directory to scan"),
) -> None:
    """List available templates, optionally filtered by discipline.

    Returns: list of templates, each with name, discipline, category,
    tool_mode, description.

    Examples:
      aec-bench generate list-templates --discipline electrical
      aec-bench --json generate list-templates | jq '.data[].name'
    """
    import time

    start = time.monotonic()
    user_dirs: list[Path] = []
    if user_dir is not None:
        user_dirs.append(user_dir.resolve())

    templates = discover_templates(user_dirs=user_dirs)

    if discipline is not None:
        templates = [(cfg, path) for cfg, path in templates if cfg.meta.discipline == discipline]

    templates_list = [
        {
            "name": cfg.meta.name,
            "discipline": cfg.meta.discipline,
            "category": cfg.meta.category,
            "tool_mode": cfg.meta.tool_mode.value,
            "description": cfg.meta.description,
        }
        for cfg, _path in templates
    ]

    def _render(data: list) -> None:
        if not data:
            console.print("[yellow]No templates found.[/yellow]")
            return

        table = Table(title="Available Templates")
        table.add_column("Name", style="bold")
        table.add_column("Discipline")
        table.add_column("Category")
        table.add_column("Tool Mode")
        table.add_column("Description")

        for t in data:
            table.add_row(
                t["name"],
                t["discipline"],
                t["category"],
                t["tool_mode"],
                t["description"],
            )

        console.print(table)

    emit(
        "generate list-templates",
        templates_list,
        start_time=start,
        human_renderer=_render,
    )


@app.command("validate-template")
def validate_template_cmd(
    template_dir: Path = typer.Argument(help="Path to the template directory to validate"),
) -> None:
    """Validate a template directory for correctness.

    Returns: template, path, valid (bool), errors (list of validation
    messages).

    Examples:
      aec-bench generate validate-template src/aec_bench/templates/builtin/voltage-drop
      aec-bench --json generate validate-template ./my-template | jq '.data.valid'
    """
    import time

    start = time.monotonic()
    resolved = template_dir.resolve()
    errors = validate_template(resolved)

    result_dict: dict[str, object] = {
        "template": resolved.name,
        "path": str(resolved),
        "valid": len(errors) == 0,
        "errors": errors,
    }

    def _render_success(data: dict) -> None:
        print_success(f"Template valid: {data['template']} (0 errors)")

    def _render_failure(data: dict) -> None:
        console.print(f"[red]Template validation failed ({len(data['errors'])} error(s)):[/red]")
        for error in data["errors"]:
            console.print(f"  [red]\u2022[/red] {error}")

    if errors:
        emit(
            "generate validate-template",
            result_dict,
            errors=errors,
            start_time=start,
            human_renderer=_render_failure,
        )
    else:
        emit(
            "generate validate-template",
            result_dict,
            start_time=start,
            human_renderer=_render_success,
        )


@app.command("dataset", deprecated=True)
@app.command("suite")
def generate_suite(
    config: Path = typer.Option(..., "--config", help="Path to suite.toml"),
    seed: int | None = typer.Option(None, "--seed", help="Override seed from config"),
    output: Path | None = typer.Option(None, "--output", help="Override output dir from config"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print plan without writing files"),
    validate_only: bool = typer.Option(False, "--validate-only", help="Check templates and config, then exit"),
) -> None:
    """Generate a suite of task instances from a suite.toml configuration.

    Returns (dry-run): dry_run, suite_name, total_instances, by_discipline,
    by_difficulty, by_visibility, by_tool_mode.

    Returns (live): same plan fields plus instances_generated, manifest_path,
    job_config_path.

    Returns (validate-only): valid, matched_templates, total_templates.

    Examples:
      aec-bench generate suite --config suite.toml --dry-run
      aec-bench --json generate suite --config suite.toml | jq '.data.total_instances'
    """
    import time

    # Lazy imports to keep CLI startup fast
    from aec_bench.generation.dataset import (
        OutputConfig,
        compose_dataset,
        execute_plan,
        filter_templates,
        load_suite_config,
    )
    from aec_bench.templates.registry import discover_templates

    start = time.monotonic()

    # Load config
    config_path = config.resolve()
    if not config_path.exists():
        emit(
            "generate suite",
            data=None,
            errors=[f"config file not found: {config_path}"],
            start_time=start,
        )
        return

    try:
        suite_config = load_suite_config(config_path)
    except Exception as exc:
        emit(
            "generate suite",
            data=None,
            errors=[f"failed to parse config: {exc}"],
            start_time=start,
        )
        return

    # Apply CLI overrides
    if seed is not None:
        suite_config = suite_config.model_copy(update={"seed": seed})
    if output is not None:
        suite_config = suite_config.model_copy(update={"output": OutputConfig(dir=output.resolve())})

    # Discover templates
    templates = discover_templates(user_dirs=[p.resolve() for p in suite_config.templates.user_dirs])

    if validate_only:
        try:
            filtered = filter_templates(templates, include=suite_config.templates.include)
            validate_data: dict[str, object] = {
                "valid": True,
                "matched_templates": len(filtered),
                "total_templates": len(templates),
            }

            def _render_validate(data: dict) -> None:
                print_success(
                    f"Config valid. {data['matched_templates']} template(s) "
                    f"matched, {data['total_templates']} total discovered."
                )

            emit(
                "generate suite",
                validate_data,
                start_time=start,
                human_renderer=_render_validate,
            )
        except ValueError as exc:
            emit(
                "generate suite",
                data=None,
                errors=[str(exc)],
                start_time=start,
            )
        return

    # Compose plan
    try:
        plan = compose_dataset(suite_config, templates)
    except ValueError as exc:
        emit(
            "generate suite",
            data=None,
            errors=[str(exc)],
            start_time=start,
        )
        return

    # Print warnings (to stderr, outside the envelope)
    for warning in plan.warnings:
        print_warning(f"[{warning.category}] {warning.message}")

    plan_summary: dict[str, object] = {
        "suite_name": plan.suite_name,
        "total_instances": plan.summary.total_instances,
        "by_discipline": dict(plan.summary.by_discipline),
        "by_difficulty": dict(plan.summary.by_difficulty),
        "by_visibility": dict(plan.summary.by_visibility),
        "by_tool_mode": dict(plan.summary.by_tool_mode),
    }

    if dry_run:
        dry_data: dict[str, object] = {
            "dry_run": True,
            **plan_summary,
        }

        def _render_dry(data: dict) -> None:
            _render_plan_table(data)
            console.print("[bold]Dry run:[/bold] no files written.")

        emit(
            "generate suite",
            dry_data,
            start_time=start,
            human_renderer=_render_dry,
        )
        return

    # Execute
    manifest = execute_plan(plan, suite_config, config_path=str(config_path))

    out_dir = suite_config.output.dir.resolve()
    result_data: dict[str, object] = {
        "dry_run": False,
        **plan_summary,
        "instances_generated": len(manifest.instances),
        "manifest_path": str(out_dir / "dataset.json"),
        "job_config_path": str(out_dir / "job.yaml"),
    }

    def _render_result(data: dict) -> None:
        _render_plan_table(data)
        print_success(f"Generated {data['instances_generated']} instance(s). Manifest: {data['manifest_path']}")
        print_success(f"Harbor job config: {data['job_config_path']}")

    emit(
        "generate suite",
        result_data,
        start_time=start,
        human_renderer=_render_result,
    )


def _render_plan_table(data: dict) -> None:
    """Render the plan summary table for generate suite output."""
    table = Table(title=f"Dataset: {data['suite_name']} ({data['total_instances']} instances)")
    table.add_column("Category", style="bold")
    table.add_column("Breakdown")

    table.add_row(
        "Discipline",
        ", ".join(f"{k}: {v}" for k, v in data["by_discipline"].items()),
    )
    table.add_row(
        "Difficulty",
        ", ".join(f"{k}: {v}" for k, v in data["by_difficulty"].items()),
    )
    table.add_row(
        "Visibility",
        ", ".join(f"{k}: {v}" for k, v in data["by_visibility"].items()),
    )
    table.add_row(
        "Tool Mode",
        ", ".join(f"{k}: {v}" for k, v in data["by_tool_mode"].items()),
    )
    console.print(table)
