# ABOUTME: Connects Harbor controllers to the registered pump-station episode host.
# ABOUTME: Keeps model transport outside world state, decisions, and transition order.

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

from pydantic import JsonValue

from aec_bench.adapters.base import AdapterRequest, AdapterResult
from aec_bench.adapters.local_registry import build_local_adapter
from aec_bench.contracts.task_definition import ToolSpec
from aec_bench.contracts.world_interface import WorldActorActionRequest
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
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import PumpStationWorldRun
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)

PUMP_STATION_MODEL_CONTROLLER_MODE = "model"
PUMP_STATION_MODEL_MAX_TURNS = 90


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


class _PumpStationActorTools:
    """Translate provider-native tool calls into the one installed actor boundary."""

    def __init__(self, host: PumpStationEpisodeHost) -> None:
        self._host = host

    @property
    def tool_specs(self) -> tuple[ToolSpec, ...]:
        methods = self.native_tools
        return tuple(
            ToolSpec(
                name=method.__name__,
                source="builtin",
                description=method.__doc__ or method.__name__.replace("_", " "),
            )
            for method in methods
        )

    @property
    def native_tools(self) -> tuple[Callable[..., str], ...]:
        return (
            self.observe_pump_station,
            self.continue_operation,
            self.request_duty_assignment,
            self.request_inspection,
            self.request_obstruction_clearance,
            self.request_functional_check,
            self.request_provisional_return,
            self.request_provisional_closure,
            self.request_post_maintenance_verification,
            self.resume_process,
            self.cancel_process,
            self.request_dependency_waiver,
            self.request_condition_check,
            self.search_evidence,
            self.fetch_evidence,
        )

    def observe_pump_station(self) -> str:
        """Read the complete current actor view without latent or future state."""
        return json.dumps(self._host.observe().model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def _invoke(self, request_id: str, action_name: str, arguments: dict[str, JsonValue]) -> str:
        observation = self._host.observe()
        result = self._host.invoke(
            WorldActorActionRequest(
                request_id=request_id,
                decision_id=observation.decision_id,
                action_name=action_name,
                arguments=arguments,
            )
        )
        return json.dumps(result.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def continue_operation(self, request_id: str, reason: str) -> str:
        """Continue the permitted operating mode to the next declared decision event."""
        return self._invoke(request_id, "continue_operation", {"reason": reason})

    def request_duty_assignment(
        self,
        request_id: str,
        reason: str,
        ordered_pump_ids: tuple[str, ...],
        source_outage_id: str | None = None,
        source_backlog_item_id: str | None = None,
    ) -> str:
        """Request an ordered assignment of eligible pumps to declared service."""
        arguments: dict[str, JsonValue] = {
            "reason": reason,
            "ordered_pump_ids": list(ordered_pump_ids),
        }
        if source_outage_id is not None:
            arguments["source_outage_id"] = source_outage_id
        if source_backlog_item_id is not None:
            arguments["source_backlog_item_id"] = source_backlog_item_id
        return self._invoke(request_id, "request_duty_assignment", arguments)

    def request_inspection(self, request_id: str, reason: str, pump_id: str, backlog_item_id: str) -> str:
        """Request a scheduled inspection of one named pump."""
        return self._invoke(
            request_id,
            "request_inspection",
            {"reason": reason, "pump_id": pump_id, "backlog_item_id": backlog_item_id},
        )

    def request_obstruction_clearance(
        self,
        request_id: str,
        reason: str,
        pump_id: str,
        backlog_item_id: str,
        inspection_evidence_id: str,
    ) -> str:
        """Request clearance against named inspection evidence."""
        return self._invoke(
            request_id,
            "request_obstruction_clearance",
            {
                "reason": reason,
                "pump_id": pump_id,
                "backlog_item_id": backlog_item_id,
                "inspection_evidence_id": inspection_evidence_id,
            },
        )

    def request_functional_check(self, request_id: str, reason: str, pump_id: str, backlog_item_id: str) -> str:
        """Request one controlled functional check for a named pump."""
        return self._invoke(
            request_id,
            "request_functional_check",
            {"reason": reason, "pump_id": pump_id, "backlog_item_id": backlog_item_id},
        )

    def request_provisional_return(
        self,
        request_id: str,
        reason: str,
        pump_id: str,
        functional_check_evidence_id: str,
    ) -> str:
        """Request return against accepted functional-check evidence."""
        return self._invoke(
            request_id,
            "request_provisional_return",
            {
                "reason": reason,
                "pump_id": pump_id,
                "functional_check_evidence_id": functional_check_evidence_id,
            },
        )

    def request_provisional_closure(self, request_id: str, reason: str, work_order_id: str) -> str:
        """Request administrative closure while operational duties remain open."""
        return self._invoke(
            request_id,
            "request_provisional_closure",
            {"reason": reason, "work_order_id": work_order_id},
        )

    def request_post_maintenance_verification(
        self,
        request_id: str,
        reason: str,
        pump_id: str,
        backlog_item_id: str,
    ) -> str:
        """Request independent post-maintenance verification."""
        return self._invoke(
            request_id,
            "request_post_maintenance_verification",
            {"reason": reason, "pump_id": pump_id, "backlog_item_id": backlog_item_id},
        )

    def resume_process(self, request_id: str, reason: str, process_id: str) -> str:
        """Resume blocked or suspended work after dependency checks."""
        return self._invoke(request_id, "resume_process", {"reason": reason, "process_id": process_id})

    def cancel_process(self, request_id: str, reason: str, process_id: str) -> str:
        """Cancel live work and release unused reservations."""
        return self._invoke(request_id, "cancel_process", {"reason": reason, "process_id": process_id})

    def request_dependency_waiver(
        self,
        request_id: str,
        reason: str,
        process_id: str,
        dependency_id: str,
        evidence_id: str,
    ) -> str:
        """Request one narrow dependency waiver with named evidence."""
        return self._invoke(
            request_id,
            "request_dependency_waiver",
            {
                "reason": reason,
                "process_id": process_id,
                "dependency_id": dependency_id,
                "evidence_id": evidence_id,
            },
        )

    def request_condition_check(self, request_id: str, reason: str, pump_id: str) -> str:
        """Request one sensor-based condition check for a named pump."""
        return self._invoke(
            request_id,
            "request_condition_check",
            {"reason": reason, "pump_id": pump_id},
        )

    def search_evidence(self, request_id: str, query: str, scope: str = "all", limit: int = 5) -> str:
        """Search the documentary evidence available to this actor now."""
        return self._invoke(
            request_id,
            "search_evidence",
            {"query": query, "scope": scope, "limit": limit},
        )

    def fetch_evidence(self, request_id: str, reference: str) -> str:
        """Fetch content through an opaque reference from an earlier search."""
        return self._invoke(request_id, "fetch_evidence", {"reference": reference})


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
    max_turns: int = PUMP_STATION_MODEL_MAX_TURNS,
    adapter_builder: Callable[..., Any] | None = None,
) -> CompletedPumpStationModelSession:
    """Let a model act through the registered actor boundary and persist accepted steps."""
    _require_registered_bridge(bridge)
    identity = _require_identity(session_identity)
    model_name = model.strip()
    if not model_name:
        raise ValueError("pump-station model episode requires a model")
    if max_turns < 1:
        raise ValueError("pump-station model episode max turns must be positive")
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
    tools = _PumpStationActorTools(host)
    trajectory = TrajectoryWriter(path=str(destination / "trajectory.jsonl"))
    try:
        resolved_builder = adapter_builder or build_local_adapter
        adapter = resolved_builder(
            adapter_kind="tool_loop",
            model_name=model_name,
            workspace=str(destination),
            trajectory_writer=trajectory,
            native_tools=tools.native_tools,
            enable_bash=False,
        )
        adapter_result = adapter.execute(
            AdapterRequest(
                instruction=(
                    "Observe the three-pump station. Use only current visible identifiers and the declared tools. "
                    "Take supported stewardship actions, explain each reason in plain language, and stop with a "
                    "short factual summary. Search documentary evidence only when it helps the current decision."
                ),
                system_prompt=(
                    "You are the accountable wastewater pump-station steward. Do not infer latent state, hidden "
                    "events, another branch, verifier expectations, or a prescribed action sequence."
                ),
                tools=list(tools.tool_specs),
                configuration={"max_turns": max_turns},
                output_path=str(destination / "output.md"),
                output_format="markdown",
            )
        )
    finally:
        trajectory.close()
    repository = PumpStationWorldRunRepository(repository_root)
    end = repository.current_snapshot()
    evidence_request, result = _episode_evidence(repository_root, identity, start, end)
    run = PumpStationWorldRun.resume_reference_system(repository=repository, snapshot=end)
    verification = run.verify()
    temporal_verification = _verify_temporal(run)
    _write_model_evidence(destination, adapter_result, model_name, max_turns)
    _write_session_evidence(destination, evidence_request, result, verification)
    _write_json(destination / "temporal-verification-report.json", temporal_verification.model_dump(mode="json"))
    _write_json(
        destination / "artifact-inventory.json",
        _artifact_inventory(
            bridge=bridge,
            output_dir=destination,
            controller_id=model_name,
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
    max_turns: int,
) -> None:
    (destination / "output.md").write_text(adapter_result.raw_output_text or "", encoding="utf-8")
    _write_json(
        destination / "agent-result.json",
        {
            "status": adapter_result.agent_output.status.value,
            "model": model,
            "adapter": "tool_loop",
            "adapter_name": adapter_result.adapter_name,
            "resolved_model": adapter_result.resolved_model,
            "configuration_record": adapter_result.configuration_record,
            "max_turns": max_turns,
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
    "run_pump_station_model_session",
    "run_pump_station_reference_session",
)
