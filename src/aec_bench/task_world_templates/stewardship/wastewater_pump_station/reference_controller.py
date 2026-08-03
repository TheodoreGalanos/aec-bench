# ABOUTME: Runs the fixed pump-station reference journey through canonical world interfaces.
# ABOUTME: Returns durable registered snapshots, temporal access summaries, and semantic evaluation.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pydantic import JsonValue

from aec_bench.contracts.world_interface import WorldActorActionRequest, WorldActorActionResult
from aec_bench.evaluation.stewardship import PumpStationSemanticOutcome, pump_station_semantic_outcome
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_work import (
    PumpStationBacklogStatus,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.episode_runtime import (
    PumpStationEpisodeHost,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PUMP_STATION_BOUND_CONTROL_VERSION,
    PUMP_STATION_OPERATIONS_REVIEW_VERSION,
    PumpStationBoundControlRequest,
    PumpStationOperationsBoundaryReviewRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_control import (
    PumpStationWorldControl,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationStateSnapshotRef,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)

PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID = "pump-station-reference-system-controller.v1"
_OPERATIONS_AUTHORITY_ID = "operations-controller"

type PumpStationReferenceRun = PumpStationWorldRun
type PumpStationTemporalAccessSummary = tuple[str, str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class PumpStationReferenceControllerResult:
    """Durable result of one canonical pump-station reference journey."""

    controller_id: str
    run: PumpStationReferenceRun
    start_snapshot: PumpStationStateSnapshotRef
    end_snapshot: PumpStationStateSnapshotRef
    temporal_access: tuple[PumpStationTemporalAccessSummary, ...]
    semantic_outcome: PumpStationSemanticOutcome


def _act(
    host: PumpStationEpisodeHost,
    request_id: str,
    action_name: str,
    **arguments: object,
) -> WorldActorActionResult:
    observation = host.observe()
    if action_name not in {"search_evidence", "fetch_evidence"}:
        arguments = {
            "reason": f"Complete {request_id} under the current visible service and work plan.",
            **arguments,
        }
    return host.invoke(
        WorldActorActionRequest(
            request_id=request_id,
            decision_id=observation.decision_id,
            action_name=action_name,
            arguments=cast(dict[str, JsonValue], arguments),
        )
    )


def _continue_to(host: PumpStationEpisodeHost, run: PumpStationReferenceRun, target: int) -> None:
    while run.state.calendar_seconds < target:
        _act(
            host,
            f"continue-{run.snapshot().sequence + 1}",
            "continue_operation",
        )
    if run.state.calendar_seconds != target:
        raise RuntimeError(f"reference controller passed target time {target}")


def _item_id(run: PumpStationReferenceRun, rule_id: str, target_id: str) -> str:
    matching = tuple(
        item.item_id
        for item in run.state.backlog
        if item.generation_rule_id == rule_id
        and item.target_id == target_id
        and item.status in {PumpStationBacklogStatus.OPEN, PumpStationBacklogStatus.PLANNED}
    )
    if len(matching) != 1:
        raise RuntimeError(f"reference work selection differs for {rule_id} and {target_id}")
    return matching[0]


def _review(
    control: PumpStationWorldControl,
    run: PumpStationReferenceRun,
    *,
    review_id: str,
    review_kind: str,
    pump_id: str,
    boundary_id: str,
    evidence_id: str,
) -> None:
    snapshot = run.snapshot()
    review = PumpStationOperationsBoundaryReviewRequest(
        version=PUMP_STATION_OPERATIONS_REVIEW_VERSION,
        review_id=review_id,
        review_kind=review_kind,
        pump_id=pump_id,
        restriction_or_isolation_permit_id=boundary_id,
        accepted_evidence_id=evidence_id,
        requested_outcome="release",
        base_state_id=snapshot.state_id,
        operations_authority_id=_OPERATIONS_AUTHORITY_ID,
        reason="Release only the matched boundary after the accepted evidence.",
    )
    control.execute(
        PumpStationBoundControlRequest(
            control_envelope_version=PUMP_STATION_BOUND_CONTROL_VERSION,
            request_id=review_id,
            run_id=snapshot.run_id,
            episode_id=snapshot.episode_id,
            world_branch_id=snapshot.world_branch_id,
            base_state_id=snapshot.state_id,
            base_commit_id=snapshot.commit_id,
            based_on_sequence=snapshot.sequence,
            control=review,
        )
    )


def _temporal_summary(result: WorldActorActionResult) -> PumpStationTemporalAccessSummary:
    references = result.task_receipt.get("references")
    versions = (
        tuple(
            str(item["version_id"])
            for item in references
            if isinstance(item, dict) and isinstance(item.get("version_id"), str)
        )
        if isinstance(references, list)
        else ()
    )
    fetched = result.task_receipt.get("fetched_content")
    if isinstance(fetched, dict) and isinstance(fetched.get("version_id"), str):
        versions = (str(fetched["version_id"]),)
    return result.action_name, result.status, versions


def _opaque_reference(result: WorldActorActionResult) -> str:
    references = result.task_receipt.get("references")
    if not isinstance(references, list) or len(references) != 1:
        raise RuntimeError("reference temporal search did not return one reference")
    reference = references[0]
    opaque_reference = reference.get("opaque_reference") if isinstance(reference, dict) else None
    if not isinstance(opaque_reference, str):
        raise RuntimeError("reference temporal search returned an invalid reference")
    return opaque_reference


def run_pump_station_reference_controller(
    repository_root: Path,
    run_id: str,
    episode_id: str,
    world_branch_id: str,
) -> PumpStationReferenceControllerResult:
    """Run the fixed Day 0 to Day 2 journey through registered world surfaces."""
    run = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(repository_root),
        run_id=run_id,
        episode_id=episode_id,
        world_branch_id=world_branch_id,
    )
    start_snapshot = run.snapshot()
    host = PumpStationEpisodeHost(repository_root)
    control = PumpStationWorldControl(
        repository_root,
        authorised_principal_ids=(_OPERATIONS_AUTHORITY_ID,),
    )

    _act(
        host,
        "a-verification",
        "request_post_maintenance_verification",
        pump_id="pump-a",
        backlog_item_id="backlog-a-verification-001",
    )
    _continue_to(host, run, 50_400)
    _review(
        control,
        run,
        review_id="operations-review-a-001",
        review_kind="post_verification_restriction",
        pump_id="pump-a",
        boundary_id="restriction-a-run-in-001",
        evidence_id="evidence-pump-a-verification-pass-001",
    )
    _continue_to(host, run, 64_800)
    _act(host, "assign-a-c", "request_duty_assignment", ordered_pump_ids=["pump-a", "pump-c"])
    _continue_to(host, run, 93_600)

    before = _act(host, "search-ccr28h-before", "search_evidence", query="CCR28H", scope="operations", limit=1)
    _continue_to(host, run, 100_800)
    after = _act(host, "search-ccr28h-after", "search_evidence", query="CCR28H", scope="operations", limit=1)
    fetched = _act(host, "fetch-ccr28h", "fetch_evidence", reference=_opaque_reference(after))
    temporal_access = tuple(_temporal_summary(item) for item in (before, after, fetched))

    _continue_to(host, run, 108_000)
    _act(
        host,
        "b-clearance",
        "request_obstruction_clearance",
        pump_id="pump-b",
        backlog_item_id="backlog-b-clearance-001",
        inspection_evidence_id="initial-b-inspection-accepted",
    )
    _continue_to(host, run, 122_400)
    _act(
        host,
        "b-functional",
        "request_functional_check",
        pump_id="pump-b",
        backlog_item_id=_item_id(run, "WG-03", "pump-b"),
    )
    _continue_to(host, run, 126_000)
    _act(
        host,
        "b-provisional-return",
        "request_provisional_return",
        pump_id="pump-b",
        functional_check_evidence_id="evidence-b-functional-check-pass-001",
    )
    _act(host, "b-provisional-closure", "request_provisional_closure", work_order_id="work-order-b-001")
    _act(
        host,
        "b-verification",
        "request_post_maintenance_verification",
        pump_id="pump-b",
        backlog_item_id=_item_id(run, "WG-04", "pump-b"),
    )
    _continue_to(host, run, 154_800)
    _review(
        control,
        run,
        review_id="operations-review-b-001",
        review_kind="post_verification_restriction",
        pump_id="pump-b",
        boundary_id="restriction-pump-b-run-in-001",
        evidence_id="evidence-pump-b-verification-pass-001",
    )
    _continue_to(host, run, 194_400)
    _act(host, "assign-a-b", "request_duty_assignment", ordered_pump_ids=["pump-a", "pump-b"])
    _act(
        host,
        "c-inspection",
        "request_inspection",
        pump_id="pump-c",
        backlog_item_id=_item_id(run, "WG-07", "pump-c"),
    )
    _continue_to(host, run, 223_200)
    _review(
        control,
        run,
        review_id="operations-review-c-001",
        review_kind="post_inspection_isolation",
        pump_id="pump-c",
        boundary_id="isolation-pump-c-c-inspection",
        evidence_id="evidence-c-inspection-no-finding-001",
    )

    end_snapshot = run.snapshot()
    return PumpStationReferenceControllerResult(
        controller_id=PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
        run=run,
        start_snapshot=start_snapshot,
        end_snapshot=end_snapshot,
        temporal_access=temporal_access,
        semantic_outcome=pump_station_semantic_outcome(run, temporal_access=temporal_access),
    )
