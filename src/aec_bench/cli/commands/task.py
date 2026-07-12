# ABOUTME: CLI commands for task management — validation, inspection, and quality checks.
# ABOUTME: Provides actionable feedback for both human users and AI agents.

from __future__ import annotations

import time
from pathlib import Path

import typer
import yaml

from aec_bench.cli.commands.hydraulic_world import app as hydraulic_world_app
from aec_bench.cli.commands.task_world_templates import app as composite_template_app
from aec_bench.cli.output import console, emit

app = typer.Typer(help="Task management commands.")
app.add_typer(composite_template_app, name="composite-template")
app.add_typer(hydraulic_world_app, name="hydraulic-world")

_SEVERITY_ICONS = {"error": "[red]✗[/red]", "warning": "[yellow]⚠[/yellow]", "info": "[dim]✓[/dim]"}


@app.command("validate")
def validate_command(
    task_path: str = typer.Argument(help="Path to the task directory to validate"),
    tasks_root: str | None = typer.Option(
        None,
        "--tasks-root",
        "-t",
        help="Root tasks directory (for deriving task_id). Defaults to parent of task_path.",
    ),
) -> None:
    """Validate a task directory for structure, schema, and verifier correctness."""
    start = time.monotonic()
    task_dir = Path(task_path).resolve()

    if not task_dir.is_dir():
        emit("task validate", data=None, errors=[f"Not a directory: {task_dir}"], start_time=start)
        raise typer.Exit(1)

    root = Path(tasks_root).resolve() if tasks_root else task_dir.parent.parent
    if not root.is_dir():
        root = task_dir.parent

    from aec_bench.tasks.validator import validate_task

    report = validate_task(task_dir, tasks_root=root)

    # Human-readable output
    console.print(f"\n[bold]{report.task_id}[/bold]\n")

    if not report.findings:
        console.print("  [green]✓ All checks passed[/green]\n")
    else:
        for finding in report.findings:
            icon = _SEVERITY_ICONS.get(finding.severity.value, "?")
            console.print(f"  {icon} [bold]{finding.check}[/bold] — {finding.file}")
            console.print(f"    {finding.message}")
            if finding.fix_hint:
                console.print(f"    [dim]Fix: {finding.fix_hint}[/dim]")

    # Summary line
    if report.passed:
        console.print(f"[green bold]Passed[/green bold] — {report.warning_count} warning(s)\n")
    else:
        console.print(
            f"[red bold]{report.error_count} error(s)[/red bold], "
            f"{report.warning_count} warning(s) — not ready for promotion\n"
        )

    # Structured JSON output for agents
    emit("task validate", report.to_dict(), start_time=start)

    if not report.passed:
        raise typer.Exit(1)


@app.command("genome")
def genome_command(
    task_path: str = typer.Argument(help="Path to the task directory to extract"),
    tasks_root: str | None = typer.Option(
        None,
        "--tasks-root",
        "-t",
        help="Root tasks directory (for deriving task_id). Defaults to parent of task_path.",
    ),
    mode: str = typer.Option(
        "heuristic",
        "--mode",
        help="Extraction mode: heuristic, evidence, or llm.",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="Model name for --mode llm.",
    ),
) -> None:
    """Extract a task genome sidecar manifest as YAML."""
    task_dir = Path(task_path).resolve()
    if not task_dir.is_dir():
        console.print(f"[red]Not a directory:[/red] {task_dir}")
        raise typer.Exit(1)

    root = Path(tasks_root).resolve() if tasks_root else task_dir.parent.parent
    if not root.is_dir():
        root = task_dir.parent

    from aec_bench.tasks.genome import (
        build_task_genome_evidence,
        extract_task_genome,
        task_genome_evidence_to_yaml,
        task_genome_to_yaml,
    )

    if mode == "heuristic":
        manifest = extract_task_genome(task_dir, root)
        typer.echo(task_genome_to_yaml(manifest))
        return

    if mode == "evidence":
        packet = build_task_genome_evidence(task_dir, root)
        typer.echo(task_genome_evidence_to_yaml(packet))
        return

    if mode == "llm":
        if not model:
            console.print("[red]--model is required when --mode llm[/red]")
            raise typer.Exit(1)
        from aec_bench.evolution.task_genome_decomposer import decompose_task_genome

        packet = build_task_genome_evidence(task_dir, root)
        manifest = decompose_task_genome(packet, model_name=model)
        typer.echo(task_genome_to_yaml(manifest))
        return

    console.print("[red]Invalid --mode. Expected heuristic, evidence, or llm.[/red]")
    raise typer.Exit(1)


