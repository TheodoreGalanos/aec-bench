# ABOUTME: Attacks durable pump-station reload with hostile versions and damaged files.
# ABOUTME: Proves only the selected immutable chain can provide run and Harbor authority.

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    PUMP_STATION_SERIALIZATION_VERSION,
    PumpStationWorldRun,
    PumpStationWorldRunError,
    PumpStationWorldRunRepository,
    RequestConditionalDeferral,
    load_reference_package,
    pump_station_artifact_bytes,
    pump_station_model_from_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
    export_pump_station_harbor_task,
    load_pump_station_harbor_bridge,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
    _artifact_inventory,
    run_pump_station_reference_session,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_verifier import (
    verify_pump_station_harbor_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationCurrentRunPointer,
)
from tests.task_world_templates.stewardship.wastewater_pump_station.world_run_support import (
    bind_proposal,
    create_world_run,
)

_VERSION_ATTACKS = (
    (
        "manifest",
        "serialization_version",
        "pump-station-world-run.unknown",
        "serialization-version",
    ),
    (
        "manifest",
        "snapshot_version",
        "pump-station-state-snapshot.unknown",
        "snapshot-version",
    ),
    (
        "manifest",
        "receipt_version",
        "pump-station-transition-receipt.unknown",
        "receipt-version",
    ),
    (
        "manifest",
        "authority_policy_version",
        "pump-station-authority-policy.unknown",
        "authority-policy-version",
    ),
    (
        "manifest",
        "transition_rule_version",
        "pump-station-transition-rules.unknown",
        "transition-rule-version",
    ),
    (
        "current",
        "serialization_version",
        "pump-station-world-run.unknown",
        "serialization-version",
    ),
    (
        "commit",
        "serialization_version",
        "pump-station-world-run.unknown",
        "serialization-version",
    ),
    (
        "receipt",
        "receipt_version",
        "pump-station-transition-receipt.unknown",
        "receipt-version",
    ),
    (
        "receipt",
        "authority_policy_version",
        "pump-station-authority-policy.unknown",
        "authority-policy-version",
    ),
    (
        "receipt",
        "transition_rule_version",
        "pump-station-transition-rules.unknown",
        "transition-rule-version",
    ),
)
_TRUNCATED_ARTIFACTS = (
    "manifest",
    "current",
    "state",
    "proposal",
    "information-set",
    "receipt",
    "event",
    "commit",
)


def _run_with_transition(root: Path) -> PumpStationWorldRun:
    run = create_world_run(root)
    proposal, information_set = bind_proposal(
        run,
        RequestConditionalDeferral,
        "proposal-persistence-attack",
        pump_id="pump-a",
    )
    run.apply(proposal, information_set=information_set)
    return run


def _artifact_paths(run: PumpStationWorldRun) -> dict[str, Path]:
    snapshot = run.snapshot()
    commit = run.repository.load_commit(snapshot.commit_id)
    assert commit.proposal_content_id is not None
    assert commit.information_set_content_id is not None
    assert commit.receipt_content_id is not None
    assert commit.event_batch_content_id is not None
    root = run.repository.root
    return {
        "manifest": root / "manifest.json",
        "current": root / "current.json",
        "state": root / "states" / f"{commit.state_id}.json",
        "proposal": root / "proposals" / f"{commit.proposal_content_id}.json",
        "information-set": (root / "information-sets" / f"{commit.information_set_content_id}.json"),
        "receipt": root / "receipts" / f"{commit.receipt_content_id}.json",
        "event": root / "events" / f"{commit.event_batch_content_id}.json",
        "commit": root / "commits" / f"{snapshot.commit_id}.json",
    }


def _rewrite_json_field(path: Path, field: str, value: str) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    payload[field] = value
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _reload_action(
    run: PumpStationWorldRun,
    artifact: str,
) -> Callable[[], object]:
    if artifact in {"proposal", "information-set", "receipt", "event"}:
        return run.repository.steps
    return run.repository.current_snapshot


@pytest.mark.parametrize(
    ("artifact", "field", "hostile_value", "error_code"),
    _VERSION_ATTACKS,
)
def test_repository_reload_rejects_every_unknown_durable_version(
    tmp_path: Path,
    artifact: str,
    field: str,
    hostile_value: str,
    error_code: str,
) -> None:
    run = _run_with_transition(tmp_path / "run")
    path = _artifact_paths(run)[artifact]
    _rewrite_json_field(path, field, hostile_value)

    with pytest.raises(PumpStationWorldRunError, match=error_code):
        _reload_action(run, artifact)()


