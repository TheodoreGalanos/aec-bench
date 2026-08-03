# ABOUTME: Provides installed CLI commands for the registered pump-station episode runtime.
# ABOUTME: Routes actor, host-control, evaluation, and Harbor calls through the current world.

from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path
from typing import cast

import typer
from pydantic import BaseModel

from aec_bench.cli.output import emit
from aec_bench.contracts.continual_world import (
    ContinualWorldActorRequest,
    ContinualWorldControlRequest,
)
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evaluation.stewardship import (
    evaluate_pump_station_reference_run,
)
from aec_bench.harness.harbor_importing.core import import_harbor_trial
from aec_bench.task_world_templates.continual.interface import (
    ContinualWorldInterfaceContext,
    dispatch_continual_actor,
    dispatch_continual_control,
)
from aec_bench.task_world_templates.continual_catalogue import default_continual_world_catalogue
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_controller import (
    PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationCoupledVerificationReport,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)

app = typer.Typer(help="Run the synthetic wastewater pump-station stewardship world.")
_DEFAULT_REFERENCE_CONTROLLER_ID = PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID
_DEFAULT_MODEL_MAX_TURNS = 90


def _model_payload(value: object) -> dict[str, object]:
    if not isinstance(value, BaseModel):
        raise TypeError("continual-world interface result must be a validated model")
    return cast(dict[str, object], value.model_dump(mode="json"))


def _verification_payload(
    report: PumpStationCoupledVerificationReport,
) -> dict[str, object]:
    return {
        "valid": report.valid,
        "replay_valid": report.replay_valid,
        "actor_proposals_valid": report.actor_proposals_valid,
        "host_controls_valid": report.host_controls_valid,
        "issues": list(report.issues),
        "replayed_transition_ids": list(report.replayed_transition_ids),
        "final_state_id": report.final_state_id,
        "conservation": {
            "valid": report.conservation.valid,
            "duty": asdict(report.conservation.duty),
            "resources": asdict(report.conservation.resources),
            "work": asdict(report.conservation.work),
            "liabilities": asdict(report.conservation.liabilities),
        },
    }


@app.command("actor-interface")
def actor_interface_command(
    run_dir: Path = typer.Option(..., "--run-dir", help="Durable world-run directory"),
    request_path: Path = typer.Option(..., "--request-path", help="Registered actor JSON request"),
) -> None:
    """Execute one separate actor request through the continual-world catalogue."""

    started = time.monotonic()
    request = ContinualWorldActorRequest.model_validate_json(request_path.read_text(encoding="utf-8"))
    repository = PumpStationWorldRunRepository(run_dir)
    run = PumpStationWorldRun.resume_reference_system(
        repository=repository,
        snapshot=repository.current_snapshot(),
    )
    result = dispatch_continual_actor(
        context=ContinualWorldInterfaceContext(
            catalogue=default_continual_world_catalogue(),
            run_root=run_dir,
            rollout_repository_root=None,
            authorised_principal_ids=(),
            actor_definition_ref=run.continual_definition_ref,
            actor_profile_ref=run.continual_profile_ref,
        ),
        request=request,
    )
    emit(
        "task pump-station-world actor-interface",
        _model_payload(result),
        start_time=started,
    )


@app.command("control-interface")
def control_interface_command(
    run_dir: Path = typer.Option(..., "--run-dir", help="Durable world-run directory"),
    request_path: Path = typer.Option(..., "--request-path", help="Registered host-control JSON request"),
    host_authority_id: str = typer.Option(
        ...,
        "--host-authority-id",
        help="Host-only control authority identity",
    ),
    rollout_dir: Path | None = typer.Option(
        None,
        "--rollout-dir",
        help="Host-private rollout repository directory",
    ),
) -> None:
    """Execute one separate host-control request through the continual-world catalogue."""

    started = time.monotonic()
    request = ContinualWorldControlRequest.model_validate_json(request_path.read_text(encoding="utf-8"))
    result = dispatch_continual_control(
        context=ContinualWorldInterfaceContext(
            catalogue=default_continual_world_catalogue(),
            run_root=run_dir,
            rollout_repository_root=rollout_dir,
            authorised_principal_ids=(host_authority_id,),
        ),
        request=request,
    )
    emit(
        "task pump-station-world control-interface",
        _model_payload(result),
        start_time=started,
    )


@app.command("verify")
def verify_command(
    run_dir: Path = typer.Option(..., "--run-dir", help="Existing durable world-run directory"),
) -> None:
    """Reload and independently replay all committed pump-station transitions."""
    started = time.monotonic()
    repository = PumpStationWorldRunRepository(run_dir)
    run = PumpStationWorldRun.resume_reference_system(
        repository=repository,
        snapshot=repository.current_snapshot(),
    )
    report = run.verify()
    emit(
        "task pump-station-world verify",
        _verification_payload(report),
        start_time=started,
    )


@app.command("evaluate")
def evaluate_command(
    run_dir: Path = typer.Option(
        ...,
        "--run-dir",
        help="Existing durable world-run directory",
    ),
) -> None:
    """Reload one pump-station run and report its evaluation vector."""

    started = time.monotonic()
    repository = PumpStationWorldRunRepository(run_dir)
    run = PumpStationWorldRun.resume_reference_system(
        repository=repository,
        snapshot=repository.current_snapshot(),
    )
    evaluation = evaluate_pump_station_reference_run(run)
    emit(
        "task pump-station-world evaluate",
        evaluation.model_dump(mode="json"),
        errors=list(evaluation.gates.errors),
        start_time=started,
    )