@app.command("genome-batch")
def genome_batch_command(
    tasks_root: str = typer.Argument(help="Root tasks directory to scan"),
    output_dir: str = typer.Option(
        "task_genomes",
        "--output-dir",
        "-o",
        help="Directory where sidecar manifests should be written.",
    ),
    mode: str = typer.Option(
        "heuristic",
        "--mode",
        help="Extraction mode: heuristic, evidence, or llm.",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="Model name for --mode llm.",
    ),
    domains: str | None = typer.Option(
        None,
        "--domains",
        help="Comma-separated domain filter using manifest discipline, e.g. electrical,mechanical.",
    ),
    include_generated: bool = typer.Option(
        False,
        "--include-generated",
        help="Include generated dataset materializations. Excluded by default.",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="Optional maximum number of manifests to write.",
    ),
) -> None:
    """Extract task genome sidecars for a task tree."""
    root = Path(tasks_root).resolve()
    if not root.is_dir():
        console.print(f"[red]Not a directory:[/red] {root}")
        raise typer.Exit(1)

    if mode not in {"heuristic", "evidence", "llm"}:
        console.print("[red]Invalid --mode. Expected heuristic, evidence, or llm.[/red]")
        raise typer.Exit(1)
    if mode == "llm" and not model:
        console.print("[red]--model is required when --mode llm[/red]")
        raise typer.Exit(1)

    from aec_bench.tasks.genome import (
        build_task_genome_evidence,
        extract_task_genome,
        task_genome_evidence_to_yaml,
        task_genome_to_yaml,
    )
    from aec_bench.tasks.loader import iter_task_instance_dirs

    selected_domains = _parse_domain_filter(domains)
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, str]] = []
    skipped = 0
    errors: list[str] = []

    for task_dir in iter_task_instance_dirs(root):
        relative_parts = task_dir.relative_to(root).parts
        if not include_generated and relative_parts and relative_parts[0] == "generated":
            skipped += 1
            continue

        try:
            if mode == "evidence":
                packet = build_task_genome_evidence(task_dir, root)
                manifest = packet.deterministic_manifest
                body = task_genome_evidence_to_yaml(packet)
            elif mode == "llm":
                from aec_bench.evolution.task_genome_decomposer import decompose_task_genome

                packet = build_task_genome_evidence(task_dir, root)
                manifest = decompose_task_genome(packet, model_name=model or "")
                body = task_genome_to_yaml(manifest)
            else:
                manifest = extract_task_genome(task_dir, root)
                body = task_genome_to_yaml(manifest)
        except Exception as exc:
            errors.append(f"{task_dir.relative_to(root).as_posix()}: {type(exc).__name__}: {exc}")
            continue

        if selected_domains and manifest.domain_frame.discipline not in selected_domains:
            skipped += 1
            continue

        sidecar_path = _catalogue_sidecar_path(destination, manifest.task_id)
        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        sidecar_path.write_text(body, encoding="utf-8")

        entries.append(
            {
                "task_id": manifest.task_id,
                "domain": manifest.domain_frame.discipline,
                "path": sidecar_path.relative_to(destination).as_posix(),
                "status": manifest.status,
            }
        )
        if limit is not None and len(entries) >= limit:
            break

    index = {
        "mode": mode,
        "tasks_root": root.as_posix(),
        "written": len(entries),
        "skipped": skipped,
        "errors": errors,
        "entries": entries,
    }
    (destination / "index.yaml").write_text(
        yaml.safe_dump(index, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )

    console.print(
        f"[green]task genome batch complete[/green] — written: {len(entries)}, "
        f"skipped: {skipped}, errors: {len(errors)}"
    )
    console.print(f"[dim]{destination / 'index.yaml'}[/dim]")
    if errors:
        raise typer.Exit(1)


@app.command("genome-template-batch")
def genome_template_batch_command(
    templates_root: str = typer.Argument(help="Root template directory to scan"),
    output_dir: str = typer.Option(
        "task_genomes/templates",
        "--output-dir",
        "-o",
        help="Directory where template sidecar manifests should be written.",
    ),
    domains: str | None = typer.Option(
        None,
        "--domains",
        help="Comma-separated domain filter using manifest discipline, e.g. electrical,mechanical.",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="Optional maximum number of manifests to write.",
    ),
) -> None:
    """Extract heuristic task genome sidecars for generation templates."""
    root = Path(templates_root).resolve()
    if not root.is_dir():
        console.print(f"[red]Not a directory:[/red] {root}")
        raise typer.Exit(1)

    from aec_bench.templates.genome import (
        extract_template_genome,
        iter_template_dirs,
        template_genome_to_yaml,
    )

    selected_domains = _parse_domain_filter(domains)
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    repo_root = _repo_root_for_catalogue(root)

    entries: list[dict[str, str]] = []
    skipped = 0
    errors: list[str] = []

    for template_dir in iter_template_dirs(root):
        try:
            manifest = extract_template_genome(template_dir, repo_root)
            body = template_genome_to_yaml(manifest)
        except Exception as exc:
            relative_template = template_dir.relative_to(root).as_posix()
            errors.append(f"{relative_template}: {type(exc).__name__}: {exc}")
            continue

        if selected_domains and manifest.domain_frame.discipline not in selected_domains:
            skipped += 1
            continue

        sidecar_path = _catalogue_sidecar_path(destination, manifest.task_id)
        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        sidecar_path.write_text(body, encoding="utf-8")

        entries.append(
            {
                "task_id": manifest.task_id,
                "domain": manifest.domain_frame.discipline,
                "path": sidecar_path.relative_to(destination).as_posix(),
                "status": manifest.status,
            }
        )
        if limit is not None and len(entries) >= limit:
            break

    index = {
        "mode": "heuristic",
        "templates_root": root.as_posix(),
        "written": len(entries),
        "skipped": skipped,
        "errors": errors,
        "entries": entries,
    }
    (destination / "index.yaml").write_text(
        yaml.safe_dump(index, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )

    console.print(
        f"[green]template genome batch complete[/green] — written: {len(entries)}, "
        f"skipped: {skipped}, errors: {len(errors)}"
    )
    console.print(f"[dim]{destination / 'index.yaml'}[/dim]")
    if errors:
        raise typer.Exit(1)


@app.command("decomposition-template-batch")
def decomposition_template_batch_command(
    genomes_root: str = typer.Argument(help="Root template genome directory to scan"),
    output_dir: str = typer.Option(
        "task_decompositions/templates",
        "--output-dir",
        "-o",
        help="Directory where decomposition sidecars should be written.",
    ),
    domains: str | None = typer.Option(
        None,
        "--domains",
        help="Comma-separated domain filter using manifest discipline, e.g. electrical,mechanical.",
    ),
    reviewer: str = typer.Option(
        "codex-spark-normalized",
        "--reviewer",
        help="Reviewer label to store in the decomposition index.",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="Optional maximum number of decompositions to write.",
    ),
) -> None:
    """Build normalized task part decompositions for template genomes."""
    root = Path(genomes_root).resolve()
    if not root.is_dir():
        console.print(f"[red]Not a directory:[/red] {root}")
        raise typer.Exit(1)

    from aec_bench.templates.decomposition import (
        build_template_decomposition,
        load_template_genome,
        task_decomposition_to_yaml,
    )

    selected_domains = _parse_domain_filter(domains)
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, str]] = []
    skipped = 0
    errors: list[str] = []

    genome_paths = sorted(path for path in root.rglob("*.yaml") if path.name != "index.yaml")
    for genome_path in genome_paths:
        try:
            manifest = load_template_genome(genome_path)
        except Exception as exc:
            relative_genome = genome_path.relative_to(root).as_posix()
            errors.append(f"{relative_genome}: {type(exc).__name__}: {exc}")
            continue

        if selected_domains and manifest.domain_frame.discipline not in selected_domains:
            skipped += 1
            continue

        source_genome_path = _relative_catalogue_path(genome_path, root)
        decomposition = build_template_decomposition(
            manifest,
            source_genome_path=source_genome_path,
        )
        sidecar_path = _catalogue_sidecar_path(destination, decomposition.task_id)
        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        sidecar_path.write_text(task_decomposition_to_yaml(decomposition), encoding="utf-8")

        entries.append(
            {
                "task_id": decomposition.task_id,
                "domain": manifest.domain_frame.discipline,
                "path": sidecar_path.relative_to(destination).as_posix(),
                "source_genome_path": decomposition.source_genome_path,
            }
        )
        if limit is not None and len(entries) >= limit:
            break

    index = {
        "version": 1,
        "reviewer": reviewer,
        "genomes_root": root.as_posix(),
        "written": len(entries),
        "skipped": skipped,
        "errors": errors,
        "entries": entries,
    }
    (destination / "index.yaml").write_text(
        yaml.safe_dump(index, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )

    console.print(
        f"[green]template decomposition batch complete[/green] — written: {len(entries)}, "
        f"skipped: {skipped}, errors: {len(errors)}"
    )
    console.print(f"[dim]{destination / 'index.yaml'}[/dim]")
    if errors:
        raise typer.Exit(1)


def _parse_domain_filter(domains: str | None) -> set[str]:
    if not domains:
        return set()
    return {domain.strip() for domain in domains.split(",") if domain.strip()}


def _catalogue_sidecar_path(output_dir: Path, task_id: str) -> Path:
    parts = task_id.split("/")
    filename = f"{parts[-1]}.yaml"
    return output_dir.joinpath(*parts[:-1], filename)


def _relative_catalogue_path(path: Path, fallback_root: Path) -> str:
    resolved = path.resolve()
    cwd = Path.cwd().resolve()
    if resolved == cwd or resolved.is_relative_to(cwd):
        return resolved.relative_to(cwd).as_posix()
    return resolved.relative_to(fallback_root.resolve()).as_posix()


def _repo_root_for_catalogue(path: Path) -> Path:
    cwd = Path.cwd().resolve()
    resolved = path.resolve()
    if resolved == cwd or resolved.is_relative_to(cwd):
        return cwd
    return resolved.parent
