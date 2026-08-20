# ABOUTME: CLI commands for current staged evidence-lifecycle tasks.
# ABOUTME: Materializes, inspects, runs, and verifies the task-owned definitions.

from __future__ import annotations

import json
import time
from pathlib import Path

import typer
import yaml

from aec_bench.cli.output import emit, print_table
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.experimentation.lifecycle_studies.ablation import (
    inspect_lifecycle_ablation_plan,
    load_lifecycle_ablation_manifest,
    run_lifecycle_ablation,
)
from aec_bench.experimentation.lifecycle_studies.calibration import (
    LifecycleCalibrationFreeze,
    write_lifecycle_calibration_freeze,
)
from aec_bench.harness.lifecycle_local import run_local_lifecycle
from aec_bench.lifecycles.application import (
    LifecycleTrial,
    branch_lifecycle,
    read_lifecycle,
    release_checkpoint,
    revisit_checkpoint,
    run_lifecycle,
    run_lifecycle_trial,
    submit_checkpoint,
)
from aec_bench.lifecycles.catalogue import (
    lifecycle_definition,
    lifecycle_operation_resolver,
    lifecycle_smoke_environment,
    lifecycle_template_ids,
    lifecycle_variant_ids,
    materialize_lifecycle,
    verify_lifecycle,
)
from aec_bench.lifecycles.runtime.episode import LifecycleExecutionMode, LifecycleVisibilityPolicy
from aec_bench.lifecycles.runtime.request_protocol import EvidenceLifecycleError
from aec_bench.trials import PlannedTrial

app = typer.Typer(help="Inspect and run staged evidence-lifecycle tasks.")
study_app = typer.Typer(help="Run lifecycle-specific studies.")
app.add_typer(study_app, name="study")


@app.command("list")
def list_command() -> None:
    start = time.monotonic()
    definitions = [lifecycle_definition(template_id) for template_id in sorted(lifecycle_template_ids())]
    data = {
        "count": len(definitions),
        "lifecycles": [
            {
                **definition.metadata.model_dump(mode="json"),
                "lifecycle_id": definition.lifecycle.lifecycle_id,
                "checkpoint_count": len(definition.lifecycle.checkpoints),
            }
            for definition in definitions
        ],
    }
    emit("task lifecycle list", data, start_time=start, human_renderer=_render_lifecycles)


@app.command("materialize")
def materialize_command(
    template_id: str = typer.Argument(..., help="Lifecycle task id"),
    output: Path = typer.Option(..., "--output", "-o", help="Directory where the lifecycle package is written"),
    variant: str | None = typer.Option(None, "--variant", help="Public semantic lifecycle variant id"),
) -> None:
    start = time.monotonic()
    try:
        definition = lifecycle_definition(template_id)
        package_dir = materialize_lifecycle(template_id, output, variant_id=variant)
    except (KeyError, ValueError) as exc:
        emit("task lifecycle materialize", None, errors=[str(exc)], start_time=start)
        return
    emit(
        "task lifecycle materialize",
        {
            "template_id": template_id,
            "package_dir": str(package_dir),
            "checkpoint_count": len(definition.lifecycle.checkpoints),
            "variant_id": _materialized_variant_id(package_dir),
        },
        start_time=start,
    )


@app.command("list-variants")
def list_variants_command(template_id: str = typer.Argument(..., help="Lifecycle task id")) -> None:
    start = time.monotonic()
    try:
        variants = lifecycle_variant_ids(template_id)
    except KeyError as exc:
        emit("task lifecycle list-variants", None, errors=[str(exc)], start_time=start)
        return
    emit(
        "task lifecycle list-variants",
        {"template_id": template_id, "variants": list(variants)},
        start_time=start,
    )


@app.command("start")
def start_command(
    package: Path = typer.Option(..., "--package", help="Materialized evidence-lifecycle package"),
    run_dir: Path = typer.Option(..., "--run-dir", help="Lifecycle run directory"),
) -> None:
    start = time.monotonic()
    result = release_checkpoint(
        package,
        run_dir,
        operation_resolver=lifecycle_operation_resolver(package, run_dir),
    )
    emit("task lifecycle start", result, start_time=start)


@app.command("submit")
def submit_command(
    package: Path = typer.Option(..., "--package", help="Materialized evidence-lifecycle package"),
    run_dir: Path = typer.Option(..., "--run-dir", help="Lifecycle run directory"),
) -> None:
    start = time.monotonic()
    result = submit_checkpoint(
        package,
        run_dir,
        operation_resolver=lifecycle_operation_resolver(package, run_dir),
    )
    emit("task lifecycle submit", result, start_time=start)


