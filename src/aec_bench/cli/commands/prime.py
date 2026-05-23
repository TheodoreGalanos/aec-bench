# ABOUTME: CLI commands for Prime Lab export and hosted-training handoff.
# ABOUTME: Converts selected aec-bench tasks into verifiers environment packages.

from __future__ import annotations

import fnmatch
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import typer

from aec_bench.cli.commands.config import resolve_path
from aec_bench.cli.output import emit, print_success
from aec_bench.prime_lab.exporter import DEFAULT_PRIME_ENVIRONMENTS_DIR, normalise_environment_id

app = typer.Typer(help="Export aec-bench tasks for Prime Lab.")


@dataclass(frozen=True)
class _PrimePackageExport:
    env_id: str
    package_dir: Path
    task_count: int


@app.command("export")
def export_prime_lab(
    name: str = typer.Option(..., "--name", help="Prime environment package name"),
    output_dir: Path = typer.Option(
        DEFAULT_PRIME_ENVIRONMENTS_DIR, "--output-dir", "-o", help="Directory for generated package"
    ),
    tasks_root: str | None = typer.Option(None, "--tasks-root", help="Tasks root override"),
    dataset: str | None = typer.Option(
        None,
        "--dataset",
        help="Dataset name or name@version to export as a Prime task collection.",
    ),
    datasets_root: str | None = typer.Option(
        None,
        "--datasets-root",
        help="Datasets root override for --dataset resolution.",
    ),
    pattern: list[str] | None = typer.Option(None, "--pattern", "-p", help="Task ID glob to include; repeatable"),
    task: list[str] | None = typer.Option(None, "--task", "-t", help="Exact task ID to include; repeatable"),
    version: str = typer.Option("0.1.0", "--version", help="Generated package version"),
    harness_mode: str = typer.Option(
        "auto",
        "--harness-mode",
        help="Prime harness mode: auto, single-turn, or stateful-workspace.",
    ),
) -> None:
    """Export selected tasks as a Prime Lab/verifiers environment package."""
    from aec_bench.prime_lab.exporter import (
        PrimeExportHarnessMode,
        PrimeLabExportConfig,
        export_prime_lab_environment,
    )
    from aec_bench.tasks.loader import derive_task_id, iter_task_instance_dirs

    resolved_tasks_root = resolve_path("tasks_root", cli_override=tasks_root)
    available_task_ids = [
        derive_task_id(instance_dir, resolved_tasks_root)
        for instance_dir in iter_task_instance_dirs(resolved_tasks_root)
    ]
    selected_ids, dataset_metadata = _select_prime_task_ids(
        available_task_ids=available_task_ids,
        dataset=dataset,
        datasets_root=datasets_root,
        pattern=pattern,
        task=task,
    )

    if not selected_ids:
        raise typer.BadParameter("no tasks matched the supplied --pattern or --task filters")

    result = export_prime_lab_environment(
        PrimeLabExportConfig(
            name=name,
            tasks_root=resolved_tasks_root,
            output_dir=output_dir,
            task_ids=selected_ids,
            version=version,
            harness_mode=_parse_harness_mode(harness_mode, PrimeExportHarnessMode),
            dataset_metadata=dataset_metadata,
        )
    )
    print_success(f"Exported {result.task_count} task(s) to Prime Lab package: {result.package_dir}")


