# ABOUTME: CLI commands for semantic dataset manifests and immutable publications.
# ABOUTME: Resolves human labels to exact repository or bundle references before execution.

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import typer

from aec_bench.cli.commands.config import resolve_path
from aec_bench.cli.output import console, emit, print_error, print_success
from aec_bench.contracts.task_definition import Difficulty

app = typer.Typer(help="Create, publish, and inspect benchmark datasets.")


@app.command("create")
def create_dataset_cmd(
    name: str = typer.Argument(help="Stable dataset ID"),
    config: Path | None = typer.Option(None, "--config", "-c", help="Generation config path"),
    from_suite_output: Path | None = typer.Option(
        None,
        "--from-suite-output",
        help="Generated suite generation-manifest.json whose exact task selection is used",
    ),
    domain: list[str] | None = typer.Option(None, "--domain", "-d", help="Filter by domain"),
    difficulty: list[str] | None = typer.Option(None, "--difficulty", help="Filter by difficulty"),
    pattern: list[str] | None = typer.Option(None, "--pattern", "-p", help="Include task pattern"),
    description: str | None = typer.Option(None, "--description", help="Dataset description"),
) -> None:
    """Create one immutable schema-2 manifest from selected local tasks."""

    from aec_bench.contracts.dataset import DatasetGeneration
    from aec_bench.dataset.creator import compose_dataset
    from aec_bench.dataset.storage import save_dataset
    from aec_bench.generation.application import load_generated_tasks, read_generated_task_set
    from aec_bench.tasks.registry import TaskRegistry

    tasks_root = resolve_path("tasks_root")
    datasets_root = resolve_path("datasets_root")
    project_root = tasks_root.parent.resolve()

    if from_suite_output is not None and (config is not None or domain or difficulty or pattern):
        print_error("--from-suite-output cannot be combined with --config, --domain, --difficulty, or --pattern")
        raise typer.Exit(1)

    generation: DatasetGeneration | None = None
    if from_suite_output is not None:
        try:
            generated = read_generated_task_set(from_suite_output)
            selected = load_generated_tasks(generated, tasks_root=tasks_root)
        except (FileNotFoundError, ValueError) as error:
            print_error(str(error))
            raise typer.Exit(1) from error
        suite = generated.manifest
        generation = DatasetGeneration(seed=suite.instances[0].seed, config_ref=suite.config_ref)
    else:
        registry = TaskRegistry(tasks_root=tasks_root)
        registry.reload()
        selected = registry.all()
        if config is not None:
            import tomllib

            config_path = config.resolve()
            try:
                config_ref = config_path.relative_to(project_root).as_posix()
            except ValueError as error:
                print_error("--config must be inside the project root")
                raise typer.Exit(1) from error
            raw_config = tomllib.loads(config_path.read_text(encoding="utf-8"))
            seed = raw_config.get("settings", {}).get("seed")
            generation = DatasetGeneration(seed=seed if isinstance(seed, int) else None, config_ref=config_ref)

    difficulties = _parse_difficulties(difficulty)
    if domain or difficulties or pattern:
        from aec_bench.tasks.selector import select_tasks

        selected = select_tasks(
            selected,
            domains=domain or None,
            difficulties=difficulties or None,
            include_patterns=pattern or None,
        )
    if not selected:
        print_error("no tasks matched the dataset selection")
        raise typer.Exit(1)

    try:
        manifest = compose_dataset(
            dataset_id=name,
            tasks=selected,
            tasks_root=tasks_root,
            description=description or f"Dataset {name}",
            generation=generation,
        )
        save_dataset(datasets_root, manifest)
    except (FileExistsError, FileNotFoundError, ValueError) as error:
        print_error(str(error))
        raise typer.Exit(1) from error

    print_success(f"Created dataset {manifest.dataset_id} ({len(manifest.tasks)} tasks)")


