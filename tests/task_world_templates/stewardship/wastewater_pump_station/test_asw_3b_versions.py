# ABOUTME: Defines the ASW-3B snapshot, serializer, rule, and receipt version contract.
# ABOUTME: Proves every unsupported durable version fails before it can become authority.

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.contracts.world_session import (
    STEWARDSHIP_STATE_SNAPSHOT_SCHEMA_VERSION,
    StewardshipStateSnapshotRef,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    PUMP_STATION_AUTHORITY_POLICY_VERSION,
    PUMP_STATION_RECEIPT_VERSION,
    PUMP_STATION_SERIALIZATION_VERSION,
    PUMP_STATION_SNAPSHOT_VERSION,
    PUMP_STATION_TRANSITION_RULE_VERSION,
    PumpStationProposalError,
    PumpStationWorldRunError,
    RequestConditionalDeferral,
    load_pump_station_artifact,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationCurrentRunPointer,
)
from tests.task_world_templates.stewardship.wastewater_pump_station.world_run_support import (
    bind_proposal,
    create_world_run,
)


def test_snapshot_versions_are_explicit_and_fail_closed(tmp_path: Path) -> None:
    run = create_world_run(tmp_path / "run")
    snapshot = run.snapshot()

    assert snapshot.snapshot_version == PUMP_STATION_SNAPSHOT_VERSION
    with pytest.raises(PumpStationWorldRunError, match="snapshot-version"):
        replace(snapshot, snapshot_version="pump-station-state-snapshot.unknown")

    host_snapshot = StewardshipStateSnapshotRef(
        schema_version=STEWARDSHIP_STATE_SNAPSHOT_SCHEMA_VERSION,
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        sequence=snapshot.sequence,
        state_id=snapshot.state_id,
        commit_id=snapshot.commit_id,
    )
    hostile_payload = host_snapshot.model_dump(mode="json")
    hostile_payload["schema_version"] = "aecbench.stewardship-state-snapshot.unknown"

    with pytest.raises(ValidationError, match="unsupported stewardship snapshot schema version"):
        StewardshipStateSnapshotRef.model_validate(hostile_payload)


def test_run_artifact_versions_are_explicit_and_fail_closed(tmp_path: Path) -> None:
    run = create_world_run(tmp_path / "run")
    manifest = run.manifest
    initial_commit = run.repository.commits()[0]
    current_pointer = load_pump_station_artifact(
        (run.repository.root / "current.json").read_bytes(),
        PumpStationCurrentRunPointer,
    )

    assert manifest.serialization_version == PUMP_STATION_SERIALIZATION_VERSION
    assert manifest.snapshot_version == PUMP_STATION_SNAPSHOT_VERSION
    assert manifest.receipt_version == PUMP_STATION_RECEIPT_VERSION
    assert manifest.authority_policy_version == PUMP_STATION_AUTHORITY_POLICY_VERSION
    assert manifest.transition_rule_version == PUMP_STATION_TRANSITION_RULE_VERSION

    with pytest.raises(PumpStationWorldRunError, match="serialization-version"):
        replace(manifest, serialization_version="pump-station-world-run.unknown")
    with pytest.raises(PumpStationWorldRunError, match="snapshot-version"):
        replace(manifest, snapshot_version="pump-station-state-snapshot.unknown")
    with pytest.raises(PumpStationWorldRunError, match="receipt-version"):
        replace(manifest, receipt_version="pump-station-transition-receipt.unknown")
    with pytest.raises(PumpStationWorldRunError, match="authority-policy-version"):
        replace(manifest, authority_policy_version="pump-station-authority-policy.unknown")
    with pytest.raises(PumpStationWorldRunError, match="transition-rule-version"):
        replace(manifest, transition_rule_version="pump-station-transition-rules.unknown")
    with pytest.raises(PumpStationWorldRunError, match="serialization-version"):
        replace(initial_commit, serialization_version="pump-station-world-run.unknown")
    with pytest.raises(PumpStationWorldRunError, match="serialization-version"):
        replace(current_pointer, serialization_version="pump-station-world-run.unknown")


def test_transition_receipt_versions_are_explicit_and_fail_closed(tmp_path: Path) -> None:
    run = create_world_run(tmp_path / "run")
    proposal, information_set = bind_proposal(
        run,
        RequestConditionalDeferral,
        "proposal-version-contract",
        pump_id="pump-a",
    )
    receipt = run.apply(proposal, information_set=information_set).receipt

    assert receipt.receipt_version == PUMP_STATION_RECEIPT_VERSION
    assert receipt.authority_policy_version == PUMP_STATION_AUTHORITY_POLICY_VERSION
    assert receipt.transition_rule_version == PUMP_STATION_TRANSITION_RULE_VERSION

    with pytest.raises(PumpStationProposalError, match="receipt-version"):
        replace(receipt, receipt_version="pump-station-transition-receipt.unknown")
    with pytest.raises(PumpStationProposalError, match="authority-policy-version"):
        replace(receipt, authority_policy_version="pump-station-authority-policy.unknown")
    with pytest.raises(PumpStationProposalError, match="transition-rule-version"):
        replace(receipt, transition_rule_version="pump-station-transition-rules.unknown")
