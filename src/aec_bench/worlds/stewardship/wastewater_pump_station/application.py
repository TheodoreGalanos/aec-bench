# ABOUTME: Provides application functions for installed pump actor, control, verification, and evaluation calls.
# ABOUTME: Keeps Typer argument parsing and output outside task-owned world orchestration.

from __future__ import annotations

from pathlib import Path

from pydantic import TypeAdapter

from aec_bench.contracts.continual_world import (
    ContinualControlExecuteRequest,
    ContinualRolloutCreateRequest,
    ContinualRolloutGroupQuery,
    ContinualRolloutGroupRequest,
    ContinualWorldActorRequest,
    ContinualWorldControlRequest,
)
from aec_bench.contracts.world_interface import WorldActorActionRequest, WorldControlRequest
from aec_bench.worlds import branch_world
from aec_bench.worlds import task as world_task
from aec_bench.worlds.runtime.rollout_control import ContinualRolloutControl
from aec_bench.worlds.stewardship.wastewater_pump_station.continual_definition import (
    pump_station_continual_world_definition,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.continual_rollout_adapter import (
    PumpStationContinualWorldBranchPort,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import PumpStationEpisodeHost
from aec_bench.worlds.stewardship.wastewater_pump_station.evaluation import evaluate_pump_station_reference_run
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_models import PumpStationBoundControlRequest
from aec_bench.worlds.stewardship.wastewater_pump_station.world_control import PumpStationWorldControl
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import PumpStationWorldRun
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import PumpStationWorldRunRepository


def invoke_actor_request(run_dir: Path, request: ContinualWorldActorRequest) -> object:
    repository = PumpStationWorldRunRepository(run_dir)
    PumpStationWorldRun.resume_reference_system(repository=repository, snapshot=repository.current_snapshot())
    host = PumpStationEpisodeHost(run_dir)
    if request.operation == "capabilities":
        return host.capabilities()
    if request.operation == "observe":
        return host.observe()
    assert request.request_id is not None
    assert request.decision_id is not None
    assert request.action_name is not None
    assert request.arguments is not None
    return host.invoke(
        WorldActorActionRequest(
            request_id=request.request_id,
            decision_id=request.decision_id,
            action_name=request.action_name,
            arguments=request.arguments,
        )
    )


def invoke_control_request(
    run_dir: Path,
    request: ContinualWorldControlRequest,
    *,
    host_authority_id: str,
    rollout_dir: Path | None = None,
) -> object:
    request_authority_id = (
        request.rollout_group_request.authority_id
        if isinstance(request, ContinualRolloutCreateRequest)
        else request.authority_id
    )
    if request_authority_id != host_authority_id:
        raise ValueError("control authority differs from the host authority")
    repository = PumpStationWorldRunRepository(run_dir)
    run = PumpStationWorldRun.resume_reference_system(repository=repository, snapshot=repository.current_snapshot())
    definition = pump_station_continual_world_definition()
    if definition.build != run.world_build:
        raise ValueError("world build does not match the installed pump-station world")
    definition.load_profile(run.continual_profile_ref)
    if request.operation in {"capabilities", "execute"}:
        control = PumpStationWorldControl(
            run_dir,
            authorised_principal_ids=(host_authority_id,),
            profile_ref=run.continual_profile_ref,
        )
        if request.operation == "capabilities":
            return control.capabilities(request_authority_id)
        assert isinstance(request, ContinualControlExecuteRequest)
        parsed: WorldControlRequest | PumpStationBoundControlRequest = TypeAdapter(
            WorldControlRequest | PumpStationBoundControlRequest
        ).validate_python(request.control_request)
        return control.execute(parsed)
    if rollout_dir is None:
        raise ValueError("rollout operations require a rollout directory")
    rollout = ContinualRolloutControl(
        definition,
        PumpStationContinualWorldBranchPort(),
        parent_run_root=run_dir,
        rollout_repository_root=rollout_dir,
        authorised_principal_ids=(host_authority_id,),
    )
    if request.operation == "create_rollout_group":
        assert isinstance(request, ContinualRolloutCreateRequest)
        return rollout.create_group(request.rollout_group_request)
    assert isinstance(request, ContinualRolloutGroupQuery) or request.operation == "rollout_child_run_ref"
    if request.operation == "rollout_group_status":
        return rollout.group_status(request.group_id)
    if request.operation == "inspect_rollout_group":
        return rollout.inspect_group(request.group_id)
    assert request.child_id is not None
    return rollout.child_run_ref(request.group_id, request.child_id)


def verify_run(run_dir: Path) -> object:
    repository = PumpStationWorldRunRepository(run_dir)
    return PumpStationWorldRun.resume_reference_system(
        repository=repository,
        snapshot=repository.current_snapshot(),
    ).verify()


def evaluate_run(run_dir: Path) -> object:
    repository = PumpStationWorldRunRepository(run_dir)
    run = PumpStationWorldRun.resume_reference_system(repository=repository, snapshot=repository.current_snapshot())
    return evaluate_pump_station_reference_run(run)


def branch_run(run_dir: Path, rollout_dir: Path, request: ContinualRolloutGroupRequest) -> object:
    repository = PumpStationWorldRunRepository(run_dir)
    parent = PumpStationWorldRun.resume_reference_system(repository=repository, snapshot=repository.current_snapshot())
    task = world_task(
        request.task_world_id,
        profile=request.profile_ref.profile_id,
        instruction=request.reason,
    )
    return branch_world(
        task=task,
        parent=parent,
        branches=request.children,
        rollout_root=rollout_dir,
        authority_id=request.authority_id,
        request_id=request.request_id,
        group_id=request.group_id,
        reason=request.reason,
    )


__all__ = ("branch_run", "evaluate_run", "invoke_actor_request", "invoke_control_request", "verify_run")
