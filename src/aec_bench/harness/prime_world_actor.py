# ABOUTME: Runs one Prime provider session against a provider-neutral Interactive World actor host.
# ABOUTME: Owns shared client, authority, endpoint, process, close, usage, and retained session evidence.

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import cast

from aec_bench.contracts.authority_evidence import AuthorityEvidenceRef
from aec_bench.contracts.world_interface import WorldActorActionResult
from aec_bench.harness.world_actor import (
    ActorInvocationAuthority,
    ActorInvocationAuthorityConfig,
    WorldActorEndpoint,
    WorldActorHost,
    install_world_actor_client,
)
from aec_bench.prime_agent.acp import PrimeAcpIsolation, PrimeAcpRun, run_prime_acp_session
from aec_bench.prime_agent.refinement import PrimeRefinementCandidate, PrimeRefinementMode
from aec_bench.prime_agent.session_evidence import PrimeAcpLimits
from aec_bench.prime_agent.skills import install_aec_world_skill
from aec_bench.trials import PlannedTrial


@dataclass(frozen=True, slots=True)
class WorldActorSession:
    """Normalized provider and actor-authority evidence for one closed session."""

    prime: PrimeAcpRun
    actor_transport_file: Path
    actor_authority_file: Path
    actor_authority_evidence: AuthorityEvidenceRef | None
    world_actor_client_sha256: str
    world_action_count: int
    world_action_limit_reached: bool
    last_action_result: WorldActorActionResult | None
    close_complete: bool


async def run_prime_world_actor_session(
    *,
    host: WorldActorHost,
    trial: PlannedTrial,
    instruction: str,
    actor_workspace: Path,
    evidence_directory: Path,
    skills: Sequence[Path] = (),
    private_paths: Sequence[Path] = (),
) -> WorldActorSession:
    """Run one Prime actor session from the complete planned-trial configuration."""

    if trial.agent.adapter != "prime-agent":
        raise ValueError(f"Prime world actor requires adapter 'prime-agent', got {trial.agent.adapter!r}")
    parameters = trial.agent.parameters
    limits = _limits(parameters)
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
    executable = str(parameters.get("executable", "prime-agent"))
    environment_value = parameters.get("environment")
    environment = _string_mapping(environment_value, name="environment")
    runtime_value = parameters.get("prime_runtime_directory")
    runtime_directory = None if runtime_value is None else Path(str(runtime_value))

    actor_workspace = actor_workspace.resolve()
    evidence_directory = evidence_directory.resolve()
    if _paths_overlap(actor_workspace, evidence_directory) or any(
        _paths_overlap(actor_workspace, path) for path in private_paths
    ):
        raise ValueError("actor workspace must be separate from host-private paths")
    actor_workspace.mkdir(parents=True, exist_ok=True)
    evidence_directory.mkdir(parents=True, exist_ok=False)
    installed_client = install_world_actor_client(actor_workspace)
    skill_directories = (install_aec_world_skill(actor_workspace), *skills)
    actor_transport_file = evidence_directory / "world-actor-transport.jsonl"
    actor_authority_file = evidence_directory / "world-actor-authority.jsonl"
    authority = ActorInvocationAuthority(
        host=host,
        config=ActorInvocationAuthorityConfig(
            actor_principal_id="actor.prime-process-composite",
            max_world_actions=int(cast(str | int, _required(parameters, "max_world_actions"))),
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
            skill_directories=skill_directories,
            instruction=instruction,
            model=trial.agent.model,
            actor_environment=endpoint.connection_environment(),
            scoped_socket=endpoint.socket_path,
            isolation=isolation,
            limits=limits,
            runtime_directory=runtime_directory,
            private_paths=tuple(Path(path).resolve() for path in private_paths),
            refinement_mode=refinement_mode,
            refinement_candidate=refinement_candidate,
            executable=executable,
            environment=environment,
        )
        last_action_result = endpoint.last_action_result
        world_action_count = endpoint.world_action_count
        world_action_limit_reached = endpoint.world_action_limit_reached
    close_report = endpoint.close()
    return WorldActorSession(
        prime=prime,
        actor_transport_file=actor_transport_file,
        actor_authority_file=actor_authority_file,
        actor_authority_evidence=close_report.authority.evidence_ref,
        world_actor_client_sha256=installed_client.content_sha256,
        world_action_count=world_action_count,
        world_action_limit_reached=world_action_limit_reached,
        last_action_result=last_action_result,
        close_complete=close_report.complete,
    )


def _limits(parameters: Mapping[str, object]) -> PrimeAcpLimits:
    return PrimeAcpLimits(
        max_model_calls=int(cast(str | int, _required(parameters, "max_model_calls"))),
        max_tokens=int(cast(str | int, _required(parameters, "max_tokens"))),
        max_cost_usd=Decimal(str(_required(parameters, "max_cost_usd"))),
        max_wall_seconds=float(cast(str | int | float, _required(parameters, "max_wall_seconds"))),
    )


def _required(parameters: Mapping[str, object], name: str) -> object:
    try:
        return parameters[name]
    except KeyError as error:
        raise ValueError(f"Prime world actor configuration requires {name}") from error


def _string_mapping(value: object, *, name: str) -> Mapping[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) or not isinstance(item, str) for key, item in value.items()
    ):
        raise ValueError(f"Prime world actor {name} must map strings to strings")
    return value


def _paths_overlap(first: Path, second: Path) -> bool:
    first = first.resolve()
    second = second.resolve()
    return first == second or first in second.parents or second in first.parents


__all__ = ("WorldActorSession", "run_prime_world_actor_session")
