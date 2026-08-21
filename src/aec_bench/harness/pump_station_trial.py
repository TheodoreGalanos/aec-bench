# ABOUTME: Runs and evaluates one complete persistent pump-station Interactive World trial.
# ABOUTME: Reuses the task-owned journey, host controls, repository, replay, and evaluation.

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, cast

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.authority_evidence import (
    ACTOR_INVOCATION_MANIFEST_PROTOCOL,
    AuthorityEvidenceKind,
    AuthorityEvidenceRef,
)
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.trial_record import (
    AgentConfiguration,
    AuthorityExpectation,
    CostRecord,
    EvaluationStatus,
    EvidenceStatus,
    ExecutionEnvironmentRef,
    ExecutionStatus,
    ProviderRoute,
    RunManifest,
    TimingRecord,
    TrialInput,
    TrialOutput,
    TrialRecord,
    UnresolvedSourceRef,
)
from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.harness.pump_station_prime.evidence import PumpStationPrimeJourneyLimits
from aec_bench.harness.pump_station_prime.journey import run_pump_station_prime_journey
from aec_bench.harness.world_trials import WorldActorSessionRunner
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.prime_agent.acp import PrimeAcpIsolation
from aec_bench.prime_agent.refinement import PrimeRefinementCandidate, PrimeRefinementMode
from aec_bench.trials import PlannedTrial
from aec_bench.worlds import load_profile
from aec_bench.worlds.stewardship.wastewater_pump_station.continual_definition import (
    PumpStationContinualProfile,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PUMP_STATION_TASK_WORLD_ID,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.evaluation import (
    evaluate_pump_station_reference_run,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import PumpStationWorldRun
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.worlds.tasks import WorldTask

type PumpStationEvaluationScope = Literal["complete_journey", "bounded_continuation"]
PUMP_STATION_WORLD_EVIDENCE_PROTOCOL = "aec-bench/pump-station-trial/1"


async def run_pump_station_trial(
    task: WorldTask,
    trial: PlannedTrial,
    *,
    actor: WorldActorSessionRunner,
    scope: PumpStationEvaluationScope = "complete_journey",
) -> TrialRecord:
    """Run the existing persistent pump journey and return one normal TrialRecord."""

    if task.world.task_world_id != PUMP_STATION_TASK_WORLD_ID:
        raise ValueError("pump-station trial requires the registered pump world")
    if trial.task_id != task.task_id:
        raise ValueError("pump-station trial plan does not match the task")
    if trial.agent.adapter != "prime-agent":
        raise ValueError(f"unsupported pump-station provider: {trial.agent.adapter}")
    loaded = load_profile(task)
    if not isinstance(loaded.value, PumpStationContinualProfile):
        raise TypeError("pump-station task loaded another profile value")
    parameters = trial.agent.parameters
    limits = PumpStationPrimeJourneyLimits(
        max_sessions=int(cast(str | int, _required(parameters, "max_sessions"))),
        max_host_controls=int(cast(str | int, _required(parameters, "max_host_controls"))),
        max_world_actions=int(cast(str | int, _required(parameters, "max_world_actions"))),
        max_model_calls=int(cast(str | int, _required(parameters, "max_model_calls"))),
        max_tokens=int(cast(str | int, _required(parameters, "max_tokens"))),
        max_cost_usd=Decimal(str(_required(parameters, "max_cost_usd"))),
        max_wall_seconds=float(cast(str | int | float, _required(parameters, "max_wall_seconds"))),
    )
    isolation = PrimeAcpIsolation(str(_required(parameters, "isolation")))
    refinement_mode = PrimeRefinementMode(str(parameters.get("refinement_mode", PrimeRefinementMode.CAPTURE)))
    candidate_value = parameters.get("refinement_candidate")
    refinement_candidate = (
        None
        if candidate_value is None
        else (
            candidate_value
            if isinstance(candidate_value, PrimeRefinementCandidate)
            else PrimeRefinementCandidate.model_validate(candidate_value)
        )
    )
    environment_value = parameters.get("environment")
    environment = None if environment_value is None else cast(dict[str, str], environment_value)
    retained_root = Path(tempfile.mkdtemp(prefix=f"aec-bench-{trial.trial_id}-"))
    world_directory = retained_root / "world"
    run_id = f"{trial.trial_id}-world"
    episode_id = f"{trial.trial_id}-episode"
    branch_id = f"{trial.trial_id}-branch"
    run = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(world_directory),
        run_id=run_id,
        episode_id=episode_id,
        world_branch_id=branch_id,
        reference_system_id=task.profile.profile_id,
    )
    snapshot = run.snapshot()
    request = WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.RESUME,
        session_id=f"{trial.trial_id}-session",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id=trial.agent.name,
        run_id=run_id,
        episode_id=episode_id,
        world_branch_id=branch_id,
        start_snapshot=StewardshipStateSnapshotRef(
            run_id=snapshot.run_id,
            episode_id=snapshot.episode_id,
            world_branch_id=snapshot.world_branch_id,
            sequence=snapshot.sequence,
            state_id=snapshot.state_id,
            commit_id=snapshot.commit_id,
        ),
    )
    started_at = datetime.now(UTC)
    journey = await run_pump_station_prime_journey(
        actor_workspace=retained_root / "actor",
        world_run_directory=world_directory,
        evidence_directory=retained_root / "evidence",
        session_request=request,
        instruction=task.instruction,
        model=trial.agent.model,
        isolation=isolation,
        limits=limits,
        pump_station_guidance=bool(parameters.get("pump_station_guidance", False)),
        actor_ledger_plan=bool(parameters.get("actor_ledger_plan", False)),
        refinement_mode=refinement_mode,
        refinement_candidate=refinement_candidate,
        executable=str(parameters.get("executable", "prime-agent")),
        environment=environment,
        planned_trial=trial,
        actor=actor,
    )
    completed_at = datetime.now(UTC)
    canonical_run = PumpStationWorldRun.resume_reference_system(
        repository=PumpStationWorldRunRepository(world_directory),
        snapshot=PumpStationWorldRunRepository(world_directory).current_snapshot(),
    )
    stewardship = evaluate_pump_station_reference_run(canonical_run, evaluation_scope=scope)
    evaluation = EvaluationResult(
        reward=1.0 if stewardship.valid and journey.completion == "completed" else 0.0,
        validity=ValidityCheck(
            output_parseable=True,
            schema_valid=True,
            verifier_completed=journey.verification.valid,
            errors=[] if journey.verification.valid else ["pump-station canonical replay verification failed"],
        ),
        breakdown=stewardship.model_dump(mode="json"),
        stewardship=stewardship,
    )
    return _pump_record(
        task=task,
        trial=trial,
        journey=journey,
        evaluation=evaluation,
        started_at=started_at,
        completed_at=completed_at,
        retained_root=retained_root,
    )


