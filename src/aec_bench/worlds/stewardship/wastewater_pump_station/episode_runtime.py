# ABOUTME: Composes the registered pump world with the shared episode shell and current durable repository.
# ABOUTME: Resolves opaque decisions from durable state without exposing session, branch, or state bindings to actors.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pydantic import JsonValue

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.world_interface import (
    WorldActorActionRequest,
    WorldActorActionResult,
    WorldActorCapabilityCatalogue,
    WorldActorObservation,
    WorldInterfaceError,
)
from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionOpenMode,
    WorldSessionRequest,
    WorldSessionResult,
)
from aec_bench.worlds.runtime.episode import (
    ActionSubmission,
    Episode,
    EpisodeFinished,
    EpisodeFunctions,
    EpisodeLimits,
    EpisodeOpened,
    EpisodeRecorder,
    EpisodeStepRecorded,
)
from aec_bench.worlds.runtime.world_logic import ActionRejected, Transition
from aec_bench.worlds.stewardship.wastewater_pump_station.actor_interface import (
    PUMP_STATION_ACTOR_WORKSPACE_TOOL_ID,
    PUMP_STATION_TEMPORAL_EVIDENCE_ACTION_NAMES,
    parse_pump_station_action,
    pump_station_actor_capabilities,
    pump_station_temporal_access_arguments,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.coupled_runtime import (
    PumpStationCoupledWorldError,
    project_coupled_information_set,
    transition,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.coupled_work import (
    PumpStationResourceError,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_identity import (
    canonical_stewardship_value,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationAction,
    PumpStationActionError,
    PumpStationCoupledTransition,
    PumpStationStewardshipState,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationCurrentContext,
    PumpStationInformationSet,
    PumpStationObservationHistory,
    bind_information_set,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence import (
    TemporalAccessContext,
    TemporalAccessPublication,
    TemporalActorVisibleEvent,
    TemporalEvidenceGateway,
    TemporalEvidenceRepository,
    TemporalInformationSetManifest,
    temporal_actor_event_id,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationCommand,
    PumpStationRegisteredWorldRunManifest,
    PumpStationStateSnapshotRef,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)

PUMP_STATION_TASK_WORLD_ID = "wastewater-pump-station-stewardship.v1"
_ACTOR_ID = "pump-station-actor"
_ACTOR_TENURE_ID = "pump-station-actor-tenure"
_EPISODE_SESSION_ID = "pump-station-episode"


@dataclass(frozen=True, slots=True)
class _SubmittedPumpAction:
    """Private request correlation supplied alongside the pure task action."""

    request_id: str
    action: PumpStationAction


def _artifact_payload(value: object) -> dict[str, JsonValue]:
    payload = canonical_stewardship_value(value)
    if not isinstance(payload, dict):
        raise TypeError("pump-station actor artifact must serialize to an object")
    return cast(dict[str, JsonValue], payload)


def _request_content_id(request: WorldActorActionRequest) -> str:
    return canonical_content_sha256(
        {
            "request_id": request.request_id,
            "decision_id": request.decision_id,
            "action_name": request.action_name,
            "arguments": request.arguments,
        }
    )


class _PumpStationRecorder(
    EpisodeRecorder[
        PumpStationStewardshipState,
        dict[str, JsonValue],
        _SubmittedPumpAction,
        PumpStationCoupledTransition,
    ]
):
    """Serialize accepted episode steps through the existing current repository."""

    def __init__(
        self,
        *,
        repository: PumpStationWorldRunRepository,
        manifest: PumpStationRegisteredWorldRunManifest,
        prior_snapshot: PumpStationStateSnapshotRef,
    ) -> None:
        self._repository = repository
        self._manifest = manifest
        self._prior_snapshot = prior_snapshot
        self._command: PumpStationCommand | None = None

    def bind(self, command: PumpStationCommand) -> None:
        """Bind the host-owned durable command for the next accepted step."""
        if self._command is not None:
            raise RuntimeError("pump recorder already has a pending command")
        self._command = command

    def record_opened(
        self,
        event: EpisodeOpened[PumpStationStewardshipState, dict[str, JsonValue]],
    ) -> None:
        del event

    def record_step(
        self,
        event: EpisodeStepRecorded[
            PumpStationStewardshipState,
            dict[str, JsonValue],
            _SubmittedPumpAction,
            PumpStationCoupledTransition,
        ],
    ) -> None:
        command = self._command
        if command is None or command.request_id != event.action.request_id or command.action != event.action.action:
            raise RuntimeError("pump recorder command does not match the accepted action")
        staged = self._repository.stage_command_transition(
            manifest=self._manifest,
            prior_snapshot=self._prior_snapshot,
            command=command,
            transition=event.output,
        )
        self._repository._publish_staged_command_under_lock(staged)
        self._command = None

    def record_finished(self, event: EpisodeFinished) -> None:
        del event


class PumpStationEpisodeHost:
    """Resolve installed actor calls against one durable registered pump episode."""

    def __init__(self, run_root: Path, *, limits: EpisodeLimits | None = None) -> None:
        self._repository = PumpStationWorldRunRepository(run_root)
        self._limits = limits

    def capabilities(self) -> WorldActorCapabilityCatalogue:
        return pump_station_actor_capabilities(
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            temporal_repository_verified=True,
        )

    def open(self, request: WorldSessionRequest) -> WorldSessionResult:
        """Create or inspect the host-selected episode without opening an actor session."""

        if request.task_world_id != PUMP_STATION_TASK_WORLD_ID:
            raise WorldInterfaceError("world-wrong-task", request.task_world_id)
        if request.open_mode is WorldSessionOpenMode.START:
            if (self._repository.root / "manifest.json").exists():
                raise WorldInterfaceError("episode-already-exists", "run root already contains an episode")
            PumpStationWorldRun.create_reference_system(
                repository=self._repository,
                run_id=request.run_id,
                episode_id=request.episode_id,
                world_branch_id=request.world_branch_id,
            )
        with self._repository.locked():
            run, snapshot, state = self._load()
            if request.open_mode is WorldSessionOpenMode.RESUME and request.start_snapshot is not None:
                selected = request.start_snapshot
                if (
                    selected.run_id,
                    selected.episode_id,
                    selected.world_branch_id,
                    selected.sequence,
                    selected.state_id,
                    selected.commit_id,
                ) != (
                    snapshot.run_id,
                    snapshot.episode_id,
                    snapshot.world_branch_id,
                    snapshot.sequence,
                    snapshot.state_id,
                    snapshot.commit_id,
                ):
                    raise WorldInterfaceError("decision-stale", "resume snapshot is no longer current")
            manifest = run.manifest
            information_set = self._information_set(manifest, state, snapshot.sequence)
            return WorldSessionResult(
                execution_kind=request.execution_kind,
                open_mode=request.open_mode,
                session_id=request.session_id,
                task_world_id=request.task_world_id,
                agent_tenure_id=request.agent_tenure_id,
                snapshot=StewardshipStateSnapshotRef(
                    run_id=snapshot.run_id,
                    episode_id=snapshot.episode_id,
                    world_branch_id=snapshot.world_branch_id,
                    sequence=snapshot.sequence,
                    state_id=snapshot.state_id,
                    commit_id=snapshot.commit_id,
                ),
                actor_view_id=information_set.base_view.view_id,
                information_set_id=information_set.information_set_id,
                tool_names=tuple(action.name for action in self.capabilities().actions),
            )

    def observe(self) -> WorldActorObservation:
        with self._repository.locked():
            run, snapshot, state = self._load()
            episode, _ = self._episode(run, snapshot, state)
            decision = episode.current_decision()
            return WorldActorObservation(decision_id=decision.decision_id, view=decision.observation)

    def invoke(self, request: WorldActorActionRequest) -> WorldActorActionResult:
        with self._repository.locked():
            if request.action_name in PUMP_STATION_TEMPORAL_EVIDENCE_ACTION_NAMES:
                return self._invoke_temporal(request)
            retried = self._retry(request)
            if retried is not None:
                return retried
            run, snapshot, state = self._load()
            episode, recorder = self._episode(run, snapshot, state)
            current = episode.current_decision()
            if request.decision_id != current.decision_id:
                raise WorldInterfaceError("decision-stale", "decision is unknown or no longer current")
            action, command = self._resolve_action(run, snapshot, state, request)
            recovered = self._repository._recover_staged_command_under_lock(command)
            if recovered is not None:
                retried = self._retry(request)
                if retried is None:
                    raise RuntimeError("recovered pump action is not on the selected history")
                return retried
            recorder.bind(command)
            reply = episode.submit(
                ActionSubmission(
                    decision_id=request.decision_id,
                    action=_SubmittedPumpAction(request_id=request.request_id, action=action),
                )
            )
            if reply.rejection is not None:
                return WorldActorActionResult(
                    request_id=request.request_id,
                    action_name=request.action_name,
                    status="rejected",
                    task_receipt={"code": reply.rejection.code, "message": reply.rejection.message},
                    next_observation=WorldActorObservation(
                        decision_id=current.decision_id,
                        view=current.observation,
                    ),
                )
            if reply.output is None:
                raise RuntimeError("accepted pump action has no transition output")
            next_observation = (
                None
                if reply.decision is None
                else WorldActorObservation(
                    decision_id=reply.decision.decision_id,
                    view=reply.decision.observation,
                )
            )
            return WorldActorActionResult(
                request_id=request.request_id,
                action_name=request.action_name,
                status=reply.output.receipt.execution_status,
                task_receipt=_artifact_payload(reply.output.receipt),
                next_observation=next_observation,
                terminated=reply.terminated,
                truncated=reply.truncated,
                reason=reply.reason,
            )

    def _invoke_temporal(self, request: WorldActorActionRequest) -> WorldActorActionResult:
        run, snapshot, state = self._load()
        manifest = run.manifest
        information_set = self._information_set(manifest, state, snapshot.sequence)
        decision_id = self._decision_id(manifest, state, snapshot.sequence)
        if request.decision_id != decision_id:
            raise WorldInterfaceError("decision-stale", "decision is unknown or no longer current")
        arguments = pump_station_temporal_access_arguments(request)
        temporal = TemporalEvidenceRepository(self._repository.root / "temporal-evidence")
        context = TemporalAccessContext(
            run_id=manifest.run_id,
            episode_id=manifest.episode_id,
            world_instance_id=manifest.run_id,
            world_branch_id=manifest.world_branch_id,
            world_state_id=snapshot.state_id,
            world_commit_id=snapshot.commit_id,
            world_sequence=snapshot.sequence,
            world_time_seconds=state.physical.calendar_seconds,
            actor_id=_ACTOR_ID,
            actor_role="station-steward",
            agent_tenure_id=_ACTOR_TENURE_ID,
            session_id=_EPISODE_SESSION_ID,
            base_view_id=information_set.base_view.view_id,
            prior_information_set_id=information_set.information_set_id,
            tool_contract_id=canonical_content_sha256(self.capabilities().model_dump(mode="json")),
            branch_ancestor_ids=manifest.initial_state_source.ancestor_branch_ids,
        )
        if temporal.has_access(request.request_id):
            publication = temporal.recover_access(request.request_id, context=context)
        else:
            retrieval_state = temporal.open_retrieval_state(context)
            event_id = temporal_actor_event_id(
                request_id=request.request_id,
                access_sequence=retrieval_state.state_sequence + 1,
                context=context,
            )
            visible_material_ids = (*information_set.current_context.visible_material_ids, event_id)
            next_context = PumpStationCurrentContext(
                continuity_carrier=information_set.current_context.continuity_carrier,
                conversation_prefix_id=information_set.current_context.conversation_prefix_id,
                workspace_tool_ids=information_set.current_context.workspace_tool_ids,
                visible_material_ids=visible_material_ids,
            )
            next_information_set = bind_information_set(
                information_set.base_view,
                PumpStationObservationHistory(
                    agent_tenure_id=_ACTOR_TENURE_ID,
                    view_ids=(information_set.base_view.view_id,),
                ),
                next_context,
            )
            gateway = TemporalEvidenceGateway(temporal.load_bundle(package=run.package))
            if request.action_name == "search_evidence":
                query, scope, limit = cast(tuple[str, str, int], arguments)
                access = gateway.search(
                    request_id=request.request_id,
                    query=query,
                    scope=scope,
                    limit=limit,
                    context=context,
                    state=retrieval_state,
                    resulting_information_set_id=next_information_set.information_set_id,
                )
            elif request.action_name == "fetch_evidence":
                access = gateway.fetch(
                    request_id=request.request_id,
                    reference=cast(str, arguments),
                    context=context,
                    state=retrieval_state,
                    resulting_information_set_id=next_information_set.information_set_id,
                )
            else:
                raise AssertionError("temporal action arguments use an unknown type")
            publication = temporal.commit_access(
                TemporalAccessPublication(
                    decision=access,
                    event=TemporalActorVisibleEvent(
                        event_id=event_id,
                        event_sequence=access.result.access_sequence,
                        actor_id=_ACTOR_ID,
                        agent_tenure_id=_ACTOR_TENURE_ID,
                        session_id=_EPISODE_SESSION_ID,
                        operation=access.result.operation,
                        access_result_id=access.result.content_sha256,
                        public_status=access.result.public_status,
                        information_set_id=next_information_set.information_set_id,
                    ),
                    information_set=TemporalInformationSetManifest(
                        information_set_id=next_information_set.information_set_id,
                        base_view_id=information_set.base_view.view_id,
                        agent_tenure_id=_ACTOR_TENURE_ID,
                        tenure_started_at_seconds=state.physical.calendar_seconds,
                        observation_history_view_ids=(information_set.base_view.view_id,),
                        continuity_carrier=next_context.continuity_carrier.value,
                        workspace_tool_ids=next_context.workspace_tool_ids,
                        visible_material_ids=next_context.visible_material_ids,
                    ),
                ),
                context=context,
            )
        result = publication.decision.result
        return WorldActorActionResult(
            request_id=request.request_id,
            action_name=request.action_name,
            status=result.public_status.value,
            task_receipt=cast(dict[str, JsonValue], result.model_dump(mode="json")),
            next_observation=WorldActorObservation(
                decision_id=decision_id,
                view=_artifact_payload(information_set.base_view),
            ),
        )

    def _load(
        self,
    ) -> tuple[
        PumpStationWorldRun,
        PumpStationStateSnapshotRef,
        PumpStationStewardshipState,
    ]:
        manifest = self._repository.load_manifest()
        if not isinstance(manifest, PumpStationRegisteredWorldRunManifest):
            raise WorldInterfaceError("world-format-obsolete", "actor calls require the current registered world")
        snapshot = self._repository.current_snapshot()
        run = PumpStationWorldRun.resume_reference_system(
            repository=self._repository,
            snapshot=snapshot,
        )
        state = self._repository.load_state(snapshot.state_id)
        return run, snapshot, state

    def _episode(
        self,
        run: PumpStationWorldRun,
        snapshot: PumpStationStateSnapshotRef,
        state: PumpStationStewardshipState,
    ) -> tuple[
        Episode[
            PumpStationStewardshipState,
            dict[str, JsonValue],
            _SubmittedPumpAction,
            PumpStationCoupledTransition,
            WorldActorCapabilityCatalogue,
        ],
        _PumpStationRecorder,
    ]:
        manifest = run.manifest
        recorder = _PumpStationRecorder(
            repository=self._repository,
            manifest=manifest,
            prior_snapshot=snapshot,
        )
        episode = Episode(
            episode_id=manifest.episode_id,
            actor_id=_ACTOR_ID,
            state=state,
            step_index=snapshot.sequence,
            decision_id=self._decision_id(manifest, state, snapshot.sequence),
            limits=self._limits,
            functions=EpisodeFunctions(
                observe=lambda current: _artifact_payload(
                    self._information_set(manifest, current, snapshot.sequence + int(current != state)).base_view
                ),
                transition=lambda current, action: self._transition(
                    run, current, action, sequence=snapshot.sequence + 1
                ),
                available_actions=lambda _current: self.capabilities(),
            ),
            recorder=recorder,
            decision_id_factory=lambda current, step: self._decision_id(manifest, current, step),
        )
        return episode, recorder

    def _resolve_action(
        self,
        run: PumpStationWorldRun,
        snapshot: PumpStationStateSnapshotRef,
        state: PumpStationStewardshipState,
        request: WorldActorActionRequest,
    ) -> tuple[PumpStationAction, PumpStationCommand]:
        manifest = run.manifest
        action = parse_pump_station_action(
            request.action_name,
            cast(dict[str, object], request.arguments),
        )
        information_set = self._information_set(manifest, state, snapshot.sequence)
        command = PumpStationCommand(
            kind="actor",
            request_id=request.request_id,
            request_content_id=_request_content_id(request),
            action=action,
            control=None,
            task_world_id=manifest.task_world_id,
            run_id=manifest.run_id,
            episode_id=manifest.episode_id,
            world_branch_id=manifest.world_branch_id,
            based_on_sequence=snapshot.sequence,
            base_state_id=snapshot.state_id,
            base_commit_id=snapshot.commit_id,
            decision_id=request.decision_id,
            actor_id=_ACTOR_ID,
            agent_tenure_id=_ACTOR_TENURE_ID,
            actor_view_id=information_set.base_view.view_id,
            information_set_id=information_set.information_set_id,
        )
        return action, command

    @staticmethod
    def _transition(
        run: PumpStationWorldRun,
        state: PumpStationStewardshipState,
        action: _SubmittedPumpAction,
        *,
        sequence: int,
    ) -> Transition[PumpStationStewardshipState, PumpStationCoupledTransition] | ActionRejected:
        try:
            task_transition = transition(
                state,
                sequence=sequence,
                request_id=action.request_id,
                action=action.action,
                model=run.model,
                event_schedule=run.event_schedule,
            )
        except (PumpStationActionError, PumpStationCoupledWorldError, PumpStationResourceError) as error:
            return ActionRejected(getattr(error, "code", "domain-action-rejected"), str(error))
        return Transition(state=task_transition.state, output=task_transition)

    def _retry(self, request: WorldActorActionRequest) -> WorldActorActionResult | None:
        committed = self._repository.find_committed_command(request.request_id)
        if committed is None:
            return None
        command, transition = self._repository._load_command_step(committed)
        if command.request_content_id != _request_content_id(request):
            raise WorldInterfaceError(
                "actor-request-id-conflict",
                f"{request.request_id} is already bound to different content",
            )
        manifest = self._repository.load_manifest()
        assert isinstance(manifest, PumpStationRegisteredWorldRunManifest)
        decision_id = self._decision_id(manifest, transition.state, committed.sequence)
        view = _artifact_payload(self._information_set(manifest, transition.state, committed.sequence).base_view)
        return WorldActorActionResult(
            request_id=request.request_id,
            action_name=request.action_name,
            status=transition.receipt.execution_status,
            task_receipt=_artifact_payload(transition.receipt),
            next_observation=WorldActorObservation(decision_id=decision_id, view=view),
        )

    @staticmethod
    def _information_set(
        manifest: PumpStationRegisteredWorldRunManifest,
        state: PumpStationStewardshipState,
        sequence: int,
    ) -> PumpStationInformationSet:
        return project_coupled_information_set(
            state,
            sequence=sequence,
            episode_id=manifest.episode_id,
            world_branch_id=manifest.world_branch_id,
            actor_id=_ACTOR_ID,
            agent_tenure_id=_ACTOR_TENURE_ID,
            source_artifact_ids=(
                manifest.reference_system_content_id,
                manifest.package_content_id,
                manifest.temporal_bundle_content_id,
            ),
            workspace_tool_ids=(PUMP_STATION_ACTOR_WORKSPACE_TOOL_ID,),
        )

    @staticmethod
    def _decision_id(
        manifest: PumpStationRegisteredWorldRunManifest,
        state: PumpStationStewardshipState,
        step_index: int,
    ) -> str:
        return canonical_content_sha256(
            {
                "task_world_id": manifest.task_world_id,
                "world_build": manifest.world_build_artifact_sha256,
                "profile": manifest.continual_profile_content_sha256,
                "run_id": manifest.run_id,
                "episode_id": manifest.episode_id,
                "world_branch_id": manifest.world_branch_id,
                "actor_id": _ACTOR_ID,
                "step_index": step_index,
                "state_id": state.state_id,
            }
        )


__all__ = ["PUMP_STATION_TASK_WORLD_ID", "PumpStationEpisodeHost"]
