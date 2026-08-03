# ABOUTME: Dispatches separate actor and host-control requests through the continual-world catalogue.
# ABOUTME: Keeps task state and task-specific control decoding inside each registered execution port.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aec_bench.contracts.continual_world import (
    ContinualWorldActorRequest,
    ContinualWorldControlRequest,
)
from aec_bench.task_world_templates.continual.actor_session import (
    invoke_world_actor,
    observe_world_actor,
)
from aec_bench.task_world_templates.continual.catalogue import ContinualWorldCatalogue
from aec_bench.task_world_templates.continual.definition import (
    ContinualWorldDefinition,
    LoadedContinualWorldProfile,
)
from aec_bench.task_world_templates.continual.rollout_control import ContinualRolloutControl


@dataclass(frozen=True, slots=True)
class ContinualWorldInterfaceContext:
    """Host-owned roots, catalogue, and authorities for one installed call."""

    catalogue: ContinualWorldCatalogue
    run_root: Path
    rollout_repository_root: Path | None
    authorised_principal_ids: tuple[str, ...]
    package_root: Path | None = None

    def __post_init__(self) -> None:
        if any(not principal.strip() for principal in self.authorised_principal_ids):
            raise ValueError("continual interface host principals must not be empty")
        if len(self.authorised_principal_ids) != len(set(self.authorised_principal_ids)):
            raise ValueError("continual interface host principals must be distinct")


def _resolve(
    context: ContinualWorldInterfaceContext,
    request: ContinualWorldActorRequest | ContinualWorldControlRequest,
) -> tuple[ContinualWorldDefinition, LoadedContinualWorldProfile]:
    definition = context.catalogue.resolve(request.definition_ref)
    loaded = definition.load_profile(request.profile_ref)
    return definition, loaded


def dispatch_continual_actor(
    *,
    context: ContinualWorldInterfaceContext,
    request: ContinualWorldActorRequest,
) -> object:
    """Execute one actor call after exact definition and profile resolution."""

    definition, loaded = _resolve(context, request)
    port = definition.execution_port
    if port is None:
        raise ValueError(f"continual world has no registered execution port: {definition.ref.task_world_id}")
    session = port.open_actor_session(
        profile=loaded,
        run_root=context.run_root,
        package_root=context.package_root,
        request=request.session_request,
    )
    if request.operation == "capabilities":
        return session.actor_capabilities
    if request.operation == "observe":
        return observe_world_actor(session)
    assert request.action_request is not None
    return invoke_world_actor(session, request.action_request)


def dispatch_continual_control(
    *,
    context: ContinualWorldInterfaceContext,
    request: ContinualWorldControlRequest,
) -> object:
    """Execute one host-control or rollout call through its registered owner."""

    definition, loaded = _resolve(context, request)
    if request.authority_id not in context.authorised_principal_ids:
        raise ValueError("continual interface control authority is not authorised")
    if request.operation == "capabilities":
        port = definition.execution_port
        if port is None:
            raise ValueError(f"continual world has no registered execution port: {definition.ref.task_world_id}")
        return port.control_capabilities(
            profile=loaded,
            run_root=context.run_root,
            package_root=context.package_root,
            authorised_principal_ids=context.authorised_principal_ids,
            authority_id=request.authority_id,
        )
    if request.operation == "execute":
        port = definition.execution_port
        if port is None:
            raise ValueError(f"continual world has no registered execution port: {definition.ref.task_world_id}")
        assert request.control_request is not None
        return port.execute_control(
            profile=loaded,
            run_root=context.run_root,
            package_root=context.package_root,
            authorised_principal_ids=context.authorised_principal_ids,
            request_payload=request.control_request,
        )
    rollout_root = context.rollout_repository_root
    if rollout_root is None:
        raise ValueError("continual rollout control requires a host-private repository root")
    rollout = ContinualRolloutControl(
        definition,
        parent_run_root=context.run_root,
        rollout_repository_root=rollout_root,
        authorised_principal_ids=context.authorised_principal_ids,
        package_root=context.package_root,
    )
    if request.operation == "create_rollout_group":
        assert request.rollout_group_request is not None
        return rollout.create_group(request.rollout_group_request)
    assert request.group_id is not None
    if request.operation == "rollout_group_status":
        return rollout.group_status(request.group_id)
    if request.operation == "inspect_rollout_group":
        return rollout.inspect_group(request.group_id)
    assert request.child_id is not None
    return rollout.child_run_ref(request.group_id, request.child_id)
