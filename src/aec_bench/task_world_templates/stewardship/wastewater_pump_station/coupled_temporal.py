# ABOUTME: Binds ASW-8 actor evidence tools to one verified durable temporal repository.
# ABOUTME: Creates root evidence atomically and keeps child retrieval state branch-local.

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.actor_interface import (
    PUMP_STATION_ACTOR_ACTION_NAMES_V2,
    PUMP_STATION_ACTOR_INTERFACE_VERSION_V2,
    TemporalEvidenceFetchArguments,
    TemporalEvidenceSearchArguments,
    pump_station_actor_capabilities_v2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_run import (
    PumpStationCoupledRun,
    PumpStationCoupledRunRepository,
    create_coupled_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
    project_coupled_actor_view,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    REFERENCE_PROFILE_V2,
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    stewardship_content_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.access_models import (
    TemporalAccessContext,
    TemporalAccessPublication,
    TemporalActorVisibleEvent,
    TemporalEvidenceAccessKind,
    TemporalEvidenceAccessResult,
    TemporalInformationSetManifest,
    temporal_actor_event_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.corpus import (
    build_asw_8_reference_temporal_evidence_bundle,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.gateway import (
    TemporalEvidenceGateway,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.models import (
    TemporalEvidenceBundle,
    TemporalEvidenceIntegrityError,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.repository import (
    TemporalEvidenceRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.verification import (
    verify_temporal_evidence_repository,
)

_TASK_WORLD_ID = "wastewater-pump-station-stewardship.v1"
_ACTOR_ID = "station-steward"
_ACTOR_ROLE = "station-steward"


def create_coupled_root_with_temporal_repository(
    run_root: Path,
    *,
    run_id: str,
    world_branch_id: str,
) -> PumpStationCoupledRun:
    """Publish one actor-ready root only after world and temporal evidence agree."""
    destination = Path(run_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"ASW-8 run output exists: {destination}")
    staging = destination.parent / f".{destination.name}.{uuid.uuid4().hex}.staging"
    run = create_coupled_run(run_id=run_id, world_branch_id=world_branch_id)
    PumpStationCoupledRunRepository(staging).create(run)
    initialize_coupled_temporal_repository(staging, run)
    os.replace(staging, destination)
    return PumpStationCoupledRunRepository(destination).open()


def initialize_coupled_temporal_repository(
    run_root: Path,
    run: PumpStationCoupledRun,
) -> TemporalEvidenceBundle:
    """Create and verify the descriptor-selected root temporal repository."""
    if run.manifest.initial_state_source.kind != "reference_system_specification":
        raise TemporalEvidenceIntegrityError("rollout children must inherit the parent temporal repository")
    package = load_reference_package(profile_id=REFERENCE_PROFILE_V2)
    bundle = build_asw_8_reference_temporal_evidence_bundle(
        package,
        world_branch_id=run.manifest.world_branch_id,
    )
    repository = TemporalEvidenceRepository(Path(run_root) / "temporal-evidence")
    loaded = repository.initialize(bundle, package=package)
    _require_manifest_temporal_bindings(run, loaded)
    report = verify_temporal_evidence_repository(repository, package=package)
    if not report.valid:
        raise TemporalEvidenceIntegrityError("ASW-8 temporal repository did not pass independent verification")
    return loaded


def copy_coupled_child_temporal_repository(
    *,
    parent_run_root: Path,
    child_run_root: Path,
    parent: PumpStationCoupledRun,
    child: PumpStationCoupledRun,
) -> TemporalEvidenceBundle:
    """Copy only immutable parent-public evidence into one fresh child ledger."""
    parent_repository, parent_bundle = verify_coupled_temporal_repository(
        parent_run_root,
        parent,
    )
    destination = Path(child_run_root) / "temporal-evidence"
    if destination.exists():
        child_repository, child_bundle = verify_coupled_temporal_repository(
            child_run_root,
            child,
        )
        if child_bundle != parent_bundle:
            raise TemporalEvidenceIntegrityError("ASW-8 child temporal bundle differs from its parent")
        if (child_repository.root / "private").exists():
            raise TemporalEvidenceIntegrityError("ASW-8 child inherited parent-private temporal evidence")
        return child_bundle
    staging = destination.parent / f".{destination.name}.{uuid.uuid4().hex}.staging"
    try:
        staging.mkdir(parents=True)
        shutil.copy2(
            parent_repository.root / "capability.json",
            staging / "capability.json",
        )
        shutil.copytree(parent_repository.root / "corpus", staging / "corpus")
        shutil.copytree(parent_repository.root / "policies", staging / "policies")
        os.replace(staging, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    child_repository, child_bundle = verify_coupled_temporal_repository(
        child_run_root,
        child,
    )
    if child_bundle != parent_bundle:
        raise TemporalEvidenceIntegrityError("ASW-8 child temporal bundle differs from its parent")
    if (child_repository.root / "private").exists():
        raise TemporalEvidenceIntegrityError("ASW-8 child inherited parent-private temporal evidence")
    return child_bundle


def verify_coupled_temporal_repository(
    run_root: Path,
    run: PumpStationCoupledRun,
) -> tuple[TemporalEvidenceRepository, TemporalEvidenceBundle]:
    """Reload the required repository and compare it with immutable run metadata."""
    package = load_reference_package(profile_id=REFERENCE_PROFILE_V2)
    repository = TemporalEvidenceRepository(Path(run_root) / "temporal-evidence")
    bundle = repository.load_bundle(package=package)
    _require_manifest_temporal_bindings(run, bundle)
    report = verify_temporal_evidence_repository(repository, package=package)
    if not report.valid:
        raise TemporalEvidenceIntegrityError("ASW-8 temporal repository did not pass independent verification")
    pump_station_actor_capabilities_v2(
        task_world_id=_TASK_WORLD_ID,
        temporal_repository_verified=True,
    )
    return repository, bundle


def execute_coupled_temporal_action(
    *,
    run_root: Path,
    run: PumpStationCoupledRun,
    request_id: str,
    action_name: str,
    arguments: dict[str, Any],
    agent_tenure_id: str,
    session_id: str,
) -> TemporalEvidenceAccessResult:
    """Execute one v2 search or fetch without mutating physical world state."""
    repository, bundle = verify_coupled_temporal_repository(run_root, run)
    base_view_id = stewardship_content_id(
        project_coupled_actor_view(run.state),
        record_profile="v4",
    )
    current = repository.load_current_information_set_for_session(
        run_id=run.manifest.run_id,
        session_id=session_id,
        agent_tenure_id=agent_tenure_id,
    )
    prior_information_set_id = (
        current.information_set_id
        if current is not None
        else stewardship_content_id(
            {
                "kind": "asw-8-initial-information-set",
                "run_id": run.manifest.run_id,
                "agent_tenure_id": agent_tenure_id,
                "session_id": session_id,
                "base_view_id": base_view_id,
            },
            record_profile="v4",
        )
    )
    context = TemporalAccessContext(
        run_id=run.manifest.run_id,
        episode_id=run.manifest.episode_id,
        world_instance_id=run.manifest.run_id,
        world_branch_id=run.manifest.world_branch_id,
        world_state_id=run.state.state_id,
        world_commit_id=run.state.state_id,
        world_sequence=run.state.sequence,
        world_time_seconds=run.state.calendar_seconds,
        actor_id=_ACTOR_ID,
        actor_role=_ACTOR_ROLE,
        agent_tenure_id=agent_tenure_id,
        session_id=session_id,
        base_view_id=base_view_id,
        prior_information_set_id=prior_information_set_id,
        tool_contract_id=PUMP_STATION_ACTOR_INTERFACE_VERSION_V2,
        branch_ancestor_ids=run.manifest.initial_state_source.ancestor_branch_ids,
    )
    if repository.has_access(request_id):
        publication = repository.recover_access(request_id, context=context)
        _require_matching_retry(publication, action_name=action_name, arguments=arguments)
        return publication.decision.result

    state = repository.open_retrieval_state(context)
    event_id = temporal_actor_event_id(
        request_id=request_id,
        access_sequence=state.state_sequence + 1,
        context=context,
    )
    history = current.observation_history_view_ids if current is not None else ()
    if not history or history[-1] != base_view_id:
        history = (*history, base_view_id)
    visible_material_ids = current.visible_material_ids if current is not None else ()
    if event_id not in visible_material_ids:
        visible_material_ids = (*visible_material_ids, event_id)
    information_set_id = stewardship_content_id(
        {
            "kind": "asw-8-temporal-information-set",
            "prior_information_set_id": prior_information_set_id,
            "base_view_id": base_view_id,
            "event_id": event_id,
        },
        record_profile="v4",
    )
    information_set = TemporalInformationSetManifest(
        information_set_id=information_set_id,
        base_view_id=base_view_id,
        agent_tenure_id=agent_tenure_id,
        tenure_started_at_seconds=(
            current.tenure_started_at_seconds if current is not None else run.state.calendar_seconds
        ),
        observation_history_view_ids=history,
        continuity_carrier="pump-station-coupled-continuity.v1",
        workspace_tool_ids=PUMP_STATION_ACTOR_ACTION_NAMES_V2,
        visible_material_ids=visible_material_ids,
    )
    gateway = TemporalEvidenceGateway(bundle)
    if action_name == "search_evidence":
        search_arguments = TemporalEvidenceSearchArguments.model_validate(arguments)
        decision = gateway.search(
            request_id=request_id,
            query=search_arguments.query,
            scope=search_arguments.scope,
            limit=search_arguments.limit,
            context=context,
            state=state,
            resulting_information_set_id=information_set_id,
        )
    elif action_name == "fetch_evidence":
        fetch_arguments = TemporalEvidenceFetchArguments.model_validate(arguments)
        decision = gateway.fetch(
            request_id=request_id,
            reference=fetch_arguments.reference,
            context=context,
            state=state,
            resulting_information_set_id=information_set_id,
        )
    else:
        raise ValueError(f"unsupported ASW-8 temporal action: {action_name}")
    publication = repository.commit_access(
        TemporalAccessPublication(
            decision=decision,
            event=TemporalActorVisibleEvent(
                event_id=event_id,
                event_sequence=decision.result.access_sequence,
                actor_id=_ACTOR_ID,
                agent_tenure_id=agent_tenure_id,
                session_id=session_id,
                operation=decision.result.operation,
                access_result_id=decision.result.content_sha256,
                public_status=decision.result.public_status,
                information_set_id=information_set_id,
            ),
            information_set=information_set,
        ),
        context=context,
    )
    repository.publish_current_information_set(context, publication.information_set)
    return publication.decision.result


def _require_manifest_temporal_bindings(
    run: PumpStationCoupledRun,
    bundle: TemporalEvidenceBundle,
) -> None:
    observed = (
        bundle.content_sha256,
        bundle.corpus_manifest.content_sha256,
        bundle.capability.content_sha256,
    )
    expected = (
        run.manifest.temporal_bundle_content_id,
        run.manifest.temporal_corpus_content_id,
        run.manifest.temporal_capability_content_id,
    )
    if observed != expected:
        raise TemporalEvidenceIntegrityError("ASW-8 temporal bundle differs from immutable world-run metadata")


def _require_matching_retry(
    publication: TemporalAccessPublication,
    *,
    action_name: str,
    arguments: dict[str, Any],
) -> None:
    receipt = publication.decision.receipt
    matches = (
        action_name == "search_evidence"
        and publication.decision.result.operation is TemporalEvidenceAccessKind.SEARCH
        and receipt.original_query == arguments.get("query")
        and receipt.requested_scope == arguments.get("scope", "all")
        and receipt.requested_limit == arguments.get("limit", 5)
    ) or (
        action_name == "fetch_evidence"
        and publication.decision.result.operation is TemporalEvidenceAccessKind.FETCH
        and receipt.requested_reference == arguments.get("reference")
    )
    if not matches:
        raise TemporalEvidenceIntegrityError("temporal access request id is already bound to different arguments")


__all__ = (
    "copy_coupled_child_temporal_repository",
    "create_coupled_root_with_temporal_repository",
    "execute_coupled_temporal_action",
    "initialize_coupled_temporal_repository",
    "verify_coupled_temporal_repository",
)
