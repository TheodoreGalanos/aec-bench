# ABOUTME: Tests version 3 evidence-health publication and earlier byte preservation.
# ABOUTME: Covers coherent record versions, strict reload, and version 2 migration lineage.

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rich_work_support import rich_work_schedule
from world_run_support import create_world_run

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    PUMP_STATION_AUTHORITY_POLICY_VERSION_V3,
    PUMP_STATION_RECEIPT_VERSION_V3,
    PUMP_STATION_RECORD_VERSIONS_V2,
    PUMP_STATION_RECORD_VERSIONS_V3,
    PUMP_STATION_SNAPSHOT_VERSION_V3,
    PUMP_STATION_STATE_VERSION_V3,
    PUMP_STATION_TRANSITION_RULE_VERSION_V3,
    PumpStationProjectionContext,
    PumpStationStewardshipState,
    PumpStationWorldRun,
    PumpStationWorldRunRepository,
    create_rich_work_reference_state,
    load_pump_station_artifact,
    load_reference_package,
    project_actor_view,
    pump_station_artifact_bytes,
    pump_station_model_from_package,
)


def test_version_one_and_two_state_bytes_remain_exact(tmp_path: Path) -> None:
    version_one = create_world_run(tmp_path / "version-one")
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    version_two_state = create_rich_work_reference_state(
        model,
        schedule=rich_work_schedule(model),
    )

    version_one_payload = pump_station_artifact_bytes(version_one.state)
    version_two_payload = pump_station_artifact_bytes(version_two_state)

    assert len(version_one_payload) == 1_307
    assert hashlib.sha256(version_one_payload).hexdigest() == (
        "02d23448e3a3dc3448ee28a27131d155b8354d09678f4311f61bb63b9902a815"
    )
    assert len(version_two_payload) == 4_935
    assert hashlib.sha256(version_two_payload).hexdigest() == (
        "0e95b0253c48409da4ee5b7b17f83f6422780b6dbae5ab827154aff5d04d57a2"
    )


def test_version_three_state_uses_its_complete_profile(tmp_path: Path) -> None:
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    version_two_state = create_rich_work_reference_state(
        model,
        schedule=rich_work_schedule(model),
    )
    version_three_state = PumpStationStewardshipState(
        physical=version_two_state.physical,
        environment=version_two_state.environment,
        sequence=version_two_state.sequence,
        resources=version_two_state.resources,
        restrictions=version_two_state.restrictions,
        obligations=version_two_state.obligations,
        work_orders=version_two_state.work_orders,
        processes=version_two_state.processes,
        evidence=version_two_state.evidence,
        scheduled_events=version_two_state.scheduled_events,
        state_version=PUMP_STATION_STATE_VERSION_V3,
        dependencies=version_two_state.dependencies,
        dependency_waivers=version_two_state.dependency_waivers,
        resource_reservations=version_two_state.resource_reservations,
        evidence_sources=(),
        evidence_treatments=(),
        pending_evidence=(),
    )

    payload = pump_station_artifact_bytes(version_three_state)
    document = json.loads(payload)
    run = PumpStationWorldRun.create(
        repository=PumpStationWorldRunRepository(tmp_path / "run-v3"),
        package=package,
        model=model,
        initial_state=version_three_state,
        run_id="run-v3",
        episode_id="episode-v3",
        world_branch_id="branch-v3",
        record_versions=PUMP_STATION_RECORD_VERSIONS_V3,
    )

    assert document["state_version"] == PUMP_STATION_STATE_VERSION_V3
    assert document["evidence_sources"] == []
    assert document["evidence_treatments"] == []
    assert document["pending_evidence"] == []
    assert load_pump_station_artifact(payload, PumpStationStewardshipState) == version_three_state
    assert run.snapshot().snapshot_version == PUMP_STATION_SNAPSHOT_VERSION_V3
    assert run.manifest.receipt_version == PUMP_STATION_RECEIPT_VERSION_V3
    assert run.manifest.authority_policy_version == PUMP_STATION_AUTHORITY_POLICY_VERSION_V3
    assert run.manifest.transition_rule_version == PUMP_STATION_TRANSITION_RULE_VERSION_V3


def test_version_two_migrates_to_version_three_with_exact_lineage(
    tmp_path: Path,
) -> None:
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    source = PumpStationWorldRun.create(
        repository=PumpStationWorldRunRepository(tmp_path / "source-v2"),
        package=package,
        model=model,
        initial_state=create_rich_work_reference_state(
            model,
            schedule=rich_work_schedule(model),
        ),
        run_id="run-v2-source",
        episode_id="episode-evidence-health",
        world_branch_id="branch-v2-source",
        record_versions=PUMP_STATION_RECORD_VERSIONS_V2,
    )

    migrated = source.migrate_to_v3(
        repository=PumpStationWorldRunRepository(tmp_path / "target-v3"),
        run_id="run-v3-target",
        world_branch_id="branch-v3-target",
    )
    lineage = migrated.repository.load_migration()

    assert migrated.state.state_version == PUMP_STATION_STATE_VERSION_V3
    assert migrated.manifest.record_versions == PUMP_STATION_RECORD_VERSIONS_V3
    assert lineage.source_state_id == source.snapshot().state_id
    assert lineage.target_state_id == migrated.snapshot().state_id
    assert lineage.source_snapshot_version.endswith(".v2")
    assert lineage.target_snapshot_version.endswith(".v3")

    actor_view = project_actor_view(
        model,
        migrated.state,
        PumpStationProjectionContext(
            episode_id=migrated.manifest.episode_id,
            world_branch_id=migrated.manifest.world_branch_id,
            actor_id="operations-actor",
            agent_tenure_id="tenure-after-migration",
            episode_started_at_seconds=0,
            tenure_started_at_seconds=migrated.state.physical.calendar_seconds,
            projection_policy_id="pump-station-projection.v3",
            source_artifact_ids=(migrated.manifest.package_content_id,),
        ),
    )

    assert migrated.state.evidence_sources
    assert all(item.health is not None for item in migrated.state.evidence)
    assert actor_view.current_state.observation_source is not None
