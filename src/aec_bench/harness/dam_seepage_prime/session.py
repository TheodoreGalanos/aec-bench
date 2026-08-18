# ABOUTME: Runs one bounded Prime session against the dam seepage monitoring world.
# ABOUTME: Keeps Prime evidence, world replay, and task evaluation as separate results.

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import cast

from pydantic import JsonValue, TypeAdapter

from aec_bench.contracts.authority_evidence import AuthorityEvidenceRef
from aec_bench.contracts.interactive_world import InteractiveWorldProfileRef, WorldBuildRef
from aec_bench.harness.world_actor import (
    ActorInvocationAuthority,
    ActorInvocationAuthorityConfig,
    WorldActorEndpoint,
    install_world_actor_client,
)
from aec_bench.prime_agent.acp import PrimeAcpIsolation, PrimeAcpRun, run_prime_acp_session
from aec_bench.prime_agent.session_evidence import PrimeAcpLimits
from aec_bench.prime_agent.skills import (
    ACTOR_LEDGER_PLAN_INSTRUCTION,
    install_actor_ledger_plan_skills,
    install_aec_world_skill,
)
from aec_bench.worlds.monitoring.dam_seepage.definition import (
    DamSeepageProfile,
    dam_seepage_world_definition,
)
from aec_bench.worlds.monitoring.dam_seepage.episode_runtime import DamSeepageEpisodeHost
from aec_bench.worlds.monitoring.dam_seepage.world import (
    SeepageEvaluation,
    evaluate,
    transition,
)
from aec_bench.worlds.runtime.episode import EpisodeStatus
from aec_bench.worlds.runtime.world_logic import ActionRejected

_EVALUATION_ADAPTER = TypeAdapter(SeepageEvaluation)


class DamSeepagePrimeSessionError(RuntimeError):
    """Raised when one dam seepage Prime session has unsafe paths."""


@dataclass(frozen=True, slots=True)
class DamSeepagePrimeSessionLimits:
    """Host limits for one Prime and dam seepage session."""

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
class DamSeepagePrimeSessionRun:
    """Separate Prime process, world episode, replay, and evaluation outcomes."""

    prime: PrimeAcpRun
    world_build: WorldBuildRef
    profile_ref: InteractiveWorldProfileRef
    world_state: str
    completion: str
    evaluation: SeepageEvaluation
    replay_valid: bool
    actor_transport_file: Path
    actor_authority_file: Path
    actor_authority_evidence: AuthorityEvidenceRef | None
    run_file: Path
    world_actor_client_sha256: str
    world_action_count: int
    world_action_limit_reached: bool
    benchmark_valid: bool


