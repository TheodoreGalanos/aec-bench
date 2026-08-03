# ABOUTME: Provides installed CLI commands for direct pump-station world sessions.
# ABOUTME: Starts, advances, resumes, and independently verifies one durable task-owned run.

from __future__ import annotations

import json
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
from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.evaluation.stewardship import (
    evaluate_pump_station_stewardship_run,
)
from aec_bench.harness.harbor_importing.core import import_harbor_trial
from aec_bench.harness.world_interface import invoke_world_actor, observe_world_actor
from aec_bench.harness.world_session import open_world_session
from aec_bench.task_world_templates.continual.interface import (
    ContinualWorldInterfaceContext,
    dispatch_continual_actor,
    dispatch_continual_control,
)
from aec_bench.task_world_templates.continual_catalogue import default_continual_world_catalogue
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
    export_pump_station_harbor_task,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_job import (
    run_pump_station_harbor_job,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
    PUMP_STATION_MODEL_MAX_TURNS,
    PUMP_STATION_REFERENCE_CONTROLLER_ID,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.local_interface import (
    PumpStationLocalInterfaceRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_local_interface import (
    PumpStationReviewLocalInterfaceRequest,
    execute_pump_station_review_local_request,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rollout_control import (
    PumpStationRolloutControl,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rollout_interface import (
    PumpStationRolloutControlRequest,
    execute_pump_station_rollout_request,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationVerificationReport,
    PumpStationVerificationReportV4,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_control import (
    PumpStationEvidenceControlRequest,
    PumpStationWorldControl,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationWorldRunManifestV2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationWorldSession,
    PumpStationWorldSessionFactory,
)

app = typer.Typer(help="Run the synthetic wastewater pump-station stewardship world.")


def _model_payload(value: object) -> dict[str, object]:
    if not isinstance(value, BaseModel):
        raise TypeError("continual-world interface result must be a validated model")
    return cast(dict[str, object], value.model_dump(mode="json"))


def _verification_payload(
    report: PumpStationVerificationReport | PumpStationVerificationReportV4,
) -> dict[str, object]:
    if isinstance(report, PumpStationVerificationReportV4):
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
    return {
        "valid": report.valid,
        "issues": list(report.issues),
        "replayed_transition_ids": list(report.replayed_transition_ids),
        "final_state_id": report.final_state_id,
        "active_restriction_ids": list(report.active_restriction_ids),
        "open_obligation_ids": list(report.open_obligation_ids),
    }


def _factory(
    run_dir: Path,
    *,
    temporal_evidence: bool = False,
) -> PumpStationWorldSessionFactory:
    return PumpStationWorldSessionFactory(
        run_dir,
        temporal_evidence=temporal_evidence,
    )


def _resume_request(
    run_dir: Path,
    *,
    session_id: str,
    agent_tenure_id: str,
) -> WorldSessionRequest:
    repository = PumpStationWorldRunRepository(run_dir)
    manifest = repository.load_manifest()
    snapshot = repository.current_snapshot()
    return WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.RESUME,
        session_id=session_id,
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id=agent_tenure_id,
        run_id=manifest.run_id,
        episode_id=manifest.episode_id,
        world_branch_id=manifest.world_branch_id,
        start_snapshot=StewardshipStateSnapshotRef(
            run_id=snapshot.run_id,
            episode_id=snapshot.episode_id,
            world_branch_id=snapshot.world_branch_id,
            sequence=snapshot.sequence,
            state_id=snapshot.state_id,
            commit_id=snapshot.commit_id,
        ),
    )


def _open(
    run_dir: Path,
    request: WorldSessionRequest,
    *,
    temporal_evidence: bool = False,
) -> PumpStationWorldSession:
    return cast(
        PumpStationWorldSession,
        open_world_session(
            request,
            _factory(run_dir, temporal_evidence=temporal_evidence),
        ),
    )


@app.command("interface")
def interface_command(
    run_dir: Path = typer.Option(..., "--run-dir", help="Durable world-run directory"),
    request_path: Path = typer.Option(..., "--request-path", help="Strict JSON interface request"),
    host_authority_id: str | None = typer.Option(
        None,
        "--host-authority-id",
        help="Host-only control authority identity",
    ),
    rollout_dir: Path | None = typer.Option(
        None,
        "--rollout-dir",
        help="Host-private rollout repository directory",
    ),
) -> None:
    """Execute one strict machine-readable actor or host-control request."""

    started = time.monotonic()
    request = PumpStationLocalInterfaceRequest.model_validate_json(request_path.read_text(encoding="utf-8"))
    if isinstance(PumpStationWorldRunRepository(run_dir).load_manifest(), PumpStationWorldRunManifestV2):
        raise typer.BadParameter(
            "registered V4 runs require actor-interface or control-interface",
            param_hint="--run-dir",
        )
    if request.surface == "actor":
        assert request.session_request is not None
        session = _open(run_dir, request.session_request)
        if request.operation == "capabilities":
            payload = session.actor_capabilities.model_dump(mode="json")
        elif request.operation == "observe":
            payload = observe_world_actor(session).model_dump(mode="json")
        else:
            assert request.action_request is not None
            payload = invoke_world_actor(
                session,
                request.action_request,
            ).model_dump(mode="json")
    else:
        if host_authority_id is None:
            raise typer.BadParameter(
                "host control requires --host-authority-id",
                param_hint="--host-authority-id",
            )
        if isinstance(request.control_request, PumpStationRolloutControlRequest):
            if rollout_dir is None:
                raise typer.BadParameter(
                    "rollout control requires --rollout-dir",
                    param_hint="--rollout-dir",
                )
            rollout_control = PumpStationRolloutControl(
                parent_repository_root=run_dir,
                rollout_repository_root=rollout_dir,
                authorised_principal_ids=(host_authority_id,),
                evidence_health=request.evidence_health,
            )
            payload = execute_pump_station_rollout_request(
                rollout_control,
                request.control_request,
            ).model_dump(mode="json")
        else:
            control = PumpStationWorldControl(
                run_dir,
                authorised_principal_ids=(host_authority_id,),
                evidence_health=(
                    request.evidence_health
                    or isinstance(
                        request.control_request,
                        PumpStationEvidenceControlRequest,
                    )
                    and request.control_request.operation
                    in {
                        "schedule_evidence_treatment",
                        "inspect_evidence_treatment",
                        "recover_evidence_treatment",
                    }
                ),
            )
            if request.operation == "capabilities":
                assert request.authority_id is not None
                payload = control.capabilities(request.authority_id).model_dump(mode="json")
            else:
                assert request.control_request is not None
                payload = control.execute(request.control_request).model_dump(mode="json")
    emit(
        "task pump-station-world interface",
        payload,
        start_time=started,
    )


@app.command("actor-interface")
def actor_interface_command(
    run_dir: Path = typer.Option(..., "--run-dir", help="Durable world-run directory"),
    request_path: Path = typer.Option(..., "--request-path", help="Registered actor JSON request"),
) -> None:
    """Execute one separate actor request through the continual-world catalogue."""

    started = time.monotonic()
    request = ContinualWorldActorRequest.model_validate_json(request_path.read_text(encoding="utf-8"))
    result = dispatch_continual_actor(
        context=ContinualWorldInterfaceContext(
            catalogue=default_continual_world_catalogue(),
            run_root=run_dir,
            rollout_repository_root=None,
            authorised_principal_ids=(),
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


@app.command("review-interface")
def review_interface_command(
    source_run_dir: Path = typer.Option(
        ...,
        "--source-run-dir",
        help="Immutable source pump-station run directory",
    ),
    review_dir: Path = typer.Option(
        ...,
        "--review-dir",
        help="Durable derived review-case directory",
    ),
    request_path: Path = typer.Option(
        ...,
        "--request-path",
        help="Strict review JSON interface request",
    ),
    host_authority_id: str | None = typer.Option(
        None,
        "--host-authority-id",
        help="Host-only review-control authority identity",
    ),
) -> None:
    """Execute one machine-readable review or host-control request."""
    started = time.monotonic()
    request = PumpStationReviewLocalInterfaceRequest.model_validate_json(request_path.read_text(encoding="utf-8"))
    payload = execute_pump_station_review_local_request(
        source_run_root=source_run_dir,
        review_repository_root=review_dir,
        request=request,
        host_authority_id=host_authority_id,
    )
    emit(
        "task pump-station-world review-interface",
        payload,
        start_time=started,
    )


@app.command("start")
def start_command(
    run_dir: Path = typer.Option(..., "--run-dir", help="Empty directory for the durable world run"),
    run_id: str = typer.Option(..., "--run-id", help="Stable world-run identity"),
    episode_id: str = typer.Option(..., "--episode-id", help="Stable episode identity"),
    world_branch_id: str = typer.Option(..., "--world-branch-id", help="Stable continuing branch identity"),
    session_id: str = typer.Option(..., "--session-id", help="Direct host-session identity"),
    agent_tenure_id: str = typer.Option(..., "--agent-tenure-id", help="Current actor-tenure identity"),
    temporal_evidence: bool = typer.Option(
        False,
        "--temporal-evidence",
        help="Enable the local temporal documentary-evidence capability",
    ),
) -> None:
    """Start one direct session over a new durable pump-station run."""
    started = time.monotonic()
    request = WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.START,
        session_id=session_id,
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id=agent_tenure_id,
        run_id=run_id,
        episode_id=episode_id,
        world_branch_id=world_branch_id,
    )
    session = _open(
        run_dir,
        request,
        temporal_evidence=temporal_evidence,
    )
    emit(
        "task pump-station-world start",
        session.result.model_dump(mode="json"),
        start_time=started,
    )


@app.command("resume")
def resume_command(
    run_dir: Path = typer.Option(..., "--run-dir", help="Existing durable world-run directory"),
    session_id: str = typer.Option(..., "--session-id", help="Direct host-session identity"),
    agent_tenure_id: str = typer.Option(..., "--agent-tenure-id", help="Fresh or continuing actor tenure"),
) -> None:
    """Resume the exact selected world state under one actor tenure."""
    started = time.monotonic()
    session = _open(
        run_dir,
        _resume_request(
            run_dir,
            session_id=session_id,
            agent_tenure_id=agent_tenure_id,
        ),
    )
    emit(
        "task pump-station-world resume",
        session.result.model_dump(mode="json"),
        start_time=started,
    )


@app.command("continue-operation")
def continue_operation_command(
    run_dir: Path = typer.Option(..., "--run-dir", help="Existing durable world-run directory"),
    session_id: str = typer.Option(..., "--session-id", help="Direct host-session identity"),
    agent_tenure_id: str = typer.Option(..., "--agent-tenure-id", help="Current actor-tenure identity"),
    proposal_id: str = typer.Option(..., "--proposal-id", help="Stable proposal identity"),
    reason: str = typer.Option(..., "--reason", help="Actor reason for continuing operation"),
) -> None:
    """Apply the explicit no-intervention proposal and advance simulated time."""
    started = time.monotonic()
    session = _open(
        run_dir,
        _resume_request(
            run_dir,
            session_id=session_id,
            agent_tenure_id=agent_tenure_id,
        ),
    )
    result = json.loads(
        session.continue_operation(
            proposal_id=proposal_id,
            reason=reason,
        )
    )
    emit(
        "task pump-station-world continue-operation",
        result,
        start_time=started,
    )


@app.command("search-evidence")
def search_evidence_command(
    run_dir: Path = typer.Option(..., "--run-dir", help="Existing durable world-run directory"),
    session_id: str = typer.Option(..., "--session-id", help="Direct host-session identity"),
    agent_tenure_id: str = typer.Option(..., "--agent-tenure-id", help="Current actor-tenure identity"),
    request_id: str = typer.Option(..., "--request-id", help="Stable access request identity"),
    query: str = typer.Option(..., "--query", help="Actor-visible documentary search query"),
    scope: str = typer.Option("all", "--scope", help="Allowlisted documentary scope"),
    limit: int = typer.Option(5, "--limit", min=1, max=5, help="Maximum visible references"),
) -> None:
    """Search evidence available at the current world time."""

    started = time.monotonic()
    session = _open(
        run_dir,
        _resume_request(
            run_dir,
            session_id=session_id,
            agent_tenure_id=agent_tenure_id,
        ),
    )
    emit(
        "task pump-station-world search-evidence",
        json.loads(
            session.search_evidence(
                request_id=request_id,
                query=query,
                scope=scope,
                limit=limit,
            )
        ),
        start_time=started,
    )


@app.command("fetch-evidence")
def fetch_evidence_command(
    run_dir: Path = typer.Option(..., "--run-dir", help="Existing durable world-run directory"),
    session_id: str = typer.Option(..., "--session-id", help="Direct host-session identity"),
    agent_tenure_id: str = typer.Option(..., "--agent-tenure-id", help="Current actor-tenure identity"),
    request_id: str = typer.Option(..., "--request-id", help="Stable access request identity"),
    reference: str = typer.Option(..., "--reference", help="Opaque reference from an earlier search"),
) -> None:
    """Fetch documentary content through one issued opaque reference."""

    started = time.monotonic()
    session = _open(
        run_dir,
        _resume_request(
            run_dir,
            session_id=session_id,
            agent_tenure_id=agent_tenure_id,
        ),
    )
    emit(
        "task pump-station-world fetch-evidence",
        json.loads(
            session.fetch_evidence(
                request_id=request_id,
                reference=reference,
            )
        ),
        start_time=started,
    )


@app.command("verify")
def verify_command(
    run_dir: Path = typer.Option(..., "--run-dir", help="Existing durable world-run directory"),
) -> None:
    """Reload and independently replay all committed pump-station transitions."""
    started = time.monotonic()
    session = _open(
        run_dir,
        _resume_request(
            run_dir,
            session_id="verification-session",
            agent_tenure_id="verification-tenure",
        ),
    )
    report = session.verify()
    emit(
        "task pump-station-world verify",
        _verification_payload(report),
        start_time=started,
    )


@app.command("verify-temporal-evidence")
def verify_temporal_evidence_command(
    run_dir: Path = typer.Option(..., "--run-dir", help="Existing temporal world-run directory"),
) -> None:
    """Reload and independently replay the temporal-evidence ledger."""

    started = time.monotonic()
    session = _open(
        run_dir,
        _resume_request(
            run_dir,
            session_id="temporal-verification-session",
            agent_tenure_id="temporal-verification-tenure",
        ),
    )
    report = session.verify_temporal_evidence()
    emit(
        "task pump-station-world verify-temporal-evidence",
        report.model_dump(mode="json"),
        errors=[item.detail for item in report.issues],
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
    evaluation = evaluate_pump_station_stewardship_run(
        run_dir=run_dir,
    )
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
    temporal_evidence: bool = typer.Option(
        False,
        "--temporal-evidence",
        help="Export the local temporal documentary-evidence profile",
    ),
) -> None:
    """Export one provider-free wastewater pump-station Harbor task."""

    started = time.monotonic()
    exported = export_pump_station_harbor_task(
        task_dir,
        project_root=project_root,
        temporal_evidence=temporal_evidence,
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
        PUMP_STATION_REFERENCE_CONTROLLER_ID,
        "--model",
        help="Reference controller ID or Bedrock model name",
    ),
    max_turns: int = typer.Option(
        PUMP_STATION_MODEL_MAX_TURNS,
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