@app.command("export-harbor")
def export_harbor_command(
    task_dir: Path = typer.Option(
        ...,
        "--task-dir",
        help="New destination for the exported Harbor task",
    ),
    project_root: Path = typer.Option(
        ...,
        "--project-root",
        help="AEC-Bench source root used to build the verifier runtime",
    ),
) -> None:
    """Export the registered wastewater pump-station Harbor task."""

    from aec_bench.task_world_templates.stewardship.wastewater_pump_station.continual_definition import (
        pump_station_continual_world_definition,
    )
    from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
        export_pump_station_harbor_task,
    )

    started = time.monotonic()
    exported = export_pump_station_harbor_task(
        task_dir,
        project_root=project_root,
        profile_ref=pump_station_continual_world_definition().spec.profiles[0],
    )
    emit(
        "task pump-station-world export-harbor",
        {
            "task_dir": str(exported.task_dir),
            "manifest_path": str(exported.manifest_path),
            "package_dir": str(exported.package_dir),
            "verifier_runtime_path": str(exported.verifier_runtime_wheel_path),
        },
        start_time=started,
    )


@app.command("run-harbor")
def run_harbor_command(
    task_dir: Path = typer.Option(
        ...,
        "--task-dir",
        help="Exported wastewater pump-station Harbor task",
    ),
    project_root: Path = typer.Option(
        ...,
        "--project-root",
        help="AEC-Bench source root that contains the entrypoint agent",
    ),
    jobs_dir: Path = typer.Option(
        ...,
        "--jobs-dir",
        help="Harbor job result directory",
    ),
    config_path: Path = typer.Option(
        ...,
        "--config-path",
        help="Destination for the generated Harbor job config",
    ),
    backend: str = typer.Option(
        "docker",
        "--backend",
        help="Harbor environment backend: docker, modal, or morph",
    ),
    model: str = typer.Option(
        _DEFAULT_REFERENCE_CONTROLLER_ID,
        "--model",
        help="Reference controller ID or Bedrock model name",
    ),
    max_turns: int = typer.Option(
        _DEFAULT_MODEL_MAX_TURNS,
        "--max-turns",
        min=1,
        help="Maximum model requests for a model-controlled session",
    ),
    execute: bool = typer.Option(
        True,
        "--execute/--no-execute",
        help="Run Harbor after the config is written",
    ),
) -> None:
    """Prepare and optionally run one local provider-free Harbor job."""

    from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_job import (
        run_pump_station_harbor_job,
    )

    started = time.monotonic()
    result = run_pump_station_harbor_job(
        task_dir=task_dir,
        project_root=project_root,
        jobs_dir=jobs_dir,
        config_path=config_path,
        backend=backend,
        model_name=model,
        max_turns=max_turns,
        execute=execute,
    )
    errors = [] if result.exit_code in (None, 0) else [f"local Harbor job failed with exit code {result.exit_code}"]
    emit(
        "task pump-station-world run-harbor",
        {
            "config_path": str(result.config_path),
            "command": list(result.command),
            "backend": backend,
            "model": model,
            "max_turns": max_turns,
            "executed": execute,
            "exit_code": result.exit_code,
        },
        errors=errors,
        start_time=started,
    )


@app.command("import-harbor-trial")
def import_harbor_trial_command(
    trial_dir: Path = typer.Option(
        ...,
        "--trial-dir",
        help="Completed Harbor trial directory",
    ),
    repo_root: Path = typer.Option(
        ...,
        "--repo-root",
        help="Repository root that owns the exported task and trial",
    ),
    record_path: Path = typer.Option(
        ...,
        "--record-path",
        help="New TrialRecord JSON path",
    ),
) -> None:
    """Strictly import one verified stewardship Harbor trial."""

    started = time.monotonic()
    if record_path.exists():
        raise FileExistsError(f"TrialRecord output already exists: {record_path}")
    record = import_harbor_trial(
        trial_dir=trial_dir,
        repo_root=repo_root,
    )
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(
        record.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    stewardship = record.evaluation.stewardship
    emit(
        "task pump-station-world import-harbor-trial",
        {
            "record_path": str(record_path),
            "trial_id": record.trial_id,
            "execution_kind": (None if record.world_execution is None else record.world_execution.execution_kind),
            "transition_count": (None if record.world_execution is None else record.world_execution.transition_count),
            "evaluation_valid": (None if stewardship is None else stewardship.valid),
            "active_terminal_restrictions": (
                None if stewardship is None else stewardship.metrics.terminal_liability.active_restriction_count
            ),
        },
        start_time=started,
    )


@app.command("reload-trial-record")
def reload_trial_record_command(
    record_path: Path = typer.Option(
        ...,
        "--record-path",
        help="Existing TrialRecord JSON path",
    ),
) -> None:
    """Reload one imported TrialRecord through the strict contract."""

    started = time.monotonic()
    record = TrialRecord.model_validate_json(record_path.read_text(encoding="utf-8"))
    stewardship = record.evaluation.stewardship
    emit(
        "task pump-station-world reload-trial-record",
        {
            "record_path": str(record_path),
            "trial_id": record.trial_id,
            "execution_kind": (None if record.world_execution is None else record.world_execution.execution_kind),
            "transition_count": (None if record.world_execution is None else record.world_execution.transition_count),
            "evaluation_valid": (None if stewardship is None else stewardship.valid),
            "active_terminal_restrictions": (
                None if stewardship is None else stewardship.metrics.terminal_liability.active_restriction_count
            ),
        },
        start_time=started,
    )