@app.command("status")
def status_command(
    package: Path = typer.Option(..., "--package", help="Materialized evidence-lifecycle package"),
    run_dir: Path = typer.Option(..., "--run-dir", help="Lifecycle run directory"),
) -> None:
    start = time.monotonic()
    result = read_lifecycle(
        package,
        run_dir,
        operation_resolver=lifecycle_operation_resolver(package, run_dir),
    )
    emit("task lifecycle status", result, start_time=start)


@app.command("revisit")
def revisit_command(
    package: Path = typer.Option(..., "--package", help="Materialized evidence-lifecycle package"),
    run_dir: Path = typer.Option(..., "--run-dir", help="Lifecycle run directory"),
    checkpoint_id: str = typer.Option(..., "--checkpoint-id", help="Submitted checkpoint to inspect"),
    reason: str = typer.Option(..., "--reason", help="Reason for the revisit"),
) -> None:
    start = time.monotonic()
    result = revisit_checkpoint(
        package,
        run_dir,
        checkpoint_id=checkpoint_id,
        reason=reason,
        operation_resolver=lifecycle_operation_resolver(package, run_dir),
    )
    emit("task lifecycle revisit", result, start_time=start)


@app.command("branch")
def branch_command(
    package: Path = typer.Option(..., "--package", help="Materialized evidence-lifecycle package"),
    parent_run_dir: Path = typer.Option(..., "--parent-run-dir", help="Existing parent lifecycle run"),
    branch_run_dir: Path = typer.Option(..., "--branch-run-dir", help="New derived lifecycle run"),
    checkpoint_id: str = typer.Option(..., "--checkpoint-id", help="Submitted checkpoint to reopen"),
    branch_id: str = typer.Option(..., "--branch-id", help="Stable identity for the derived run"),
    reason: str = typer.Option(..., "--reason", help="Reason for the branch"),
) -> None:
    start = time.monotonic()
    result = branch_lifecycle(
        package,
        parent_run_dir,
        branch_run_dir,
        checkpoint_id=checkpoint_id,
        branch_id=branch_id,
        reason=reason,
        operation_resolver=lifecycle_operation_resolver(package, parent_run_dir),
    )
    emit("task lifecycle branch", result, start_time=start)


@app.command("run")
def run_command(
    package: Path = typer.Option(..., "--package", help="Materialized evidence-lifecycle package"),
    run_dir: Path = typer.Option(..., "--run-dir", help="Lifecycle run directory"),
    model: str = typer.Option(..., "--model", "-m", help="Model name for the lifecycle agent"),
    adapter: str = typer.Option("tool_loop", "--adapter", "-a", help="Local adapter kind"),
    mode: LifecycleExecutionMode = typer.Option(
        LifecycleExecutionMode.PERSISTENT_CONTEXT,
        "--mode",
        help="Lifecycle execution mode",
    ),
    visibility_policy: LifecycleVisibilityPolicy | None = typer.Option(
        None,
        "--visibility-policy",
        help="Actor-visible lifecycle memory policy",
    ),
    max_turns: int = typer.Option(60, "--max-turns", min=1, help="Maximum requests in each model session"),
) -> None:
    start = time.monotonic()
    selected_visibility = visibility_policy or (
        LifecycleVisibilityPolicy.PERSISTENT_CONTEXT
        if mode is LifecycleExecutionMode.PERSISTENT_CONTEXT
        else LifecycleVisibilityPolicy.ARTIFACT_MEMORY
    )
    task_id = _package_template_id(package)
    planned = PlannedTrial(
        trial_id=f"lifecycle-{run_dir.name}",
        experiment_id=f"lifecycle-{run_dir.name}",
        task_id=task_id,
        agent=AgentConfig(
            name="lifecycle-agent",
            adapter=adapter,
            model=model,
            parameters={"max_turns_per_session": max_turns},
        ),
        compute=ComputeConfig(backend="local"),
        repetition=1,
    )
    trial = LifecycleTrial(
        planned=planned,
        package_dir=package,
        run_dir=run_dir,
        execution_mode=mode,
        visibility_policy=selected_visibility,
    )
    record = run_lifecycle_trial(trial=trial, execute=run_local_lifecycle, verify=verify_lifecycle)
    emit("task lifecycle run", record.model_dump(mode="json"), start_time=start)