@app.command("publish")
def publish_dataset_cmd(
    name: str = typer.Argument(help="Stable dataset ID"),
    label: str = typer.Option(..., "--label", help="Human discovery label"),
    repository: bool = typer.Option(False, "--repository", help="Use the current Git commit instead of a bundle"),
) -> None:
    """Publish an exact immutable dataset reference under one new label."""

    from aec_bench.config import load_config
    from aec_bench.dataset.publication import publish_dataset
    from aec_bench.dataset.storage import read_manifest_by_id

    config = load_config()
    manifest = read_manifest_by_id(config.datasets_root, name)
    if manifest is None:
        print_error(f"dataset manifest not found: {name}")
        raise typer.Exit(1)
    try:
        publication = publish_dataset(
            manifest=manifest,
            datasets_root=config.datasets_root,
            project_root=config.project_root,
            label=label,
            repository=repository,
        )
    except (FileExistsError, FileNotFoundError, ValueError) as error:
        print_error(str(error))
        raise typer.Exit(1) from error
    print_success(f"Published {name}@{label} as an immutable {publication.dataset_ref.kind} reference")


@app.command("config")
def dataset_config_cmd(
    dataset_ref: str = typer.Argument(help="Dataset ID or ID@label"),
    model: str = typer.Option(..., "--model", "-m", help="Model name"),
    adapter: str = typer.Option("tool_loop", "--adapter", "--harness", help="Agent harness"),
    backend: str = typer.Option("modal", "--backend", help="Compute backend"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write to file instead of stdout"),
    repetitions: int = typer.Option(1, "--repetitions", "-n", help="Repetitions per task"),
) -> None:
    """Resolve a dataset label and write an experiment with the exact reference."""

    from aec_bench.config import load_config
    from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
    from aec_bench.dataset.experiment import build_experiment_config, write_experiment_yaml
    from aec_bench.dataset.publication import resolve_dataset

    config = load_config()
    resolved = resolve_dataset(
        datasets_root=config.datasets_root,
        selector=dataset_ref,
        project_root=config.project_root,
    )
    if resolved is None:
        print_error(f"dataset publication not found: {dataset_ref}")
        raise typer.Exit(1)

    manifest = build_experiment_config(
        dataset=resolved.reference,
        agents=[AgentConfig(name=f"{adapter}-{model.split('-')[0]}", adapter=adapter, model=model)],
        compute=ComputeConfig(backend=backend, resource_limits={"n_concurrent_trials": 1}),
        repetitions=repetitions,
    )
    yaml_text = write_experiment_yaml(manifest, output_path=str(output) if output else None)
    if output is None:
        console.print(yaml_text)
    else:
        print_success(f"Wrote experiment config to {output}")


@app.command("list")
def list_datasets_cmd(
    datasets_root: str | None = typer.Option(None, "--datasets-root", help="Datasets directory"),
) -> None:
    """List stable dataset IDs, task counts, and publication labels."""

    from aec_bench.dataset.storage import list_datasets, list_publications

    start = time.monotonic()
    root = resolve_path("datasets_root", cli_override=datasets_root)
    labels: dict[str, list[str]] = {}
    for publication in list_publications(root):
        labels.setdefault(publication.dataset_ref.dataset_id, []).append(publication.label)
    data = [
        {
            "dataset_id": manifest.dataset_id,
            "description": manifest.description,
            "task_count": len(manifest.tasks),
            "labels": sorted(labels.get(manifest.dataset_id, [])),
        }
        for manifest in list_datasets(root)
    ]
    emit("dataset list", data, start_time=start, human_renderer=_render_dataset_list)


def _render_dataset_list(data: list[dict[str, Any]]) -> None:
    if not data:
        console.print("[dim]No datasets found.[/dim]")
        return
    from rich.table import Table

    table = Table(title=f"Datasets ({len(data)} total)")
    table.add_column("Dataset", style="bold")
    table.add_column("Tasks", justify="right")
    table.add_column("Labels")
    table.add_column("Description")
    for item in data:
        table.add_row(
            item["dataset_id"],
            str(item["task_count"]),
            ", ".join(item["labels"]) or "—",
            item["description"],
        )
    console.print(table)


@app.command("info")
def dataset_info(reference: str = typer.Argument(help="Dataset ID or ID@label")) -> None:
    """Show semantic content and exact-reference integrity for a publication."""

    from aec_bench.config import load_config
    from aec_bench.dataset.publication import resolve_dataset, verify_resolved_dataset

    start = time.monotonic()
    config = load_config()
    resolved = resolve_dataset(
        datasets_root=config.datasets_root,
        selector=reference,
        project_root=config.project_root,
    )
    if resolved is None:
        emit("dataset info", None, errors=[f"dataset publication not found: {reference}"], start_time=start)
        return
    integrity = verify_resolved_dataset(
        resolved,
        datasets_root=config.datasets_root,
        project_root=config.project_root,
    )
    data = _dataset_info_data(resolved.reference.kind, resolved.manifest, integrity)
    emit(
        "dataset info",
        data,
        errors=None if integrity.is_clean else ["dataset materialisation failed integrity verification"],
        start_time=start,
        human_renderer=_render_dataset_info,
    )


def _dataset_info_data(kind: str, manifest: Any, integrity: Any) -> dict[str, Any]:
    return {
        "dataset_id": manifest.dataset_id,
        "description": manifest.description,
        "task_count": len(manifest.tasks),
        "task_ids": [task.task_id for task in manifest.tasks],
        "reference_kind": kind,
        "integrity": {
            "verified": integrity.verified,
            "missing": list(integrity.missing),
            "modified": list(integrity.modified),
            "unexpected": list(integrity.unexpected),
            "is_clean": integrity.is_clean,
        },
    }


def _render_dataset_info(data: dict[str, Any]) -> None:
    console.print(f"[bold]{data['dataset_id']}[/bold]")
    console.print(f"  {data['description']}")
    console.print(f"  [dim]Tasks:[/dim] {data['task_count']}")
    console.print(f"  [dim]Reference:[/dim] {data['reference_kind']}")
    integrity = data["integrity"]
    if integrity["is_clean"]:
        print_success(f"Integrity: {integrity['verified']}/{data['task_count']} tasks verified")
    else:
        print_error("Dataset materialisation is not clean")


@app.command("export")
def export_dataset_cmd(
    reference: str = typer.Argument(help="Dataset ID or ID@label"),
    output: Path = typer.Option(..., "--output", "-o", help="Output archive path"),
) -> None:
    """Export one resolved dataset as a deterministic detached bundle."""

    from aec_bench.config import load_config
    from aec_bench.contracts.dataset import BundleDatasetRef
    from aec_bench.dataset.porter import export_dataset
    from aec_bench.dataset.publication import resolve_dataset, verify_resolved_dataset
    from aec_bench.ledger.artifact_repository import ArtifactRepository

    config = load_config()
    resolved = resolve_dataset(
        datasets_root=config.datasets_root,
        selector=reference,
        project_root=config.project_root,
    )
    if resolved is None:
        print_error(f"dataset publication not found: {reference}")
        raise typer.Exit(1)
    integrity = verify_resolved_dataset(
        resolved,
        datasets_root=config.datasets_root,
        project_root=config.project_root,
    )
    if not integrity.is_clean:
        print_error("dataset materialisation failed integrity verification")
        raise typer.Exit(1)
    try:
        if output.exists():
            raise FileExistsError(f"dataset export already exists: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(resolved.reference, BundleDatasetRef):
            payload = ArtifactRepository(config.datasets_root / "artifacts").read_bytes(resolved.reference.artifact)
            output.write_bytes(payload)
        else:
            export_dataset(manifest=resolved.manifest, project_root=config.project_root, output_path=output)
    except (FileExistsError, FileNotFoundError, ValueError) as error:
        print_error(str(error))
        raise typer.Exit(1) from error
    print_success(f"Exported {resolved.manifest.dataset_id} to {output}")


@app.command("import")
def import_dataset_cmd(archive: Path = typer.Argument(help="Schema-2 dataset bundle")) -> None:
    """Validate and import a detached dataset bundle without overwriting local data."""

    from aec_bench.dataset.porter import import_dataset

    if not archive.is_file():
        print_error(f"archive not found: {archive}")
        raise typer.Exit(1)
    try:
        imported = import_dataset(
            archive_path=archive,
            tasks_root=resolve_path("tasks_root"),
            datasets_root=resolve_path("datasets_root"),
        )
    except (FileExistsError, ValueError) as error:
        print_error(str(error))
        raise typer.Exit(1) from error
    print_success(f"Imported {imported.manifest.dataset_id} ({len(imported.manifest.tasks)} tasks)")


@app.command("validate")
def validate_dataset(reference: str = typer.Argument(help="Dataset ID or ID@label")) -> None:
    """Verify exact source identity and current task materialisation."""

    from aec_bench.config import load_config
    from aec_bench.dataset.publication import resolve_dataset, verify_resolved_dataset

    start = time.monotonic()
    config = load_config()
    resolved = resolve_dataset(
        datasets_root=config.datasets_root,
        selector=reference,
        project_root=config.project_root,
    )
    if resolved is None:
        emit("dataset validate", None, errors=[f"dataset publication not found: {reference}"], start_time=start)
        return
    result = verify_resolved_dataset(
        resolved,
        datasets_root=config.datasets_root,
        project_root=config.project_root,
    )
    data = {
        "verified": result.verified,
        "total": len(resolved.manifest.tasks),
        "missing": list(result.missing),
        "modified": list(result.modified),
        "unexpected": list(result.unexpected),
        "is_clean": result.is_clean,
    }
    emit(
        "dataset validate",
        data,
        errors=None if result.is_clean else ["dataset materialisation failed integrity verification"],
        start_time=start,
        human_renderer=lambda item: print_success(f"{item['verified']}/{item['total']} tasks verified — clean")
        if item["is_clean"]
        else print_error("Dataset materialisation is not clean"),
    )


@app.command("results")
def dataset_results_cmd(reference: str = typer.Argument(help="Dataset ID or ID@label")) -> None:
    """Show trial results pinned to the resolved immutable dataset reference."""

    from aec_bench.config import load_config
    from aec_bench.contracts.dataset import dataset_reference_key
    from aec_bench.dataset.publication import resolve_dataset
    from aec_bench.ledger.reader import query_trial_records

    start = time.monotonic()
    config = load_config()
    resolved = resolve_dataset(
        datasets_root=config.datasets_root,
        selector=reference,
        project_root=config.project_root,
    )
    if resolved is None:
        emit("dataset results", None, errors=[f"dataset publication not found: {reference}"], start_time=start)
        return
    identity = dataset_reference_key(resolved.reference)
    records = query_trial_records(config.ledger_root, dataset_id=identity)
    rewards = [record.evaluation.reward for record in records]
    data = {
        "dataset_id": resolved.manifest.dataset_id,
        "reference_kind": resolved.reference.kind,
        "summary": {
            "total_trials": len(records),
            "mean_reward": sum(rewards) / len(rewards) if rewards else 0.0,
            "passed": sum(reward >= 1.0 for reward in rewards),
            "failed": sum(reward == 0.0 for reward in rewards),
        },
    }
    emit("dataset results", data, start_time=start)


def _parse_difficulties(values: list[str] | None) -> list[Difficulty]:
    parsed: list[Difficulty] = []
    for value in values or []:
        try:
            parsed.append(Difficulty(value))
        except ValueError as error:
            print_error(f"unknown difficulty: {value}. Available: {', '.join(item.value for item in Difficulty)}")
            raise typer.Exit(1) from error
    return parsed
