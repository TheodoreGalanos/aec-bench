# ABOUTME: Composes one isolated Prime session with one host-owned pump-station episode.
# ABOUTME: Keeps Prime protocol code separate from pump-world execution and evaluation policy.

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from aec_bench.contracts.authority_evidence import AuthorityEvidenceRef
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.world_session import WorldSessionRequest, WorldSessionResult
from aec_bench.harness.prime_world_actor import run_prime_world_actor_session
from aec_bench.harness.world_trials import WorldActorSessionRunner
from aec_bench.prime_agent.acp import PrimeAcpIsolation, PrimeAcpRun
from aec_bench.prime_agent.refinement import PrimeRefinementCandidate, PrimeRefinementMode
from aec_bench.prime_agent.session_evidence import PrimeAcpLimits
from aec_bench.prime_agent.skills import (
    ACTOR_LEDGER_PLAN_INSTRUCTION,
    install_actor_ledger_plan_skills,
    install_prime_refine_skill,
    install_prime_skill,
)
from aec_bench.trials import PlannedTrial
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import PumpStationEpisodeHost
from aec_bench.worlds.stewardship.wastewater_pump_station.evaluation import (
    evaluate_pump_station_reference_run,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)

if TYPE_CHECKING:
    from aec_bench.contracts.evaluation_result import StewardshipEvaluation
    from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_verifier import (
        PumpStationCoupledVerificationReport,
    )

PUMP_STATION_GUIDANCE_INSTRUCTION = (
    "Before your first world action, load and follow the full `pump-station-guidance` skill. "
    "Keep its compact state and exact action ledger throughout the episode. "
    "Use its references when they help the current decision."
)


class PumpStationPrimeSessionError(RuntimeError):
    """Raised when one pump-station Prime session has unsafe paths."""


@dataclass(frozen=True, slots=True)
class PumpStationPrimeSessionLimits:
    """Host limits for one composed Prime and pump-world session."""

    max_world_actions: int
    max_model_calls: int
    max_tokens: int
    max_cost_usd: Decimal
    max_wall_seconds: float

    def __post_init__(self) -> None:
        if self.max_world_actions < 1:
            raise ValueError("Prime world max_world_actions must be positive")
        self.acp_limits()

    def acp_limits(self) -> PrimeAcpLimits:
        return PrimeAcpLimits(
            max_model_calls=self.max_model_calls,
            max_tokens=self.max_tokens,
            max_cost_usd=self.max_cost_usd,
            max_wall_seconds=self.max_wall_seconds,
        )


@dataclass(frozen=True, slots=True)
class PumpStationPrimeSessionRun:
    """Separate Prime-session and canonical pump-world outcomes."""

    prime: PrimeAcpRun
    world_session: WorldSessionResult
    world_state: str
    completion: str
    verification: PumpStationCoupledVerificationReport
    evaluation: StewardshipEvaluation
    actor_transport_file: Path
    actor_authority_file: Path
    actor_authority_evidence: AuthorityEvidenceRef | None
    run_file: Path
    world_actor_client_sha256: str
    world_action_count: int
    world_action_limit_reached: bool
    benchmark_valid: bool


def install_pump_station_guidance_skill(actor_workspace: Path) -> Path:
    """Install the explicit pump guidance in one isolated actor workspace."""
    source = Path(__file__).with_name("skills") / "pump-station-guidance"
    return install_prime_skill(actor_workspace, source)


