# ABOUTME: Exposes the pump-station world as a direct host session with closed typed tools.
# ABOUTME: Composes durable runs, actor projections, information binding, actions, snapshots, and replay.

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from aec_bench.contracts.task_definition import ToolSpec
from aec_bench.contracts.world_session import (
    STEWARDSHIP_STATE_SNAPSHOT_SCHEMA_VERSION,
    StewardshipStateSnapshotRef,
    WorldSessionOpenMode,
    WorldSessionRequest,
    WorldSessionResult,
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
    ContinueOperation,
    ProposalContext,
    PumpStationProposal,
    RequestConditionalDeferral,
    RequestInspection,
    RequestObstructionClearance,
    RequestProvisionalClosure,
    RequestProvisionalReturn,
    RequestVerification,
    TransferDuty,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_state_machine import (
    create_stewardship_state,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationVerificationReport,
    verify_stewardship_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationActorView,
    PumpStationContinuityCarrier,
    PumpStationCurrentContext,
    PumpStationInformationSet,
    PumpStationObservationHistory,
    PumpStationProjectionContext,
    bind_information_set,
    project_actor_view,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
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


def _pump_station_snapshot(snapshot: StewardshipStateSnapshotRef) -> PumpStationStateSnapshotRef:
    return PumpStationStateSnapshotRef(
        snapshot_version=PUMP_STATION_SNAPSHOT_VERSION,
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
            projection_policy_id=PUMP_STATION_PROJECTION_POLICY_ID,
            source_artifact_ids=(
                run.package.package_content_id,
                run.package.manifest_content_id,
            ),
        )
        self._current_context = PumpStationCurrentContext(
            continuity_carrier=PumpStationContinuityCarrier.CURRENT_ACTOR_VIEW,
            conversation_prefix_id=None,
            workspace_tool_ids=PUMP_STATION_TOOL_NAMES,
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
            tool_names=PUMP_STATION_TOOL_NAMES,
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
            for name in PUMP_STATION_TOOL_NAMES
        )

    @property
    def native_tools(self) -> tuple[Callable[..., str], ...]:
        """Return the bound native functions in the declared tool order."""
        return tuple(getattr(self, name) for name in PUMP_STATION_TOOL_NAMES)

    def observe_pump_station(self) -> str:
        """Read the complete current actor view without latent or future state."""
        return pump_station_artifact_bytes(self._view).decode("utf-8")

    def continue_operation(self, proposal_id: str, reason: str) -> str:
        """Continue the permitted operating mode to the next declared decision event."""
        return self._apply(
            ContinueOperation(
                context=self._proposal_context(proposal_id, reason),
            )
        )

    def transfer_duty(self, proposal_id: str, reason: str) -> str:
        """Request the one permitted transfer from duty to standby pump."""
        return self._apply(
            TransferDuty(
                context=self._proposal_context(proposal_id, reason),
            )
        )

    def request_inspection(self, proposal_id: str, reason: str, pump_id: str) -> str:
        """Request a scheduled inspection of one named pump."""
        return self._apply(
            RequestInspection(
                context=self._proposal_context(proposal_id, reason),
                pump_id=pump_id,
            )
        )

    def request_conditional_deferral(self, proposal_id: str, reason: str, pump_id: str) -> str:
        """Request the fixed transfer-then-isolate conditional deferral."""
        return self._apply(
            RequestConditionalDeferral(
                context=self._proposal_context(proposal_id, reason),
                pump_id=pump_id,
            )
        )

    def request_obstruction_clearance(
        self,
        proposal_id: str,
        reason: str,
        pump_id: str,
        inspection_evidence_id: str,
    ) -> str:
        """Request obstruction clearance against named inspection evidence."""
        return self._apply(
            RequestObstructionClearance(
                context=self._proposal_context(proposal_id, reason),
                pump_id=pump_id,
                inspection_evidence_id=inspection_evidence_id,
            )
        )

    def request_provisional_return(
        self,
        proposal_id: str,
        reason: str,
        pump_id: str,
        functional_check_evidence_id: str,
    ) -> str:
        """Request provisional return against accepted functional-check evidence."""
        return self._apply(
            RequestProvisionalReturn(
                context=self._proposal_context(proposal_id, reason),
                pump_id=pump_id,
                functional_check_evidence_id=functional_check_evidence_id,
            )
        )

    def request_provisional_closure(
        self,
        proposal_id: str,
        reason: str,
        work_order_id: str,
    ) -> str:
        """Request administrative closure while verification duties remain open."""
        return self._apply(
            RequestProvisionalClosure(
                context=self._proposal_context(proposal_id, reason),
                work_order_id=work_order_id,
            )
        )

    def request_post_maintenance_verification(
        self,
        proposal_id: str,
        reason: str,
        pump_id: str,
    ) -> str:
        """Request independent post-maintenance verification for one pump."""
        return self._apply(
            RequestVerification(
                context=self._proposal_context(proposal_id, reason),
                pump_id=pump_id,
            )
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

    def _proposal_context(self, proposal_id: str, reason: str) -> ProposalContext:
        return ProposalContext(
            proposal_id=proposal_id,
            agent_tenure_id=self._request.agent_tenure_id,
            based_on_sequence=self._run.state.sequence,
            base_view_id=self._view.view_id,
            information_set_id=self._information_set.information_set_id,
            reason=reason,
        )

    def _apply(self, proposal: PumpStationProposal) -> str:
        transition = self._run.apply(
            proposal,
            information_set=self._information_set,
        )
        self._refresh_projection()
        return json.dumps(
            {
                "status": transition.receipt.execution.value,
                "snapshot": self.result.snapshot.model_dump(mode="json"),
                "receipt": _artifact_payload(transition.receipt),
                "view": _artifact_payload(self._view),
            },
            sort_keys=True,
            separators=(",", ":"),
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


class PumpStationWorldSessionFactory:
    """Create or resume pump-station sessions from one host-supplied repository."""

    task_world_id = PUMP_STATION_TASK_WORLD_ID

    def __init__(
        self,
        repository_root: Path,
        *,
        package_root: Path | None = None,
    ) -> None:
        self._repository = PumpStationWorldRunRepository(repository_root)
        self._package_root = package_root

    def open(self, request: WorldSessionRequest) -> PumpStationWorldSession:
        """Open a new or exact resumed session for the requested actor tenure."""
        if request.task_world_id != self.task_world_id:
            raise ValueError("world-session request belongs to another task world")
        package = load_reference_package(self._package_root)
        model = pump_station_model_from_package(package)
        if request.open_mode is WorldSessionOpenMode.START:
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
            )
            run = PumpStationWorldRun.create(
                repository=self._repository,
                package=package,
                model=model,
                initial_state=state,
                run_id=request.run_id,
                episode_id=request.episode_id,
                world_branch_id=request.world_branch_id,
            )
        else:
            if request.start_snapshot is None:
                raise ValueError("resume request has no start snapshot")
            run = PumpStationWorldRun.resume(
                repository=self._repository,
                package=package,
                model=model,
                snapshot=_pump_station_snapshot(request.start_snapshot),
            )
        return PumpStationWorldSession(request=request, run=run)