def _pump_record(
    *,
    task: WorldTask,
    trial: PlannedTrial,
    journey: object,
    evaluation: EvaluationResult,
    started_at: datetime,
    completed_at: datetime,
    retained_root: Path,
) -> TrialRecord:
    from aec_bench.harness.pump_station_prime.journey import PumpStationPrimeJourneyRun

    if not isinstance(journey, PumpStationPrimeJourneyRun):
        raise TypeError("pump journey returned another result type")
    actor_manifest = retained_root / "actor-authority-manifest.json"
    provider_manifest = retained_root / "provider-evidence-manifest.json"
    actor_files = sorted((retained_root / "evidence" / "segments").glob("*/world-actor-authority.jsonl"))
    provider_files = [retained_root / "evidence" / segment.prime_run for segment in journey.segments]
    _write_file_manifest(actor_manifest, actor_files)
    _write_file_manifest(provider_manifest, provider_files)
    actor_ref = ArtifactRepository(retained_root / "authority-artifacts").publish_bytes(
        data=actor_manifest.read_bytes(), media_type="application/json"
    )
    authority = AuthorityEvidenceRef(
        authority_kind=AuthorityEvidenceKind.ACTOR_INVOCATION,
        protocol=ACTOR_INVOCATION_MANIFEST_PROTOCOL,
        artifact=actor_ref,
    )
    total_seconds = max(0.0, (completed_at - started_at).total_seconds())
    execution_completed = journey.benchmark_valid
    run_id = ":".join((trial.experiment_id, trial.agent.adapter, trial.agent.model, trial.compute.backend))
    manifest = RunManifest(
        run_id=run_id,
        experiment_id=trial.experiment_id,
        source=UnresolvedSourceRef(reason="world task source was not supplied to the direct trial runner"),
        agent=AgentConfiguration(adapter=trial.agent.adapter, model=trial.agent.model, configuration={}),
        execution_environment=ExecutionEnvironmentRef(
            runtime_image=str(trial.agent.parameters.get("runtime_image", "local-prime-world")),
            compute_backend=trial.compute.backend,
        ),
        provider_route=ProviderRoute(provider="prime-intellect", route="prime-agent"),
        expected_authorities=(
            AuthorityExpectation(
                authority_kind=AuthorityEvidenceKind.ACTOR_INVOCATION,
                protocol=ACTOR_INVOCATION_MANIFEST_PROTOCOL,
            ),
            AuthorityExpectation(
                authority_kind=AuthorityEvidenceKind.WORLD,
                protocol=PUMP_STATION_WORLD_EVIDENCE_PROTOCOL,
            ),
            AuthorityExpectation(authority_kind=AuthorityEvidenceKind.PROVIDER, protocol="aec-bench/prime-acp/1"),
        ),
    )
    usage = journey.usage
    record = TrialRecord(
        trial_id=trial.trial_id,
        run_id=run_id,
        task_id=task.task_id,
        execution_status=ExecutionStatus.COMPLETED if execution_completed else ExecutionStatus.FAILED,
        evaluation_status=EvaluationStatus.COMPLETED,
        evidence_status=EvidenceStatus.PENDING,
        started_at=started_at,
        completed_at=completed_at,
        input=TrialInput(
            instruction=task.instruction,
            task_revision=task.task_revision,
            task_kind="world",
            visibility=task.visibility,
            system_prompt=trial.agent.system_prompt,
        ),
        output=TrialOutput(
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED if execution_completed else AgentOutputStatus.PARTIAL,
                output_path=str(journey.run_file),
                output_format="json",
            ),
            agent_result={
                "completion": journey.completion,
                "world_state": journey.world_state,
                "stop_reason": journey.stop_reason,
                "world_action_count": journey.world_action_count,
            },
            terminated=journey.completion == "completed",
            truncated=journey.completion != "completed",
            final_reason=journey.stop_reason,
        ),
        evaluation=evaluation,
        timing=TimingRecord(total_seconds=total_seconds, agent_seconds=journey.elapsed_seconds),
        cost=CostRecord(
            model_calls=usage.model_calls,
            tokens_in=usage.input_tokens,
            tokens_out=usage.output_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            cache_write_tokens=usage.cache_write_tokens,
            estimated_cost_usd=float(usage.cost_usd),
        ),
        authority_evidence=(authority,),
    ).bind_run_manifest(manifest)
    record.attach_artifact("provider_evidence", provider_manifest, media_type="application/json")
    record.attach_artifact(
        f"authority:world:{PUMP_STATION_WORLD_EVIDENCE_PROTOCOL}",
        journey.run_file,
        media_type="application/json",
    )
    return record


def _write_file_manifest(path: Path, files: list[Path]) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "path": file.relative_to(path.parent).as_posix(),
                    "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                }
                for file in files
            ],
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _required(parameters: dict[str, object], name: str) -> object:
    try:
        return parameters[name]
    except KeyError as error:
        raise ValueError(f"pump-station trial configuration requires {name}") from error


__all__ = ("PumpStationEvaluationScope", "run_pump_station_trial")
