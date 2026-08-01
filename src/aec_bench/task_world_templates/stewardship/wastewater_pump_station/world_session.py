# ABOUTME: Exposes the pump-station world as a direct host session with closed typed tools.
# ABOUTME: Composes durable runs, actor projections, information binding, actions, snapshots, and replay.

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from aec_bench.contracts.task_definition import ToolSpec
from aec_bench.contracts.world_interface import (
    WorldActorActionRequest,
    WorldActorActionResult,
    WorldActorBinding,
    WorldActorCapabilityCatalogue,
    WorldActorObservation,
    WorldInterfaceError,
)
from aec_bench.contracts.world_session import (
    STEWARDSHIP_STATE_SNAPSHOT_SCHEMA_VERSION,
    StewardshipStateSnapshotRef,
    WorldSessionOpenMode,
    WorldSessionRequest,
    WorldSessionResult,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.actor_interface import (
    pump_station_actor_capabilities,
    pump_station_proposal_from_actor_request,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_kernel import (
    advance_pump_station,
    initial_pump_station_state,
    pump_station_model_from_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    OperatingInterval,
    PumpStationEnvironment,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationProposal,
    PumpStationSchedule,
    PumpStationTransition,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_state_machine import (
    create_evidence_health_reference_state,
    create_rich_work_reference_state,
    create_stewardship_state,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationVerificationReport,
    verify_stewardship_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationActorHistoryEntry,
    PumpStationActorView,
    PumpStationContinuityCarrier,
    PumpStationCurrentContext,
    PumpStationInformationSet,
    PumpStationObservationHistory,
    PumpStationProjectionContext,
    PumpStationStructuredHandover,
    actor_history_entry,
    bind_information_set,
    project_actor_view,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PUMP_STATION_RECORD_VERSIONS_V1,
    PUMP_STATION_RECORD_VERSIONS_V2,
    PUMP_STATION_RECORD_VERSIONS_V3,
    PUMP_STATION_SNAPSHOT_VERSION,
    PumpStationStateSnapshotRef,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    pump_station_artifact_bytes,
)

PUMP_STATION_TASK_WORLD_ID = "wastewater-pump-station-stewardship.v1"
PUMP_STATION_PROJECTION_POLICY_ID = "pump-station-current-state.v1"
PUMP_STATION_REVIEW_RUNTIME_SECONDS = 7_200_000
PUMP_STATION_REVIEW_COMPLETED_STARTS = 1_000
PUMP_STATION_TOOL_NAMES = (
    "observe_pump_station",
    "continue_operation",
    "transfer_duty",
    "request_inspection",
    "request_conditional_deferral",
    "request_obstruction_clearance",
    "request_provisional_return",
    "request_provisional_closure",
    "request_post_maintenance_verification",
    "snapshot_pump_station",
)
PUMP_STATION_RICH_WORK_TOOL_NAMES = (
    *PUMP_STATION_TOOL_NAMES[:-1],
    "resume_process",
    "cancel_process",
    "request_dependency_waiver",
    PUMP_STATION_TOOL_NAMES[-1],
)
PUMP_STATION_EVIDENCE_HEALTH_TOOL_NAMES = (
    *PUMP_STATION_RICH_WORK_TOOL_NAMES[:-1],
    "request_condition_check",
    PUMP_STATION_RICH_WORK_TOOL_NAMES[-1],
)


def _snapshot_ref(snapshot: PumpStationStateSnapshotRef) -> StewardshipStateSnapshotRef:
    return StewardshipStateSnapshotRef(
        schema_version=STEWARDSHIP_STATE_SNAPSHOT_SCHEMA_VERSION,
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        sequence=snapshot.sequence,
        state_id=snapshot.state_id,
        commit_id=snapshot.commit_id,
    )


def _pump_station_snapshot(
    snapshot: StewardshipStateSnapshotRef,
    *,
    snapshot_version: str = PUMP_STATION_SNAPSHOT_VERSION,
) -> PumpStationStateSnapshotRef:
    return PumpStationStateSnapshotRef(
        snapshot_version=snapshot_version,
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        sequence=snapshot.sequence,
        state_id=snapshot.state_id,
        commit_id=snapshot.commit_id,
    )


def _artifact_payload(value: object) -> dict[str, Any]:
    payload = json.loads(pump_station_artifact_bytes(value))
    if not isinstance(payload, dict):
        raise TypeError("pump-station session artifact must serialize to an object")
    return payload


class PumpStationWorldSession:
    """One opened actor tenure over a continuing durable pump-station run."""

    def __init__(
        self,
        *,
        request: WorldSessionRequest,
        run: PumpStationWorldRun,
    ) -> None:
        self._request = request
        self._run = run
        self._evidence_health = run.manifest.snapshot_version.endswith(".v3")
        self._rich_work_processes = not run.manifest.snapshot_version.endswith(".v1")
        self._tool_names = (
            PUMP_STATION_EVIDENCE_HEALTH_TOOL_NAMES
            if self._evidence_health
            else PUMP_STATION_RICH_WORK_TOOL_NAMES
            if self._rich_work_processes
            else PUMP_STATION_TOOL_NAMES
        )
        self._actor_results: dict[
            str,
            tuple[WorldActorActionRequest, WorldActorActionResult],
        ] = {}
        state = run.state
        initial_state = run.repository.load_state(run.manifest.initial_state_id)
        episode_started_at_seconds = initial_state.physical.calendar_seconds
        tenure_started_at_seconds = (
            episode_started_at_seconds
            if request.open_mode is WorldSessionOpenMode.START
            else state.physical.calendar_seconds
        )
        self._projection_context = PumpStationProjectionContext(
            episode_id=request.episode_id,
            world_branch_id=request.world_branch_id,
            actor_id="station-steward",
            agent_tenure_id=request.agent_tenure_id,
            episode_started_at_seconds=episode_started_at_seconds,
            tenure_started_at_seconds=tenure_started_at_seconds,
            projection_policy_id=(
                "pump-station-current-state.v3"
                if self._evidence_health
                else "pump-station-current-state.v2"
                if self._rich_work_processes
                else PUMP_STATION_PROJECTION_POLICY_ID
            ),
            source_artifact_ids=(
                run.package.package_content_id,
                run.package.manifest_content_id,
            ),
        )
        self._current_context = PumpStationCurrentContext(
            continuity_carrier=PumpStationContinuityCarrier.CURRENT_ACTOR_VIEW,
            conversation_prefix_id=None,
            workspace_tool_ids=self._tool_names,
            visible_material_ids=(),
        )
        self._view = self._project()
        self._view_ids: tuple[str, ...] = (self._view.view_id,)
        self._information_set = self._bind_information_set()

    @property
    def result(self) -> WorldSessionResult:
        """Return the current shared host result without task-private state."""
        return WorldSessionResult(
            execution_kind=self._request.execution_kind,
            open_mode=self._request.open_mode,
            session_id=self._request.session_id,
            task_world_id=self._request.task_world_id,
            agent_tenure_id=self._request.agent_tenure_id,
            snapshot=_snapshot_ref(self._run.snapshot()),
            actor_view_id=self._view.view_id,
            information_set_id=self._information_set.information_set_id,
            tool_names=self._tool_names,
        )

    @property
    def tool_specs(self) -> tuple[ToolSpec, ...]:
        """Return the closed agent-visible tool catalogue."""
        return tuple(
            ToolSpec(
                name=name,
                source="builtin",
                description=getattr(self, name).__doc__ or name.replace("_", " "),
            )
            for name in self._tool_names
        )

    @property
    def actor_capabilities(self) -> WorldActorCapabilityCatalogue:
        """Return task-owned actions without host-control capabilities."""

        return pump_station_actor_capabilities(
            task_world_id=self._request.task_world_id,
            rich_work_processes=self._rich_work_processes,
            evidence_health=self._evidence_health,
        )

    @property
    def current_actor_binding(self) -> WorldActorBinding:
        """Return the exact public binding required by the next actor action."""

        result = self.result
        return WorldActorBinding(
            task_world_id=result.task_world_id,
            session_id=result.session_id,
            run_id=result.snapshot.run_id,
            episode_id=result.snapshot.episode_id,
            world_branch_id=result.snapshot.world_branch_id,
            sequence=result.snapshot.sequence,
            state_id=result.snapshot.state_id,
            commit_id=result.snapshot.commit_id,
            agent_tenure_id=result.agent_tenure_id,
            actor_view_id=result.actor_view_id,
            information_set_id=result.information_set_id,
        )

    def observe_actor(self) -> WorldActorObservation:
        """Return the current actor view with no latent or future world state."""

        return WorldActorObservation(
            binding=self.current_actor_binding,
            view=_artifact_payload(self._view),
        )

    def invoke_actor_action(
        self,
        request: WorldActorActionRequest,
    ) -> WorldActorActionResult:
        """Validate and apply one exact-bound task-owned actor action."""

        cached = self._actor_results.get(request.request_id)
        if cached is not None:
            cached_request, cached_result = cached
            if cached_request != request:
                raise WorldInterfaceError(
                    "actor-request-id-conflict",
                    f"{request.request_id} is already bound to different content",
                )
            return cached_result
        self._validate_actor_binding(request.binding)
        if request.action_name not in {item.name for item in self.actor_capabilities.actions}:
            raise WorldInterfaceError("actor-action-unavailable", request.action_name)
        proposal = pump_station_proposal_from_actor_request(request)
        transition = self._apply_proposal(proposal)
        observation = self.observe_actor()
        result = WorldActorActionResult(
            request_content_sha256=request.content_sha256,
            action_name=request.action_name,
            status=transition.receipt.execution.value,
            pre_binding=request.binding,
            post_binding=observation.binding,
            task_receipt=_artifact_payload(transition.receipt),
            next_observation=observation,
        )
        self._actor_results[request.request_id] = (request, result)
        return result

    @property
    def actor_view(self) -> PumpStationActorView:
        """Return the exact host-side actor view used by this tenure."""

        return self._view

    @property
    def run(self) -> PumpStationWorldRun:
        """Return the durable run used by the host session."""
        return self._run

    @property
    def actor_history(self) -> tuple[PumpStationActorHistoryEntry, ...]:
        """Return bounded-source entries reconstructed from durable proposals."""

        return tuple(
            actor_history_entry(step.transition, step.proposal)
            for step in self._run.steps()
            if step.proposal is not None
        )

    @property
    def event_schedule_sha256(self) -> str:
        """Return a commitment to the hidden remaining event schedule."""

        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
            stewardship_content_id,
        )

        return stewardship_content_id(self._run.state.scheduled_events)

    def install_structured_handover(
        self,
        handover: PumpStationStructuredHandover,
    ) -> None:
        """Bind one host-created handover before the fresh tenure acts."""

        if self._request.open_mode is not WorldSessionOpenMode.RESUME:
            raise ValueError("structured handover requires a resumed fresh tenure")
        if len(self._view_ids) != 1:
            raise ValueError("structured handover must be installed before the tenure acts")
        if self._current_context.continuity_carrier is not PumpStationContinuityCarrier.CURRENT_ACTOR_VIEW:
            raise ValueError("continuity material is already installed")
        if handover.to_tenure_id != self._request.agent_tenure_id:
            raise ValueError("structured handover belongs to another recipient tenure")
        if handover.current_actor_view != self._view:
            raise ValueError("structured handover current view differs from the live session")
        self._current_context = PumpStationCurrentContext(
            continuity_carrier=PumpStationContinuityCarrier.STRUCTURED_HANDOVER,
            conversation_prefix_id=None,
            workspace_tool_ids=self._tool_names,
            visible_material_ids=(handover.handover_id,),
        )
        self._information_set = self._bind_information_set()

    @property
    def native_tools(self) -> tuple[Callable[..., str], ...]:
        """Return the bound native functions in the declared tool order."""
        return tuple(getattr(self, name) for name in self._tool_names)

    def observe_pump_station(self) -> str:
        """Read the complete current actor view without latent or future state."""
        return json.dumps(
            self.observe_actor().view,
            sort_keys=True,
            separators=(",", ":"),
        )

    def continue_operation(self, proposal_id: str, reason: str) -> str:
        """Continue the permitted operating mode to the next declared decision event."""
        return self._invoke_actor_tool(
            proposal_id,
            "continue_operation",
            {"reason": reason},
        )

    def transfer_duty(self, proposal_id: str, reason: str) -> str:
        """Request the one permitted transfer from duty to standby pump."""
        return self._invoke_actor_tool(
            proposal_id,
            "transfer_duty",
            {"reason": reason},
        )

    def request_inspection(self, proposal_id: str, reason: str, pump_id: str) -> str:
        """Request a scheduled inspection of one named pump."""
        return self._invoke_actor_tool(
            proposal_id,
            "request_inspection",
            {"reason": reason, "pump_id": pump_id},
        )

    def request_condition_check(
        self,
        proposal_id: str,
        reason: str,
        pump_id: str,
    ) -> str:
        """Request one sensor-based condition check for a named pump."""
        return self._invoke_actor_tool(
            proposal_id,
            "request_condition_check",
            {"reason": reason, "pump_id": pump_id},
        )

    def request_conditional_deferral(self, proposal_id: str, reason: str, pump_id: str) -> str:
        """Request the fixed transfer-then-isolate conditional deferral."""
        return self._invoke_actor_tool(
            proposal_id,
            "request_conditional_deferral",
            {"reason": reason, "pump_id": pump_id},
        )

    def request_obstruction_clearance(
        self,
        proposal_id: str,
        reason: str,
        pump_id: str,
        inspection_evidence_id: str,
    ) -> str:
        """Request obstruction clearance against named inspection evidence."""
        return self._invoke_actor_tool(
            proposal_id,
            "request_obstruction_clearance",
            {
                "reason": reason,
                "pump_id": pump_id,
                "inspection_evidence_id": inspection_evidence_id,
            },
        )

    def request_provisional_return(
        self,
        proposal_id: str,
        reason: str,
        pump_id: str,
        functional_check_evidence_id: str,
    ) -> str:
        """Request provisional return against accepted functional-check evidence."""
        return self._invoke_actor_tool(
            proposal_id,
            "request_provisional_return",
            {
                "reason": reason,
                "pump_id": pump_id,
                "functional_check_evidence_id": functional_check_evidence_id,
            },
        )

    def request_provisional_closure(
        self,
        proposal_id: str,
        reason: str,
        work_order_id: str,
    ) -> str:
        """Request administrative closure while verification duties remain open."""
        return self._invoke_actor_tool(
            proposal_id,
            "request_provisional_closure",
            {"reason": reason, "work_order_id": work_order_id},
        )

    def request_post_maintenance_verification(
        self,
        proposal_id: str,
        reason: str,
        pump_id: str,
    ) -> str:
        """Request independent post-maintenance verification for one pump."""
        return self._invoke_actor_tool(
            proposal_id,
            "request_post_maintenance_verification",
            {"reason": reason, "pump_id": pump_id},
        )

    def resume_process(
        self,
        proposal_id: str,
        reason: str,
        process_id: str,
    ) -> str:
        """Resume blocked or suspended work after dependency and resource checks."""
        return self._invoke_actor_tool(
            proposal_id,
            "resume_process",
            {"reason": reason, "process_id": process_id},
        )

    def cancel_process(
        self,
        proposal_id: str,
        reason: str,
        process_id: str,
    ) -> str:
        """Cancel live work and release its unused reservations."""
        return self._invoke_actor_tool(
            proposal_id,
            "cancel_process",
            {"reason": reason, "process_id": process_id},
        )

    def request_dependency_waiver(
        self,
        proposal_id: str,
        reason: str,
        process_id: str,
        dependency_id: str,
        evidence_id: str,
    ) -> str:
        """Request a narrow administrative closeout waiver with named evidence."""
        return self._invoke_actor_tool(
            proposal_id,
            "request_dependency_waiver",
            {
                "reason": reason,
                "process_id": process_id,
                "dependency_id": dependency_id,
                "evidence_id": evidence_id,
            },
        )

    def snapshot_pump_station(self) -> str:
        """Read the exact current dynamic snapshot reference."""
        return self.result.snapshot.model_dump_json()

    def verify(self) -> PumpStationVerificationReport:
        """Replay the durable transition chain through the independent task verifier."""
        initial_state = self._run.repository.load_state(
            self._run.manifest.initial_state_id,
        )
        return verify_stewardship_run(
            self._run.model,
            initial_state,
            self._run.steps(),
        )

    def _validate_actor_binding(self, binding: WorldActorBinding) -> None:
        current = self.current_actor_binding
        if (
            binding.task_world_id,
            binding.session_id,
            binding.run_id,
            binding.episode_id,
            binding.world_branch_id,
        ) != (
            current.task_world_id,
            current.session_id,
            current.run_id,
            current.episode_id,
            current.world_branch_id,
        ):
            raise WorldInterfaceError(
                "actor-wrong-world",
                "actor request belongs to another session or world",
            )
        if binding.agent_tenure_id != current.agent_tenure_id:
            raise WorldInterfaceError(
                "actor-wrong-tenure",
                "actor request belongs to another tenure",
            )
        if binding.sequence != current.sequence:
            raise WorldInterfaceError(
                "actor-stale-sequence",
                "actor request does not use the current sequence",
            )
        if binding.information_set_id != current.information_set_id:
            raise WorldInterfaceError(
                "actor-wrong-information-set",
                "actor request uses another information set",
            )
        if binding.actor_view_id != current.actor_view_id:
            raise WorldInterfaceError(
                "actor-stale-view",
                "actor request does not use the current view",
            )
        if (binding.state_id, binding.commit_id) != (current.state_id, current.commit_id):
            raise WorldInterfaceError(
                "actor-stale-snapshot",
                "actor request does not use the current snapshot",
            )

    def _invoke_actor_tool(
        self,
        request_id: str,
        action_name: str,
        arguments: dict[str, Any],
    ) -> str:
        result = self.invoke_actor_action(
            WorldActorActionRequest(
                request_id=request_id,
                action_name=action_name,
                binding=self.current_actor_binding,
                arguments=arguments,
            )
        )
        return json.dumps(
            {
                "status": result.status,
                "snapshot": self.result.snapshot.model_dump(mode="json"),
                "receipt": result.task_receipt,
                "view": result.next_observation.view,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def _apply_proposal(self, proposal: PumpStationProposal) -> PumpStationTransition:
        transition = self._run.apply(
            proposal,
            information_set=self._information_set,
        )
        self._refresh_projection()
        return transition

    def _project(self) -> PumpStationActorView:
        return project_actor_view(
            self._run.model,
            self._run.state,
            self._projection_context,
        )

    def _bind_information_set(self) -> PumpStationInformationSet:
        return bind_information_set(
            self._view,
            PumpStationObservationHistory(
                agent_tenure_id=self._request.agent_tenure_id,
                view_ids=self._view_ids,
            ),
            self._current_context,
        )

    def _refresh_projection(self) -> None:
        self._view = self._project()
        self._view_ids = (*self._view_ids, self._view.view_id)
        self._information_set = self._bind_information_set()


class PumpStationWorldSessionFactory:
    """Create or resume pump-station sessions from one host-supplied repository."""

    task_world_id = PUMP_STATION_TASK_WORLD_ID

    def __init__(
        self,
        repository_root: Path,
        *,
        package_root: Path | None = None,
        schedule: PumpStationSchedule | None = None,
        rich_work_processes: bool = False,
        evidence_health: bool = False,
    ) -> None:
        self._repository = PumpStationWorldRunRepository(repository_root)
        self._package_root = package_root
        self._schedule = schedule
        self._evidence_health = evidence_health
        self._rich_work_processes = rich_work_processes or evidence_health

    def open(self, request: WorldSessionRequest) -> PumpStationWorldSession:
        """Open a new or exact resumed session for the requested actor tenure."""
        if request.task_world_id != self.task_world_id:
            raise ValueError("world-session request belongs to another task world")
        package = load_reference_package(self._package_root)
        model = pump_station_model_from_package(package)
        if request.open_mode is WorldSessionOpenMode.START:
            if self._evidence_health:
                state = create_evidence_health_reference_state(
                    model,
                    schedule=self._schedule,
                )
            elif self._rich_work_processes:
                state = create_rich_work_reference_state(
                    model,
                    schedule=self._schedule,
                )
            else:
                environment = PumpStationEnvironment(
                    inflow_m3_s=model.inflow.assessment_m3_s,
                    wet_well_level_m=model.wet_well.start_level_m,
                    isolated=False,
                )
                physical = advance_pump_station(
                    model,
                    initial_pump_station_state(model),
                    OperatingInterval(
                        elapsed_seconds=PUMP_STATION_REVIEW_RUNTIME_SECONDS,
                        duty_runtime_seconds=PUMP_STATION_REVIEW_RUNTIME_SECONDS,
                        duty_completed_starts=PUMP_STATION_REVIEW_COMPLETED_STARTS,
                        environment=environment,
                    ),
                ).state
                state = create_stewardship_state(
                    model,
                    physical,
                    environment,
                    schedule=self._schedule,
                )
            run = PumpStationWorldRun.create(
                repository=self._repository,
                package=package,
                model=model,
                initial_state=state,
                run_id=request.run_id,
                episode_id=request.episode_id,
                world_branch_id=request.world_branch_id,
                record_versions=(
                    PUMP_STATION_RECORD_VERSIONS_V3
                    if self._evidence_health
                    else PUMP_STATION_RECORD_VERSIONS_V2
                    if self._rich_work_processes
                    else PUMP_STATION_RECORD_VERSIONS_V1
                ),
            )
        else:
            if request.start_snapshot is None:
                raise ValueError("resume request has no start snapshot")
            run = PumpStationWorldRun.resume(
                repository=self._repository,
                package=package,
                model=model,
                snapshot=_pump_station_snapshot(
                    request.start_snapshot,
                    snapshot_version=self._repository.load_manifest().snapshot_version,
                ),
            )
        return PumpStationWorldSession(request=request, run=run)
