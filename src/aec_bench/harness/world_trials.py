# ABOUTME: Maps planned Interactive World tasks to complete TrialRecord-returning trial functions.
# ABOUTME: Validates ordered experiment results and builds retained Prime world evidence records.

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Protocol

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.authority_evidence import AuthorityEvidenceKind
from aec_bench.contracts.evaluation_result import EvaluationResult
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
from aec_bench.harness.prime_world_actor import WorldActorSession
from aec_bench.harness.world_actor import ACTOR_INVOCATION_EVIDENCE_SCHEMA, WorldActorHost
from aec_bench.trials import PlannedTrial
from aec_bench.worlds.tasks import WorldTask

type WorldTrialRunner = Callable[[WorldTask, PlannedTrial], Awaitable[TrialRecord]]


class WorldActorSessionRunner(Protocol):
    async def __call__(
        self,
        *,
        host: WorldActorHost,
        trial: PlannedTrial,
        instruction: str,
        actor_workspace: Path,
        evidence_directory: Path,
        skills: Sequence[Path] = (),
        private_paths: Sequence[Path] = (),
    ) -> WorldActorSession: ...


async def run_world_experiment(
    *,
    tasks: Sequence[WorldTask],
    trials: Sequence[PlannedTrial],
    run_trial: WorldTrialRunner,
    persist: Callable[[TrialRecord], object] | None = None,
) -> list[TrialRecord]:
    """Run complete world trials sequentially and preserve declared plan order."""

    task_ids = [task.task_id for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("world experiment tasks must have distinct task_id values")
    trial_ids = [trial.trial_id for trial in trials]
    if len(trial_ids) != len(set(trial_ids)):
        raise ValueError("world experiment trials must have distinct trial_id values")
    by_id = {task.task_id: task for task in tasks}
    records: list[TrialRecord] = []
    for trial in trials:
        try:
            task = by_id[trial.task_id]
        except KeyError as error:
            raise ValueError(f"planned world trial has no supplied task: {trial.task_id}") from error
        record = await run_trial(task, trial)
        _validate_world_record(task, trial, record)
        if persist is not None:
            persist(record)
        records.append(record)
    return records


def build_prime_world_trial_record(
    *,
    task: WorldTask,
    trial: PlannedTrial,
    session: WorldActorSession,
    evaluation: EvaluationResult,
    world_evidence_file: Path,
    world_evidence_protocol: str,
    execution_completed: bool,
    terminated: bool,
    truncated: bool,
    final_reason: str,
) -> TrialRecord:
    """Build one world TrialRecord from closed Prime and task-owned evidence."""

    evidence_file = world_evidence_file
    started_at = session.prime.started_at
    completed_at = session.prime.finished_at
    total_seconds = max(0.0, (completed_at - started_at).total_seconds())
    actor_evidence = () if session.actor_authority_evidence is None else (session.actor_authority_evidence,)
    execution_status = ExecutionStatus.COMPLETED if execution_completed else ExecutionStatus.FAILED
    output_status = AgentOutputStatus.COMPLETED if execution_completed else AgentOutputStatus.FAILED
    run_id = ":".join((trial.experiment_id, trial.agent.adapter, trial.agent.model, trial.compute.backend))
    manifest = RunManifest(
        run_id=run_id,
        experiment_id=trial.experiment_id,
        source=UnresolvedSourceRef(reason="world task source was not supplied to the direct trial runner"),
        agent=AgentConfiguration(
            adapter=trial.agent.adapter,
            model=trial.agent.model,
            configuration={
                key: value
                for key, value in trial.agent.parameters.items()
                if key not in {"environment", "prime_runtime_directory", "work_root"}
            },
        ),
        execution_environment=ExecutionEnvironmentRef(
            runtime_image=str(trial.agent.parameters.get("runtime_image", "local-prime-world")),
            compute_backend=trial.compute.backend,
        ),
        provider_route=ProviderRoute(provider="prime-intellect", route="prime-agent"),
        expected_authorities=(
            AuthorityExpectation(
                authority_kind=AuthorityEvidenceKind.ACTOR_INVOCATION,
                protocol=ACTOR_INVOCATION_EVIDENCE_SCHEMA,
            ),
            AuthorityExpectation(authority_kind=AuthorityEvidenceKind.WORLD, protocol=world_evidence_protocol),
            AuthorityExpectation(authority_kind=AuthorityEvidenceKind.PROVIDER, protocol="aec-bench/prime-acp/1"),
        ),
    )
    usage = session.prime.usage
    record = TrialRecord(
        trial_id=trial.trial_id,
        run_id=run_id,
        task_id=task.task_id,
        execution_status=execution_status,
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
                status=output_status,
                output_path=str(evidence_file),
                output_format="json",
                error_message=None if execution_completed else final_reason,
            ),
            agent_result={
                "provider_session_state": session.prime.session_state,
                "provider_stop_reason": session.prime.stop_reason,
                "world_action_count": session.world_action_count,
                "world_action_limit_reached": session.world_action_limit_reached,
                "actor_authority_closed": session.close_complete,
            },
            terminated=terminated,
            truncated=truncated,
            final_reason=final_reason,
        ),
        evaluation=evaluation,
        timing=TimingRecord(total_seconds=total_seconds, agent_seconds=session.prime.elapsed_seconds),
        cost=CostRecord(
            model_calls=usage.model_calls,
            tokens_in=usage.input_tokens,
            tokens_out=usage.output_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            cache_write_tokens=usage.cache_write_tokens,
            estimated_cost_usd=float(usage.cost_usd),
        ),
        authority_evidence=actor_evidence,
    ).bind_run_manifest(manifest)
    record.attach_artifact("provider_evidence", session.prime.paths.run_file, media_type="application/json")
    record.attach_artifact(
        f"authority:world:{world_evidence_protocol}",
        evidence_file,
        media_type="application/json",
    )
    record.attach_artifact(
        "output:world_actor_transport",
        session.actor_transport_file,
        media_type="application/x-ndjson",
    )
    return record


def _validate_world_record(task: WorldTask, trial: PlannedTrial, record: TrialRecord) -> None:
    if record.trial_id != trial.trial_id or record.task_id != task.task_id:
        raise ValueError("world trial record does not match the planned trial")
    if record.experiment_id != trial.experiment_id:
        raise ValueError("world trial record experiment does not match the planned trial")
    if record.input.task_kind != "world" or record.input.task_revision != task.task_revision:
        raise ValueError("world trial record does not match the world task")
    if record.agent.adapter != trial.agent.adapter or record.agent.model != trial.agent.model:
        raise ValueError("world trial record agent does not match the planned trial")


__all__ = (
    "WorldActorSessionRunner",
    "WorldTrialRunner",
    "build_prime_world_trial_record",
    "run_world_experiment",
)
