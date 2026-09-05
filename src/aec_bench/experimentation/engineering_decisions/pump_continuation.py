# ABOUTME: Compares verification and deferral under one pump profile and common future horizon.
# ABOUTME: Uses durable actor execution, fresh-host recovery, task-owned Operations controls, and replay evaluation.

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from aec_bench import worlds
from aec_bench.contracts.evaluation_result import EvaluationResult, StewardshipEvaluation, ValidityCheck
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.experimentation.engineering_decisions.definitions import PumpExperiment
from aec_bench.experimentation.engineering_decisions.records import publish_record, world_record, write_plan
from aec_bench.harness.world_trials import run_world_experiment
from aec_bench.trials import PlannedTrial, plan_trials
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import PumpStationEpisodeHost
from aec_bench.worlds.stewardship.wastewater_pump_station.evaluation import evaluate_pump_station_reference_run
from aec_bench.worlds.stewardship.wastewater_pump_station.handover import (
    PumpHandover,
    assess_pump_handover,
    required_pump_handover,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.host_continuation import (
    resolve_pump_station_host_continuation,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_system import PUMP_STATION_REFERENCE_SYSTEM_ID
from aec_bench.worlds.stewardship.wastewater_pump_station.world_control import PumpStationWorldControl
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import PumpStationWorldRun
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import PumpStationWorldRunRepository
from aec_bench.worlds.tasks import WorldTask


def run_pump_continuation(
    output: Path,
    *,
    omit_verification_work: bool = False,
    horizon_seconds: int = 93600,
    reference_system_id: str = PUMP_STATION_REFERENCE_SYSTEM_ID,
    max_actions: int = 512,
) -> dict[str, Any]:
    """Run a bounded synthetic handover control; horizon is an absolute task calendar time."""
    if max_actions < 1:
        raise ValueError("max_actions must be positive")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("pump continuation output must be empty")
    run = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(output),
        run_id="continuation",
        episode_id="continuation",
        world_branch_id="continuation",
        reference_system_id=reference_system_id,
    )
    if not run.state.calendar_seconds < horizon_seconds <= run.state.disclosed_through_calendar_seconds:
        raise ValueError("horizon must follow opening time and remain within disclosed conditions")
    source = PumpStationEpisodeHost(output).observe()
    handover = required_pump_handover(source)
    if omit_verification_work:
        handover = PumpHandover(
            source_view_id=handover.source_view_id,
            facts={
                k: v
                for k, v in handover.facts.items()
                if not (isinstance(v, dict) and v.get("work_type") == "post_maintenance_verification")
            },
        )
    assessment = assess_pump_handover(source, handover)
    # Reopen through the installed host. No old session state is carried to the new actor.
    host = PumpStationEpisodeHost(output)
    control = PumpStationWorldControl(output, authorised_principal_ids=("operations-controller",))
    verification = next(
        (
            v
            for v in handover.facts.values()
            if isinstance(v, dict) and v.get("work_type") == "post_maintenance_verification"
        ),
        None,
    )
    actions_taken = 0
    if verification is not None:
        result = host.invoke(
            WorldActorActionRequest(
                request_id="handover-verification",
                decision_id=host.observe().decision_id,
                action_name="request_post_maintenance_verification",
                arguments={
                    "pump_id": verification["target_id"],
                    "backlog_item_id": verification["item_id"],
                    "reason": "Complete the verification recorded in the public handover.",
                },
            )
        )
        actions_taken += 1
        if result.status != "applied":
            raise RuntimeError(f"verification control was rejected: {result.status}")
    first_service = {k: source.view[k] for k in ("served_scu", "unserved_scu")}
    for index in range(max_actions - actions_taken):
        if run.state.calendar_seconds >= horizon_seconds:
            break
        before = run.state.calendar_seconds
        result = host.invoke(
            WorldActorActionRequest(
                request_id=f"continue-{index}",
                decision_id=host.observe().decision_id,
                action_name="continue_operation",
                arguments={"reason": "Observe consequences over the common horizon."},
            )
        )
        actions_taken += 1
        if result.status != "applied" or run.state.calendar_seconds <= before:
            raise RuntimeError(f"continuation did not advance: {result.status}")
        continuation = resolve_pump_station_host_continuation(run)
        if continuation.control_request is not None:
            control.execute(continuation.control_request)
    if run.state.calendar_seconds > horizon_seconds:
        raise ValueError("the selected horizon must coincide with a canonical world boundary")
    evaluation = evaluate_pump_station_reference_run(run, evaluation_scope="bounded_continuation")
    if not run.verify().valid:
        raise RuntimeError("pump continuation replay failed")
    return {
        "opening_state_id": run.manifest.initial_state_id,
        "profile_id": reference_system_id,
        "horizon_seconds": horizon_seconds,
        "actor_actions": actions_taken,
        "closing_calendar_seconds": run.state.calendar_seconds,
        "horizon_reached": run.state.calendar_seconds == horizon_seconds,
        "immediate_service": first_service,
        "handover": handover.model_dump(mode="json"),
        "handover_assessment": assessment.model_dump(mode="json"),
        "handover_complete": assessment.complete,
        "evaluation": evaluation.model_dump(mode="json"),
        "replay_valid": True,
        "evidence_scope": "deterministic_synthetic_control_not_model_handover_performance",
    }


def run_pump_experiment(output: Path, definition: PumpExperiment | None = None) -> list[TrialRecord]:
    definition = definition or PumpExperiment()
    task = worlds.task(
        "wastewater-pump-station-stewardship.v1",
        profile=definition.profile,
        instruction="Continue operation from the supplied public handover to the declared calendar horizon.",
    )
    agents = [
        AgentConfig(
            name="omitted_work" if omit else "complete_handover",
            adapter="deterministic",
            model="handover-control",
            parameters={
                "omit_verification_work": omit,
                "horizon_seconds": definition.horizon_seconds,
                "max_actions": definition.max_actions,
            },
        )
        for omit in definition.omit_verification_work
    ]
    trials = plan_trials(
        experiment_id=definition.experiment_id, tasks=[task], agents=agents, compute=ComputeConfig(backend="local")
    )
    write_plan(output, definition, trials)

    async def execute(task: WorldTask, trial: PlannedTrial) -> TrialRecord:
        started = datetime.now(UTC)
        trial_root = output / trial.trial_id
        report = run_pump_continuation(
            trial_root / "world",
            omit_verification_work=trial.agent.parameters["omit_verification_work"],
            horizon_seconds=definition.horizon_seconds,
            reference_system_id=definition.profile,
            max_actions=definition.max_actions,
        )
        stewardship = StewardshipEvaluation.model_validate(report["evaluation"])
        evaluation = EvaluationResult(
            reward=float(stewardship.valid and report["horizon_reached"]),
            stewardship=stewardship,
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=True,
                verifier_completed=report["replay_valid"],
                errors=list(stewardship.gates.errors),
            ),
            breakdown={"evaluation_scope": "bounded_continuation"},
        )
        path = trial_root / "world-evidence.json"
        record = world_record(
            task=task,
            trial=trial,
            evaluation=evaluation,
            evidence=report,
            evidence_file=path,
            started_at=started,
            completed_at=datetime.now(UTC),
            terminated=report["horizon_reached"],
        )
        diagnostic_path = path.with_name("diagnostics.json")
        diagnostic_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        record.attach_artifact("experiment_diagnostics", diagnostic_path, media_type="application/json")
        # Keep the canonical repository layout, including empty files, in one retained archive.
        archive_path = trial_root / "world-run.zip"
        with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
            for source in sorted((trial_root / "world").rglob("*")):
                if source.is_file() and not source.is_symlink():
                    archive.writestr(source.relative_to(trial_root / "world").as_posix(), source.read_bytes())
        record.attach_artifact("world_run", archive_path, media_type="application/zip")
        return record

    records = asyncio.run(run_world_experiment(tasks=[task], trials=trials, run_trial=execute))
    return [publish_record(output, record) for record in records]
