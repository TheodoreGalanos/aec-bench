# ABOUTME: Constructs and scores the paired delayed-evidence station scenario.
# ABOUTME: Keeps treatment delivery, retrieval limits, and endpoint rules executable.

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.task_definition import ToolSpec
from aec_bench.contracts.world_interface import WorldInterfaceError
from aec_bench.contracts.world_session import (
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.experiments.retrieval_state_continuity.contracts import (
    PlannedTrial,
    StudyBlock,
    StudyManifest,
    StudyPhase,
    StudyPlan,
    Treatment,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationSchedule,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationStructuredHandover,
    create_structured_handover,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence import (
    RetrievalBudgetVector,
    TemporalEvidenceIntegrityError,
    TemporalRetrievalStateCarrier,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationWorldSession,
    PumpStationWorldSessionFactory,
)


@dataclass(frozen=True, slots=True)
class ScenarioScore:
    """Machine-scored endpoint and secondary retrieval measures for one run."""

    epistemic_decision_failure: bool
    material_evidence_acquired: bool
    material_evidence_used: bool
    stale_source_relied_on: bool
    conservative_action: bool
    search_call_count: int
    fetch_call_count: int
    visible_retrieval_bytes: int
    visible_retrieval_tokens: int


class ScenarioTools:
    """Bounded temporal tools plus the unchanged live station tool surface."""

    def __init__(self, session: PumpStationWorldSession, manifest: StudyManifest) -> None:
        self._session = session
        self._manifest = manifest
        self._post_handover_search_calls = 0
        self._fetch_calls = 0
        self._material_references: set[str] = set()
        self._reference_versions: dict[str, str] = {}
        self._material_fetched = False

    def __getattr__(self, name: str) -> Any:
        """Delegate non-retrieval tools to the bound live session."""

        return getattr(self._session, name)

    @property
    def native_tools(self) -> tuple[Any, ...]:
        """Return the session tools with retrieval calls guarded by study limits."""

        return tuple(
            self._agent_tool(
                self.search_evidence
                if name == "search_evidence"
                else self.fetch_evidence
                if name == "fetch_evidence"
                else getattr(self._session, name)
            )
            for name in self._session.result.tool_names
        )

    @property
    def tool_specs(self) -> tuple[ToolSpec, ...]:
        """Return the unchanged task-owned declarations shown to the model."""

        return self._session.tool_specs

    @property
    def total_search_calls(self) -> int:
        """Include the fixed pre-handover search in the conserved budget."""

        return 1 + self._post_handover_search_calls

    @property
    def fetch_calls(self) -> int:
        return self._fetch_calls

    @property
    def material_references(self) -> frozenset[str]:
        return frozenset(self._material_references)

    @property
    def reference_versions(self) -> dict[str, str]:
        return dict(self._reference_versions)

    @property
    def material_fetched(self) -> bool:
        return self._material_fetched

    @staticmethod
    def _agent_tool(function: Any) -> Any:
        """Return contract rejections as tool results so the agent can correct them."""

        @wraps(function)
        def guarded(*args: Any, **kwargs: Any) -> str:
            try:
                result = function(*args, **kwargs)
                if not isinstance(result, str):
                    raise TypeError("agent tool returned a non-string payload")
                return result
            except WorldInterfaceError as error:
                return json.dumps(
                    {
                        "status": "rejected",
                        "error_code": error.code,
                        "detail": error.detail,
                    },
                    sort_keys=True,
                )
            except ValueError as error:
                return json.dumps(
                    {
                        "status": "rejected",
                        "error_code": "study-tool-limit",
                        "detail": str(error),
                    },
                    sort_keys=True,
                )

        return guarded

    def search_evidence(
        self,
        request_id: str,
        query: str,
        scope: str = "all",
        limit: int = 5,
    ) -> str:
        """Search once after handover because the prefix already used one call."""

        if self.total_search_calls >= self._manifest.budget.maximum_search_calls:
            raise ValueError("study search-call budget is exhausted")
        if limit > self._manifest.budget.maximum_references_per_result:
            raise ValueError("study result-reference limit is exceeded")
        payload = self._session.search_evidence(request_id, query, scope, limit)
        self._post_handover_search_calls += 1
        parsed = json.loads(payload)
        for reference in parsed["receipt"].get("references", []):
            opaque = reference["opaque_reference"]
            version = reference["version_id"]
            self._reference_versions[opaque] = version
            if version == self._manifest.material_evidence_version_id:
                self._material_references.add(opaque)
        return payload

    def fetch_evidence(self, request_id: str, reference: str) -> str:
        """Fetch at most one reference under the fixed per-run budget."""

        if self._fetch_calls >= self._manifest.budget.maximum_fetch_calls:
            raise ValueError("study fetch-call budget is exhausted")
        payload = self._session.fetch_evidence(request_id, reference)
        self._fetch_calls += 1
        parsed = json.loads(payload)
        fetched = parsed["receipt"].get("fetched_content")
        if fetched is not None:
            version = fetched["version_id"]
            self._reference_versions[reference] = version
            if version == self._manifest.material_evidence_version_id:
                self._material_references.add(reference)
                self._material_fetched = True
        return payload


@dataclass(slots=True)
class PreparedTrialScenario:
    """One fresh tenure after exact base and retrieval carrier delivery."""

    manifest: StudyManifest
    plan: StudyPlan
    block: StudyBlock
    trial: PlannedTrial
    session: PumpStationWorldSession
    handover: PumpStationStructuredHandover
    carrier: TemporalRetrievalStateCarrier
    tools: ScenarioTools
    pre_handover_status: str
    shared_visible_input_sha256: str
    base_carrier_sha256: str
    treatment_projection_sha256: str | None
    initial_budget: RetrievalBudgetVector


def prepare_trial_scenario(
    root: Path,
    *,
    manifest: StudyManifest,
    plan: StudyPlan,
    block: StudyBlock,
    trial: PlannedTrial,
) -> PreparedTrialScenario:
    """Build one real durable prefix and install exactly one assigned carrier."""

    if manifest.phase is StudyPhase.ANALYSIS_FIXTURE:
        raise ValueError("real scenario requires shakedown or confirmatory authority")
    if plan.manifest_content_sha256 != manifest.content_sha256:
        raise ValueError("scenario plan does not belong to the manifest")
    if trial not in block.trials:
        raise ValueError("scenario trial does not belong to the block")
    destination = Path(root)
    if destination.exists():
        raise FileExistsError(f"trial world already exists: {destination}")

    initial_budget = _retrieval_budget(manifest)
    identity = block.block_id[-16:]
    source_request = _session_request(
        identity=identity,
        world_history_seed=block.world_history_seed,
        open_mode=WorldSessionOpenMode.START,
    )
    schedule = PumpStationSchedule(
        access_available_after_seconds=1_209_600,
        repair_kit_available_after_seconds=1_209_600,
        access_withdrawal_after_seconds=1_224_000,
        access_restored_after_seconds=1_238_400,
        decision_point_after_seconds=(
            manifest.evidence_available_at_seconds - manifest.pre_handover_world_time_seconds,
            manifest.decision_deadline_seconds - manifest.pre_handover_world_time_seconds,
        ),
    )
    source = PumpStationWorldSessionFactory(
        destination,
        schedule=schedule,
        temporal_evidence=True,
        temporal_budget=initial_budget,
    ).open(source_request)
    if source.run.state.physical.calendar_seconds != manifest.pre_handover_world_time_seconds:
        raise ValueError("trial prefix starts at the wrong world time")
    query = manifest.development_query_routes[
        manifest.world_history_seeds.index(block.world_history_seed) % len(manifest.development_query_routes)
    ]
    pre_handover = json.loads(
        source.search_evidence(
            request_id=f"prefix-search-{identity}",
            query=query,
            scope="condition",
            limit=manifest.budget.maximum_references_per_result,
        )
    )
    pre_handover_status = str(pre_handover["receipt"]["public_status"])
    if pre_handover_status != "NO_ACCESSIBLE_RESULT":
        raise ValueError("pre-handover material search was not unresolved")
    source.continue_operation(
        proposal_id=f"outgoing-advance-{identity}",
        reason="Advance the station to the declared handover decision point.",
    )
    if source.run.state.physical.calendar_seconds != manifest.evidence_available_at_seconds:
        raise ValueError("trial handover does not occur at the open decision point")

    recipient_request = _session_request(
        identity=identity,
        world_history_seed=block.world_history_seed,
        open_mode=WorldSessionOpenMode.RESUME,
        snapshot=source.result.snapshot,
    )
    complete_carrier = source.create_retrieval_handover(
        to_tenure_id=recipient_request.agent_tenure_id,
        to_session_id=recipient_request.session_id,
        include_fetched_content=False,
    )
    carrier = (
        complete_carrier
        if trial.treatment is Treatment.RETRIEVAL_STATE_PRESERVED
        else TemporalRetrievalStateCarrier(
            run_id=complete_carrier.run_id,
            episode_id=complete_carrier.episode_id,
            world_branch_id=complete_carrier.world_branch_id,
            from_agent_tenure_id=complete_carrier.from_agent_tenure_id,
            from_session_id=complete_carrier.from_session_id,
            to_agent_tenure_id=complete_carrier.to_agent_tenure_id,
            to_session_id=complete_carrier.to_session_id,
            created_at_seconds=complete_carrier.created_at_seconds,
            include_fetched_content=False,
            access_results=(),
            unresolved_search_ids=(),
            remaining_budget=complete_carrier.remaining_budget,
        )
    )
    recipient = PumpStationWorldSessionFactory(destination).open(recipient_request)
    handover = create_structured_handover(
        recipient.actor_view,
        from_tenure_id=source_request.agent_tenure_id,
        history=source.actor_history,
        maximum_history_entries=10,
    )
    recipient.install_structured_handover(handover)
    recipient.install_retrieval_handover(carrier)
    base_carrier_sha256 = canonical_content_sha256(
        {
            "handover_id": handover.handover_id,
            "current_view_id": handover.current_actor_view.view_id,
            "history": [item.transition_id for item in handover.history],
        }
    )
    shared_visible_input_sha256 = canonical_content_sha256(
        {
            "base_carrier_sha256": base_carrier_sha256,
            "current_state_id": recipient.result.snapshot.state_id,
            "event_schedule_sha256": recipient.event_schedule_sha256,
            "tool_names": recipient.result.tool_names,
            "remaining_budget": carrier.remaining_budget.model_dump(mode="json"),
            "prompt_id": manifest.model_execution.prompt_id if manifest.model_execution else None,
        }
    )
    treatment_projection_sha256 = (
        canonical_content_sha256(
            {
                "access_results": [item.model_dump(mode="json") for item in carrier.access_results],
                "unresolved_search_ids": carrier.unresolved_search_ids,
            }
        )
        if trial.treatment is Treatment.RETRIEVAL_STATE_PRESERVED
        else None
    )
    return PreparedTrialScenario(
        manifest=manifest,
        plan=plan,
        block=block,
        trial=trial,
        session=recipient,
        handover=handover,
        carrier=carrier,
        tools=ScenarioTools(recipient, manifest),
        pre_handover_status=pre_handover_status,
        shared_visible_input_sha256=shared_visible_input_sha256,
        base_carrier_sha256=base_carrier_sha256,
        treatment_projection_sha256=treatment_projection_sha256,
        initial_budget=initial_budget,
    )


def score_trial_scenario(prepared: PreparedTrialScenario) -> ScenarioScore:
    """Apply the sealed endpoint to durable actions and retrieval receipts."""

    chosen_proposal_id: str | None = None
    report_action = False
    for step in prepared.session.run.steps():
        proposal = step.proposal
        if proposal is None:
            continue
        pre_action_seconds = (
            step.transition.state.physical.calendar_seconds - step.transition.receipt.clock_delta_seconds
        )
        if not (
            prepared.manifest.evidence_available_at_seconds
            <= pre_action_seconds
            < prepared.manifest.decision_deadline_seconds
        ):
            continue
        history = next(
            item for item in prepared.session.actor_history if item.proposal_id == proposal.context.proposal_id
        )
        pump_id = getattr(proposal, "pump_id", None)
        report_action = (
            history.action_type == "request_condition_check"
            and history.execution in {"completed", "scheduled"}
            and pump_id == "pump-a"
        )
        chosen_proposal_id = proposal.context.proposal_id
        break

    relied_on: tuple[str, ...] = ()
    if chosen_proposal_id is not None:
        try:
            relied_on = prepared.session.load_evidence_reliance(chosen_proposal_id).relied_on_evidence_refs
        except (FileNotFoundError, TemporalEvidenceIntegrityError, ValueError):
            relied_on = ()
    material_used = bool(set(relied_on) & set(prepared.tools.material_references))
    conservative_action = report_action and material_used
    stale_source_relied_on = any(
        prepared.tools.reference_versions.get(reference) == "pump-a-maintenance-procedure.v1" for reference in relied_on
    )
    remaining = prepared.session.retrieval_state.remaining_budget
    return ScenarioScore(
        epistemic_decision_failure=not conservative_action,
        material_evidence_acquired=prepared.tools.material_fetched,
        material_evidence_used=material_used,
        stale_source_relied_on=stale_source_relied_on,
        conservative_action=conservative_action,
        search_call_count=prepared.tools.total_search_calls,
        fetch_call_count=prepared.tools.fetch_calls,
        visible_retrieval_bytes=(prepared.initial_budget.visible_bytes - remaining.visible_bytes),
        visible_retrieval_tokens=(prepared.initial_budget.visible_tokens - remaining.visible_tokens),
    )


def _retrieval_budget(manifest: StudyManifest) -> RetrievalBudgetVector:
    budget = manifest.budget
    return RetrievalBudgetVector(
        calls=budget.maximum_search_calls + budget.maximum_fetch_calls,
        returned_references=(budget.maximum_search_calls * budget.maximum_references_per_result),
        visible_bytes=budget.maximum_visible_bytes,
        visible_tokens=budget.maximum_visible_tokens,
        turns=budget.maximum_agent_turns,
        simulated_duration_seconds=budget.simulated_retrieval_duration_seconds,
        provider_spend_microusd=budget.external_retrieval_provider_spend_microusd,
    )


def _session_request(
    *,
    identity: str,
    world_history_seed: int,
    open_mode: WorldSessionOpenMode,
    snapshot: Any | None = None,
) -> WorldSessionRequest:
    incoming = open_mode is WorldSessionOpenMode.RESUME
    return WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=open_mode,
        session_id=(f"incoming-session-{identity}" if incoming else f"outgoing-session-{identity}"),
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id=(f"incoming-tenure-{identity}" if incoming else f"outgoing-tenure-{identity}"),
        run_id=f"run-{identity}",
        episode_id=f"episode-{identity}",
        world_branch_id=f"history-{world_history_seed}",
        start_snapshot=snapshot,
    )
