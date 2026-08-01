# ABOUTME: Integration-tests version-1 preservation and version-2 rich-work publication.
# ABOUTME: Covers migration lineage, durable replay, views, handover, and unknown versions.

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest
from rich_work_support import apply_bound, latest_process, rich_work_schedule
from world_run_support import bind_proposal, create_world_run

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    PUMP_STATION_AUTHORITY_POLICY_VERSION_V2,
    PUMP_STATION_RECEIPT_VERSION_V2,
    PUMP_STATION_RECORD_VERSIONS_V2,
    PUMP_STATION_SNAPSHOT_VERSION_V2,
    PUMP_STATION_STATE_VERSION_V1,
    PUMP_STATION_STATE_VERSION_V2,
    PUMP_STATION_TRANSITION_RULE_VERSION_V2,
    ContinueOperation,
    PumpStationProcessKind,
    PumpStationProcessStatus,
    PumpStationProjectionContext,
    PumpStationWorldRun,
    PumpStationWorldRunError,
    PumpStationWorldRunRepository,
    RequestInspection,
    TransferDuty,
    advance_to_next_decision_point,
    create_rich_work_reference_state,
    create_structured_handover,
    load_reference_package,
    project_actor_view,
    pump_station_artifact_bytes,
    pump_station_model_from_package,
    verify_stewardship_run,
)


def _all_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != ".world-run.lock"
    }


def test_version_one_bytes_reload_and_migrate_without_change(tmp_path: Path) -> None:
    source = create_world_run(tmp_path / "source-v1")
    source_payload = pump_station_artifact_bytes(source.state)
    source_state_id = source.snapshot().state_id
    before = _all_bytes(source.repository.root)

    migrated = source.migrate_to_v2(
        repository=PumpStationWorldRunRepository(tmp_path / "target-v2"),
        run_id="run-rich-v2",
        world_branch_id="branch-rich-v2",
    )
    repeated = source.migrate_to_v2(
        repository=PumpStationWorldRunRepository(tmp_path / "target-v2-repeat"),
        run_id="run-rich-v2-repeat",
        world_branch_id="branch-rich-v2-repeat",
    )
    migration = migrated.repository.load_migration()

    assert source.state.state_version == PUMP_STATION_STATE_VERSION_V1
    assert len(source_payload) == 1307
    assert hashlib.sha256(source_payload).hexdigest() == (
        "02d23448e3a3dc3448ee28a27131d155b8354d09678f4311f61bb63b9902a815"
    )
    assert source_state_id == "42b3d784e5dce3a37f296491835cefc90c3d80aded40ffc6cf4863dc374306ff"
    assert _all_bytes(source.repository.root) == before
    assert (
        PumpStationWorldRun.resume(
            repository=source.repository,
            package=source.package,
            model=source.model,
            snapshot=source.snapshot(),
        ).state
        == source.state
    )

    assert migrated.state.state_version == PUMP_STATION_STATE_VERSION_V2
    assert migrated.manifest.snapshot_version == PUMP_STATION_SNAPSHOT_VERSION_V2
    assert migrated.manifest.receipt_version == PUMP_STATION_RECEIPT_VERSION_V2
    assert migrated.manifest.authority_policy_version == (PUMP_STATION_AUTHORITY_POLICY_VERSION_V2)
    assert migrated.manifest.transition_rule_version == (PUMP_STATION_TRANSITION_RULE_VERSION_V2)
    assert migration.source_run_id == source.manifest.run_id
    assert migration.source_state_id == source.snapshot().state_id
    assert migration.target_state_id == migrated.snapshot().state_id
    assert migration.target_snapshot_version == PUMP_STATION_SNAPSHOT_VERSION_V2
    assert repeated.snapshot().state_id == migrated.snapshot().state_id
    assert pump_station_artifact_bytes(repeated.state) == pump_station_artifact_bytes(
        migrated.state,
    )