@app.command("push")
def prime_push(
    name: str = typer.Option(..., "--name", help="Prime environment package name"),
    output_dir: Path = typer.Option(
        DEFAULT_PRIME_ENVIRONMENTS_DIR, "--output-dir", "-o", help="Directory for generated package"
    ),
    tasks_root: str | None = typer.Option(None, "--tasks-root", help="Tasks root override"),
    dataset: str | None = typer.Option(
        None,
        "--dataset",
        help="Dataset name or name@version to export and push as a Prime environment.",
    ),
    datasets_root: str | None = typer.Option(
        None,
        "--datasets-root",
        help="Datasets root override for --dataset resolution.",
    ),
    pattern: list[str] | None = typer.Option(None, "--pattern", "-p", help="Task ID glob to include; repeatable"),
    task: list[str] | None = typer.Option(None, "--task", "-t", help="Exact task ID to include; repeatable"),
    version: str = typer.Option("0.1.0", "--version", help="Generated package version"),
    harness_mode: str = typer.Option(
        "auto",
        "--harness-mode",
        help="Prime harness mode: auto, single-turn, or stateful-workspace.",
    ),
    visibility: str = typer.Option(
        "PRIVATE",
        "--visibility",
        help="Prime Hub visibility: PRIVATE or PUBLIC.",
    ),
    owner: str | None = typer.Option(None, "--owner", help="Prime Hub owner slug"),
    team: str | None = typer.Option(None, "--team", help="Prime Hub team slug"),
) -> None:
    """Export selected tasks, then push the generated environment to Prime Hub."""
    export_result = _export_prime_package(
        name=name,
        output_dir=output_dir,
        tasks_root=tasks_root,
        dataset=dataset,
        datasets_root=datasets_root,
        pattern=pattern,
        task=task,
        version=version,
        harness_mode=harness_mode,
    )
    command = _prime_env_push_command(visibility=visibility, owner=owner, team=team)
    _run_prime_command(command, cwd=export_result.package_dir)
    metadata = _read_prime_metadata(export_result.package_dir)
    data = {
        "environment_id": export_result.env_id,
        "package_dir": str(export_result.package_dir),
        "task_count": export_result.task_count,
        "remote_environment": _metadata_remote_environment(metadata),
        "visibility": visibility,
    }
    emit("prime push", data, human_renderer=_render_prime_push)