@pytest.mark.parametrize("artifact", _TRUNCATED_ARTIFACTS)
def test_repository_reload_never_accepts_silent_truncation(
    tmp_path: Path,
    artifact: str,
) -> None:
    run = _run_with_transition(tmp_path / "run")
    path = _artifact_paths(run)[artifact]
    payload = path.read_bytes()
    path.write_bytes(payload[: len(payload) // 2])

    with pytest.raises(PumpStationWorldRunError):
        _reload_action(run, artifact)()


def test_fresh_reload_ignores_forged_working_pointer_and_reconciles_once(
    tmp_path: Path,
) -> None:
    run = create_world_run(tmp_path / "run")
    proposal, information_set = bind_proposal(
        run,
        RequestConditionalDeferral,
        "proposal-working-file",
        pump_id="pump-a",
    )
    before = run.snapshot()
    staged = run.stage(proposal, information_set=information_set)
    working_pointer = PumpStationCurrentRunPointer(
        serialization_version=PUMP_STATION_SERIALIZATION_VERSION,
        run_id=staged.snapshot.run_id,
        sequence=staged.snapshot.sequence,
        state_id=staged.snapshot.state_id,
        commit_id=staged.snapshot.commit_id,
    )
    working_path = run.repository.root / ".current.forged.tmp"
    working_path.write_bytes(pump_station_artifact_bytes(working_pointer))
    working_path.chmod(0o600)

    repository = PumpStationWorldRunRepository(run.repository.root)
    assert repository.current_snapshot() == before
    assert len(repository.commits()) == 1
    assert repository.steps() == ()

    package = load_reference_package()
    model = pump_station_model_from_package(package)
    recovered = PumpStationWorldRun.resume(
        repository=repository,
        package=package,
        model=model,
        snapshot=before,
    )
    first = recovered.apply(proposal, information_set=information_set)
    repeated = recovered.apply(proposal, information_set=information_set)

    assert repeated == first
    assert recovered.state.sequence == 1
    assert len(recovered.steps()) == 1
    assert len(recovered.state.restrictions) == 1
    assert len(recovered.state.obligations) == 1
    assert len(recovered.state.work_orders) == 1


def test_initialization_retry_never_reopens_an_advanced_run(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = create_world_run(root)

    assert create_world_run(root).snapshot() == run.snapshot()

    proposal, information_set = bind_proposal(
        run,
        RequestConditionalDeferral,
        "proposal-before-late-start",
        pump_id="pump-a",
    )
    run.apply(proposal, information_set=information_set)

    with pytest.raises(PumpStationWorldRunError, match="world-run-exists"):
        create_world_run(root)


def test_harbor_provenance_ignores_repository_working_files(tmp_path: Path) -> None:
    task_dir = tmp_path / "tasks" / "stewardship" / "wastewater-pump-station"
    exported = export_pump_station_harbor_task(
        task_dir,
        project_root=Path(__file__).resolve().parents[4],
    )
    bridge = load_pump_station_harbor_bridge(task_dir / "environment")
    run_dir = tmp_path / "world-session"
    run_pump_station_reference_session(
        bridge=bridge,
        output_dir=run_dir,
        session_identity="working-file-provenance",
    )
    stored_inventory = json.loads((run_dir / "artifact-inventory.json").read_text(encoding="utf-8"))
    world_run = run_dir / "world-run"
    current_payload = (world_run / "current.json").read_bytes()
    working_paths = (
        world_run / ".current.response-lost.tmp",
        world_run / "states" / ".state.response-lost.tmp",
    )
    for path in working_paths:
        path.write_bytes(current_payload)
        path.chmod(0o600)

    regenerated = _artifact_inventory(
        bridge=bridge,
        output_dir=run_dir,
        start_snapshot=stored_inventory["start_snapshot"],
        end_snapshot=stored_inventory["end_snapshot"],
    )
    artifact_paths = {item["path"] for item in regenerated["artifacts"]}

    assert not artifact_paths.intersection(path.relative_to(run_dir).as_posix() for path in working_paths)
    assert (
        verify_pump_station_harbor_run(
            run_dir=run_dir,
            export_manifest_path=exported.manifest_path,
            package_dir=exported.package_dir,
        )["valid"]
        is True
    )