@app.command("verify")
def verify_command(
    package_dir: Path = typer.Argument(..., help="Materialized lifecycle package directory"),
    run_dir: Path = typer.Option(..., "--run-dir", help="Completed lifecycle run directory"),
) -> None:
    start = time.monotonic()
    emit("task lifecycle verify", verify_lifecycle(package_dir, run_dir), start_time=start)


@app.command("run-smoke")
def run_smoke_command(
    package_dir: Path = typer.Argument(..., help="Materialized public lifecycle package directory"),
    run_dir: Path = typer.Option(..., "--run-dir", help="Empty output directory for the deterministic run"),
) -> None:
    start = time.monotonic()
    try:
        template_id = _package_template_id(package_dir)
        environment = lifecycle_smoke_environment(template_id, package_dir)
        if environment is None:
            raise ValueError(f"lifecycle task {template_id!r} does not declare a smoke environment")
        lifecycle = run_lifecycle(
            package_dir,
            run_dir,
            episode_environment=environment,
            operation_resolver=lifecycle_operation_resolver(package_dir, run_dir),
        )
        verification = verify_lifecycle(package_dir, run_dir)
    except (EvidenceLifecycleError, json.JSONDecodeError, KeyError, OSError, ValueError) as exc:
        emit("task lifecycle run-smoke", None, errors=[str(exc)], start_time=start)
        return
    emit(
        "task lifecycle run-smoke",
        {
            "template_id": template_id,
            "package_dir": str(package_dir),
            "run_dir": str(run_dir),
            "lifecycle_status": lifecycle["status"],
            "overall": verification["overall"],
            "passed": verification["passed"],
            "reward": verification["reward"],
            "gates": verification["gates"],
        },
        start_time=start,
    )


@study_app.command("ablation")
def ablation_command(
    config: Path = typer.Option(..., "--config", help="Lifecycle ablation YAML manifest"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the exact plan without model execution"),
) -> None:
    start = time.monotonic()
    command = "task lifecycle study ablation"
    try:
        manifest = load_lifecycle_ablation_manifest(config)
        result = (
            {"dry_run": True, **inspect_lifecycle_ablation_plan(manifest)}
            if dry_run
            else run_lifecycle_ablation(manifest).model_dump(mode="json")
        )
    except (OSError, ValueError, yaml.YAMLError) as exc:
        emit(command, None, errors=[str(exc)], start_time=start)
        return
    emit(command, result, start_time=start)


@study_app.command("calibration-freeze")
def calibration_freeze_command(
    config: Path = typer.Option(..., "--config", help="Preregistered lifecycle calibration YAML manifest"),
    output: Path | None = typer.Option(None, "--output", help="Write-once frozen condition JSON"),
) -> None:
    start = time.monotonic()
    command = "task lifecycle study calibration-freeze"
    try:
        manifest = load_lifecycle_ablation_manifest(config)
        destination = output or (Path(manifest.output_root) / "frozen-condition.json")
        path = write_lifecycle_calibration_freeze(manifest, destination)
        freeze = LifecycleCalibrationFreeze.model_validate_json(path.read_text(encoding="utf-8"))
        result = {"freeze_path": str(path.resolve()), "freeze": freeze.model_dump(mode="json")}
    except (OSError, ValueError, yaml.YAMLError) as exc:
        emit(command, None, errors=[str(exc)], start_time=start)
        return
    emit(command, result, start_time=start)


def _materialized_variant_id(package_dir: Path) -> str | None:
    path = package_dir / "hidden" / "variant.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload["variant_id"])


def _package_template_id(package_dir: Path) -> str:
    payload = json.loads((Path(package_dir) / "template.json").read_text(encoding="utf-8"))
    template_id = payload.get("template_id") if isinstance(payload, dict) else None
    if not isinstance(template_id, str) or not template_id:
        raise ValueError("lifecycle package template identity is invalid")
    return template_id


def _render_lifecycles(data: dict[str, object]) -> None:
    lifecycles = data["lifecycles"]
    if not isinstance(lifecycles, list):
        return
    rows = [
        [
            str(lifecycle["template_id"]),
            str(lifecycle["name"]),
            str(lifecycle["discipline"]),
            str(lifecycle["checkpoint_count"]),
        ]
        for lifecycle in lifecycles
        if isinstance(lifecycle, dict)
    ]
    print_table("Lifecycle Tasks", ["Task", "Name", "Discipline", "Checkpoints"], rows)