@app.command("eval")
def prime_eval(
    name: str | None = typer.Option(None, "--name", help="Prime environment package name"),
    output_dir: Path = typer.Option(
        DEFAULT_PRIME_ENVIRONMENTS_DIR, "--output-dir", "-o", help="Directory for generated package"
    ),
    tasks_root: str | None = typer.Option(None, "--tasks-root", help="Tasks root override"),
    dataset: str | None = typer.Option(
        None,
        "--dataset",
        help="Dataset name or name@version to export and evaluate.",
    ),
    datasets_root: str | None = typer.Option(
        None,
        "--datasets-root",
        help="Datasets root override for --dataset resolution.",
    ),
    pattern: list[str] | None = typer.Option(None, "--pattern", "-p", help="Task ID glob to include; repeatable"),
    task: list[str] | None = typer.Option(None, "--task", "-t", help="Exact task ID to include; repeatable"),
    version: str = typer.Option("0.1.0", "--version", help="Generated package version"),
    harness_mode: str = typer.Option(
        "auto",
        "--harness-mode",
        help="Prime harness mode: auto, single-turn, or stateful-workspace.",
    ),
    model: str = typer.Option(..., "--model", "-m", help="Model id for `prime eval run`"),
    adapter_id: str | None = typer.Option(
        None,
        "--adapter-id",
        help=(
            "Optional deployed Prime inference adapter id from `prime deployments list`; "
            "composed as '<model>:<adapter-id>'."
        ),
    ),
    adapter_from_run: str | None = typer.Option(
        None,
        "--adapter-from-run",
        help="Resolve the deployed adapter id for a hosted training run.",
    ),
    adapter_step: str | None = typer.Option(
        None,
        "--adapter-step",
        help="Optional adapter step to select when using --adapter-from-run; defaults to latest.",
    ),
    remote_env: str | None = typer.Option(
        None,
        "--remote-env",
        help="Existing Prime Hub environment slug, e.g. owner/env_name.",
    ),
    hosted: bool = typer.Option(False, "--hosted", help="Run the eval on Prime hosted infra"),
    push: bool = typer.Option(
        True,
        "--push/--no-push",
        help="For hosted evals, push the exported environment before running.",
    ),
    visibility: str = typer.Option(
        "PRIVATE",
        "--visibility",
        help="Visibility used when --push is enabled.",
    ),
    owner: str | None = typer.Option(None, "--owner", help="Prime Hub owner slug"),
    team: str | None = typer.Option(None, "--team", help="Prime Hub team slug"),
    num_examples: int | None = typer.Option(None, "--num-examples", "-n", min=1),
    rollouts_per_example: int = typer.Option(1, "--rollouts-per-example", "-r", min=1),
    max_tokens: int | None = typer.Option(None, "--max-tokens", min=1),
    max_concurrent: int | None = typer.Option(None, "--max-concurrent", min=1),
    split: str | None = typer.Option(
        None,
        "--split",
        help="Environment split passed to load_environment via --env-args.",
    ),
    difficulty: list[str] | None = typer.Option(
        None,
        "--difficulty",
        help="Difficulty value passed to load_environment; repeatable.",
    ),
    harness: str | None = typer.Option(
        None,
        "--harness",
        help="Harness hint passed to load_environment, e.g. stateful.",
    ),
    env_num_examples: int | None = typer.Option(
        None,
        "--env-num-examples",
        min=1,
        help="num_examples passed to load_environment via --env-args.",
    ),
    seed: int | None = typer.Option(
        None,
        "--seed",
        help="Seed passed to load_environment via --env-args.",
    ),
    env_arg: list[str] | None = typer.Option(
        None,
        "--env-arg",
        help="Additional load_environment argument as KEY=VALUE; repeatable.",
    ),
    eval_name: str | None = typer.Option(
        None,
        "--eval-name",
        help="Hosted evaluation name passed through to Prime.",
    ),
    timeout_minutes: int = typer.Option(
        120,
        "--timeout-minutes",
        min=1,
        help="Hosted evaluation wall-clock timeout in minutes.",
    ),
    follow: bool = typer.Option(True, "--follow/--no-follow", help="Follow hosted eval logs"),
) -> None:
    """Export selected tasks and run `prime eval run`, locally or hosted."""
    if remote_env is None and name is None:
        raise typer.BadParameter("--name is required unless --remote-env is provided")

    export_result: _PrimePackageExport | None = None
    eval_environment = remote_env
    cwd: Path | None = None

    if name is not None:
        export_result = _export_prime_package(
            name=name,
            output_dir=output_dir,
            tasks_root=tasks_root,
            dataset=dataset,
            datasets_root=datasets_root,
            pattern=pattern,
            task=task,
            version=version,
            harness_mode=harness_mode,
        )
        cwd = export_result.package_dir
        eval_environment = export_result.env_id

    if hosted and eval_environment is None:
        raise typer.BadParameter("hosted eval requires --remote-env or an exported --name")

    if hosted and remote_env is None and push:
        assert export_result is not None
        _run_prime_command(
            _prime_env_push_command(visibility=visibility, owner=owner, team=team),
            cwd=export_result.package_dir,
        )
        metadata = _read_prime_metadata(export_result.package_dir)
        remote_from_metadata = _metadata_remote_environment(metadata)
        if remote_from_metadata is None:
            raise typer.BadParameter("Prime push did not produce remote metadata; pass --remote-env owner/name")
        eval_environment = remote_from_metadata

    if hosted and remote_env is None and not push and owner is not None and name is not None:
        eval_environment = f"{owner}/{normalise_environment_id(name)}"

    if hosted and remote_env is None and not push and "/" not in str(eval_environment):
        raise typer.BadParameter("hosted eval with --no-push requires --remote-env or --owner")

    if adapter_id is not None and adapter_from_run is not None:
        raise typer.BadParameter("--adapter-id cannot be combined with --adapter-from-run")

    assert eval_environment is not None
    resolved_adapter_id = adapter_id
    if adapter_from_run is not None:
        resolved_adapter_id = _resolve_prime_adapter_id(
            training_run_id=adapter_from_run,
            base_model=model,
            adapter_step=adapter_step,
        )
    eval_model = _compose_prime_model(model=model, adapter_id=resolved_adapter_id)
    env_args = _prime_eval_env_args(
        split=split,
        difficulty=difficulty,
        harness=harness,
        env_num_examples=env_num_examples,
        seed=seed,
        env_arg=env_arg,
    )
    command = _prime_eval_command(
        environment=eval_environment,
        model=eval_model,
        hosted=hosted,
        env_args=env_args,
        num_examples=num_examples,
        rollouts_per_example=rollouts_per_example,
        max_tokens=max_tokens,
        max_concurrent=max_concurrent,
        timeout_minutes=timeout_minutes,
        follow=follow,
        eval_name=eval_name,
    )
    _run_prime_command(command, cwd=cwd)
    data = {
        "environment": eval_environment,
        "model": eval_model,
        "adapter_id": resolved_adapter_id,
        "adapter_from_run": adapter_from_run,
        "hosted": hosted,
        "package_dir": str(cwd) if cwd is not None else None,
    }
    emit("prime eval", data, human_renderer=_render_prime_eval)