async def run_dam_seepage_prime_session(
    *,
    actor_workspace: Path,
    evidence_directory: Path,
    profile_ref: InteractiveWorldProfileRef,
    instruction: str,
    model: str,
    isolation: PrimeAcpIsolation,
    limits: DamSeepagePrimeSessionLimits,
    prime_runtime_directory: Path | None = None,
    additional_private_paths: Sequence[Path] = (),
    actor_ledger_plan: bool = False,
    executable: str = "prime-agent",
    environment: Mapping[str, str] | None = None,
) -> DamSeepagePrimeSessionRun:
    """Run one Prime session against one exact dam seepage profile."""
    actor_workspace = actor_workspace.resolve()
    evidence_directory = evidence_directory.resolve()
    if _paths_overlap(actor_workspace, evidence_directory):
        raise DamSeepagePrimeSessionError("actor workspace must be separate from host evidence")

    definition = dam_seepage_world_definition()
    loaded = definition.load_profile(profile_ref)
    if not isinstance(loaded.value, DamSeepageProfile):
        raise TypeError("dam seepage profile loader returned another task value")
    profile = loaded.value

    actor_workspace.mkdir(parents=True, exist_ok=True)
    evidence_directory.mkdir(parents=True, exist_ok=False)
    installed_client = install_world_actor_client(actor_workspace)
    skill_directories = [install_aec_world_skill(actor_workspace)]
    prime_instruction = instruction
    if actor_ledger_plan:
        skill_directories.extend(install_actor_ledger_plan_skills(actor_workspace, executable=executable))
        prime_instruction = instruction.rstrip() + "\n\n" + ACTOR_LEDGER_PLAN_INSTRUCTION + "\n"

    host = DamSeepageEpisodeHost(profile=profile)
    actor_transport_file = evidence_directory / "world-actor-transport.jsonl"
    actor_authority_file = evidence_directory / "world-actor-authority.jsonl"
    authority = ActorInvocationAuthority(
        host=host,
        config=ActorInvocationAuthorityConfig(
            actor_principal_id="actor.prime-process-composite",
            max_world_actions=limits.max_world_actions,
            evidence_path=actor_authority_file,
        ),
    )
    endpoint = WorldActorEndpoint(
        authority=authority,
        socket_directory=actor_workspace / ".actor",
        evidence_file=actor_transport_file,
    )
    with endpoint:
        prime = await run_prime_acp_session(
            actor_workspace=actor_workspace,
            evidence_directory=evidence_directory,
            skill_directories=tuple(skill_directories),
            instruction=prime_instruction,
            model=model,
            actor_environment=endpoint.connection_environment(),
            scoped_socket=endpoint.socket_path,
            isolation=isolation,
            limits=limits.acp_limits(),
            runtime_directory=prime_runtime_directory,
            private_paths=(evidence_directory, *additional_private_paths),
            executable=executable,
            environment=environment,
        )
        world_action_count = endpoint.world_action_count
        world_action_limit_reached = endpoint.world_action_limit_reached
    close_report = endpoint.close()
    actor_authority_evidence = close_report.authority.evidence_ref

    evaluation = evaluate(host.state)
    replay_valid = _replay_valid(profile=profile, host=host, evaluation=evaluation)
    world_state = _world_state(host.status)
    completion = _completion(prime=prime, world_state=world_state, replay_valid=replay_valid)
    benchmark_valid = prime.benchmark_valid and replay_valid and close_report.complete
    evaluation_payload = _EVALUATION_ADAPTER.dump_python(evaluation, mode="json")
    if not isinstance(evaluation_payload, dict):
        raise RuntimeError("dam seepage evaluation did not serialize to an object")
    run_file = evidence_directory / "prime-dam-seepage-run.json"
    run_file.write_text(
        json.dumps(
            {
                "world_build": asdict(definition.build),
                "profile": asdict(profile_ref),
                "treatment": "planned" if actor_ledger_plan else "open",
                "limits": {
                    "max_world_actions": limits.max_world_actions,
                    "max_model_calls": limits.max_model_calls,
                    "max_tokens": limits.max_tokens,
                    "max_cost_usd": str(limits.max_cost_usd),
                    "max_wall_seconds": limits.max_wall_seconds,
                },
                "actions": [step.action.value for step in host.recorder.steps],
                "world_actor_client_sha256": installed_client.content_sha256,
                "world_action_count": world_action_count,
                "world_action_limit_reached": world_action_limit_reached,
                "world_actor_close_complete": close_report.complete,
                "actor_authority_evidence": (
                    None if actor_authority_evidence is None else actor_authority_evidence.model_dump(mode="json")
                ),
                "prime_session_state": prime.session_state,
                "prime_limit_reason": prime.limit_reason,
                "world_state": world_state,
                "completion": completion,
                "evaluation": cast(dict[str, JsonValue], evaluation_payload),
                "replay_valid": replay_valid,
                "benchmark_valid": benchmark_valid,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return DamSeepagePrimeSessionRun(
        prime=prime,
        world_build=definition.build,
        profile_ref=profile_ref,
        world_state=world_state,
        completion=completion,
        evaluation=evaluation,
        replay_valid=replay_valid,
        actor_transport_file=actor_transport_file,
        actor_authority_file=actor_authority_file,
        actor_authority_evidence=actor_authority_evidence,
        run_file=run_file,
        world_actor_client_sha256=installed_client.content_sha256,
        world_action_count=world_action_count,
        world_action_limit_reached=world_action_limit_reached,
        benchmark_valid=benchmark_valid,
    )


def _replay_valid(
    *,
    profile: DamSeepageProfile,
    host: DamSeepageEpisodeHost,
    evaluation: SeepageEvaluation,
) -> bool:
    state = profile.opening_state
    for recorded in host.recorder.steps:
        result = transition(state, recorded.action)
        if isinstance(result, ActionRejected) or result.state != recorded.next_state:
            return False
        state = result.state
    return state == host.state and evaluate(state) == evaluation


def _world_state(status: EpisodeStatus) -> str:
    if status is EpisodeStatus.TERMINATED:
        return "completed"
    return status.value


def _completion(*, prime: PrimeAcpRun, world_state: str, replay_valid: bool) -> str:
    if prime.session_state == "failed" or not replay_valid:
        return "failed"
    if prime.session_state == "cancelled":
        return "interrupted"
    if world_state == "completed":
        return "completed"
    if world_state == "truncated":
        return "truncated"
    return "incomplete"


def _paths_overlap(first: Path, second: Path) -> bool:
    first = first.resolve()
    second = second.resolve()
    return first == second or first in second.parents or second in first.parents
