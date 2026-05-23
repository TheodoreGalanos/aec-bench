# ABOUTME: CLI subcommands for creating, listing, and managing benchmark datasets.
# ABOUTME: Wraps dataset.creator, dataset.storage, and dataset.integrity with terminal output.

from __future__ import annotations

from pathlib import Path

import typer

from aec_bench.cli.commands.config import resolve_path
from aec_bench.cli.output import (
    console,
    emit,
    print_error,
    print_success,
    print_warning,
)
from aec_bench.contracts.task_definition import Difficulty

app = typer.Typer(help="Create and manage versioned benchmark datasets.")


@app.command("create")
def create_dataset_cmd(
    name: str = typer.Option(..., "--name", help="Dataset name"),
    version: str = typer.Option(..., "--version", help="Dataset version (e.g. 1.0.0)"),
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to suite.toml (optional)"),
    from_suite_output: Path | None = typer.Option(
        None,
        "--from-suite-output",
        help="Path to a generated suite dataset.json to freeze exactly",
    ),
    domain: list[str] | None = typer.Option(None, "--domain", "-d", help="Filter by domain (repeatable)"),
    difficulty: list[str] | None = typer.Option(
        None,
        "--difficulty",
        help="Filter by difficulty: easy, medium, or hard (repeatable)",
    ),
    pattern: list[str] | None = typer.Option(None, "--pattern", "-p", help="Include pattern (repeatable)"),
    summary: str | None = typer.Option(None, "--summary", help="One-line description"),
    purpose: str | None = typer.Option(None, "--purpose", help="Why this dataset exists"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing version"),
) -> None:
    """Create a dataset by freezing tasks into a versioned manifest.

    Freeze exact generated suite output with --from-suite-output, or filter existing tasks
    with --domain, --difficulty, and/or --pattern. Without filters, includes all tasks.

    Examples:

      aec-bench dataset create --name elec-v1 --version 1.0.0 --domain electrical

      aec-bench dataset create --name easy-v1 --version 1.0.0 --difficulty easy

      aec-bench dataset create --name suite-v1 --version 1.0.0 \\
        --from-suite-output tasks/dataset.json

      aec-bench dataset create --name bench-v1 --version 1.0.0 --pattern "electrical/*"
    """
    from aec_bench.contracts.dataset import DatasetSource
    from aec_bench.dataset.creator import create_dataset_from_tasks
    from aec_bench.tasks.registry import TaskRegistry

    tasks_root = resolve_path("tasks_root")
    datasets_root = resolve_path("datasets_root")

    if from_suite_output is not None and (config is not None or domain or difficulty or pattern):
        print_error("--from-suite-output cannot be combined with --config, --domain, --difficulty, or --pattern")
        raise typer.Exit(1)

    if config is not None:
        import tomllib

        suite_raw = tomllib.loads(config.read_text(encoding="utf-8"))
        source = DatasetSource(
            method="suite_config",
            suite_config=suite_raw,
            seed=suite_raw.get("settings", {}).get("seed"),
        )
    else:
        source = DatasetSource(method="manual")

    if from_suite_output is not None:
        suite_manifest = _load_suite_output_manifest(from_suite_output)
        all_tasks = _load_tasks_from_suite_output(from_suite_output, tasks_root, suite_manifest)
        source = _source_from_suite_output(from_suite_output, suite_manifest)
    else:
        registry = TaskRegistry(tasks_root=tasks_root)
        registry.reload()
        all_tasks = registry.all()

    # Apply filters using select_tasks — same function the experiment pipeline uses
    difficulties = _parse_difficulties(difficulty)

    if domain or difficulties or pattern:
        from aec_bench.tasks.selector import select_tasks

        all_tasks = select_tasks(
            all_tasks,
            domains=domain or None,
            difficulties=difficulties or None,
            include_patterns=pattern or None,
        )

    if not all_tasks:
        print_error("no tasks matched the filters — check --domain, --difficulty, and --pattern")
        raise typer.Exit(1)

    try:
        manifest = create_dataset_from_tasks(
            name=name,
            version=version,
            tasks=all_tasks,
            tasks_root=tasks_root,
            datasets_root=datasets_root,
            source=source,
            summary=summary,
            purpose=purpose,
            overwrite=overwrite,
        )
    except FileExistsError as exc:
        print_error(str(exc))
        raise typer.Exit(1) from exc

    print_success(
        f"Created dataset {manifest.name}@{manifest.version} "
        f"({manifest.description.task_count} tasks, hash: {manifest.content_hash[:12]})"
    )


def _parse_difficulties(values: list[str] | None) -> list[Difficulty]:
    if not values:
        return []

    parsed: list[Difficulty] = []
    for raw_value in values:
        try:
            parsed.append(Difficulty(raw_value))
        except ValueError as exc:
            allowed = ", ".join(difficulty.value for difficulty in Difficulty)
            print_error(f"unknown difficulty: {raw_value}. Available: {allowed}")
            raise typer.Exit(1) from exc
    return parsed


def _load_suite_output_manifest(suite_output: Path):
    from aec_bench.generation.dataset import DatasetManifest as SuiteOutputManifest

    manifest_path = suite_output.resolve()
    if not manifest_path.is_file():
        print_error(f"suite output not found: {manifest_path}")
        raise typer.Exit(1)

    try:
        return SuiteOutputManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print_error(f"failed to read suite output: {exc}")
        raise typer.Exit(1) from exc


def _load_tasks_from_suite_output(suite_output: Path, tasks_root: Path, manifest):
    from aec_bench.tasks.loader import load_task_definition

    manifest_path = suite_output.resolve()
    suite_root = manifest_path.parent
    resolved_tasks_root = tasks_root.resolve()
    tasks = []
    for entry in manifest.instances:
        task_dir = (suite_root / entry.path).resolve()
        if not task_dir.is_dir():
            print_error(f"suite output references missing task directory: {task_dir}")
            raise typer.Exit(1)
        try:
            task_dir.relative_to(resolved_tasks_root)
        except ValueError as exc:
            print_error(
                f"suite output task is outside tasks root: {task_dir}. "
                f"Generate suites under {resolved_tasks_root} before freezing them."
            )
            raise typer.Exit(1) from exc
        tasks.append(load_task_definition(task_dir, resolved_tasks_root))

    return tasks


def _source_from_suite_output(suite_output: Path, manifest):
    from aec_bench.contracts.dataset import DatasetSource

    manifest_path = suite_output.resolve()
    suite_data = manifest.model_dump(mode="json")
    suite_data["suite_output"] = str(manifest_path)
    return DatasetSource(
        method="suite_config",
        suite_config=suite_data,
        seed=manifest.seed,
    )


@app.command("config")
def dataset_config_cmd(
    dataset_ref: str = typer.Argument(help="Dataset name or name@version"),
    model: str = typer.Option(..., "--model", "-m", help="Model name (e.g. gpt-41-mini)"),
    adapter: str = typer.Option("tool_loop", "--adapter", "--harness", help="Agent harness"),
    backend: str = typer.Option("modal", "--backend", help="Compute backend"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write to file (default: stdout)"),
    repetitions: int = typer.Option(1, "--repetitions", "-n", help="Repetitions per task"),
) -> None:
    """Generate an experiment.yaml from a dataset reference.

    Example:

      aec-bench dataset config electrical-only@1.0.0 --model gpt-41-mini -o experiment.yaml
    """
    from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
    from aec_bench.dataset.experiment import build_experiment_config, write_experiment_yaml
    from aec_bench.dataset.storage import resolve_dataset

    # Verify dataset exists
    datasets_root = resolve_path("datasets_root")
    resolved = resolve_dataset(datasets_root, dataset_ref)
    if resolved is None:
        print_error(f"Dataset {dataset_ref} not found")
        raise typer.Exit(1)

    # Use the resolved name@version for the reference
    full_ref = f"{resolved.name}@{resolved.version}"

    agent_name = f"{adapter}-{model.split('-')[0]}"
    agents = [AgentConfig(name=agent_name, adapter=adapter, model=model)]
    compute = ComputeConfig(backend=backend, resource_limits={"n_concurrent_trials": 1})

    manifest = build_experiment_config(
        dataset=full_ref,
        agents=agents,
        compute=compute,
        repetitions=repetitions,
    )

    yaml_str = write_experiment_yaml(manifest, output_path=str(output) if output else None)

    if output:
        print_success(f"Wrote experiment config to {output}")
    else:
        console.print(yaml_str)


@app.command("list")
def list_datasets_cmd(
    datasets_root: str | None = typer.Option(None, "--datasets-root", help="Datasets directory"),
) -> None:
    """List all datasets and their versions.

    Returns: list of datasets, each with name, version, task_count, domains,
    content_hash, created_at.

    Examples:
      aec-bench dataset list
      aec-bench dataset list --json | jq '.data[].name'
    """
    import time

    from aec_bench.dataset.storage import list_datasets

    start = time.monotonic()
    resolved_root = resolve_path("datasets_root", cli_override=datasets_root)
    manifests = list_datasets(resolved_root)

    if not manifests:
        emit("dataset list", [], start_time=start, human_renderer=_render_dataset_list)
        return

    data = [
        {
            "name": m.name,
            "version": m.version,
            "task_count": m.description.task_count,
            "domains": m.description.domains,
            "content_hash": m.content_hash[:12],
            "created_at": m.created_at.isoformat(),
        }
        for m in manifests
    ]

    emit("dataset list", data, start_time=start, human_renderer=_render_dataset_list)


def _render_dataset_list(data: list) -> None:
    """Human renderer for dataset list output."""
    if not data:
        console.print("[dim]No datasets found.[/dim]")
        return

    from rich.table import Table

    table = Table(title=f"Datasets ({len(data)} total)")
    table.add_column("Name", style="bold")
    table.add_column("Version")
    table.add_column("Tasks", justify="right")
    table.add_column("Domains")
    table.add_column("Hash", style="dim")
    table.add_column("Created", style="dim")

    for m in data:
        table.add_row(
            m["name"],
            m["version"],
            str(m["task_count"]),
            ", ".join(m["domains"]),
            m["content_hash"],
            m["created_at"],
        )

    console.print(table)


@app.command("info")
def dataset_info(
    reference: str = typer.Argument(help="Dataset name or name@version"),
) -> None:
    """Show dataset description and integrity status.

    Returns: name, version, summary, purpose, task_count, template_count,
    domains, standards, difficulty_distribution, created_at, content_hash,
    integrity (verified, total, drifted, missing, is_clean).

    Examples:
      aec-bench dataset info electrical-only@1.0.0
      aec-bench dataset info electrical-only --json | jq '.data.integrity'
    """
    import time

    from aec_bench.config import load_config
    from aec_bench.dataset.integrity import verify_dataset_integrity
    from aec_bench.dataset.storage import resolve_dataset

    start = time.monotonic()
    datasets_root = resolve_path("datasets_root")
    manifest = resolve_dataset(datasets_root, reference)
    if manifest is None:
        emit(
            "dataset info",
            data=None,
            errors=[f"dataset not found: {reference}"],
            start_time=start,
        )
        return

    desc = manifest.description
    project_root = load_config().project_root
    integrity = verify_dataset_integrity(manifest.tasks, project_root=project_root)

    info_dict: dict[str, object] = {
        "name": manifest.name,
        "version": manifest.version,
        "summary": desc.summary,
        "purpose": desc.purpose,
        "task_count": desc.task_count,
        "template_count": desc.template_count,
        "domains": desc.domains,
        "standards": desc.standards,
        "difficulty_distribution": desc.difficulty_distribution,
        "created_at": manifest.created_at.isoformat(),
        "content_hash": manifest.content_hash,
        "integrity": {
            "verified": integrity.verified,
            "total": len(manifest.tasks),
            "drifted": list(integrity.drifted),
            "missing": list(integrity.missing),
            "is_clean": integrity.is_clean,
        },
    }

    integrity_errors: list[str] = []
    if not integrity.is_clean:
        parts: list[str] = []
        if integrity.drifted:
            parts.append(f"{len(integrity.drifted)} drifted")
        if integrity.missing:
            parts.append(f"{len(integrity.missing)} missing")
        integrity_errors.append(", ".join(parts))

    def _render(data: dict) -> None:
        console.print(f"[bold]{data['name']}[/bold] v{data['version']}")
        console.print(f"  {data['summary']}")
        if data.get("purpose"):
            console.print(f"  [dim]Purpose:[/dim] {data['purpose']}")
        console.print(f"  [dim]Domains:[/dim] {', '.join(data['domains'])}")
        console.print(f"  [dim]Tasks:[/dim] {data['task_count']}")
        console.print(f"  [dim]Templates:[/dim] {data['template_count']}")
        if data.get("standards"):
            console.print(f"  [dim]Standards:[/dim] {', '.join(data['standards'])}")
        console.print(f"  [dim]Difficulty:[/dim] {data['difficulty_distribution']}")
        console.print(f"  [dim]Hash:[/dim] {data['content_hash'][:16]}...")
        console.print(f"  [dim]Created:[/dim] {data['created_at']}")

        integ = data["integrity"]
        if integ["is_clean"]:
            print_success(f"Integrity: {integ['verified']}/{integ['total']} tasks verified")
        else:
            if integ["drifted"]:
                print_warning(f"Drifted: {', '.join(integ['drifted'])}")
            if integ["missing"]:
                print_warning(f"Missing: {', '.join(integ['missing'])}")

    emit(
        "dataset info",
        info_dict,
        errors=integrity_errors or None,
        start_time=start,
        human_renderer=_render,
    )


@app.command("export")
def export_dataset_cmd(
    reference: str = typer.Argument(help="Dataset name or name@version"),
    output: Path = typer.Option(..., "--output", "-o", help="Output archive path (.tar.gz)"),
) -> None:
    """Export a dataset as a portable archive."""
    from aec_bench.config import load_config
    from aec_bench.dataset.porter import export_dataset
    from aec_bench.dataset.storage import resolve_dataset

    datasets_root = resolve_path("datasets_root")
    manifest = resolve_dataset(datasets_root, reference)
    if manifest is None:
        print_error(f"dataset not found: {reference}")
        raise typer.Exit(1)

    project_root = load_config().project_root
    export_dataset(manifest=manifest, project_root=project_root, output_path=output)
    print_success(f"Exported {manifest.name}@{manifest.version} to {output}")


@app.command("import")
def import_dataset_cmd(
    archive: Path = typer.Argument(help="Path to dataset archive (.tar.gz)"),
) -> None:
    """Import a dataset from a portable archive."""
    from aec_bench.dataset.porter import import_dataset

    if not archive.exists():
        print_error(f"archive not found: {archive}")
        raise typer.Exit(1)

    tasks_root = resolve_path("tasks_root")
    datasets_root = resolve_path("datasets_root")

    try:
        manifest = import_dataset(
            archive_path=archive,
            tasks_root=tasks_root,
            datasets_root=datasets_root,
        )
    except (ValueError, FileExistsError) as e:
        print_error(str(e))
        raise typer.Exit(1) from e

    print_success(f"Imported {manifest.name}@{manifest.version} ({manifest.description.task_count} tasks)")


@app.command("validate")
def validate_dataset(
    reference: str = typer.Argument(help="Dataset name or name@version"),
) -> None:
    """Verify dataset integrity. Exits 0 if clean, 1 if drifted or missing.

    Returns: verified, total, drifted (list), missing (list), is_clean.

    Examples:
      aec-bench dataset validate electrical-only@1.0.0
      aec-bench dataset validate electrical-only --json | jq '.data.is_clean'
    """
    import time

    from aec_bench.config import load_config
    from aec_bench.dataset.integrity import verify_dataset_integrity
    from aec_bench.dataset.storage import resolve_dataset

    start = time.monotonic()
    datasets_root = resolve_path("datasets_root")
    manifest = resolve_dataset(datasets_root, reference)
    if manifest is None:
        emit(
            "dataset validate",
            data=None,
            errors=[f"dataset not found: {reference}"],
            start_time=start,
        )
        return

    project_root = load_config().project_root
    result = verify_dataset_integrity(manifest.tasks, project_root=project_root)

    result_dict: dict[str, object] = {
        "verified": result.verified,
        "total": len(manifest.tasks),
        "drifted": list(result.drifted),
        "missing": list(result.missing),
        "is_clean": result.is_clean,
    }

    def _render_success(data: dict) -> None:
        print_success(f"{data['verified']}/{data['total']} tasks verified — clean")

    def _render_failure(data: dict) -> None:
        if data["drifted"]:
            print_error(f"Drifted tasks: {', '.join(data['drifted'])}")
        if data["missing"]:
            print_error(f"Missing tasks: {', '.join(data['missing'])}")

    if result.is_clean:
        emit(
            "dataset validate",
            result_dict,
            start_time=start,
            human_renderer=_render_success,
        )
    else:
        errors_summary: list[str] = []
        parts: list[str] = []
        if result.drifted:
            parts.append(f"{len(result.drifted)} drifted")
        if result.missing:
            parts.append(f"{len(result.missing)} missing")
        errors_summary.append(", ".join(parts))

        emit(
            "dataset validate",
            result_dict,
            errors=errors_summary,
            start_time=start,
            human_renderer=_render_failure,
        )


@app.command("results")
def dataset_results_cmd(
    reference: str = typer.Argument(help="Dataset name or name@version"),
) -> None:
    """Show experiment results for all trials that used this dataset.

    Returns: dataset_id, summary (total_trials, mean_reward, passed, failed,
    total_tokens), trials list (task_id, model, reward, tokens_in, turns
    per trial).

    Examples:
      aec-bench dataset results electrical-only@1.0.0
      aec-bench dataset results electrical-only --json | jq '.data.summary'
    """
    import time

    from aec_bench.dataset.storage import resolve_dataset
    from aec_bench.ledger.reader import query_trial_records

    start = time.monotonic()
    datasets_root = resolve_path("datasets_root")
    manifest = resolve_dataset(datasets_root, reference)
    if manifest is None:
        emit(
            "dataset results",
            data=None,
            errors=[f"Dataset {reference} not found"],
            start_time=start,
        )
        return

    dataset_id = f"{manifest.name}@{manifest.version}"
    ledger_root = resolve_path("ledger_root")
    records = query_trial_records(ledger_root, dataset_id=dataset_id)

    if not records:
        empty_data: dict[str, object] = {
            "dataset_id": dataset_id,
            "trials": [],
            "summary": {
                "total_trials": 0,
                "mean_reward": 0.0,
                "passed": 0,
                "failed": 0,
                "total_tokens": 0,
            },
        }

        def _render_empty(data: dict) -> None:
            console.print(f"[dim]No trial results found for dataset {data['dataset_id']}[/dim]")
            console.print("[dim]Run an experiment referencing this dataset first.[/dim]")

        emit("dataset results", empty_data, start_time=start, human_renderer=_render_empty)
        return

    # Summary stats
    rewards = [r.evaluation.reward for r in records]
    mean_reward = sum(rewards) / len(rewards) if rewards else 0.0
    passed = sum(1 for r in rewards if r >= 1.0)
    failed = sum(1 for r in rewards if r == 0.0)
    total_tokens = sum((r.cost.tokens_in or 0) for r in records)

    # Per-task results
    trials_list: list[dict[str, object]] = []
    for record in sorted(records, key=lambda r: r.task.task_id):
        agent_result = record.outputs.agent_result or {}
        trials_list.append(
            {
                "task_id": record.task.task_id,
                "model": record.agent.model,
                "reward": record.evaluation.reward,
                "tokens_in": record.cost.tokens_in if record.cost else None,
                "turns": agent_result.get("turns_used"),
            }
        )

    results_data: dict[str, object] = {
        "dataset_id": dataset_id,
        "trials": trials_list,
        "summary": {
            "total_trials": len(records),
            "mean_reward": mean_reward,
            "passed": passed,
            "failed": failed,
            "total_tokens": total_tokens,
        },
    }

    def _render(data: dict) -> None:
        from rich.table import Table

        summary = data["summary"]
        console.print(f"\n[bold]{data['dataset_id']}[/bold] — {summary['total_trials']} trials")
        console.print(
            f"  Mean reward: [bold]{summary['mean_reward']:.3f}[/bold]  "
            f"Pass: [green]{summary['passed']}[/green]  "
            f"Fail: [red]{summary['failed']}[/red]  "
            f"Tokens: {summary['total_tokens']:,}"
        )

        table = Table(title="Results by Task")
        table.add_column("Task")
        table.add_column("Agent")
        table.add_column("Reward", justify="right")
        table.add_column("Tokens In", justify="right")
        table.add_column("Turns", justify="right")

        for trial in data["trials"]:
            reward = trial["reward"]
            reward_color = "green" if reward >= 1.0 else "red" if reward == 0.0 else "yellow"
            tokens_in = f"{trial['tokens_in']:,}" if trial["tokens_in"] is not None else "\u2014"
            turns = str(trial["turns"]) if trial["turns"] is not None else "\u2014"

            table.add_row(
                trial["task_id"],
                trial["model"],
                f"[{reward_color}]{reward:.3f}[/]",
                tokens_in,
                turns,
            )

        console.print(table)

    emit("dataset results", results_data, start_time=start, human_renderer=_render)