@app.command("adapters")
def prime_adapters() -> None:
    """List Prime inference adapter deployments."""
    deployments = _prime_deployments()
    adapters = deployments.get("models", [])
    data = adapters if isinstance(adapters, list) else []
    emit("prime adapters", data, human_renderer=_render_prime_adapters)


@app.command("train-config")
def prime_train_config(
    environment: str = typer.Option(
        ...,
        "--environment",
        help="Prime Hub environment slug, e.g. owner/env_name.",
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="Path for the hosted training TOML config.",
    ),
    model: str = typer.Option(
        "Qwen/Qwen3.5-0.8B",
        "--model",
        "-m",
        help="Hosted Training model id.",
    ),
    split: str = typer.Option(
        "train",
        "--split",
        help="Environment split passed to load_environment.",
    ),
    difficulty: list[str] | None = typer.Option(
        None,
        "--difficulty",
        help="Difficulty value passed through to load_environment; repeatable.",
    ),
    harness: str | None = typer.Option(
        None,
        "--harness",
        help="Harness hint passed through to load_environment args.",
    ),
    num_examples: int | None = typer.Option(
        None,
        "--num-examples",
        min=1,
        help="Training examples passed through to load_environment args.",
    ),
    max_steps: int = typer.Option(20, "--max-steps", min=1),
    batch_size: int = typer.Option(32, "--batch-size", min=1),
    rollouts_per_example: int = typer.Option(4, "--rollouts-per-example", min=1),
    max_tokens: int = typer.Option(2048, "--max-tokens", min=1),
    eval_interval: int | None = typer.Option(10, "--eval-interval", min=1),
    eval_num_examples: int | None = typer.Option(10, "--eval-num-examples", min=1),
    eval_rollouts_per_example: int = typer.Option(1, "--eval-rollouts-per-example", min=1),
    no_eval_base_model: bool = typer.Option(
        False,
        "--no-eval-base-model",
        help="Do not evaluate the base model during hosted training evals.",
    ),
    adapters_keep_last: int = typer.Option(3, "--adapters-keep-last", min=1),
) -> None:
    """Write a conservative Hosted Training config for a Prime environment."""
    if batch_size % rollouts_per_example != 0:
        raise typer.BadParameter("--batch-size must be divisible by --rollouts-per-example")

    env_args: dict[str, object] = {"split": split}
    if difficulty:
        env_args["difficulty"] = difficulty[0] if len(difficulty) == 1 else list(difficulty)
    if harness is not None:
        env_args["harness"] = harness
    if num_examples is not None:
        env_args["num_examples"] = num_examples

    config_text = _render_train_config(
        environment=environment,
        model=model,
        max_steps=max_steps,
        batch_size=batch_size,
        rollouts_per_example=rollouts_per_example,
        max_tokens=max_tokens,
        env_args=env_args,
        eval_interval=eval_interval,
        eval_num_examples=eval_num_examples,
        eval_rollouts_per_example=eval_rollouts_per_example,
        eval_base_model=not no_eval_base_model,
        adapters_keep_last=adapters_keep_last,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(config_text, encoding="utf-8")
    data = {
        "config_path": str(output),
        "environment": environment,
        "model": model,
        "max_steps": max_steps,
    }
    emit("prime train config", data, human_renderer=_render_prime_train_config)


@app.command("train")
def prime_train(
    config_path: Path = typer.Argument(..., help="Hosted Training TOML config path"),
    env_var: list[str] | None = typer.Option(
        None,
        "--env-var",
        "-e",
        help="Environment variable or secret passed through to `prime train`.",
    ),
    env_file: Path | None = typer.Option(
        None,
        "--env-file",
        help="Secrets env file passed through to `prime train`.",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip Prime confirmation prompt."),
) -> None:
    """Launch a Hosted Training run through the Prime CLI."""
    command = ["prime", "train", str(config_path), "--plain"]
    for item in env_var or []:
        command.extend(["--env-var", item])
    if env_file is not None:
        command.extend(["--env-file", str(env_file)])
    if yes:
        command.append("--yes")
    _run_prime_command(command, cwd=None)
    data = {"config_path": str(config_path)}
    emit("prime train", data, human_renderer=_render_prime_train)


@app.command("doctor")
def prime_doctor(
    check_inference: bool = typer.Option(
        False,
        "--check-inference",
        help="Also check Prime Inference model-list connectivity.",
    ),
) -> None:
    """Check local readiness for the optional Prime integration."""
    from aec_bench.prime_lab.doctor import run_prime_doctor

    checks = run_prime_doctor(check_inference=check_inference)
    data = [{"check": check.name, "ok": check.ok, "detail": check.detail} for check in checks]
    errors = [f"{check.name}: {check.detail}" for check in checks if not check.ok]
    emit("prime doctor", data, errors=errors, human_renderer=_render_checks)


@app.command("smoke")
def prime_smoke(
    name: str = typer.Option(..., "--name", help="Prime environment package name"),
    task: str | None = typer.Option(None, "--task", "-t", help="Exact task ID to export and smoke"),
    output_dir: Path = typer.Option(
        DEFAULT_PRIME_ENVIRONMENTS_DIR, "--output-dir", "-o", help="Directory for generated package"
    ),
    tasks_root: str | None = typer.Option(None, "--tasks-root", help="Tasks root override"),
    dataset: str | None = typer.Option(
        None,
        "--dataset",
        help="Dataset name or name@version to export and smoke as a Prime task collection.",
    ),
    datasets_root: str | None = typer.Option(
        None,
        "--datasets-root",
        help="Datasets root override for --dataset resolution.",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="Optional model for a one-example `prime eval run`; omitted keeps smoke local.",
    ),
    endpoints_path: Path | None = typer.Option(
        None,
        "--endpoints-path",
        help="Optional endpoints TOML passed through to `prime eval run`.",
    ),
    max_tokens: int = typer.Option(
        2048,
        "--max-tokens",
        min=1,
        help="Maximum model output tokens for the one-example `prime eval run`.",
    ),
    harness_mode: str = typer.Option(
        "auto",
        "--harness-mode",
        help="Prime harness mode: auto, single-turn, or stateful-workspace.",
    ),
) -> None:
    """Export, install, and locally load one Prime environment package."""
    from aec_bench.prime_lab.doctor import (
        install_generated_environment,
        load_generated_environment,
        run_prime_eval_smoke,
    )
    from aec_bench.prime_lab.exporter import (
        PrimeExportHarnessMode,
        PrimeLabExportConfig,
        export_prime_lab_environment,
    )

    env_id = normalise_environment_id(name)
    resolved_tasks_root = resolve_path("tasks_root", cli_override=tasks_root)
    selected_ids, dataset_metadata = _select_prime_task_ids(
        available_task_ids=[],
        dataset=dataset,
        datasets_root=datasets_root,
        pattern=None,
        task=[task] if task is not None else None,
    )
    result = export_prime_lab_environment(
        PrimeLabExportConfig(
            name=name,
            tasks_root=resolved_tasks_root,
            output_dir=output_dir,
            task_ids=selected_ids,
            harness_mode=_parse_harness_mode(harness_mode, PrimeExportHarnessMode),
            dataset_metadata=dataset_metadata,
        )
    )
    checks = [
        install_generated_environment(output_dir, env_id),
        load_generated_environment(result.package_dir, env_id),
    ]
    if model is not None:
        checks.append(
            run_prime_eval_smoke(
                env_id=env_id,
                model=model,
                endpoints_path=endpoints_path,
                cwd=result.package_dir,
                max_tokens=max_tokens,
            )
        )

    data = {
        "environment_id": env_id,
        "package_dir": str(result.package_dir),
        "checks": [{"check": check.name, "ok": check.ok, "detail": check.detail} for check in checks],
    }
    errors = [f"{check.name}: {check.detail}" for check in checks if not check.ok]
    emit("prime smoke", data, errors=errors, human_renderer=_render_smoke)


def _render_checks(data: list[dict[str, object]]) -> None:
    from rich.table import Table

    table = Table(title="Prime Integration Checks")
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Detail")
    for row in data:
        table.add_row(
            str(row["check"]),
            "OK" if row["ok"] else "FAIL",
            str(row["detail"]),
        )
    from aec_bench.cli.output import console

    console.print(table)


def _select_prime_task_ids(
    *,
    available_task_ids: list[str],
    dataset: str | None,
    datasets_root: str | None,
    pattern: list[str] | None,
    task: list[str] | None,
) -> tuple[list[str], dict[str, str] | None]:
    if dataset is not None:
        if pattern or task:
            raise typer.BadParameter("--dataset cannot be combined with --task or --pattern")
        from aec_bench.dataset.storage import resolve_dataset

        resolved_datasets_root = resolve_path("datasets_root", cli_override=datasets_root)
        manifest = resolve_dataset(resolved_datasets_root, dataset)
        if manifest is None:
            raise typer.BadParameter(f"dataset not found: {dataset}")
        metadata = {
            "name": manifest.name,
            "version": manifest.version,
            "content_hash": manifest.content_hash,
        }
        return [entry.task_id for entry in manifest.tasks], metadata

    selected_ids = available_task_ids
    if pattern:
        selected_ids = [
            task_id
            for task_id in selected_ids
            if any(fnmatch.fnmatchcase(task_id, include_pattern) for include_pattern in pattern)
        ]

    if task:
        task_set = set(task)
        if selected_ids:
            selected_ids = [task_id for task_id in selected_ids if task_id in task_set]
        else:
            selected_ids = list(task)

    if not selected_ids:
        raise typer.BadParameter("no tasks matched the supplied --pattern or --task filters")
    return selected_ids, None


def _export_prime_package(
    *,
    name: str,
    output_dir: Path,
    tasks_root: str | None,
    dataset: str | None,
    datasets_root: str | None,
    pattern: list[str] | None,
    task: list[str] | None,
    version: str,
    harness_mode: str,
) -> _PrimePackageExport:
    from aec_bench.prime_lab.exporter import (
        PrimeExportHarnessMode,
        PrimeLabExportConfig,
        export_prime_lab_environment,
    )
    from aec_bench.tasks.loader import derive_task_id, iter_task_instance_dirs

    resolved_tasks_root = resolve_path("tasks_root", cli_override=tasks_root)
    available_task_ids: list[str] = []
    if dataset is None:
        available_task_ids = [
            derive_task_id(instance_dir, resolved_tasks_root)
            for instance_dir in iter_task_instance_dirs(resolved_tasks_root)
        ]
    selected_ids, dataset_metadata = _select_prime_task_ids(
        available_task_ids=available_task_ids,
        dataset=dataset,
        datasets_root=datasets_root,
        pattern=pattern,
        task=task,
    )

    result = export_prime_lab_environment(
        PrimeLabExportConfig(
            name=name,
            tasks_root=resolved_tasks_root,
            output_dir=output_dir,
            task_ids=selected_ids,
            version=version,
            harness_mode=_parse_harness_mode(harness_mode, PrimeExportHarnessMode),
            dataset_metadata=dataset_metadata,
        )
    )
    return _PrimePackageExport(
        env_id=normalise_environment_id(name),
        package_dir=result.package_dir,
        task_count=result.task_count,
    )


def _prime_env_push_command(
    *,
    visibility: str,
    owner: str | None,
    team: str | None,
) -> list[str]:
    command = ["prime", "env", "push", "--visibility", visibility, "--plain"]
    if owner is not None:
        command.extend(["--owner", owner])
    if team is not None:
        command.extend(["--team", team])
    return command


def _prime_eval_command(
    *,
    environment: str,
    model: str,
    hosted: bool,
    env_args: dict[str, object],
    num_examples: int | None,
    rollouts_per_example: int,
    max_tokens: int | None,
    max_concurrent: int | None,
    timeout_minutes: int,
    follow: bool,
    eval_name: str | None,
) -> list[str]:
    command = ["prime", "--plain", "eval", "run", environment, "--model", model]
    if env_args:
        command.extend(["--env-args", json.dumps(env_args)])
    if num_examples is not None:
        command.extend(["--num-examples", str(num_examples)])
    command.extend(["--rollouts-per-example", str(rollouts_per_example)])
    if max_tokens is not None:
        command.extend(["--max-tokens", str(max_tokens)])
    if max_concurrent is not None:
        command.extend(["--max-concurrent", str(max_concurrent)])
    if hosted:
        command.append("--hosted")
        command.extend(["--timeout-minutes", str(timeout_minutes)])
        if follow:
            command.append("--follow")
        if eval_name is not None:
            command.extend(["--eval-name", eval_name])
    else:
        command.extend(["--disable-tui", "--abbreviated-summary"])
    return command


def _compose_prime_model(*, model: str, adapter_id: str | None) -> str:
    if adapter_id is None:
        return model
    if ":" in model:
        raise typer.BadParameter("--adapter-id cannot be combined with an adapter-qualified --model")
    return f"{model}:{adapter_id}"


def _prime_deployments() -> dict[str, object]:
    command = ["prime", "--plain", "deployments", "list", "--output", "json"]
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise typer.BadParameter("prime CLI not found; install and log in with Prime first") from exc
    except subprocess.CalledProcessError as exc:
        raise typer.Exit(exc.returncode) from exc
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter("prime deployments list did not return valid JSON") from exc
    if not isinstance(payload, dict):
        raise typer.BadParameter("prime deployments list returned an unexpected payload")
    return payload


def _resolve_prime_adapter_id(
    *,
    training_run_id: str,
    base_model: str,
    adapter_step: str | None,
) -> str:
    deployments = _prime_deployments()
    raw_models = deployments.get("models", [])
    if not isinstance(raw_models, list):
        raise typer.BadParameter("prime deployments list returned no models array")

    candidates = [
        model
        for model in raw_models
        if isinstance(model, dict)
        and model.get("rft_run_id") == training_run_id
        and model.get("base_model") == base_model
        and model.get("deployment_status") == "DEPLOYED"
        and model.get("status") == "READY"
    ]
    if adapter_step is not None and adapter_step.strip().lower() != "latest":
        candidates = [model for model in candidates if str(model.get("step")) == adapter_step]
    if not candidates:
        step_note = f" at step {adapter_step}" if adapter_step is not None else ""
        raise typer.BadParameter(
            "no deployed READY adapter found for "
            f"training run {training_run_id}, base model {base_model}{step_note}; "
            "check `aec-bench prime adapters` or `prime deployments list`"
        )

    selected = max(
        candidates,
        key=lambda model: (
            str(model.get("deployed_at") or ""),
            str(model.get("updated_at") or ""),
            str(model.get("created_at") or ""),
            str(model.get("id") or ""),
        ),
    )
    adapter_id = selected.get("id")
    if not isinstance(adapter_id, str) or not adapter_id:
        raise typer.BadParameter("selected Prime adapter deployment has no id")
    return adapter_id


def _prime_eval_env_args(
    *,
    split: str | None,
    difficulty: list[str] | None,
    harness: str | None,
    env_num_examples: int | None,
    seed: int | None,
    env_arg: list[str] | None,
) -> dict[str, object]:
    env_args: dict[str, object] = {}
    if split is not None:
        env_args["split"] = split
    if difficulty:
        env_args["difficulty"] = difficulty[0] if len(difficulty) == 1 else list(difficulty)
    if harness is not None:
        env_args["harness"] = harness
    if env_num_examples is not None:
        env_args["num_examples"] = env_num_examples
    if seed is not None:
        env_args["seed"] = seed
    for item in env_arg or []:
        key, value = _parse_env_arg(item)
        env_args[key] = value
    return env_args


def _parse_env_arg(item: str) -> tuple[str, object]:
    key, separator, raw_value = item.partition("=")
    if not separator or not key.strip():
        raise typer.BadParameter("--env-arg must use KEY=VALUE format")
    key = key.strip()
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        value = raw_value
    return key, value


def _render_train_config(
    *,
    environment: str,
    model: str,
    max_steps: int,
    batch_size: int,
    rollouts_per_example: int,
    max_tokens: int,
    env_args: dict[str, object],
    eval_interval: int | None,
    eval_num_examples: int | None,
    eval_rollouts_per_example: int,
    eval_base_model: bool,
    adapters_keep_last: int,
) -> str:
    lines = [
        f"model = {_toml_string(model)}",
        f"max_steps = {max_steps}",
        f"batch_size = {batch_size}",
        f"rollouts_per_example = {rollouts_per_example}",
        "",
        "[sampling]",
        f"max_tokens = {max_tokens}",
        "",
        "[[env]]",
        f"id = {_toml_string(environment)}",
    ]
    if env_args:
        lines.append(f"args = {_toml_inline_table(env_args)}")

    if eval_interval is not None:
        lines.extend(
            [
                "",
                "[eval]",
                f"interval = {eval_interval}",
            ]
        )
        if eval_num_examples is not None:
            lines.append(f"num_examples = {eval_num_examples}")
        lines.extend(
            [
                f"rollouts_per_example = {eval_rollouts_per_example}",
                f"eval_base_model = {_toml_bool(eval_base_model)}",
            ]
        )

    lines.extend(
        [
            "",
            "[adapters]",
            "interval = 0",
            f"keep_last = {adapters_keep_last}",
            "",
        ]
    )
    return "\n".join(lines)


def _toml_inline_table(values: dict[str, object]) -> str:
    bits = [f"{key} = {_toml_value(value)}" for key, value in values.items()]
    return "{ " + ", ".join(bits) + " }"


def _toml_value(value: object) -> str:
    if isinstance(value, str):
        return _toml_string(value)
    if isinstance(value, bool):
        return _toml_bool(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TypeError(f"unsupported TOML value: {value!r}")


def _toml_string(value: str) -> str:
    return json.dumps(value)


def _toml_bool(value: bool) -> str:
    return "true" if value else "false"


def _run_prime_command(command: list[str], *, cwd: Path | None) -> None:
    try:
        subprocess.run(command, cwd=cwd, check=True)
    except FileNotFoundError as exc:
        raise typer.BadParameter("prime CLI not found; install and log in with Prime first") from exc
    except subprocess.CalledProcessError as exc:
        raise typer.Exit(exc.returncode) from exc


def _read_prime_metadata(package_dir: Path) -> dict[str, object]:
    metadata_path = package_dir / ".prime" / ".env-metadata.json"
    if not metadata_path.is_file():
        return {}
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _metadata_remote_environment(metadata: dict[str, object]) -> str | None:
    owner = metadata.get("owner")
    name = metadata.get("name")
    if isinstance(owner, str) and isinstance(name, str):
        return f"{owner}/{name}"
    return None


def _parse_harness_mode(raw_mode: str, mode_type: type) -> object:
    normalized = raw_mode.strip().replace("-", "_")
    try:
        return mode_type(normalized)
    except ValueError as exc:
        raise typer.BadParameter("harness mode must be one of: auto, single-turn, stateful-workspace") from exc


def _render_smoke(data: dict[str, object]) -> None:
    from rich.table import Table

    from aec_bench.cli.output import console

    console.print(f"Environment: [bold]{data['environment_id']}[/bold]")
    console.print(f"Package: {data['package_dir']}")
    table = Table(title="Smoke Checks")
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Detail")
    for row in data["checks"]:
        table.add_row(
            str(row["check"]),
            "OK" if row["ok"] else "FAIL",
            str(row["detail"]),
        )
    console.print(table)


def _render_prime_push(data: dict[str, object]) -> None:
    from aec_bench.cli.output import console

    console.print(f"Environment: [bold]{data['environment_id']}[/bold]")
    console.print(f"Package: {data['package_dir']}")
    console.print(f"Tasks: {data['task_count']}")
    if data.get("remote_environment"):
        console.print(f"Remote: {data['remote_environment']}")


def _render_prime_eval(data: dict[str, object]) -> None:
    from aec_bench.cli.output import console

    mode = "hosted" if data["hosted"] else "local"
    console.print(f"Evaluation: [bold]{mode}[/bold]")
    console.print(f"Environment: {data['environment']}")
    console.print(f"Model: {data['model']}")
    if data.get("adapter_id") is not None:
        console.print(f"Adapter: {data['adapter_id']}")


def _render_prime_adapters(data: list[object]) -> None:
    from rich.table import Table

    from aec_bench.cli.output import console

    table = Table(title="Prime Adapter Deployments")
    table.add_column("ID", style="bold")
    table.add_column("Run")
    table.add_column("Base Model")
    table.add_column("Step")
    table.add_column("Status")
    table.add_column("Deployment")
    for item in data:
        if not isinstance(item, dict):
            continue
        step = item.get("step")
        table.add_row(
            str(item.get("id", "")),
            str(item.get("rft_run_id", "")),
            str(item.get("base_model", "")),
            "" if step is None else str(step),
            str(item.get("status", "")),
            str(item.get("deployment_status", "")),
        )
    console.print(table)


def _render_prime_train_config(data: dict[str, object]) -> None:
    from aec_bench.cli.output import console

    console.print(f"Training config: [bold]{data['config_path']}[/bold]")
    console.print(f"Environment: {data['environment']}")
    console.print(f"Model: {data['model']}")
    console.print(f"Max steps: {data['max_steps']}")


def _render_prime_train(data: dict[str, object]) -> None:
    from aec_bench.cli.output import console

    console.print(f"Hosted training launched from: [bold]{data['config_path']}[/bold]")
