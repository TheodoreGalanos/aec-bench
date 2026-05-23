# ABOUTME: CLI init command for scaffolding an aec-bench project directory.
# ABOUTME: Creates config, directories, skills, and optionally an example task instance.

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from aec_bench.init.scaffold import (
    ScaffoldResult,
    copy_skills,
    create_scaffold,
    write_gitignore,
    write_project_config,
    write_suite_toml,
)

_console = Console()


def init_project(
    *,
    target: Path,
    force: bool = False,
    update_skills: bool = False,
    generate_example: bool = True,
) -> ScaffoldResult:
    """Scaffold an aec-bench project at *target*.

    Returns a ScaffoldResult describing what was created and any messages.
    """
    config_path = target / "aec-bench.toml"
    messages: list[str] = []

    # If already initialised and neither force nor update_skills, bail out.
    if config_path.exists() and not force and not update_skills:
        return ScaffoldResult(
            created=False,
            project_root=target,
            messages=("Already initialised — use --force to overwrite or --update-skills to refresh skills.",),
        )

    # Update-skills-only mode: refresh bundled skills and return.
    if update_skills:
        copy_skills(target)
        return ScaffoldResult(
            created=True,
            project_root=target,
            messages=("Skills updated.",),
        )

    # Full scaffold: directories, config files, skills.
    scaffold_result = create_scaffold(target)
    messages.extend(scaffold_result.messages)

    write_project_config(target, project_name=target.name, force=force)
    messages.append("Wrote aec-bench.toml")

    write_suite_toml(target, force=force)
    messages.append("Wrote suite.toml")

    write_gitignore(target, force=force)
    messages.append("Wrote .gitignore")

    copy_skills(target)
    messages.append("Copied skills to .claude/skills/")

    # Optionally generate one example task instance.
    if generate_example:
        try:
            from aec_bench.generation.sampler import sample_instance
            from aec_bench.generation.scaffolder import scaffold_task_instance
            from aec_bench.templates.registry import discover_templates, load_engine_module

            templates = discover_templates()
            # Find the terzaghi-bearing-capacity template.
            terzaghi = next(
                ((cfg, tdir) for cfg, tdir in templates if cfg.meta.name == "terzaghi-bearing-capacity"),
                None,
            )
            if terzaghi is not None:
                cfg, tdir = terzaghi
                engine_mod = load_engine_module(tdir)
                engine_source = (tdir / "engine.py").read_text(encoding="utf-8")
                # Pick the first difficulty preset available.
                difficulty_name = next(iter(cfg.difficulty))
                instance = sample_instance(
                    cfg,
                    engine_mod.compute,
                    difficulty_name,
                    seed=42,
                    instance_index=0,
                )
                tasks_dir = target / "tasks"
                scaffold_task_instance(cfg, engine_source, tdir, instance, tasks_dir)
                messages.append(f"Generated example instance: {instance.instance_name}")
            else:
                messages.append("Warning: terzaghi-bearing-capacity template not found — skipping example.")
        except Exception as exc:
            messages.append(f"Warning: example generation failed: {exc}")

    return ScaffoldResult(
        created=True,
        project_root=target,
        messages=tuple(messages),
    )


def init_command(
    directory: Path = typer.Argument(Path("."), help="Target directory"),
    update_skills: bool = typer.Option(False, "--update-skills", help="Refresh skills only"),
    force: bool = typer.Option(False, "--force", help="Overwrite config files"),
    no_example: bool = typer.Option(False, "--no-example", help="Skip example generation"),
) -> None:
    """Initialise an aec-bench project directory."""
    target = directory.resolve()
    target.mkdir(parents=True, exist_ok=True)

    result = init_project(
        target=target,
        force=force,
        update_skills=update_skills,
        generate_example=not no_example,
    )

    for msg in result.messages:
        if msg.lower().startswith("warning"):
            _console.print(f"[yellow]{msg}[/yellow]")
        else:
            _console.print(f"[green]{msg}[/green]")

    if not result.created:
        raise typer.Exit(code=1)