def test_version_two_publication_replays_and_recovers_staged_work(
    tmp_path: Path,
) -> None:
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    initial = create_rich_work_reference_state(
        model,
        schedule=rich_work_schedule(model),
    )
    run = PumpStationWorldRun.create(
        repository=PumpStationWorldRunRepository(tmp_path / "run-v2"),
        package=package,
        model=model,
        initial_state=initial,
        run_id="run-v2",
        episode_id="episode-v2",
        world_branch_id="branch-v2",
        record_versions=PUMP_STATION_RECORD_VERSIONS_V2,
    )
    proposal, information_set = bind_proposal(
        run,
        ContinueOperation,
        "proposal-resource-arrival",
    )

    staged = run.stage(proposal, information_set=information_set)
    assert run.snapshot() == staged.prior_snapshot

    recovered = PumpStationWorldRun.resume(
        repository=run.repository,
        package=package,
        model=model,
        snapshot=run.snapshot(),
    )
    published = recovered.repository.publish_staged_transition(staged)
    verification = verify_stewardship_run(
        model,
        initial,
        recovered.steps(),
        record_versions=PUMP_STATION_RECORD_VERSIONS_V2,
    )

    assert recovered.state == published.state
    assert published.receipt.receipt_version == PUMP_STATION_RECEIPT_VERSION_V2
    assert verification.valid is True


def test_suspended_process_and_parent_child_limit_survive_handover() -> None:
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    state = create_rich_work_reference_state(
        model,
        schedule=rich_work_schedule(model),
    )
    state = advance_to_next_decision_point(model, state).state
    state = apply_bound(model, state, TransferDuty, "proposal-transfer").state
    state = apply_bound(
        model,
        state,
        RequestInspection,
        "proposal-inspection",
        pump_id="pump-b",
    ).state
    state = advance_to_next_decision_point(model, state).state
    suspended = latest_process(state, PumpStationProcessKind.INSPECTION, "pump-b")

    first_view = project_actor_view(
        model,
        state,
        PumpStationProjectionContext(
            episode_id="episode-rich",
            world_branch_id="branch-rich",
            actor_id="station-steward",
            agent_tenure_id="tenure-1",
            episode_started_at_seconds=state.physical.calendar_seconds - 1,
            tenure_started_at_seconds=state.physical.calendar_seconds - 1,
            projection_policy_id="pump-station-current-state.v2",
            source_artifact_ids=(
                package.package_content_id,
                package.manifest_content_id,
            ),
        ),
    )
    recipient_view = replace(
        first_view,
        view_id="recipient-view",
        agent_tenure_id="tenure-2",
    )
    handover = create_structured_handover(
        recipient_view,
        from_tenure_id="tenure-1",
        history=(),
        maximum_history_entries=8,
    )
    visible_process = next(
        item for item in handover.current_actor_view.current_state.processes if item.process_id == suspended.process_id
    )
    child = next(
        item
        for item in handover.current_actor_view.current_state.restrictions
        if item.parent_restriction_id is not None
    )

    assert visible_process.status is PumpStationProcessStatus.SUSPENDED
    assert any(
        item.restriction_id == child.parent_restriction_id
        for item in handover.current_actor_view.current_state.restrictions
    )
    assert handover.current_actor_view.current_state.dependencies


def test_unknown_version_fails_before_state_change(tmp_path: Path) -> None:
    run = create_world_run(tmp_path / "run")
    with pytest.raises(PumpStationWorldRunError, match="snapshot-version"):
        replace(
            run.manifest,
            snapshot_version="pump-station-state-snapshot.unknown",
        )
    with pytest.raises(PumpStationWorldRunError, match="receipt-version"):
        replace(
            run.manifest,
            receipt_version="pump-station-transition-receipt.unknown",
        )
    with pytest.raises(PumpStationWorldRunError, match="authority-policy-version"):
        replace(
            run.manifest,
            authority_policy_version="pump-station-authority-policy.unknown",
        )
    with pytest.raises(PumpStationWorldRunError, match="transition-rule-version"):
        replace(
            run.manifest,
            transition_rule_version="pump-station-transition-rule.unknown",
        )
