# ABOUTME: Composes bounded Prime pump sessions with deterministic host-owned continuation.
# ABOUTME: Enforces journey-wide safeguards and recovers exact host controls from canonical world evidence.

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from aec_bench.contracts.evaluation_result import StewardshipEvaluation
from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.harness.pump_station_prime import evidence as journey_evidence
from aec_bench.harness.pump_station_prime.session import (
    PumpStationPrimeSessionLimits,
    PumpStationPrimeSessionRun,
    run_pump_station_prime_session,
)
from aec_bench.prime_agent.acp import PrimeAcpIsolation
from aec_bench.prime_agent.refinement import (
    PrimeRefinementCandidate,
    PrimeRefinementMode,
    validate_refinement_request,
)
from aec_bench.prime_agent.session_evidence import PrimeAcpUsage, acp_usage_payload, aggregate_acp_usage
from aec_bench.worlds.stewardship.wastewater_pump_station import host_continuation as pump_host
from aec_bench.worlds.stewardship.wastewater_pump_station.evaluation import (
    evaluate_pump_station_reference_run,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationBoundControlRequest,
    PumpStationOperationsBoundaryReviewRequest,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationCoupledVerificationReport,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_control import (
    PumpStationRootControlResult,
    PumpStationWorldControl,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationStateSnapshotRef,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_serialization import (
    pump_station_artifact_id,
)

PumpStationPrimeJourneyLimits = journey_evidence.PumpStationPrimeJourneyLimits
PumpStationPrimeJourneyRecoveryError = journey_evidence.PumpStationPrimeJourneyRecoveryError


@dataclass(frozen=True, slots=True)
class PumpStationPrimeJourneyRun:
    """One complete or stopped pump journey with separate actor and world outcomes."""

    segments: tuple[journey_evidence.PumpStationPrimeJourneySegment, ...]
    host_controls: tuple[journey_evidence.PumpStationPrimeJourneyControl, ...]
    final_snapshot: StewardshipStateSnapshotRef
    world_state: str
    completion: str
    stop_reason: str
    verification: PumpStationCoupledVerificationReport
    evaluation: StewardshipEvaluation
    usage: PrimeAcpUsage
    elapsed_seconds: float
    world_action_count: int
    run_file: Path
    benchmark_valid: bool
    refinement_candidate: PrimeRefinementCandidate | None


async def run_pump_station_prime_journey(
    *,
    actor_workspace: Path,
    world_run_directory: Path,
    evidence_directory: Path,
    session_request: WorldSessionRequest,
    instruction: str,
    model: str,
    isolation: PrimeAcpIsolation,
    limits: PumpStationPrimeJourneyLimits,
    pump_station_guidance: bool = False,
    actor_ledger_plan: bool = False,
    refinement_mode: PrimeRefinementMode = PrimeRefinementMode.CAPTURE,
    refinement_candidate: PrimeRefinementCandidate | None = None,
    resume: bool = False,
    executable: str = "prime-agent",
    environment: Mapping[str, str] | None = None,
) -> PumpStationPrimeJourneyRun:
    """Run clean Prime sessions and exact pump-owned host continuation."""
    if pump_station_guidance and actor_ledger_plan:
        raise ValueError("Prime pump treatment must be open, guided, or planned")
    validate_refinement_request(refinement_mode, refinement_candidate)
    actor_workspace = actor_workspace.resolve()
    world_run_directory = world_run_directory.resolve()
    evidence_directory = evidence_directory.resolve()
    if any(_paths_overlap(actor_workspace, path) for path in (world_run_directory, evidence_directory)):
        raise ValueError("actor workspace must be separate from host world and journey evidence paths")
    if _paths_overlap(world_run_directory, evidence_directory):
        raise ValueError("world run and journey evidence paths must be separate")
    policy_sha256 = _host_policy_sha256()
    config_id = journey_evidence.journey_config_id(
        session_request=session_request,
        instruction=instruction,
        model=model,
        isolation=isolation,
        limits=limits,
        guided=pump_station_guidance,
        planned=actor_ledger_plan,
        refinement_mode=refinement_mode,
        refinement_candidate=refinement_candidate,
        executable=executable,
        host_policy_sha256=policy_sha256,
    )
    checkpoint_file = evidence_directory / journey_evidence.CHECKPOINT_NAME
    if resume:
        if not actor_workspace.is_dir() or not evidence_directory.is_dir():
            raise PumpStationPrimeJourneyRecoveryError("Prime journey resume paths do not exist")
        checkpoint = journey_evidence.read_checkpoint(checkpoint_file, config_id)
        if checkpoint.phase == "running":
            raise PumpStationPrimeJourneyRecoveryError("cannot resume a Prime session without a terminal checkpoint")
    else:
        actor_workspace.mkdir(parents=True, exist_ok=False)
        evidence_directory.mkdir(parents=True, exist_ok=False)
        checkpoint = journey_evidence.PumpStationPrimeJourneyCheckpoint(
            config_id=config_id,
            journey_id=session_request.session_id,
            host_policy_sha256=policy_sha256,
            started_at=datetime.now(UTC),
            phase="ready",
            next_session=session_request,
            refinement_candidate=refinement_candidate,
        )
        journey_evidence.write_checkpoint(checkpoint_file, checkpoint)

    control = PumpStationWorldControl(
        world_run_directory,
        authorised_principal_ids=(pump_host.PUMP_STATION_OPERATIONS_AUTHORITY_ID,),
    )

    def finish(
        current: journey_evidence.PumpStationPrimeJourneyCheckpoint,
        completion: str,
        world_state: str,
        stop_reason: str,
    ) -> PumpStationPrimeJourneyRun:
        return _finish(
            current,
            completion=completion,
            world_state=world_state,
            stop_reason=stop_reason,
            limits=limits,
            instruction=instruction,
            model=model,
            isolation=isolation,
            pump_station_guidance=pump_station_guidance,
            actor_ledger_plan=actor_ledger_plan,
            world_run_directory=world_run_directory,
            evidence_directory=evidence_directory,
            checkpoint_file=checkpoint_file,
        )

    while True:
        if checkpoint.phase == "finished":
            return _result(
                checkpoint,
                world_run_directory=world_run_directory,
                evidence_directory=evidence_directory,
            )
        if checkpoint.phase == "control_pending":
            checkpoint, completed = _apply_pending_control(
                checkpoint,
                control=control,
                world_run_directory=world_run_directory,
                initial_session=session_request,
            )
            if completed:
                return finish(checkpoint, "completed", "completed", "declared-terminal-state")
            journey_evidence.write_checkpoint(checkpoint_file, checkpoint)
            continue
        if checkpoint.phase == "ready":
            limit_reason = _journey_limit_reason(checkpoint, limits)
            if limit_reason is not None:
                return finish(checkpoint, "interrupted", "active", limit_reason)
            current_request = checkpoint.next_session
            if current_request is None:
                raise PumpStationPrimeJourneyRecoveryError("ready journey checkpoint has no next session")
            running = checkpoint.model_copy(update={"phase": "running"})
            journey_evidence.write_checkpoint(checkpoint_file, running)
            index = len(checkpoint.segments)
            runtime_directory = actor_workspace / ".prime-runtimes" / f"segment-{index:03d}"
            segment = await run_pump_station_prime_session(
                actor_workspace=actor_workspace,
                world_run_directory=world_run_directory,
                evidence_directory=evidence_directory / "segments" / f"segment-{index:03d}",
                prime_runtime_directory=runtime_directory,
                additional_private_paths=(evidence_directory,),
                session_request=current_request,
                instruction=_segment_instruction(instruction, index),
                model=model,
                isolation=isolation,
                limits=_remaining_session_limits(checkpoint, limits),
                pump_station_guidance=pump_station_guidance,
                actor_ledger_plan=actor_ledger_plan,
                refinement_mode=refinement_mode,
                refinement_candidate=checkpoint.refinement_candidate,
                executable=executable,
                environment=environment,
            )
            _remove_closed_prime_runtime(actor_workspace, runtime_directory)
            run = _resume_verified_run(world_run_directory)
            summary = _segment_summary(segment, run, index=index, evidence_directory=evidence_directory)
            checkpoint = running.model_copy(
                update={
                    "phase": "segment_ended",
                    "next_session": None,
                    "segments": (*checkpoint.segments, summary),
                    "refinement_candidate": (
                        segment.prime.refinement_harness.global_candidate
                        if refinement_mode is PrimeRefinementMode.DISCOVER
                        else checkpoint.refinement_candidate
                    ),
                }
            )
            journey_evidence.write_checkpoint(checkpoint_file, checkpoint)
            continue
        if checkpoint.phase != "segment_ended" or not checkpoint.segments:
            raise PumpStationPrimeJourneyRecoveryError(f"unsupported journey checkpoint phase: {checkpoint.phase}")

        run = _resume_verified_run(world_run_directory)
        stop = _segment_stop(checkpoint.segments[-1])
        if stop is not None:
            completion, reason = stop
            return finish(checkpoint, completion, "active", reason)
        decision = pump_host.resolve_pump_station_host_continuation(run)
        if decision.status is pump_host.PumpStationJourneyStatus.COMPLETED:
            return finish(checkpoint, "completed", "completed", decision.reason)
        limit_reason = _journey_limit_reason(checkpoint, limits)
        if limit_reason is not None:
            return finish(checkpoint, "interrupted", "active", limit_reason)
        if decision.control_request is None:
            return finish(checkpoint, "incomplete", "active", decision.reason)
        if len(checkpoint.host_controls) >= limits.max_host_controls:
            return finish(checkpoint, "interrupted", "active", "max_host_controls")
        checkpoint = checkpoint.model_copy(
            update={
                "phase": "control_pending",
                "pending_request_id": decision.control_request.request_id,
                "pending_parent": _shared_snapshot(run.snapshot()),
            }
        )
        journey_evidence.write_checkpoint(checkpoint_file, checkpoint)


def _apply_pending_control(
    checkpoint: journey_evidence.PumpStationPrimeJourneyCheckpoint,
    *,
    control: PumpStationWorldControl,
    world_run_directory: Path,
    initial_session: WorldSessionRequest,
) -> tuple[journey_evidence.PumpStationPrimeJourneyCheckpoint, bool]:
    request = _pending_control_request(checkpoint, world_run_directory)
    result = control.execute(request)
    if not isinstance(result, PumpStationRootControlResult):
        raise PumpStationPrimeJourneyRecoveryError("pump host continuation returned a non-root control result")
    parent = checkpoint.pending_parent
    receipt = result.receipt
    if (
        parent is None
        or not receipt.state_changed
        or receipt.prior_snapshot != parent
        or receipt.result_snapshot is None
        or receipt.result_snapshot == parent
    ):
        raise PumpStationPrimeJourneyRecoveryError(
            "pump host continuation did not advance the exact canonical snapshot"
        )
    run = _resume_verified_run(world_run_directory)
    result_snapshot = _shared_snapshot(run.snapshot())
    if receipt.result_snapshot != result_snapshot:
        raise PumpStationPrimeJourneyRecoveryError(
            "pump host continuation result differs from the selected canonical snapshot"
        )
    host_control = journey_evidence.PumpStationPrimeJourneyControl(
        index=len(checkpoint.host_controls),
        request_id=receipt.request_id,
        operation=receipt.operation,
        parent_snapshot=parent,
        result_snapshot=result_snapshot,
    )
    checkpoint = checkpoint.model_copy(
        update={
            "pending_request_id": None,
            "pending_parent": None,
            "host_controls": (*checkpoint.host_controls, host_control),
        }
    )
    if pump_host.pump_station_journey_status(run.state) is pump_host.PumpStationJourneyStatus.COMPLETED:
        return checkpoint.model_copy(update={"phase": "segment_ended"}), True
    next_session = WorldSessionRequest(
        execution_kind=initial_session.execution_kind,
        open_mode=WorldSessionOpenMode.RESUME,
        session_id=f"{initial_session.session_id}-continuation-{len(checkpoint.segments):03d}",
        task_world_id=initial_session.task_world_id,
        agent_tenure_id=initial_session.agent_tenure_id,
        run_id=initial_session.run_id,
        episode_id=initial_session.episode_id,
        world_branch_id=initial_session.world_branch_id,
        start_snapshot=result_snapshot,
    )
    return checkpoint.model_copy(update={"phase": "ready", "next_session": next_session}), False


def _pending_control_request(
    checkpoint: journey_evidence.PumpStationPrimeJourneyCheckpoint,
    world_run_directory: Path,
) -> PumpStationBoundControlRequest:
    request_id = checkpoint.pending_request_id
    parent = checkpoint.pending_parent
    if request_id is None or parent is None:
        raise PumpStationPrimeJourneyRecoveryError("pending host control checkpoint is incomplete")
    repository = PumpStationWorldRunRepository(world_run_directory)
    committed = repository.find_committed_command(request_id)
    if committed is None:
        run = _resume_verified_run(world_run_directory)
        if _shared_snapshot(run.snapshot()) != parent:
            raise PumpStationPrimeJourneyRecoveryError(
                "pending host control parent differs from the canonical snapshot"
            )
        decision = pump_host.resolve_pump_station_host_continuation(run)
        if decision.control_request is None or decision.control_request.request_id != request_id:
            raise PumpStationPrimeJourneyRecoveryError(
                "pending host control cannot be reproduced from its parent snapshot"
            )
        return decision.control_request
    matching = tuple(step.command for step in repository.command_steps() if step.command.request_id == request_id)
    if len(matching) != 1:
        raise PumpStationPrimeJourneyRecoveryError("pending host control has no unique canonical command")
    command = matching[0]
    if command.kind != "operations_review" or not isinstance(
        command.control, PumpStationOperationsBoundaryReviewRequest
    ):
        raise PumpStationPrimeJourneyRecoveryError("pending host control differs from the pump continuation policy")
    return PumpStationBoundControlRequest(
        request_id=command.request_id,
        run_id=command.run_id,
        episode_id=command.episode_id,
        world_branch_id=command.world_branch_id,
        base_state_id=command.base_state_id,
        base_commit_id=command.base_commit_id,
        based_on_sequence=command.based_on_sequence,
        control=command.control,
    )


def _segment_summary(
    segment: PumpStationPrimeSessionRun,
    run: PumpStationWorldRun,
    *,
    index: int,
    evidence_directory: Path,
) -> journey_evidence.PumpStationPrimeJourneySegment:
    return journey_evidence.PumpStationPrimeJourneySegment(
        index=index,
        world_session_id=segment.world_session.session_id,
        prime_session_id=segment.prime.session_id,
        open_mode=segment.world_session.open_mode,
        start_snapshot=segment.world_session.snapshot,
        end_snapshot=_shared_snapshot(run.snapshot()),
        prime_run=segment.prime.paths.run_file.relative_to(evidence_directory).as_posix(),
        world_run=segment.run_file.relative_to(evidence_directory).as_posix(),
        session_state=segment.prime.session_state,
        stop_reason=segment.prime.stop_reason,
        limit_reason=segment.prime.limit_reason,
        completion=segment.completion,
        usage=segment.prime.usage,
        elapsed_seconds=segment.prime.elapsed_seconds,
        world_action_count=segment.world_action_count,
        world_action_limit_reached=segment.world_action_limit_reached,
        benchmark_valid=segment.benchmark_valid,
        refinement_mode=segment.prime.refinement_harness.mode,
        refinement_candidate_sha256=segment.prime.refinement_harness.candidate.content_sha256,
        refinement_global_candidate_sha256=(segment.prime.refinement_harness.global_candidate.content_sha256),
        refinement_changed=segment.prime.refinement_harness.changed,
        refinement_portable=segment.prime.refinement_harness.portable,
        refinement_issues=segment.prime.refinement_harness.issues,
    )


def _segment_stop(segment: journey_evidence.PumpStationPrimeJourneySegment) -> tuple[str, str] | None:
    if segment.session_state == "failed" or segment.completion == "failed":
        return "failed", "prime-session-failed"
    if segment.refinement_mode is PrimeRefinementMode.DISCOVER and not segment.refinement_portable:
        return "incomplete", "refinement-not-portable"
    if segment.limit_reason is not None:
        return "interrupted", segment.limit_reason
    if segment.world_action_limit_reached:
        return "interrupted", "max_world_actions"
    if segment.session_state == "cancelled" or segment.stop_reason == "cancelled":
        return "interrupted", "cancelled"
    if segment.stop_reason in {"max_tokens", "max_turn_requests"}:
        return "interrupted", segment.stop_reason
    if segment.stop_reason != "end_turn":
        return "failed", "unsupported-prime-stop-reason"
    if segment.completion in {"interrupted", "truncated"}:
        return "interrupted", "prime-session-interrupted"
    return None


def _finish(
    checkpoint: journey_evidence.PumpStationPrimeJourneyCheckpoint,
    *,
    completion: str,
    world_state: str,
    stop_reason: str,
    limits: PumpStationPrimeJourneyLimits,
    instruction: str,
    model: str,
    isolation: PrimeAcpIsolation,
    pump_station_guidance: bool,
    actor_ledger_plan: bool,
    world_run_directory: Path,
    evidence_directory: Path,
    checkpoint_file: Path,
) -> PumpStationPrimeJourneyRun:
    finished = checkpoint.model_copy(
        update={
            "phase": "finished",
            "finished_at": datetime.now(UTC),
            "next_session": None,
            "completion": completion,
            "world_state": world_state,
            "stop_reason": stop_reason,
        }
    )
    _write_run_evidence(
        finished,
        limits=limits,
        instruction=instruction,
        model=model,
        isolation=isolation,
        pump_station_guidance=pump_station_guidance,
        actor_ledger_plan=actor_ledger_plan,
        world_run_directory=world_run_directory,
        evidence_directory=evidence_directory,
    )
    journey_evidence.write_checkpoint(checkpoint_file, finished)
    return _result(finished, world_run_directory=world_run_directory, evidence_directory=evidence_directory)


def _result(
    checkpoint: journey_evidence.PumpStationPrimeJourneyCheckpoint,
    *,
    world_run_directory: Path,
    evidence_directory: Path,
) -> PumpStationPrimeJourneyRun:
    if checkpoint.phase != "finished" or None in (
        checkpoint.completion,
        checkpoint.world_state,
        checkpoint.stop_reason,
    ):
        raise PumpStationPrimeJourneyRecoveryError("journey result requires a finished checkpoint")
    run = _resume_verified_run(world_run_directory)
    verification = run.verify()
    world_state = str(checkpoint.world_state)
    evaluation = evaluate_pump_station_reference_run(
        run,
        evaluation_scope="complete_journey" if world_state == "completed" else "bounded_continuation",
    )
    usage = aggregate_acp_usage(segment.usage for segment in checkpoint.segments)
    return PumpStationPrimeJourneyRun(
        segments=checkpoint.segments,
        host_controls=checkpoint.host_controls,
        final_snapshot=_shared_snapshot(run.snapshot()),
        world_state=world_state,
        completion=str(checkpoint.completion),
        stop_reason=str(checkpoint.stop_reason),
        verification=verification,
        evaluation=evaluation,
        usage=usage,
        elapsed_seconds=journey_evidence.elapsed_seconds(checkpoint),
        world_action_count=sum(segment.world_action_count for segment in checkpoint.segments),
        run_file=evidence_directory / journey_evidence.RUN_NAME,
        benchmark_valid=(
            bool(checkpoint.segments)
            and all(segment.benchmark_valid for segment in checkpoint.segments)
            and verification.valid
        ),
        refinement_candidate=checkpoint.refinement_candidate,
    )


def _write_run_evidence(
    checkpoint: journey_evidence.PumpStationPrimeJourneyCheckpoint,
    *,
    limits: PumpStationPrimeJourneyLimits,
    instruction: str,
    model: str,
    isolation: PrimeAcpIsolation,
    pump_station_guidance: bool,
    actor_ledger_plan: bool,
    world_run_directory: Path,
    evidence_directory: Path,
) -> None:
    run = _resume_verified_run(world_run_directory)
    usage = aggregate_acp_usage(segment.usage for segment in checkpoint.segments)
    final_snapshot = _shared_snapshot(run.snapshot())
    evaluation_scope: Literal["complete_journey", "bounded_continuation"] = (
        "complete_journey" if checkpoint.world_state == "completed" else "bounded_continuation"
    )
    evaluation = evaluate_pump_station_reference_run(run, evaluation_scope=evaluation_scope)
    payload = {
        "schema": "aecbench.prime-world-journey.v1",
        "journey_id": checkpoint.journey_id,
        "config_id": checkpoint.config_id,
        "instruction_sha256": hashlib.sha256(instruction.encode("utf-8")).hexdigest(),
        "model_requested": model,
        "treatment": "guided" if pump_station_guidance else "planned" if actor_ledger_plan else "open",
        "refinement": {
            "mode": (checkpoint.segments[0].refinement_mode if checkpoint.segments else PrimeRefinementMode.CAPTURE),
            "candidate_sha256": (
                None if checkpoint.refinement_candidate is None else checkpoint.refinement_candidate.content_sha256
            ),
        },
        "isolation": isolation,
        "actor_principal_scope": "prime-journey-composite",
        "actor_workspace_continuity": "shared_actor_files_fresh_prime_runtime",
        "host_policy_sha256": checkpoint.host_policy_sha256,
        "safeguards": journey_evidence.limit_payload(limits),
        "world_manifest_content_id": pump_station_artifact_id(run.manifest),
        "initial_snapshot": checkpoint.segments[0].start_snapshot.model_dump(mode="json"),
        "segments": [segment.model_dump(mode="json") for segment in checkpoint.segments],
        "host_controls": [control.model_dump(mode="json") for control in checkpoint.host_controls],
        "totals": acp_usage_payload(usage),
        "elapsed_seconds": journey_evidence.elapsed_seconds(checkpoint),
        "world_action_count": sum(segment.world_action_count for segment in checkpoint.segments),
        "world_state": checkpoint.world_state,
        "completion": checkpoint.completion,
        "stop_reason": checkpoint.stop_reason,
        "evaluation_scope": evaluation_scope,
        "evaluation_valid": evaluation.valid,
        "benchmark_valid": (
            bool(checkpoint.segments)
            and all(segment.benchmark_valid for segment in checkpoint.segments)
            and run.verify().valid
        ),
        "final_snapshot": final_snapshot.model_dump(mode="json"),
    }
    journey_evidence.atomic_write_json(evidence_directory / journey_evidence.RUN_NAME, payload)


def _journey_limit_reason(
    checkpoint: journey_evidence.PumpStationPrimeJourneyCheckpoint,
    limits: PumpStationPrimeJourneyLimits,
) -> str | None:
    usage = aggregate_acp_usage(segment.usage for segment in checkpoint.segments)
    if len(checkpoint.segments) >= limits.max_sessions:
        return "max_sessions"
    if sum(segment.world_action_count for segment in checkpoint.segments) >= limits.max_world_actions:
        return "max_world_actions"
    if usage.model_calls >= limits.max_model_calls:
        return "max_model_calls"
    if usage.total_tokens >= limits.max_tokens:
        return "max_tokens"
    if usage.cost_usd >= limits.max_cost_usd:
        return "max_cost_usd"
    if journey_evidence.elapsed_seconds(checkpoint) >= limits.max_wall_seconds:
        return "max_wall_seconds"
    return None


def _remaining_session_limits(
    checkpoint: journey_evidence.PumpStationPrimeJourneyCheckpoint,
    limits: PumpStationPrimeJourneyLimits,
) -> PumpStationPrimeSessionLimits:
    usage = aggregate_acp_usage(segment.usage for segment in checkpoint.segments)
    return PumpStationPrimeSessionLimits(
        max_world_actions=limits.max_world_actions - sum(segment.world_action_count for segment in checkpoint.segments),
        max_model_calls=limits.max_model_calls - usage.model_calls,
        max_tokens=limits.max_tokens - usage.total_tokens,
        max_cost_usd=limits.max_cost_usd - usage.cost_usd,
        max_wall_seconds=limits.max_wall_seconds - journey_evidence.elapsed_seconds(checkpoint),
    )


def _segment_instruction(instruction: str, segment_index: int) -> str:
    if segment_index == 0:
        return instruction
    return (
        instruction.rstrip()
        + "\n\n"
        + f"This is continuation segment {segment_index}. Reuse the actor-owned ledger, compact state, "
        "calculations, and handover files already in this workspace. The host may have advanced an authorised "
        "boundary while Prime was closed. Call observe before acting and use only the new actor-visible evidence."
    )


def _resume_verified_run(repository_root: Path) -> PumpStationWorldRun:
    repository = PumpStationWorldRunRepository(repository_root)
    run = PumpStationWorldRun.resume_reference_system(repository=repository, snapshot=repository.current_snapshot())
    if not run.verify().valid:
        raise PumpStationPrimeJourneyRecoveryError("pump world canonical replay or verification failed")
    return run


def _shared_snapshot(snapshot: PumpStationStateSnapshotRef) -> StewardshipStateSnapshotRef:
    return StewardshipStateSnapshotRef(
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        sequence=snapshot.sequence,
        state_id=snapshot.state_id,
        commit_id=snapshot.commit_id,
    )


def _host_policy_sha256() -> str:
    source = getattr(pump_host, "__file__", None)
    if source is None:
        raise PumpStationPrimeJourneyRecoveryError("pump host continuation source is unavailable")
    return hashlib.sha256(Path(source).read_bytes()).hexdigest()


def _remove_closed_prime_runtime(actor_workspace: Path, runtime_directory: Path) -> None:
    expected_parent = actor_workspace / ".prime-runtimes"
    if runtime_directory.parent != expected_parent or runtime_directory.is_symlink():
        raise PumpStationPrimeJourneyRecoveryError("closed Prime runtime path is unsafe to remove")
    if not runtime_directory.exists():
        return
    try:
        shutil.rmtree(runtime_directory)
    except OSError as error:
        raise PumpStationPrimeJourneyRecoveryError("closed Prime runtime could not be removed") from error


def _paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents
