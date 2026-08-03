# ABOUTME: Proves the registered reference system uses the one current durable world run.
# ABOUTME: Covers exact opening persistence, bound resume, interruption recovery, and tamper rejection.

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from aec_bench.task_world_templates import continual_catalogue as continual_catalogue_module
from aec_bench.task_world_templates.continual.catalogue import ContinualWorldCatalogue
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
    create_asw_8_world_state,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_system import (
    PUMP_STATION_ASW_8_EVENT_SCHEDULE_ID,
    PUMP_STATION_ASW_8_INITIAL_STATE_SPECIFICATION_ID,
    PUMP_STATION_ASW_8_TEMPORAL_TEMPLATE_ID,
    PUMP_STATION_REFERENCE_SYSTEM_ID,
    load_reference_system,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.corpus import (
    build_asw_8_reference_temporal_evidence_bundle,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.repository import (
    TemporalEvidenceRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PUMP_STATION_RECORD_VERSIONS,
    PumpStationRegisteredWorldRunManifest,
    PumpStationWorldRunError,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    load_pump_station_artifact,
    pump_station_artifact_bytes,
)


def _start(root: Path) -> PumpStationWorldRun:
    return PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="reference-run",
        episode_id="reference-episode",
        world_branch_id="reference-branch",
    )


def test_current_reference_system_persists_exact_registered_identity(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = _start(root)
    manifest = run.manifest
    snapshot = run.snapshot()
    system = load_reference_system()
    bundle = build_asw_8_reference_temporal_evidence_bundle(
        run.package,
        world_branch_id=snapshot.world_branch_id,
    )

    assert manifest.record_versions == PUMP_STATION_RECORD_VERSIONS
    assert manifest.reference_system_id == PUMP_STATION_REFERENCE_SYSTEM_ID
    assert manifest.reference_system_content_id == system.descriptor_content_id
    assert manifest.opening_state_specification_id == PUMP_STATION_ASW_8_INITIAL_STATE_SPECIFICATION_ID
    assert manifest.event_schedule_id == PUMP_STATION_ASW_8_EVENT_SCHEDULE_ID
    assert manifest.temporal_template_id == PUMP_STATION_ASW_8_TEMPORAL_TEMPLATE_ID
    assert manifest.temporal_bundle_content_id == bundle.content_sha256
    assert manifest.initial_state_source.kind == "reference_system_specification"
    assert snapshot.snapshot_version == PUMP_STATION_RECORD_VERSIONS.snapshot_version
    assert snapshot.sequence == 0
    assert run.state == create_asw_8_world_state()
    assert TemporalEvidenceRepository(root / "temporal-evidence").load_bundle(package=run.package) == bundle
    assert len(run.repository.commits()) == 1
    assert not (root / "HEAD").exists()
    assert not (root / "generations").exists()


def test_current_reference_system_resumes_from_its_stored_manifest(tmp_path: Path) -> None:
    root = tmp_path / "run"
    started = _start(root)
    resumed = PumpStationWorldRun.resume_reference_system(
        repository=PumpStationWorldRunRepository(root),
        snapshot=started.snapshot(),
    )

    assert resumed.manifest == started.manifest
    assert resumed.package == started.package
    assert resumed.model == started.model
    assert resumed.state == started.state


def test_reference_system_rejects_tampered_state_and_manifest(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    state_run = _start(state_root)
    state_path = state_root / "states" / f"{state_run.snapshot().state_id}.json"
    state_path.write_bytes(state_path.read_bytes().replace(b'"calendar_seconds":21600', b'"calendar_seconds":21601'))
    with pytest.raises(PumpStationWorldRunError, match="artifact-integrity"):
        PumpStationWorldRun.resume_reference_system(
            repository=PumpStationWorldRunRepository(state_root),
            snapshot=state_run.snapshot(),
        )

    manifest_root = tmp_path / "manifest"
    manifest_run = _start(manifest_root)
    changed = replace(manifest_run.manifest, definition_content_sha256="0" * 64)
    (manifest_root / "manifest.json").write_bytes(pump_station_artifact_bytes(changed))
    with pytest.raises(PumpStationWorldRunError, match="world-run-identity"):
        PumpStationWorldRun.resume_reference_system(
            repository=PumpStationWorldRunRepository(manifest_root),
            snapshot=manifest_run.snapshot(),
        )


def test_opening_publication_recovers_after_interruption(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "run"
    interrupted = PumpStationWorldRunRepository(root)

    def fail_selection(_pointer: object) -> None:
        raise OSError("interrupt before opening selection")

    monkeypatch.setattr(interrupted, "_replace_current", fail_selection)
    with pytest.raises(OSError, match="interrupt before opening selection"):
        PumpStationWorldRun.create_reference_system(
            repository=interrupted,
            run_id="reference-run",
            episode_id="reference-episode",
            world_branch_id="reference-branch",
        )

    recovered = _start(root)
    assert recovered.snapshot().sequence == 0
    assert recovered.state == create_asw_8_world_state()
    assert len(recovered.repository.commits()) == 1


def test_current_manifest_and_snapshot_round_trip_strictly(tmp_path: Path) -> None:
    run = _start(tmp_path / "run")
    manifest_payload = pump_station_artifact_bytes(run.manifest)
    snapshot_payload = pump_station_artifact_bytes(run.snapshot())

    assert (
        load_pump_station_artifact(
            manifest_payload,
            PumpStationRegisteredWorldRunManifest,
        )
        == run.manifest
    )
    assert (
        load_pump_station_artifact(
            snapshot_payload,
            type(run.snapshot()),
        )
        == run.snapshot()
    )


def test_reference_system_requires_catalogue_registration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        continual_catalogue_module,
        "default_continual_world_catalogue",
        lambda: ContinualWorldCatalogue(definitions=()),
    )
    with pytest.raises(PumpStationWorldRunError, match="world-run-identity"):
        _start(tmp_path / "run")