async def run_pump_station_prime_session(
    *,
    actor_workspace: Path,
    world_run_directory: Path,
    evidence_directory: Path,
    session_request: WorldSessionRequest,
    instruction: str,
    model: str,
    isolation: PrimeAcpIsolation,
    limits: PumpStationPrimeSessionLimits,
    prime_runtime_directory: Path | None = None,
    additional_private_paths: Sequence[Path] = (),
    pump_station_guidance: bool = False,
    actor_ledger_plan: bool = False,
    refinement_mode: PrimeRefinementMode = PrimeRefinementMode.CAPTURE,
    refinement_candidate: PrimeRefinementCandidate | None = None,
    executable: str = "prime-agent",
    environment: Mapping[str, str] | None = None,
    planned_trial: PlannedTrial | None = None,
    actor: WorldActorSessionRunner = run_prime_world_actor_session,
) -> PumpStationPrimeSessionRun:
    """Run Prime against one scoped pump actor without changing the world runtime."""
    if pump_station_guidance and actor_ledger_plan:
        raise ValueError("Prime pump treatment must be open, guided, or planned")
    actor_workspace = actor_workspace.resolve()
    world_run_directory = world_run_directory.resolve()
    evidence_directory = evidence_directory.resolve()
    if _paths_overlap(actor_workspace, world_run_directory) or _paths_overlap(actor_workspace, evidence_directory):
        raise PumpStationPrimeSessionError("actor workspace must be separate from host world and evidence paths")
    actor_workspace.mkdir(parents=True, exist_ok=True)
    skill_directories: list[Path] = []
    if refinement_mode is PrimeRefinementMode.DISCOVER:
        skill_directories.append(install_prime_refine_skill(actor_workspace))
    prime_instruction = instruction
    if pump_station_guidance:
        skill_directories.append(install_pump_station_guidance_skill(actor_workspace))
        prime_instruction = instruction.rstrip() + "\n\n" + PUMP_STATION_GUIDANCE_INSTRUCTION + "\n"
    elif actor_ledger_plan:
        skill_directories.extend(install_actor_ledger_plan_skills(actor_workspace, executable=executable))
        prime_instruction = instruction.rstrip() + "\n\n" + ACTOR_LEDGER_PLAN_INSTRUCTION + "\n"
    host = PumpStationEpisodeHost(world_run_directory)
    world_session = host.open(session_request)
    session_trial = planned_trial or PlannedTrial(
        trial_id="pump-station-prime-session",
        experiment_id="pump-station-prime-session",
        task_id=session_request.task_world_id,
        agent=AgentConfig(
            name="prime-agent",
            adapter="prime-agent",
            model=model,
            parameters={
                "isolation": isolation.value,
                "max_world_actions": limits.max_world_actions,
                "max_model_calls": limits.max_model_calls,
                "max_tokens": limits.max_tokens,
                "max_cost_usd": str(limits.max_cost_usd),
                "max_wall_seconds": limits.max_wall_seconds,
                "prime_runtime_directory": prime_runtime_directory,
                "refinement_mode": refinement_mode.value,
                "refinement_candidate": refinement_candidate,
                "executable": executable,
                "environment": environment,
            },
        ),
        compute=ComputeConfig(backend="local"),
        repetition=1,
    )
    if session_trial.agent.model != model or session_trial.agent.adapter != "prime-agent":
        raise ValueError("planned Prime world trial differs from the pump session configuration")
    if planned_trial is not None:
        session_trial = replace(
            planned_trial,
            agent=planned_trial.agent.model_copy(
                update={
                    "parameters": {
                        **planned_trial.agent.parameters,
                        "isolation": isolation.value,
                        "max_world_actions": limits.max_world_actions,
                        "max_model_calls": limits.max_model_calls,
                        "max_tokens": limits.max_tokens,
                        "max_cost_usd": str(limits.max_cost_usd),
                        "max_wall_seconds": limits.max_wall_seconds,
                        "prime_runtime_directory": prime_runtime_directory,
                        "refinement_mode": refinement_mode.value,
                        "refinement_candidate": refinement_candidate,
                        "executable": executable,
                        "environment": environment,
                    }
                }
            ),
        )
    session = await actor(
        host=host,
        trial=session_trial,
        instruction=prime_instruction,
        actor_workspace=actor_workspace,
        evidence_directory=evidence_directory,
        skills=skill_directories,
        private_paths=(world_run_directory, evidence_directory, *additional_private_paths),
    )
    prime = session.prime
    last_action = session.last_action_result
    world_action_count = session.world_action_count
    world_action_limit_reached = session.world_action_limit_reached
    actor_authority_evidence = session.actor_authority_evidence

    repository = PumpStationWorldRunRepository(world_run_directory)
    run = PumpStationWorldRun.resume_reference_system(
        repository=repository,
        snapshot=repository.current_snapshot(),
    )
    verification = run.verify()
    # One Prime session can make only actor-authorised progress. Operations
    # reviews remain outside this capability and require host continuation.
    evaluation = evaluate_pump_station_reference_run(run, evaluation_scope="bounded_continuation")
    if not verification.valid:
        world_state = "failed"
    elif last_action is not None and last_action.terminated:
        world_state = "completed"
    elif last_action is not None and last_action.truncated:
        world_state = "truncated"
    else:
        world_state = "active"
    if prime.session_state == "failed" or world_state == "failed":
        completion = "failed"
    elif prime.session_state == "cancelled":
        completion = "interrupted"
    elif world_state == "completed":
        completion = "completed"
    elif world_state == "truncated":
        completion = "truncated"
    else:
        completion = "incomplete"
    benchmark_valid = prime.benchmark_valid and verification.valid and session.close_complete
    run_file = evidence_directory / "prime-world-run.json"
    run_file.write_text(
        json.dumps(
            {
                "schema": "aecbench.prime-world-run.v1",
                "limits": {
                    "max_world_actions": limits.max_world_actions,
                    "max_model_calls": limits.max_model_calls,
                    "max_tokens": limits.max_tokens,
                    "max_cost_usd": str(limits.max_cost_usd),
                    "max_wall_seconds": limits.max_wall_seconds,
                },
                "world_actor_client_sha256": session.world_actor_client_sha256,
                "world_action_count": world_action_count,
                "world_action_limit_reached": world_action_limit_reached,
                "world_actor_close_complete": session.close_complete,
                "actor_authority_evidence": (
                    None if actor_authority_evidence is None else actor_authority_evidence.model_dump(mode="json")
                ),
                "prime_session_state": prime.session_state,
                "prime_limit_reason": prime.limit_reason,
                "world_state": world_state,
                "completion": completion,
                "evaluation_scope": evaluation.evaluation_scope,
                "evaluation_valid": evaluation.valid,
                "benchmark_valid": benchmark_valid,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return PumpStationPrimeSessionRun(
        prime=prime,
        world_session=world_session,
        world_state=world_state,
        completion=completion,
        verification=verification,
        evaluation=evaluation,
        actor_transport_file=session.actor_transport_file,
        actor_authority_file=session.actor_authority_file,
        actor_authority_evidence=actor_authority_evidence,
        run_file=run_file,
        world_actor_client_sha256=session.world_actor_client_sha256,
        world_action_count=world_action_count,
        world_action_limit_reached=world_action_limit_reached,
        benchmark_valid=benchmark_valid,
    )


def _paths_overlap(first: Path, second: Path) -> bool:
    first = first.resolve()
    second = second.resolve()
    return first == second or first in second.parents or second in first.parents
