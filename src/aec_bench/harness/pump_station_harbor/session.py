# ABOUTME: Connects Harbor controllers to the registered pump-station episode host.
# ABOUTME: Keeps model transport outside world state, decisions, and transition order.

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, cast

from aec_bench.adapters.base import AdapterRequest, AdapterResult
from aec_bench.adapters.deepseek_harness.native_world_tools import (
    WORLD_OBSERVE_DESCRIPTION,
    WORLD_OBSERVE_TOOL_NAME,
    compile_world_native_tools,
    native_world_tool_surface_record,
)
from aec_bench.adapters.local_registry import build_local_adapter
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.task_definition import ToolSpec
from aec_bench.contracts.world_interface import WorldActorActionRequest, WorldActorCapabilityCatalogue
from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
    WorldSessionResult,
)
from aec_bench.harness.harbor_task_exporting.stable_io import directory_sha256
from aec_bench.harness.pump_station_harbor.export import (
    PUMP_STATION_HARBOR_EXECUTION_KIND,
    PumpStationHarborBridge,
    is_pump_station_harbor_inventory_artifact,
)
from aec_bench.harness.world_actor import (
    ActorCorrelation,
    ActorInvocationAuthority,
    ActorInvocationAuthorityConfig,
    AuthorityCloseReport,
)
from aec_bench.trajectory.writer import TrajectoryWriter
from aec_bench.worlds.stewardship.wastewater_pump_station.actor_interface import (
    PUMP_STATION_ACTOR_ACTION_NAMES,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.continual_rollout_adapter import (
    validate_pump_station_rollout_child_run,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationEpisodeHost,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.host_continuation import (
    PUMP_STATION_OPERATIONS_AUTHORITY_ID,
    PumpStationJourneyStatus,
    resolve_pump_station_host_continuation,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_controller import (
    PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
    run_pump_station_reference_controller,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationCoupledVerificationReport,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence import (
    TemporalEvidenceCapability,
    TemporalEvidenceRepository,
    TemporalEvidenceVerificationReport,
    verify_temporal_evidence_repository,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_control import PumpStationWorldControl
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import PumpStationWorldRun
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)

PUMP_STATION_MODEL_CONTROLLER_MODE = "model"
PUMP_STATION_MODEL_MAX_TURNS = 90
PUMP_STATION_MODEL_MAX_TOKENS = 8192
PUMP_STATION_MODEL_MAX_WORLD_ACTIONS = 90
_PUMP_STATION_MODEL_MAX_SEGMENTS = 8
_PUMP_STATION_TOOL_LOOP_TRANSPORT = "python-tool-loop"


@dataclass(frozen=True)
class CompletedPumpStationReferenceSession:
    """Result of one provider-free registered episode."""

    request: WorldSessionRequest
    result: WorldSessionResult
    verification: PumpStationCoupledVerificationReport
    output_dir: Path


@dataclass(frozen=True)
class CompletedPumpStationModelSession:
    """Result and adapter evidence from one model-controlled registered episode."""

    request: WorldSessionRequest
    result: WorldSessionResult
    verification: PumpStationCoupledVerificationReport
    adapter_result: AdapterResult
    output_dir: Path
    journey_status: PumpStationJourneyStatus
    stop_reason: str
    segment_count: int
    host_control_count: int


def _world_tool_specs(catalogue: WorldActorCapabilityCatalogue) -> tuple[ToolSpec, ...]:
    return (
        ToolSpec(name=WORLD_OBSERVE_TOOL_NAME, source="builtin", description=WORLD_OBSERVE_DESCRIPTION),
        *(
            ToolSpec(name=action.name, source="builtin", description=action.description)
            for action in sorted(catalogue.actions, key=lambda action: action.name)
        ),
    )


def _compile_tool_loop_world_tools(
    authority: ActorInvocationAuthority,
    catalogue: WorldActorCapabilityCatalogue,
) -> tuple[Any, ...]:
    """Compile the frozen catalogue into explicit PydanticAI tools."""
    from pydantic_ai import Tool

    def observe() -> str:
        observation = authority.observe(correlation=ActorCorrelation())
        return json.dumps(observation.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def action_handler(action_name: str) -> Callable[..., str]:
        def invoke(**arguments: Any) -> str:
            request_id = f"tool-loop:{uuid.uuid4().hex}"
            outcome = authority.invoke_current(
                request_id=request_id,
                action_name=action_name,
                arguments=arguments,
                transport=_PUMP_STATION_TOOL_LOOP_TRANSPORT,
                correlation=ActorCorrelation(transport_request_id=request_id),
            )
            return json.dumps(outcome.result.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

        return invoke

    tools: list[Any] = [
        Tool.from_schema(
            observe,
            name=WORLD_OBSERVE_TOOL_NAME,
            description=WORLD_OBSERVE_DESCRIPTION,
            json_schema={"type": "object", "properties": {}, "additionalProperties": False},
            sequential=True,
        )
    ]
    tools.extend(
        Tool.from_schema(
            action_handler(action.name),
            name=action.name,
            description=action.description,
            json_schema=action.input_schema,
            sequential=True,
        )
        for action in sorted(catalogue.actions, key=lambda action: action.name)
    )
    return tuple(tools)


def run_pump_station_reference_session(
    *,
    bridge: PumpStationHarborBridge,
    output_dir: Path,
    session_identity: str,
) -> CompletedPumpStationReferenceSession:
    """Execute the registered reference policy through the episode host."""
    _require_registered_bridge(bridge)
    identity = _require_identity(session_identity)
    destination = _create_destination(output_dir)
    repository_root = destination / "world-run"
    if bridge.rollout_child_ref is not None:
        start, end = _run_rollout_child_reference(bridge, repository_root, identity)
        controller_id = PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID
    else:
        controller = run_pump_station_reference_controller(
            repository_root=repository_root,
            run_id=f"run.{identity}",
            episode_id=f"episode.{identity}",
            world_branch_id=f"branch.{identity}",
        )
        start, end = controller.start_snapshot, controller.end_snapshot
        controller_id = controller.controller_id
    request, result = _episode_evidence(repository_root, identity, start, end)
    run = PumpStationWorldRun.resume_reference_system(
        repository=PumpStationWorldRunRepository(repository_root),
        snapshot=end,
    )
    verification = run.verify()
    if not verification.valid:
        raise ValueError("registered pump-station reference episode did not verify")
    temporal_verification = _verify_temporal(run)
    if not temporal_verification.valid:
        raise ValueError("registered pump-station temporal evidence did not verify")
    _write_session_evidence(destination, request, result, verification)
    _write_json(destination / "temporal-verification-report.json", temporal_verification.model_dump(mode="json"))
    _write_json(
        destination / "artifact-inventory.json",
        _artifact_inventory(
            bridge=bridge,
            output_dir=destination,
            controller_id=controller_id,
            start_snapshot=request.start_snapshot.model_dump(mode="json") if request.start_snapshot else {},
            end_snapshot=result.snapshot.model_dump(mode="json"),
            tool_names=result.tool_names,
        ),
    )
    return CompletedPumpStationReferenceSession(request, result, verification, destination)


def run_pump_station_model_session(
    *,
    bridge: PumpStationHarborBridge,
    output_dir: Path,
    session_identity: str,
    model: str,
    adapter_kind: str = "tool_loop",
    max_turns: int = PUMP_STATION_MODEL_MAX_TURNS,
    max_world_actions: int = PUMP_STATION_MODEL_MAX_WORLD_ACTIONS,
    max_tokens: int | None = None,
    timeout_sec: int | None = None,
    adapter_builder: Callable[..., Any] | None = None,
) -> CompletedPumpStationModelSession:
    """Let a model act through the registered actor boundary and persist accepted steps."""
    _require_registered_bridge(bridge)
    identity = _require_identity(session_identity)
    model_name = model.strip()
    if not model_name:
        raise ValueError("pump-station model episode requires a model")
    if adapter_kind not in {"deepseek_harness", "tool_loop"}:
        raise ValueError(f"unsupported pump-station model adapter: {adapter_kind}")
    if max_turns < 1:
        raise ValueError("pump-station model episode max turns must be positive")
    if isinstance(max_world_actions, bool) or max_world_actions < 1:
        raise ValueError("pump-station model episode world action budget must be positive")
    request_configuration: dict[str, int]
    if adapter_kind == "deepseek_harness":
        resolved_max_tokens = PUMP_STATION_MODEL_MAX_TOKENS if max_tokens is None else max_tokens
        request_configuration = {"max_tokens": resolved_max_tokens}
        if timeout_sec is not None:
            request_configuration["timeout_sec"] = timeout_sec
        for name, value in request_configuration.items():
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
    else:
        if max_tokens is not None:
            raise ValueError("max_tokens is supported only for deepseek_harness pump-station sessions")
        if timeout_sec is not None:
            raise ValueError("timeout_sec is supported only for deepseek_harness pump-station sessions")
        request_configuration = {"max_turns": max_turns}
    destination = _create_destination(output_dir)
    repository_root = destination / "world-run"
    request = _start_request(identity, bridge)
    host = PumpStationEpisodeHost(repository_root)
    if bridge.rollout_child_ref is not None:
        _copy_rollout_child_for_execution(bridge=bridge, repository_root=repository_root)
        start = PumpStationWorldRunRepository(repository_root).current_snapshot()
    else:
        started = host.open(request)
        start = _private_snapshot(started.snapshot)
    authority = ActorInvocationAuthority(
        host=host,
        config=ActorInvocationAuthorityConfig(
            authority_id=f"actor-authority.{identity}",
            actor_principal_id=f"actor.{identity}",
            max_world_actions=max_world_actions,
            evidence_path=destination / "actor-invocation-evidence.jsonl",
        ),
    )
    authority.start()
    trajectory = TrajectoryWriter(path=str(destination / "trajectory.jsonl"))
    adapter_results: list[AdapterResult] = []
    native_world_surface: dict[str, Any] | None = None
    host_control_count = 0
    journey_status = PumpStationJourneyStatus.ACTIVE
    stop_reason = "max-segments"
    authority_close_report: AuthorityCloseReport | None = None
    try:
        catalogue = authority.capabilities(correlation=ActorCorrelation())
        if tuple(action.name for action in catalogue.actions) != bridge.allowed_tools:
            raise ValueError("pump-station bridge tools differ from the frozen actor catalogue")
        tool_specs = _world_tool_specs(catalogue)
        resolved_builder = adapter_builder or build_local_adapter
        control = PumpStationWorldControl(
            repository_root,
            authorised_principal_ids=(PUMP_STATION_OPERATIONS_AUTHORITY_ID,),
        )
        for _segment_index in range(_PUMP_STATION_MODEL_MAX_SEGMENTS):
            if adapter_kind == "deepseek_harness":
                native_tool_definitions = compile_world_native_tools(authority=authority, catalogue=catalogue)
                segment_surface = native_world_tool_surface_record(
                    catalogue=catalogue,
                    definitions=native_tool_definitions,
                )
                if native_world_surface is None:
                    native_world_surface = segment_surface
                    _write_json(destination / "native-world-tool-surface.json", native_world_surface)
                elif (
                    segment_surface["public_tool_surface_sha256"] != native_world_surface["public_tool_surface_sha256"]
                ):
                    raise RuntimeError("DeepSeek native world tool surface changed between model segments")
                native_tools = None
            else:
                native_tool_definitions = None
                native_tools = _compile_tool_loop_world_tools(authority, catalogue)
            adapter = resolved_builder(
                adapter_kind=adapter_kind,
                model_name=model_name,
                workspace=str(destination),
                trajectory_writer=trajectory,
                native_tools=native_tools,
                native_tool_definitions=native_tool_definitions,
                enable_bash=False,
            )
            segment_result = adapter.execute(
                AdapterRequest(
                    instruction=_model_segment_instruction(),
                    system_prompt=(
                        "You are the accountable wastewater pump-station steward. Do not infer latent state, hidden "
                        "events, another branch, verifier expectations, or a prescribed action sequence."
                    ),
                    tools=list(tool_specs),
                    configuration=request_configuration,
                    output_path=str(destination / "output.md"),
                    output_format="markdown",
                )
            )
            adapter_results.append(segment_result)
            if segment_result.agent_output.status is not AgentOutputStatus.COMPLETED:
                stop_reason = f"adapter-{segment_result.agent_output.status.value}"
                break
            current = PumpStationWorldRun.resume_reference_system(
                repository=PumpStationWorldRunRepository(repository_root),
                snapshot=PumpStationWorldRunRepository(repository_root).current_snapshot(),
            )
            decision = resolve_pump_station_host_continuation(current)
            journey_status = decision.status
            stop_reason = decision.reason
            if decision.status is PumpStationJourneyStatus.COMPLETED:
                break
            if authority.world_action_limit_reached:
                stop_reason = "max-world-actions"
                break
            if decision.control_request is None or bridge.rollout_child_ref is not None:
                break
            control.execute(decision.control_request)
            host_control_count += 1
            current = PumpStationWorldRun.resume_reference_system(
                repository=PumpStationWorldRunRepository(repository_root),
                snapshot=PumpStationWorldRunRepository(repository_root).current_snapshot(),
            )
            journey_status = resolve_pump_station_host_continuation(current).status
            if journey_status is PumpStationJourneyStatus.COMPLETED:
                stop_reason = "declared-terminal-state"
                break
    finally:
        try:
            trajectory.close()
        finally:
            authority_close_report = authority.close()
    if not authority_close_report.complete:
        raise RuntimeError("pump-station actor invocation authority did not close completely")
    if not adapter_results:
        raise RuntimeError("pump-station model journey produced no adapter segment")
    adapter_result = _aggregate_adapter_results(
        adapter_results,
        journey_status=journey_status,
        stop_reason=stop_reason,
        host_control_count=host_control_count,
    )
    adapter_configuration = dict(adapter_result.configuration_record)
    adapter_configuration["actor_invocation_authority"] = {
        "authority_id": authority.authority_id,
        "actor_principal_id": authority.config.actor_principal_id,
        "catalogue_sha256": authority.catalogue_hash,
        "max_world_actions": authority.config.max_world_actions,
        "world_action_count": authority.world_action_count,
        "evidence_path": "actor-invocation-evidence.jsonl",
        "close": {
            "quiescent": authority_close_report.quiescent,
            "complete": authority_close_report.complete,
            "unsettled_request_ids": list(authority_close_report.unsettled_request_ids),
            "unknown_outcome_request_ids": list(authority_close_report.unknown_outcome_request_ids),
            "closed_at": authority_close_report.closed_at.isoformat(),
        },
    }
    if native_world_surface is not None:
        adapter_configuration["native_world_tools"] = {
            "catalogue_sha256": native_world_surface["catalogue_sha256"],
            "public_tool_surface_sha256": native_world_surface["public_tool_surface_sha256"],
            "evidence_path": "native-world-tool-surface.json",
            "presentation_mode": "deepseek-native",
        }
    adapter_result = replace(adapter_result, configuration_record=adapter_configuration)
    repository = PumpStationWorldRunRepository(repository_root)
    end = repository.current_snapshot()
    evidence_request, result = _episode_evidence(repository_root, identity, start, end)
    run = PumpStationWorldRun.resume_reference_system(repository=repository, snapshot=end)
    verification = run.verify()
    temporal_verification = _verify_temporal(run)
    _write_model_evidence(
        destination,
        adapter_result,
        model_name,
        adapter_kind=adapter_kind,
        request_configuration=request_configuration,
    )
    _write_session_evidence(destination, evidence_request, result, verification)
    _write_json(destination / "temporal-verification-report.json", temporal_verification.model_dump(mode="json"))
    _write_json(
        destination / "artifact-inventory.json",
        _artifact_inventory(
            bridge=bridge,
            output_dir=destination,
            controller_id=adapter_result.resolved_model,
            start_snapshot=evidence_request.start_snapshot.model_dump(mode="json")
            if evidence_request.start_snapshot
            else {},
            end_snapshot=result.snapshot.model_dump(mode="json"),
            tool_names=result.tool_names,
        ),
    )
    return CompletedPumpStationModelSession(
        evidence_request,
        result,
        verification,
        adapter_result,
        destination,
        journey_status,
        stop_reason,
        len(adapter_results),
        host_control_count,
    )


def _model_segment_instruction() -> str:
    return (
        "Observe the three-pump station. Use only current visible identifiers and the declared tools. "
        "Manage the station until the next host-authority boundary or the declared terminal state. After each action, "
        "use its next_observation or observe again. When work is active or the next decision is in the future, use "
        "continue_operation to advance to the next declared decision event. Do not stop only because one action was "
        "accepted. Retry visible unfinished work after conflicting work completes or resources become available. "
        "Continue while a visible process, backlog item, obligation, restriction, outage, or service requirement needs "
        "another supported action. Explain each reason in plain language, then stop with a short factual summary. "
        "Search documentary evidence only when it helps the current decision."
    )


def _aggregate_adapter_results(
    results: list[AdapterResult],
    *,
    journey_status: PumpStationJourneyStatus,
    stop_reason: str,
    host_control_count: int,
) -> AdapterResult:
    last = results[-1]
    complete = journey_status is PumpStationJourneyStatus.COMPLETED
    if complete:
        status = AgentOutputStatus.COMPLETED
    elif last.agent_output.status is AgentOutputStatus.COMPLETED:
        status = AgentOutputStatus.PARTIAL
    else:
        status = last.agent_output.status
    summaries = [result.raw_output_text for result in results if result.raw_output_text]
    configuration = dict(last.configuration_record)
    configuration.update(
        {
            "world_segment_count": len(results),
            "world_host_control_count": host_control_count,
            "world_journey_status": journey_status.value,
            "world_stop_reason": stop_reason,
        }
    )
    return replace(
        last,
        configuration_record=configuration,
        agent_output=last.agent_output.model_copy(update={"status": status}),
        turns_used=sum(result.turns_used or 0 for result in results),
        raw_output_text="\n\n".join(summaries),
        usage_model_calls=sum(result.usage_model_calls or 0 for result in results),
        usage_input_tokens=sum(result.usage_input_tokens or 0 for result in results),
        usage_output_tokens=sum(result.usage_output_tokens or 0 for result in results),
        usage_cache_read_tokens=sum(result.usage_cache_read_tokens or 0 for result in results),
        usage_cache_write_tokens=sum(result.usage_cache_write_tokens or 0 for result in results),
    )


def _require_registered_bridge(bridge: PumpStationHarborBridge) -> None:
    if bridge.profile_ref is None or bridge.reference_system_root is None:
        raise ValueError("obsolete pump-station Harbor export lacks a registered world profile")


def _require_identity(value: str) -> str:
    identity = value.strip()
    if not identity:
        raise ValueError("pump-station Harbor episode identity is required")
    return identity


def _create_destination(output_dir: Path) -> Path:
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError(f"episode output already exists: {destination}")
    destination.mkdir(parents=True)
    return destination


def _start_request(identity: str, bridge: PumpStationHarborBridge) -> WorldSessionRequest:
    child = bridge.rollout_child_ref
    return WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.RESUME if child is not None else WorldSessionOpenMode.START,
        session_id=f"episode.{identity}",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id=f"actor.{identity}",
        run_id=child.run_id if child is not None else f"run.{identity}",
        episode_id=child.episode_id if child is not None else f"episode.{identity}",
        world_branch_id=child.world_branch_id if child is not None else f"branch.{identity}",
        start_snapshot=(_shared_snapshot(child.initial_snapshot) if child is not None else None),
    )


def _episode_evidence(
    repository_root: Path,
    identity: str,
    start: Any,
    end: Any,
) -> tuple[WorldSessionRequest, WorldSessionResult]:
    request = WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.RESUME,
        session_id=f"episode.{identity}",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id=f"actor.{identity}",
        run_id=end.run_id,
        episode_id=end.episode_id,
        world_branch_id=end.world_branch_id,
        start_snapshot=_shared_snapshot(start),
    )
    current_request = request.model_copy(update={"start_snapshot": _shared_snapshot(end)})
    result = PumpStationEpisodeHost(repository_root).open(current_request)
    return request, result


def _run_rollout_child_reference(
    bridge: PumpStationHarborBridge,
    repository_root: Path,
    identity: str,
) -> tuple[Any, Any]:
    _copy_rollout_child_for_execution(bridge=bridge, repository_root=repository_root)
    repository = PumpStationWorldRunRepository(repository_root)
    start = repository.current_snapshot()
    host = PumpStationEpisodeHost(repository_root)
    observation = host.observe()
    host.invoke(
        WorldActorActionRequest(
            request_id=f"rollout-child-condition-check.{identity}",
            decision_id=observation.decision_id,
            action_name="request_condition_check",
            arguments={
                "reason": "Record one bounded condition check from the selected rollout point.",
                "pump_id": "pump-a",
            },
        )
    )
    return start, repository.current_snapshot()


def _copy_rollout_child_for_execution(*, bridge: PumpStationHarborBridge, repository_root: Path) -> None:
    source = bridge.initial_run_root
    child_ref = bridge.rollout_child_ref
    world_build = bridge.world_build
    profile_ref = bridge.profile_ref
    if source is None or child_ref is None or world_build is None or profile_ref is None:
        raise ValueError("pump-station Harbor rollout child authority is incomplete")
    validate_pump_station_rollout_child_run(
        source,
        child_ref,
        world_build=world_build,
        profile_ref=profile_ref,
    )
    expected_sha256 = directory_sha256(source)
    shutil.copytree(source, repository_root, symlinks=True)
    if directory_sha256(source) != expected_sha256 or directory_sha256(repository_root) != expected_sha256:
        raise ValueError("pump-station Harbor rollout child changed while it was copied")
    validate_pump_station_rollout_child_run(
        repository_root,
        child_ref,
        world_build=world_build,
        profile_ref=profile_ref,
    )


def _shared_snapshot(snapshot: Any) -> StewardshipStateSnapshotRef:
    return StewardshipStateSnapshotRef(
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        sequence=snapshot.sequence,
        state_id=snapshot.state_id,
        commit_id=snapshot.commit_id,
    )


def _private_snapshot(snapshot: StewardshipStateSnapshotRef) -> Any:
    from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_models import (
        PumpStationStateSnapshotRef,
    )

    return PumpStationStateSnapshotRef(
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        sequence=snapshot.sequence,
        state_id=snapshot.state_id,
        commit_id=snapshot.commit_id,
    )


def _verify_temporal(run: Any) -> TemporalEvidenceVerificationReport:
    actor_bindings = {
        step.command.request_id: (
            step.command.information_set_id or "",
            step.command.actor_view_id or "",
        )
        for step in run.repository.command_steps()
        if step.command.kind == "actor"
    }
    return verify_temporal_evidence_repository(
        TemporalEvidenceRepository(run.repository.root / "temporal-evidence"),
        package=run.package,
        actor_bindings=actor_bindings,
    )


def _artifact_inventory(
    *,
    bridge: PumpStationHarborBridge,
    output_dir: Path,
    controller_id: str,
    start_snapshot: dict[str, Any],
    end_snapshot: dict[str, Any],
    tool_names: tuple[str, ...] = PUMP_STATION_ACTOR_ACTION_NAMES,
) -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or not is_pump_station_harbor_inventory_artifact(output_dir, path):
            continue
        payload = path.read_bytes()
        artifacts.append(
            {
                "path": path.relative_to(output_dir).as_posix(),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            }
        )
    inventory: dict[str, Any] = {
        "execution_kind": PUMP_STATION_HARBOR_EXECUTION_KIND,
        "task_world_id": PUMP_STATION_TASK_WORLD_ID,
        "controller_id": controller_id,
        "export_manifest_sha256": bridge.export_manifest_sha256,
        "verifier_runtime_sha256": bridge.verifier_runtime_sha256,
        "package_content_id": bridge.package.package_content_id,
        "package_manifest_content_id": bridge.package.manifest_content_id,
        "tool_names": list(tool_names),
        "start_snapshot": start_snapshot,
        "end_snapshot": end_snapshot,
        "transition_count": end_snapshot["sequence"] - start_snapshot["sequence"],
        "artifacts": artifacts,
    }
    capability = TemporalEvidenceCapability.model_validate(
        _read_json(output_dir / "world-run" / "temporal-evidence" / "capability.json")
    )
    temporal_report = TemporalEvidenceVerificationReport.model_validate(
        _read_json(output_dir / "temporal-verification-report.json")
    )
    inventory["temporal_evidence"] = {
        "profile": capability.profile,
        "capability_id": capability.content_sha256,
        "corpus_snapshot_id": capability.corpus_snapshot_id,
        "retrieval_policy_id": capability.retrieval_policy_id,
        "access_policy_id": capability.access_policy_id,
        "availability_schedule_id": capability.availability_schedule_id,
        "branch_namespace_policy_id": capability.branch_namespace_policy_id,
        "cost_policy_id": capability.simulated_cost_policy_id,
        "access_count": temporal_report.access_count,
        "reliance_count": temporal_report.reliance_count,
        "carrier_count": temporal_report.carrier_count,
        "verification_report_id": temporal_report.content_sha256,
    }
    return inventory


def _write_model_evidence(
    destination: Path,
    adapter_result: AdapterResult,
    model: str,
    *,
    adapter_kind: str,
    request_configuration: dict[str, int],
) -> None:
    (destination / "output.md").write_text(adapter_result.raw_output_text or "", encoding="utf-8")
    _write_json(
        destination / "agent-result.json",
        {
            "status": adapter_result.agent_output.status.value,
            "model": model,
            "adapter": adapter_kind,
            "adapter_name": adapter_result.adapter_name,
            "resolved_model": adapter_result.resolved_model,
            "configuration_record": adapter_result.configuration_record,
            "limits": request_configuration,
            "turns_used": adapter_result.turns_used,
            "model_calls": adapter_result.usage_model_calls or 0,
            "input_tokens": adapter_result.usage_input_tokens or 0,
            "output_tokens": adapter_result.usage_output_tokens or 0,
            "cache_read_tokens": adapter_result.usage_cache_read_tokens or 0,
            "cache_write_tokens": adapter_result.usage_cache_write_tokens or 0,
            "failure_kind": None if adapter_result.failure_kind is None else adapter_result.failure_kind.value,
            "provider_error": adapter_result.provider_error,
        },
    )


def _write_session_evidence(
    destination: Path,
    request: WorldSessionRequest,
    result: WorldSessionResult,
    verification: PumpStationCoupledVerificationReport,
) -> None:
    _write_json(destination / "world-session-request.json", request.model_dump(mode="json"))
    _write_json(destination / "world-session-result.json", result.model_dump(mode="json"))
    _write_json(
        destination / "verification-report.json",
        cast(dict[str, Any], json.loads(json.dumps(asdict(verification)))),
    )


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)


__all__ = (
    "CompletedPumpStationModelSession",
    "CompletedPumpStationReferenceSession",
    "PUMP_STATION_MODEL_CONTROLLER_MODE",
    "PUMP_STATION_MODEL_MAX_TURNS",
    "PUMP_STATION_MODEL_MAX_TOKENS",
    "PUMP_STATION_MODEL_MAX_WORLD_ACTIONS",
    "run_pump_station_model_session",
    "run_pump_station_reference_session",
)
