# ABOUTME: Exposes the pump-station world as a direct host session with closed typed tools.
# ABOUTME: Composes durable runs, actor projections, information binding, actions, snapshots, and replay.

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

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
    TemporalEvidenceFetchArguments,
    TemporalEvidenceSearchArguments,
    pump_station_actor_capabilities,
    pump_station_evidence_reliance_refs,
    pump_station_proposal_from_actor_request,
    pump_station_request_without_evidence_reliance,
    pump_station_temporal_access_arguments,
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
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence import (
    RetrievalBudgetVector,
    TemporalAccessContext,
    TemporalAccessPublication,
    TemporalActorVisibleEvent,
    TemporalEvidenceAccessKind,
    TemporalEvidenceGateway,
    TemporalEvidenceIntegrityError,
    TemporalEvidenceRelianceRecord,
    TemporalEvidenceRepository,
    TemporalEvidenceVerificationReport,
    TemporalInformationSetManifest,
    TemporalRetrievalState,
    TemporalRetrievalStateCarrier,
    build_reference_temporal_evidence_bundle,
    temporal_actor_event_id,
    verify_temporal_evidence_repository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.time_presentation import (
    PUMP_STATION_TIME_PROJECTION_POLICY_ID,
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
PUMP_STATION_TEMPORAL_EVIDENCE_TOOL_NAMES = (
    *PUMP_STATION_EVIDENCE_HEALTH_TOOL_NAMES[:-1],
    "search_evidence",
    "fetch_evidence",
    PUMP_STATION_EVIDENCE_HEALTH_TOOL_NAMES[-1],
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
    payload = (
        json.loads(value.model_dump_json())
        if isinstance(value, BaseModel)
        else json.loads(pump_station_artifact_bytes(value))
    )
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
        temporal_repository: TemporalEvidenceRepository | None = None,
        temporal_gateway: TemporalEvidenceGateway | None = None,
    ) -> None:
        self._request = request
        self._run = run
        self._temporal_repository = temporal_repository
        self._temporal_gateway = temporal_gateway
        self._temporal_evidence = temporal_repository is not None
        if self._temporal_evidence != (temporal_gateway is not None):
            raise ValueError("temporal repository and gateway must be supplied together")
        self._evidence_health = run.manifest.snapshot_version.endswith(".v3")
        self._rich_work_processes = not run.manifest.snapshot_version.endswith(".v1")
        self._tool_names = (
            PUMP_STATION_TEMPORAL_EVIDENCE_TOOL_NAMES
            if self._temporal_evidence
            else PUMP_STATION_EVIDENCE_HEALTH_TOOL_NAMES
            if self._evidence_health
            else PUMP_STATION_RICH_WORK_TOOL_NAMES
            if self._rich_work_processes
            else PUMP_STATION_TOOL_NAMES
        )
        self._actor_results: dict[
            str,
            tuple[WorldActorActionRequest, WorldActorActionResult],
        ] = {}
        stored_information_set = (
            temporal_repository.load_current_information_set_for_session(
                run_id=request.run_id,
                session_id=request.session_id,
                agent_tenure_id=request.agent_tenure_id,
            )
            if temporal_repository is not None
            else None
        )
        state = run.state
        initial_state = run.repository.load_state(run.manifest.initial_state_id)
        episode_started_at_seconds = initial_state.physical.calendar_seconds
        tenure_started_at_seconds = (
            stored_information_set.tenure_started_at_seconds
            if stored_information_set is not None
            else (
                episode_started_at_seconds
                if request.open_mode is WorldSessionOpenMode.START
                else state.physical.calendar_seconds
            )
        )
        self._projection_context = PumpStationProjectionContext(
            episode_id=request.episode_id,
            world_branch_id=request.world_branch_id,
            actor_id="station-steward",
            agent_tenure_id=request.agent_tenure_id,
            episode_started_at_seconds=episode_started_at_seconds,
            tenure_started_at_seconds=tenure_started_at_seconds,
            projection_policy_id=(
                PUMP_STATION_TIME_PROJECTION_POLICY_ID
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
        if self._temporal_repository is not None:
            context = self._temporal_access_context()
            retrieval_state = self._temporal_repository.open_retrieval_state(context)
            stored = stored_information_set
            continuity_carrier = self._current_context.continuity_carrier
            conversation_prefix_id = self._current_context.conversation_prefix_id
            visible_material_ids: tuple[str, ...] = ()
            if stored is not None:
                continuity_carrier = PumpStationContinuityCarrier(stored.continuity_carrier)
                self._view_ids = stored.observation_history_view_ids
                if stored.base_view_id != self._view.view_id:
                    self._view_ids = (*self._view_ids, self._view.view_id)
                visible_material_ids = stored.visible_material_ids
            for material_id in (
                *retrieval_state.actor_event_ids,
                *((retrieval_state.installed_carrier_id,) if retrieval_state.installed_carrier_id else ()),
            ):
                if material_id not in visible_material_ids:
                    visible_material_ids = (*visible_material_ids, material_id)
            self._current_context = PumpStationCurrentContext(
                continuity_carrier=continuity_carrier,
                conversation_prefix_id=conversation_prefix_id,
                workspace_tool_ids=self._tool_names,
                visible_material_ids=visible_material_ids,
            )
            self._information_set = self._bind_information_set()
            self._publish_temporal_current_information_set()

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
            temporal_evidence=self._temporal_evidence,
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
            if cached_request == request:
                return cached_result
            if request.action_name not in {"search_evidence", "fetch_evidence"}:
                raise WorldInterfaceError(
                    "actor-request-id-conflict",
                    f"{request.request_id} is already bound to different content",
                )
        self._validate_actor_binding(request.binding)
        if request.action_name not in {item.name for item in self.actor_capabilities.actions}:
            raise WorldInterfaceError("actor-action-unavailable", request.action_name)
        if request.action_name in {"search_evidence", "fetch_evidence"}:
            publication = self._apply_temporal_access(
                request.request_id,
                pump_station_temporal_access_arguments(request),
            )
            observation = self.observe_actor()
            result = WorldActorActionResult(
                request_content_sha256=request.content_sha256,
                action_name=request.action_name,
                status=publication.decision.result.public_status.value,
                pre_binding=request.binding,
                post_binding=observation.binding,
                task_receipt=_artifact_payload(publication.decision.result),
                next_observation=observation,
            )
            self._actor_results[request.request_id] = (request, result)
            return result
        reliance: TemporalEvidenceRelianceRecord | None = None
        relied_on_evidence_refs = pump_station_evidence_reliance_refs(request)
        proposal_request = pump_station_request_without_evidence_reliance(request)
        if self._temporal_repository is not None:
            if relied_on_evidence_refs:
                try:
                    reliance = self._temporal_repository.record_evidence_reliance(
                        self._temporal_access_context(),
                        action_request_id=request.request_id,
                        action_name=request.action_name,
                        relied_on_evidence_refs=relied_on_evidence_refs,
                    )
                except TemporalEvidenceIntegrityError as error:
                    raise WorldInterfaceError(
                        "actor-evidence-reliance-invalid",
                        str(error),
                    ) from error
        proposal = pump_station_proposal_from_actor_request(proposal_request)
        transition = self._apply_proposal(proposal)
        observation = self.observe_actor()
        task_receipt = _artifact_payload(transition.receipt)
        if reliance is not None:
            task_receipt["evidence_reliance_id"] = reliance.content_sha256
        result = WorldActorActionResult(
            request_content_sha256=request.content_sha256,
            action_name=request.action_name,
            status=transition.receipt.execution.value,
            pre_binding=request.binding,
            post_binding=observation.binding,
            task_receipt=task_receipt,
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
    def retrieval_state(self) -> TemporalRetrievalState:
        """Return the current host-side retrieval state for an enabled session."""

        if self._temporal_repository is None:
            raise ValueError("temporal documentary evidence is not enabled")
        return self._temporal_repository.load_retrieval_state(self._temporal_access_context())

    def load_evidence_reliance(
        self,
        action_request_id: str,
    ) -> TemporalEvidenceRelianceRecord:
        """Reload one exact explicit action reliance record."""

        if self._temporal_repository is None:
            raise ValueError("temporal documentary evidence is not enabled")
        return self._temporal_repository.load_evidence_reliance(action_request_id)

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
        self._publish_temporal_current_information_set()

    def create_retrieval_handover(
        self,
        *,
        to_tenure_id: str,
        to_session_id: str,
        include_fetched_content: bool,
    ) -> TemporalRetrievalStateCarrier:
        """Create a sanitized retrieval-state carrier for one fresh tenure."""

        if self._temporal_repository is None:
            raise ValueError("temporal documentary evidence is not enabled")
        return self._temporal_repository.create_retrieval_handover(
            self._temporal_access_context(),
            to_agent_tenure_id=to_tenure_id,
            to_session_id=to_session_id,
            include_fetched_content=include_fetched_content,
        )

    def install_retrieval_handover(
        self,
        carrier: TemporalRetrievalStateCarrier,
    ) -> None:
        """Install one sanitized retrieval carrier after a structured handover."""

        if self._temporal_repository is None:
            raise ValueError("temporal documentary evidence is not enabled")
        if self._current_context.continuity_carrier is not PumpStationContinuityCarrier.STRUCTURED_HANDOVER:
            raise ValueError("retrieval carrier requires a structured handover")
        if len(self._view_ids) != 1:
            raise ValueError("retrieval carrier must be installed before the tenure acts")
        self._temporal_repository.install_retrieval_handover(
            carrier,
            context=self._temporal_access_context(),
        )
        visible_material_ids = self._current_context.visible_material_ids
        if carrier.content_sha256 not in visible_material_ids:
            visible_material_ids = (*visible_material_ids, carrier.content_sha256)
        self._current_context = PumpStationCurrentContext(
            continuity_carrier=self._current_context.continuity_carrier,
            conversation_prefix_id=self._current_context.conversation_prefix_id,
            workspace_tool_ids=self._current_context.workspace_tool_ids,
            visible_material_ids=visible_material_ids,
        )
        self._information_set = self._bind_information_set()
        self._publish_temporal_current_information_set()

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

    def continue_operation(
        self,
        proposal_id: str,
        reason: str,
        relied_on_evidence_refs: tuple[str, ...] = (),
    ) -> str:
        """Continue the permitted operating mode to the next declared decision event."""
        return self._invoke_actor_tool(
            proposal_id,
            "continue_operation",
            {"reason": reason, "relied_on_evidence_refs": relied_on_evidence_refs},
        )

    def transfer_duty(
        self,
        proposal_id: str,
        reason: str,
        relied_on_evidence_refs: tuple[str, ...] = (),
    ) -> str:
        """Request the one permitted transfer from duty to standby pump."""
        return self._invoke_actor_tool(
            proposal_id,
            "transfer_duty",
            {"reason": reason, "relied_on_evidence_refs": relied_on_evidence_refs},
        )

    def request_inspection(
        self,
        proposal_id: str,
        reason: str,
        pump_id: str,
        relied_on_evidence_refs: tuple[str, ...] = (),
    ) -> str:
        """Request a scheduled inspection of one named pump."""
        return self._invoke_actor_tool(
            proposal_id,
            "request_inspection",
            {
                "reason": reason,
                "pump_id": pump_id,
                "relied_on_evidence_refs": relied_on_evidence_refs,
            },
        )

    def request_condition_check(
        self,
        proposal_id: str,
        reason: str,
        pump_id: str,
        relied_on_evidence_refs: tuple[str, ...] = (),
    ) -> str:
        """Request one sensor-based condition check for a named pump."""
        return self._invoke_actor_tool(
            proposal_id,
            "request_condition_check",
            {
                "reason": reason,
                "pump_id": pump_id,
                "relied_on_evidence_refs": relied_on_evidence_refs,
            },
        )

    def request_conditional_deferral(
        self,
        proposal_id: str,
        reason: str,
        pump_id: str,
        relied_on_evidence_refs: tuple[str, ...] = (),
    ) -> str:
        """Request the fixed transfer-then-isolate conditional deferral."""
        return self._invoke_actor_tool(
            proposal_id,
            "request_conditional_deferral",
            {
                "reason": reason,
                "pump_id": pump_id,
                "relied_on_evidence_refs": relied_on_evidence_refs,
            },
        )

    def request_obstruction_clearance(
        self,
        proposal_id: str,
        reason: str,
        pump_id: str,
        inspection_evidence_id: str,
        relied_on_evidence_refs: tuple[str, ...] = (),
    ) -> str:
        """Request obstruction clearance against named inspection evidence."""
        return self._invoke_actor_tool(
            proposal_id,
            "request_obstruction_clearance",
            {
                "reason": reason,
                "pump_id": pump_id,
                "inspection_evidence_id": inspection_evidence_id,
                "relied_on_evidence_refs": relied_on_evidence_refs,
            },
        )

    def request_provisional_return(
        self,
        proposal_id: str,
        reason: str,
        pump_id: str,
        functional_check_evidence_id: str,
        relied_on_evidence_refs: tuple[str, ...] = (),
    ) -> str:
        """Request provisional return against accepted functional-check evidence."""
        return self._invoke_actor_tool(
            proposal_id,
            "request_provisional_return",
            {
                "reason": reason,
                "pump_id": pump_id,
                "functional_check_evidence_id": functional_check_evidence_id,
                "relied_on_evidence_refs": relied_on_evidence_refs,
            },
        )

    def request_provisional_closure(
        self,
        proposal_id: str,
        reason: str,
        work_order_id: str,
        relied_on_evidence_refs: tuple[str, ...] = (),
    ) -> str:
        """Request administrative closure while verification duties remain open."""
        return self._invoke_actor_tool(
            proposal_id,
            "request_provisional_closure",
            {
                "reason": reason,
                "work_order_id": work_order_id,
                "relied_on_evidence_refs": relied_on_evidence_refs,
            },
        )

    def request_post_maintenance_verification(
        self,
        proposal_id: str,
        reason: str,
        pump_id: str,
        relied_on_evidence_refs: tuple[str, ...] = (),
    ) -> str:
        """Request independent post-maintenance verification for one pump."""
        return self._invoke_actor_tool(
            proposal_id,
            "request_post_maintenance_verification",
            {
                "reason": reason,
                "pump_id": pump_id,
                "relied_on_evidence_refs": relied_on_evidence_refs,
            },
        )

    def resume_process(
        self,
        proposal_id: str,
        reason: str,
        process_id: str,
        relied_on_evidence_refs: tuple[str, ...] = (),
    ) -> str:
        """Resume blocked or suspended work after dependency and resource checks."""
        return self._invoke_actor_tool(
            proposal_id,
            "resume_process",
            {
                "reason": reason,
                "process_id": process_id,
                "relied_on_evidence_refs": relied_on_evidence_refs,
            },
        )

    def cancel_process(
        self,
        proposal_id: str,
        reason: str,
        process_id: str,
        relied_on_evidence_refs: tuple[str, ...] = (),
    ) -> str:
        """Cancel live work and release its unused reservations."""
        return self._invoke_actor_tool(
            proposal_id,
            "cancel_process",
            {
                "reason": reason,
                "process_id": process_id,
                "relied_on_evidence_refs": relied_on_evidence_refs,
            },
        )

    def request_dependency_waiver(
        self,
        proposal_id: str,
        reason: str,
        process_id: str,
        dependency_id: str,
        evidence_id: str,
        relied_on_evidence_refs: tuple[str, ...] = (),
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
                "relied_on_evidence_refs": relied_on_evidence_refs,
            },
        )

    def search_evidence(
        self,
        request_id: str,
        query: str,
        scope: str = "all",
        limit: int = 5,
    ) -> str:
        """Search documentary evidence available to this tenure at the current world time."""

        return self._invoke_actor_tool(
            request_id,
            "search_evidence",
            {"query": query, "scope": scope, "limit": limit},
        )

    def fetch_evidence(self, request_id: str, reference: str) -> str:
        """Fetch documentary content through an opaque reference issued to this tenure."""

        return self._invoke_actor_tool(
            request_id,
            "fetch_evidence",
            {"reference": reference},
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

    def verify_temporal_evidence(self) -> TemporalEvidenceVerificationReport:
        """Independently replay the enabled temporal-evidence ledger."""

        if self._temporal_repository is None:
            raise ValueError("temporal documentary evidence is not enabled")
        proposal_bindings = {
            step.proposal.context.proposal_id: (
                step.proposal.context.information_set_id,
                step.proposal.context.base_view_id,
            )
            for step in self._run.steps()
            if step.proposal is not None
        }
        return verify_temporal_evidence_repository(
            self._temporal_repository,
            package=self._run.package,
            proposal_bindings=proposal_bindings,
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
        json_arguments = {key: list(value) if isinstance(value, tuple) else value for key, value in arguments.items()}
        result = self.invoke_actor_action(
            WorldActorActionRequest(
                request_id=request_id,
                action_name=action_name,
                binding=self.current_actor_binding,
                arguments=json_arguments,
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

    def _apply_temporal_access(
        self,
        request_id: str,
        arguments: TemporalEvidenceSearchArguments | TemporalEvidenceFetchArguments,
    ) -> TemporalAccessPublication:
        repository = self._temporal_repository
        gateway = self._temporal_gateway
        if repository is None or gateway is None:
            raise WorldInterfaceError(
                "actor-action-unavailable",
                "temporal documentary evidence is not enabled",
            )
        context = self._temporal_access_context()
        if repository.has_access(request_id):
            publication = repository.recover_access(request_id, context=context)
            self._validate_temporal_retry(publication, arguments)
            if publication.information_set.information_set_id != self._information_set.information_set_id:
                raise WorldInterfaceError(
                    "actor-request-id-conflict",
                    "recovered access belongs to another visible information set",
                )
            return publication

        state = repository.load_retrieval_state(context)
        event_id = temporal_actor_event_id(
            request_id=request_id,
            access_sequence=state.state_sequence + 1,
            context=context,
        )
        visible_material_ids = self._current_context.visible_material_ids
        if event_id not in visible_material_ids:
            visible_material_ids = (*visible_material_ids, event_id)
        next_context = PumpStationCurrentContext(
            continuity_carrier=self._current_context.continuity_carrier,
            conversation_prefix_id=self._current_context.conversation_prefix_id,
            workspace_tool_ids=self._current_context.workspace_tool_ids,
            visible_material_ids=visible_material_ids,
        )
        next_information_set = bind_information_set(
            self._view,
            PumpStationObservationHistory(
                agent_tenure_id=self._request.agent_tenure_id,
                view_ids=self._view_ids,
            ),
            next_context,
        )
        information_manifest = TemporalInformationSetManifest(
            information_set_id=next_information_set.information_set_id,
            base_view_id=self._view.view_id,
            agent_tenure_id=self._request.agent_tenure_id,
            tenure_started_at_seconds=self._projection_context.tenure_started_at_seconds,
            observation_history_view_ids=self._view_ids,
            continuity_carrier=next_context.continuity_carrier.value,
            workspace_tool_ids=next_context.workspace_tool_ids,
            visible_material_ids=next_context.visible_material_ids,
        )
        if isinstance(arguments, TemporalEvidenceSearchArguments):
            decision = gateway.search(
                request_id=request_id,
                query=arguments.query,
                scope=arguments.scope,
                limit=arguments.limit,
                context=context,
                state=state,
                resulting_information_set_id=next_information_set.information_set_id,
            )
        else:
            decision = gateway.fetch(
                request_id=request_id,
                reference=arguments.reference,
                context=context,
                state=state,
                resulting_information_set_id=next_information_set.information_set_id,
            )
        publication = repository.commit_access(
            TemporalAccessPublication(
                decision=decision,
                event=TemporalActorVisibleEvent(
                    event_id=event_id,
                    event_sequence=decision.result.access_sequence,
                    actor_id=self._projection_context.actor_id,
                    agent_tenure_id=self._request.agent_tenure_id,
                    session_id=self._request.session_id,
                    operation=decision.result.operation,
                    access_result_id=decision.result.content_sha256,
                    public_status=decision.result.public_status,
                    information_set_id=next_information_set.information_set_id,
                ),
                information_set=information_manifest,
            ),
            context=context,
        )
        self._current_context = next_context
        self._information_set = next_information_set
        self._publish_temporal_current_information_set()
        return publication

    def _validate_temporal_retry(
        self,
        publication: TemporalAccessPublication,
        arguments: TemporalEvidenceSearchArguments | TemporalEvidenceFetchArguments,
    ) -> None:
        receipt = publication.decision.receipt
        matches = (
            isinstance(arguments, TemporalEvidenceSearchArguments)
            and publication.decision.result.operation is TemporalEvidenceAccessKind.SEARCH
            and receipt.original_query == arguments.query
            and receipt.requested_scope == arguments.scope
            and receipt.requested_limit == arguments.limit
        ) or (
            isinstance(arguments, TemporalEvidenceFetchArguments)
            and publication.decision.result.operation is TemporalEvidenceAccessKind.FETCH
            and receipt.requested_reference == arguments.reference
        )
        if not matches:
            raise WorldInterfaceError(
                "actor-request-id-conflict",
                "temporal access request id is already bound to different arguments",
            )

    def _temporal_access_context(self) -> TemporalAccessContext:
        snapshot = self._run.snapshot()
        return TemporalAccessContext(
            run_id=self._request.run_id,
            episode_id=self._request.episode_id,
            world_instance_id=self._run.manifest.run_id,
            world_branch_id=self._request.world_branch_id,
            world_state_id=snapshot.state_id,
            world_commit_id=snapshot.commit_id,
            world_sequence=snapshot.sequence,
            world_time_seconds=self._run.state.physical.calendar_seconds,
            actor_id=self._projection_context.actor_id,
            actor_role="station-steward",
            agent_tenure_id=self._request.agent_tenure_id,
            session_id=self._request.session_id,
            base_view_id=self._view.view_id,
            prior_information_set_id=self._information_set.information_set_id,
            tool_contract_id=self.actor_capabilities.content_sha256,
            branch_ancestor_ids=(),
        )

    def _temporal_information_set_manifest(self) -> TemporalInformationSetManifest:
        return TemporalInformationSetManifest(
            information_set_id=self._information_set.information_set_id,
            base_view_id=self._view.view_id,
            agent_tenure_id=self._request.agent_tenure_id,
            tenure_started_at_seconds=self._projection_context.tenure_started_at_seconds,
            observation_history_view_ids=self._view_ids,
            continuity_carrier=self._current_context.continuity_carrier.value,
            workspace_tool_ids=self._current_context.workspace_tool_ids,
            visible_material_ids=self._current_context.visible_material_ids,
        )

    def _publish_temporal_current_information_set(self) -> None:
        if self._temporal_repository is None:
            return
        self._temporal_repository.publish_current_information_set(
            self._temporal_access_context(),
            self._temporal_information_set_manifest(),
        )

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
        self._publish_temporal_current_information_set()


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
        temporal_evidence: bool = False,
        temporal_budget: RetrievalBudgetVector | None = None,
    ) -> None:
        self._repository = PumpStationWorldRunRepository(repository_root)
        self._package_root = package_root
        self._schedule = schedule
        self._temporal_evidence = temporal_evidence
        self._temporal_budget = temporal_budget
        self._evidence_health = evidence_health or temporal_evidence
        self._rich_work_processes = rich_work_processes or self._evidence_health

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
        temporal_repository: TemporalEvidenceRepository | None = None
        temporal_gateway: TemporalEvidenceGateway | None = None
        temporal_enabled = (
            self._temporal_evidence
            if request.open_mode is WorldSessionOpenMode.START
            else TemporalEvidenceRepository.is_enabled(self._repository.root)
        )
        if temporal_enabled:
            temporal_repository = TemporalEvidenceRepository(self._repository.root / "temporal-evidence")
            if request.open_mode is WorldSessionOpenMode.START:
                bundle = temporal_repository.initialize(
                    build_reference_temporal_evidence_bundle(
                        package,
                        world_branch_id=request.world_branch_id,
                        initial_budget=self._temporal_budget,
                    ),
                    package=package,
                )
            else:
                bundle = temporal_repository.load_bundle(package=package)
            temporal_gateway = TemporalEvidenceGateway(bundle)
        return PumpStationWorldSession(
            request=request,
            run=run,
            temporal_repository=temporal_repository,
            temporal_gateway=temporal_gateway,
        )
