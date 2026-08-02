# ABOUTME: Tests the real filesystem repository for one durable pump-station run.
# ABOUTME: Proves immutable artifacts, strict reload, snapshot continuity, and verifier replay.

from __future__ import annotations

import stat
from dataclasses import replace
from pathlib import Path

import pytest
from world_run_support import bind_proposal, create_world_run

import aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository as repository_runtime
from aec_bench.ledger.durability import (
    DurableFileReplaceConfinementError,
    DurableFileReplaceIntegrityError,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    ContinueOperation,
    PumpStationExecutionOutcome,
    PumpStationObligationKind,
    PumpStationWorldRun,
    PumpStationWorldRunError,
    RequestConditionalDeferral,
    RequestInspection,
    TransferDuty,
    pump_station_artifact_bytes,
    verify_stewardship_run,
)


@pytest.mark.parametrize(
    ("failure", "expected_code"),
    (
        (DurableFileReplaceConfinementError("unsafe destination"), "artifact-confinement"),
        (DurableFileReplaceIntegrityError("replacement drift"), "artifact-integrity"),
    ),
)
def test_repository_maps_shared_pointer_replacement_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
    expected_code: str,
) -> None:
    def fail_replacement(*_args: object, **_kwargs: object) -> None:
        raise failure

    monkeypatch.setattr(
        repository_runtime,
        "replace_file_bytes_durable",
        fail_replacement,
    )

    with pytest.raises(PumpStationWorldRunError) as raised:
        create_world_run(tmp_path / "run")

    assert raised.value.code == expected_code


def test_filesystem_run_reloads_complete_state_and_verifier_steps(tmp_path) -> None:
    run = create_world_run(tmp_path / "run")
    initial_state = run.state
    proposal, information_set = bind_proposal(
        run,
        RequestConditionalDeferral,
        "proposal-resource-effect",
        pump_id="pump-a",
    )

    transition = run.apply(
        proposal,
        information_set=information_set,
    )
    snapshot = run.snapshot()
    resumed = PumpStationWorldRun.resume(
        repository=run.repository,
        package=run.package,
        model=run.model,
        snapshot=snapshot,
    )
    verification = verify_stewardship_run(
        run.model,
        initial_state,
        resumed.steps(),
    )

    assert resumed.state == transition.state
    assert resumed.snapshot() == snapshot
    assert resumed.state.obligation(
        PumpStationObligationKind.DEFERRED_FOLLOW_UP,
        "pump-a",
    ) == transition.state.obligation(
        PumpStationObligationKind.DEFERRED_FOLLOW_UP,
        "pump-a",
    )
    assert verification.valid is True

    expected_counts = {
        "states": 2,
        "proposals": 1,
        "information-sets": 1,
        "receipts": 1,
        "events": 1,
        "commits": 2,
    }
    for directory, expected_count in expected_counts.items():
        assert len(tuple((run.repository.root / directory).glob("*.json"))) == expected_count


def test_repository_rejects_content_moved_under_the_wrong_identity(tmp_path) -> None:
    run = create_world_run(tmp_path / "run")
    assert stat.S_IMODE(run.repository.root.stat().st_mode) == 0o700
    proposal, information_set = bind_proposal(
        run,
        RequestConditionalDeferral,
        "proposal-content-integrity",
        pump_id="pump-a",
    )
    transition = run.apply(
        proposal,
        information_set=information_set,
    )
    receipt_path = next((run.repository.root / "receipts").glob("*.json"))
    receipt_path.write_bytes(
        pump_station_artifact_bytes(
            replace(
                transition.receipt,
                execution=PumpStationExecutionOutcome.CANCELLED,
            )
        )
    )

    with pytest.raises(PumpStationWorldRunError, match="artifact-integrity"):
        run.steps()


def test_repository_keeps_each_new_root_directory_private(tmp_path: Path) -> None:
    private_parent = tmp_path / "private" / "worlds"

    run = create_world_run(private_parent / "run")

    assert [
        stat.S_IMODE(path.stat().st_mode)
        for path in (
            tmp_path / "private",
            private_parent,
            run.repository.root,
        )
    ] == [0o700, 0o700, 0o700]


def test_repository_keeps_existing_ancestor_mode_and_privatises_existing_root(
    tmp_path: Path,
) -> None:
    existing_parent = tmp_path / "existing"
    existing_parent.mkdir()
    existing_parent.chmod(0o750)
    existing_root = existing_parent / "run"
    existing_root.mkdir()
    existing_root.chmod(0o750)

    repository = repository_runtime.PumpStationWorldRunRepository(existing_root)

    assert stat.S_IMODE(existing_parent.stat().st_mode) == 0o750
    assert stat.S_IMODE(repository.root.stat().st_mode) == 0o700


@pytest.mark.parametrize(
    ("unsafe_kind", "expected_code"),
    (
        ("symbolic-link", "artifact-confinement"),
        ("directory", "artifact-integrity"),
        ("public-permissions", "artifact-confinement"),
        ("unreadable", "artifact-integrity"),
    ),
)
def test_repository_rejects_unsafe_manifest_files(
    tmp_path: Path,
    unsafe_kind: str,
    expected_code: str,
) -> None:
    run = create_world_run(tmp_path / "run")
    manifest = run.repository.root / "manifest.json"
    if unsafe_kind == "symbolic-link":
        outside = tmp_path / "outside.json"
        outside.write_bytes(manifest.read_bytes())
        manifest.unlink()
        manifest.symlink_to(outside)
    elif unsafe_kind == "directory":
        manifest.unlink()
        manifest.mkdir()
    elif unsafe_kind == "unreadable":
        manifest.chmod(0o000)
    else:
        manifest.chmod(0o644)

    try:
        with pytest.raises(PumpStationWorldRunError) as raised:
            run.repository.load_manifest()
    finally:
        if unsafe_kind == "unreadable":
            manifest.chmod(0o600)

    assert raised.value.code == expected_code


def test_snapshot_preserves_elapsed_time_and_applied_event_identity(tmp_path) -> None:
    run = create_world_run(tmp_path / "run")
    proposals = (
        (RequestConditionalDeferral, "proposal-deferral", {"pump_id": "pump-a"}),
        (TransferDuty, "proposal-transfer", {}),
        (RequestInspection, "proposal-inspection", {"pump_id": "pump-a"}),
        (ContinueOperation, "proposal-continue", {}),
    )
    transition = None
    for proposal_type, proposal_id, parameters in proposals:
        proposal, information_set = bind_proposal(
            run,
            proposal_type,
            proposal_id,
            **parameters,
        )
        transition = run.apply(
            proposal,
            information_set=information_set,
        )

    assert transition is not None
    snapshot = run.snapshot()
    resumed = PumpStationWorldRun.resume(
        repository=run.repository,
        package=run.package,
        model=run.model,
        snapshot=snapshot,
    )

    assert resumed.state.physical.calendar_seconds == run.model.inflow.diagnostic_period_seconds
    assert transition.receipt.clock_delta_seconds == run.model.inflow.diagnostic_period_seconds
    assert transition.receipt.applied_event_ids
    assert resumed.snapshot() == snapshot
