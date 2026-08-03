# ABOUTME: Proves the registered pump reference system starts on the existing durable world run.
# ABOUTME: Covers exact V4 opening-state persistence, bound resume, and static-identity rejection.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from aec_bench.task_world_templates import continual_catalogue as continual_catalogue_module
from aec_bench.task_world_templates.continual.catalogue import ContinualWorldCatalogue
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
    create_asw_8_world_state,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.evidence_health import (
    PumpStationEvidenceTreatmentRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_kernel import (
    pump_station_model_from_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpStationCoupledModel,
    PumpStationModel,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_treatments import (
    PumpStationPhysicalTreatmentActivationRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_system import (
    PUMP_STATION_ASW_8_EVENT_SCHEDULE_ID,
    PUMP_STATION_ASW_8_INITIAL_STATE_SPECIFICATION_ID,
    PUMP_STATION_ASW_8_TEMPORAL_TEMPLATE_ID,
    PUMP_STATION_REFERENCE_SYSTEM_ID,
    load_reference_system,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationCoupledStewardshipState,
    PumpStationLegacyStewardshipState,
    PumpStationProposal,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationInformationSet,
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
    PUMP_STATION_RECORD_VERSIONS_V4,
    PumpStationWorldRunError,
    PumpStationWorldRunManifestV2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    load_pump_station_artifact,
    pump_station_artifact_bytes,
)

type PumpStationReferenceRun = PumpStationWorldRun[
    PumpStationCoupledModel,
    PumpStationCoupledStewardshipState,
]


def _start_reference_system(
    root: Path,
) -> PumpStationReferenceRun:
    return PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="run-rs1-opening",
        episode_id="episode-rs1-opening",
        world_branch_id="branch-rs1-opening",
    )


def _replace_static_binding(
    manifest: PumpStationWorldRunManifestV2,
    field_name: str,
) -> PumpStationWorldRunManifestV2:
    changed = "0" * 64
    if field_name == "definition_content_sha256":
        return replace(manifest, definition_content_sha256=changed)
    if field_name == "continual_profile_content_sha256":
        return replace(manifest, continual_profile_content_sha256=changed)
    if field_name == "reference_system_content_id":
        return replace(manifest, reference_system_content_id=changed)
    if field_name == "event_schedule_sha256":
        return replace(manifest, event_schedule_sha256=changed)
    if field_name == "package_content_id":
        return replace(manifest, package_content_id=changed)
    if field_name == "model_id":
        return replace(manifest, model_id=changed)
    if field_name == "temporal_bundle_content_id":
        return replace(manifest, temporal_bundle_content_id=changed)
    raise AssertionError(f"unsupported static binding: {field_name}")


def test_registered_reference_system_uses_the_existing_world_run_repository(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _start_reference_system(root)
    manifest = run.manifest
    snapshot = run.snapshot()
    system = load_reference_system()
    bundle = build_asw_8_reference_temporal_evidence_bundle(
        run.package,
        world_branch_id=snapshot.world_branch_id,
    )
    definition = run.continual_definition_ref
    profile = run.continual_profile_ref

    assert manifest.serialization_version == "pump-station-world-run.v2"
    assert isinstance(manifest, PumpStationWorldRunManifestV2)
    assert manifest.record_versions == PUMP_STATION_RECORD_VERSIONS_V4
    assert manifest.task_world_id == definition.task_world_id
    assert manifest.definition_version == definition.definition_version
    assert manifest.definition_content_sha256 == definition.content_sha256
    assert manifest.continual_profile_id == profile.profile_id
    assert manifest.continual_profile_version == profile.profile_version
    assert manifest.continual_profile_content_sha256 == profile.profile_content_sha256
    assert manifest.reference_system_id == PUMP_STATION_REFERENCE_SYSTEM_ID
    assert manifest.reference_system_content_id == system.descriptor_content_id
    assert manifest.opening_state_specification_id == PUMP_STATION_ASW_8_INITIAL_STATE_SPECIFICATION_ID
    assert manifest.event_schedule_id == PUMP_STATION_ASW_8_EVENT_SCHEDULE_ID
    assert manifest.temporal_template_id == PUMP_STATION_ASW_8_TEMPORAL_TEMPLATE_ID
    assert manifest.temporal_bundle_content_id == bundle.content_sha256
    assert manifest.temporal_corpus_content_id == bundle.corpus_manifest.content_sha256
    assert manifest.temporal_capability_content_id == bundle.capability.content_sha256
    assert manifest.initial_state_source is not None
    assert manifest.initial_state_source.kind == "reference_system_specification"
    assert manifest.initial_state_source.opening_specification_id == (PUMP_STATION_ASW_8_INITIAL_STATE_SPECIFICATION_ID)
    assert manifest.initial_state_source.parent_run_id is None
    assert snapshot.snapshot_version == PUMP_STATION_RECORD_VERSIONS_V4.snapshot_version
    assert snapshot.sequence == 0
    assert run.state == create_asw_8_world_state()
    assert (
        TemporalEvidenceRepository(root / "temporal-evidence").load_bundle(
            package=run.package,
        )
        == bundle
    )
    assert len(run.repository.commits()) == 1
    assert (root / "manifest.json").is_file()
    assert (root / "current.json").is_file()
    assert not (root / "HEAD").exists()
    assert not (root / "generations").exists()


def test_reference_system_resume_resolves_the_profile_from_the_manifest(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    started = _start_reference_system(root)
    snapshot = started.snapshot()

    resumed = PumpStationWorldRun.resume_reference_system(
        repository=PumpStationWorldRunRepository(root),
        snapshot=snapshot,
    )

    assert resumed.manifest == started.manifest
    assert resumed.package == started.package
    assert resumed.model == started.model
    assert resumed.state == started.state
    assert resumed.snapshot() == snapshot

    with pytest.raises(PumpStationWorldRunError) as caller_override:
        PumpStationWorldRun.resume(
            repository=PumpStationWorldRunRepository(root),
            package=started.package,
            model=cast(PumpStationModel, started.model),
            snapshot=snapshot,
        )
    assert caller_override.value.code == "reference-system-resume-required"


def test_reference_system_resume_rejects_changed_stored_state(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    started = _start_reference_system(root)
    snapshot = started.snapshot()
    state_path = root / "states" / f"{snapshot.state_id}.json"
    state_path.write_bytes(
        state_path.read_bytes().replace(
            b'"calendar_seconds":21600',
            b'"calendar_seconds":21601',
        )
    )

    with pytest.raises(PumpStationWorldRunError) as raised:
        PumpStationWorldRun.resume_reference_system(
            repository=PumpStationWorldRunRepository(root),
            snapshot=snapshot,
        )

    assert raised.value.code == "artifact-integrity"


def test_reference_system_start_requires_a_catalogue_registration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        continual_catalogue_module,
        "default_continual_world_catalogue",
        lambda: ContinualWorldCatalogue(definitions=()),
    )

    with pytest.raises(PumpStationWorldRunError) as raised:
        _start_reference_system(tmp_path / "run")

    assert raised.value.code == "world-run-identity"


@pytest.mark.parametrize(
    "field_name",
    (
        "definition_content_sha256",
        "continual_profile_content_sha256",
        "reference_system_content_id",
        "event_schedule_sha256",
        "package_content_id",
        "model_id",
        "temporal_bundle_content_id",
    ),
)
def test_reference_system_resume_rejects_changed_static_binding(
    tmp_path: Path,
    field_name: str,
) -> None:
    root = tmp_path / "run"
    started = _start_reference_system(root)
    manifest = started.manifest
    assert isinstance(manifest, PumpStationWorldRunManifestV2)
    changed = _replace_static_binding(manifest, field_name)
    (root / "manifest.json").write_bytes(
        pump_station_artifact_bytes(changed),
    )

    with pytest.raises(PumpStationWorldRunError) as raised:
        PumpStationWorldRun.resume_reference_system(
            repository=PumpStationWorldRunRepository(root),
            snapshot=started.snapshot(),
        )

    assert raised.value.code == "world-run-identity"


def test_reference_system_resume_rejects_missing_temporal_evidence(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    started = _start_reference_system(root)
    snapshot = started.snapshot()
    (root / "temporal-evidence" / "capability.json").unlink()

    with pytest.raises(PumpStationWorldRunError) as raised:
        PumpStationWorldRun.resume_reference_system(
            repository=PumpStationWorldRunRepository(root),
            snapshot=snapshot,
        )

    assert raised.value.code == "temporal-evidence"


def test_exact_start_retry_selects_one_opening_after_interruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "run"
    interrupted_repository = PumpStationWorldRunRepository(root)

    def interrupt_before_selection(_pointer: object) -> None:
        raise OSError("injected interruption before initial pointer selection")

    monkeypatch.setattr(
        interrupted_repository,
        "_replace_current",
        interrupt_before_selection,
    )
    with pytest.raises(OSError, match="injected interruption"):
        PumpStationWorldRun.create_reference_system(
            repository=interrupted_repository,
            run_id="run-rs1-opening",
            episode_id="episode-rs1-opening",
            world_branch_id="branch-rs1-opening",
        )

    assert not (root / "current.json").exists()
    assert (root / "temporal-evidence" / "capability.json").is_file()

    recovered = _start_reference_system(root)

    assert recovered.snapshot().sequence == 0
    assert recovered.state == create_asw_8_world_state()
    assert len(recovered.repository.commits()) == 1


def test_manifest_v2_and_snapshot_v4_round_trip_strictly(tmp_path: Path) -> None:
    run = _start_reference_system(tmp_path / "run")

    manifest_payload = pump_station_artifact_bytes(run.manifest)
    snapshot_payload = pump_station_artifact_bytes(run.snapshot())

    assert (
        load_pump_station_artifact(
            manifest_payload,
            type(run.manifest),
        )
        == run.manifest
    )
    assert b'"$type":"PumpStationWorldRunManifestV2"' in manifest_payload
    assert (
        load_pump_station_artifact(
            snapshot_payload,
            type(run.snapshot()),
            record_profile="v4",
        )
        == run.snapshot()
    )


def test_manifest_v2_rejects_a_non_text_reference_binding(tmp_path: Path) -> None:
    run = _start_reference_system(tmp_path / "run")
    manifest = run.manifest
    assert isinstance(manifest, PumpStationWorldRunManifestV2)

    with pytest.raises(PumpStationWorldRunError) as raised:
        replace(
            manifest,
            task_world_id=cast(str, 7),
        )

    assert raised.value.code == "world-run-shape"


def test_free_form_create_does_not_accept_v4_profile_inputs(tmp_path: Path) -> None:
    registered = _start_reference_system(tmp_path / "registered")

    with pytest.raises(PumpStationWorldRunError) as raised:
        PumpStationWorldRun.create(
            repository=PumpStationWorldRunRepository(tmp_path / "free-form"),
            package=registered.package,
            model=cast(PumpStationModel, registered.model),
            initial_state=cast(PumpStationLegacyStewardshipState, registered.state),
            run_id="run-free-form-v4",
            episode_id="episode-free-form-v4",
            world_branch_id="branch-free-form-v4",
            record_versions=PUMP_STATION_RECORD_VERSIONS_V4,
        )

    assert raised.value.code == "record-versions"


def test_registered_v4_state_cannot_enter_the_legacy_repository_profile(
    tmp_path: Path,
) -> None:
    run = _start_reference_system(tmp_path / "run")

    with pytest.raises(PumpStationWorldRunError) as raised:
        run.repository.load_legacy_state(run.snapshot().state_id)

    assert raised.value.code == "record-versions"


def test_run_container_rejects_mismatched_manifest_and_model_profiles(
    tmp_path: Path,
) -> None:
    run = _start_reference_system(tmp_path / "run")

    with pytest.raises(PumpStationWorldRunError) as raised:
        PumpStationWorldRun(
            repository=run.repository,
            package=run.package,
            model=pump_station_model_from_package(load_reference_package()),
            manifest=run.manifest,
        )

    assert raised.value.code == "world-run-identity"


@pytest.mark.parametrize(
    "operation",
    (
        lambda run: run.stage(
            cast(PumpStationProposal, object()),
            information_set=cast(PumpStationInformationSet, object()),
        ),
        lambda run: run.apply(
            cast(PumpStationProposal, object()),
            information_set=cast(PumpStationInformationSet, object()),
        ),
        lambda run: run.stage_evidence_treatment(
            cast(PumpStationEvidenceTreatmentRequest, object()),
        ),
        lambda run: run.schedule_evidence_treatment(
            cast(PumpStationEvidenceTreatmentRequest, object()),
        ),
        lambda run: run.apply_physical_treatment(
            cast(PumpStationPhysicalTreatmentActivationRequest, object()),
        ),
    ),
)
def test_registered_v4_run_rejects_every_legacy_mutation_entry_point(
    tmp_path: Path,
    operation: Callable[[PumpStationReferenceRun], object],
) -> None:
    run = _start_reference_system(tmp_path / "run")

    with pytest.raises(PumpStationWorldRunError) as raised:
        operation(run)

    assert raised.value.code == "v4-transition-not-routed"
