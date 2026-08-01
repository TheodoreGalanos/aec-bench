# ABOUTME: Implements the host-only pump-station run-control surface and immutable receipts.
# ABOUTME: Keeps controls separate from actor actions and rejects raw state or undeclared operations.

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Self

from pydantic import JsonValue, model_validator

from aec_bench.contracts.harness_kernel import ContentAddressedModel
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.contracts.world_interface import (
    WorldControlCapabilityCatalogue,
    WorldControlOperationCapability,
    WorldControlProgress,
    WorldControlReceipt,
    WorldControlRequest,
    WorldControlResult,
    WorldControlVerification,
    WorldInterfaceError,
)
from aec_bench.contracts.world_session import (
    STEWARDSHIP_STATE_SNAPSHOT_SCHEMA_VERSION,
    StewardshipStateSnapshotRef,
    WorldSessionOpenMode,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.evidence_health import (
    PumpStationEvidenceTreatment,
    PumpStationEvidenceTreatmentRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_kernel import (
    pump_station_model_from_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationSchedule,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationVerificationReport,
    verify_stewardship_run,
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
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    pump_station_artifact_bytes,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationWorldSessionFactory,
)

PUMP_STATION_CONTROL_INTERFACE_VERSION = "pump-station.control.v1"
PUMP_STATION_CONTROL_INTERFACE_VERSION_V2 = "pump-station.control.v2"
PUMP_STATION_CONTROL_OPERATIONS = (
    "create_session",
    "open_session",
    "resume_session",
    "inspect_progress",
    "snapshot",
    "verify",
)
PUMP_STATION_EVIDENCE_CONTROL_OPERATIONS = (
    "schedule_evidence_treatment",
    "inspect_evidence_treatment",
    "recover_evidence_treatment",
)


class PumpStationEvidenceControlRequest(ContentAddressedModel):
    """One task-owned host request for a governed evidence treatment."""

    schema_version: str = "pump-station.evidence-control.v1"
    request_id: NonEmptyStr
    operation: Literal[
        "schedule_evidence_treatment",
        "inspect_evidence_treatment",
        "recover_evidence_treatment",
    ]
    task_world_id: NonEmptyStr
    authority_id: NonEmptyStr
    treatment_request: PumpStationEvidenceTreatmentRequest | None = None
    treatment_request_id: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.schema_version != "pump-station.evidence-control.v1":
            raise ValueError("unsupported pump-station evidence control version")
        if self.operation == "schedule_evidence_treatment":
            if self.treatment_request is None or self.treatment_request_id is not None:
                raise ValueError("schedule requires exactly one treatment request")
            if self.request_id != self.treatment_request.request_id:
                raise ValueError("schedule and treatment request identities differ")
        elif self.treatment_request is not None or self.treatment_request_id is None:
            raise ValueError("inspect and recover require one treatment request identity")
        return self


class PumpStationEvidenceControlResult(ContentAddressedModel):
    """Host-private treatment manifest and optional immutable transition receipt."""

    schema_version: str = "pump-station.evidence-control.v1"
    request_content_sha256: NonEmptyStr
    receipt: WorldControlReceipt
    treatment_request: PumpStationEvidenceTreatmentRequest
    treatment: PumpStationEvidenceTreatment
    transition_receipt: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.schema_version != "pump-station.evidence-control.v1":
            raise ValueError("unsupported pump-station evidence control version")
        if self.receipt.request_content_sha256 != self.request_content_sha256:
            raise ValueError("evidence control result and receipt identities differ")
        return self


def _shared_snapshot(snapshot: PumpStationStateSnapshotRef) -> StewardshipStateSnapshotRef:
    return StewardshipStateSnapshotRef(
        schema_version=STEWARDSHIP_STATE_SNAPSHOT_SCHEMA_VERSION,
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        sequence=snapshot.sequence,
        state_id=snapshot.state_id,
        commit_id=snapshot.commit_id,
    )


def _artifact_payload(value: object) -> dict[str, JsonValue]:
    payload = json.loads(pump_station_artifact_bytes(value))
    if not isinstance(payload, dict):
        raise TypeError("pump-station control artifact must serialize to an object")
    return payload


class PumpStationWorldControl:
    """Host-authorised control surface for one durable pump-station run root."""

    def __init__(
        self,
        repository_root: Path,
        *,
        authorised_principal_ids: tuple[str, ...],
        package_root: Path | None = None,
        schedule: PumpStationSchedule | None = None,
        rich_work_processes: bool = False,
        evidence_health: bool = False,
    ) -> None:
        if not authorised_principal_ids or any(not item.strip() for item in authorised_principal_ids):
            raise ValueError("world control requires an authorised host principal")
        if len(authorised_principal_ids) != len(set(authorised_principal_ids)):
            raise ValueError("world control host principals must be distinct")
        self._repository_root = Path(repository_root)
        self._authorised_principal_ids = frozenset(authorised_principal_ids)
        self._package_root = package_root
        self._schedule = schedule
        self._evidence_health = evidence_health
        self._rich_work_processes = rich_work_processes or evidence_health
        self._results: dict[str, tuple[object, object]] = {}

    def capabilities(self, authority_id: str) -> WorldControlCapabilityCatalogue:
        """Return the closed host-only catalogue after authority validation."""

        self._require_authority(authority_id)
        operations: tuple[str, ...] = PUMP_STATION_CONTROL_OPERATIONS
        if self._evidence_health:
            operations = (*operations, *PUMP_STATION_EVIDENCE_CONTROL_OPERATIONS)
        return WorldControlCapabilityCatalogue(
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            interface_version=(
                PUMP_STATION_CONTROL_INTERFACE_VERSION_V2
                if self._evidence_health
                else PUMP_STATION_CONTROL_INTERFACE_VERSION
            ),
            operations=tuple(
                WorldControlOperationCapability(
                    operation=operation,
                    version="v1",
                    changes_durable_state=operation
                    in {
                        "create_session",
                        "open_session",
                        "schedule_evidence_treatment",
                    },
                )
                for operation in operations
            ),
        )

    def execute(
        self,
        request: WorldControlRequest | PumpStationEvidenceControlRequest,
    ) -> WorldControlResult | PumpStationEvidenceControlResult:
        """Execute one declared host operation without exposing a raw state editor."""

        self._require_authority(request.authority_id)
        if request.task_world_id != PUMP_STATION_TASK_WORLD_ID:
            raise WorldInterfaceError(
                "control-wrong-task-world",
                request.task_world_id,
            )
        operations = {item.operation for item in self.capabilities(request.authority_id).operations}
        if request.operation not in operations:
            raise WorldInterfaceError(
                "control-capability-unavailable",
                request.operation,
            )
        if isinstance(request, PumpStationEvidenceControlRequest):
            return self._execute_evidence_control(request)
        cached = self._results.get(request.request_id)
        if cached is not None:
            cached_request, cached_result = cached
            if cached_request != request:
                raise WorldInterfaceError(
                    "control-request-id-conflict",
                    f"{request.request_id} is already bound to different content",
                )
            if not isinstance(cached_result, WorldControlResult):
                raise WorldInterfaceError(
                    "control-request-id-conflict",
                    f"{request.request_id} is already bound to different content",
                )
            return cached_result

        prior_snapshot = self._current_snapshot_if_present()
        session_result = None
        progress = None
        snapshot = None
        verification = None
        if request.operation in {"create_session", "open_session", "resume_session"}:
            session_request = request.session_request
            if session_request is None:
                raise WorldInterfaceError(
                    "control-request-invalid",
                    f"{request.operation} requires a session request",
                )
            session = self._factory().open(session_request)
            session_result = session.result
            result_snapshot = session.result.snapshot
            state_changed = prior_snapshot is None and session_request.open_mode is WorldSessionOpenMode.START
        elif request.operation == "inspect_progress":
            selected = self._repository().current_snapshot()
            result_snapshot = _shared_snapshot(selected)
            progress = WorldControlProgress(
                snapshot=result_snapshot,
                transition_count=selected.sequence,
            )
            state_changed = False
        elif request.operation == "snapshot":
            result_snapshot = _shared_snapshot(self._repository().current_snapshot())
            snapshot = result_snapshot
            state_changed = False
        else:
            report = self._verification_report()
            result_snapshot = _shared_snapshot(self._repository().current_snapshot())
            verification = WorldControlVerification(
                valid=report.valid,
                issues=report.issues,
                replayed_transition_ids=report.replayed_transition_ids,
                final_state_id=report.final_state_id,
            )
            state_changed = False
        receipt = WorldControlReceipt(
            request_content_sha256=request.content_sha256,
            operation=request.operation,
            authority_id=request.authority_id,
            status="completed",
            state_changed=state_changed,
            prior_snapshot=prior_snapshot,
            result_snapshot=result_snapshot,
        )
        result = WorldControlResult(
            request_content_sha256=request.content_sha256,
            receipt=receipt,
            session_result=session_result,
            progress=progress,
            snapshot=snapshot,
            verification=verification,
        )
        self._results[request.request_id] = (request, result)
        return result

    def _execute_evidence_control(
        self,
        request: PumpStationEvidenceControlRequest,
    ) -> PumpStationEvidenceControlResult:
        cached = self._results.get(request.request_id)
        if cached is not None:
            cached_request, cached_result = cached
            if cached_request != request or not isinstance(
                cached_result,
                PumpStationEvidenceControlResult,
            ):
                raise WorldInterfaceError(
                    "control-request-id-conflict",
                    f"{request.request_id} is already bound to different content",
                )
            return cached_result
        run = self._resume_run()
        prior = _shared_snapshot(run.snapshot())
        transition_receipt: dict[str, JsonValue] | None = None
        treatment: PumpStationEvidenceTreatment
        if request.operation == "schedule_evidence_treatment":
            treatment_request = request.treatment_request
            if treatment_request is None:
                raise WorldInterfaceError(
                    "control-request-invalid",
                    "schedule requires a treatment request",
                )
            transition = run.schedule_evidence_treatment(treatment_request)
            committed = run.repository.find_committed_control_request(
                treatment_request.request_id,
            )
            if committed is None:
                raise WorldInterfaceError(
                    "control-publication-missing",
                    treatment_request.request_id,
                )
            result_snapshot = _shared_snapshot(
                run.repository.snapshot_for_commit(committed),
            )
            if committed.parent_commit_id is None:
                raise WorldInterfaceError(
                    "control-publication-invalid",
                    "treatment commit has no parent",
                )
            parent = run.repository.load_commit(committed.parent_commit_id)
            prior = _shared_snapshot(run.repository.snapshot_for_commit(parent))
            selected_treatment = next(
                (
                    item
                    for item in transition.state.evidence_treatments
                    if item.treatment_id == treatment_request.request_id
                ),
                None,
            )
            if selected_treatment is None:
                raise WorldInterfaceError(
                    "control-publication-invalid",
                    "treatment transition has no manifest",
                )
            treatment = selected_treatment
            transition_receipt = _artifact_payload(transition.receipt)
            state_changed = True
        elif request.operation == "inspect_evidence_treatment":
            treatment_request_id = request.treatment_request_id
            if treatment_request_id is None:
                raise WorldInterfaceError(
                    "control-request-invalid",
                    "inspection requires a treatment request identity",
                )
            selected_treatment = next(
                (item for item in run.state.evidence_treatments if item.treatment_id == treatment_request_id),
                None,
            )
            if selected_treatment is None:
                raise WorldInterfaceError(
                    "control-request-not-found",
                    treatment_request_id,
                )
            treatment = selected_treatment
            treatment_request = treatment.request
            result_snapshot = prior
            state_changed = False
        else:
            treatment_request_id = request.treatment_request_id
            if treatment_request_id is None:
                raise WorldInterfaceError(
                    "control-request-invalid",
                    "recovery requires a treatment request identity",
                )
            treatment_request, transition = run.recover_evidence_treatment(
                treatment_request_id,
            )
            selected_treatment = next(
                (
                    item
                    for item in transition.state.evidence_treatments
                    if item.treatment_id == treatment_request.request_id
                ),
                None,
            )
            if selected_treatment is None:
                raise WorldInterfaceError(
                    "control-publication-invalid",
                    "recovered transition has no treatment manifest",
                )
            treatment = selected_treatment
            transition_receipt = _artifact_payload(transition.receipt)
            result_snapshot = prior
            state_changed = False
        receipt = WorldControlReceipt(
            request_content_sha256=request.content_sha256,
            operation=request.operation,
            authority_id=request.authority_id,
            status="completed",
            state_changed=state_changed,
            prior_snapshot=prior,
            result_snapshot=result_snapshot,
        )
        result = PumpStationEvidenceControlResult(
            request_content_sha256=request.content_sha256,
            receipt=receipt,
            treatment_request=treatment_request,
            treatment=treatment,
            transition_receipt=transition_receipt,
        )
        self._results[request.request_id] = (request, result)
        return result

    def _factory(self) -> PumpStationWorldSessionFactory:
        return PumpStationWorldSessionFactory(
            self._repository_root,
            package_root=self._package_root,
            schedule=self._schedule,
            rich_work_processes=self._rich_work_processes,
            evidence_health=self._evidence_health,
        )

    def _repository(self) -> PumpStationWorldRunRepository:
        return PumpStationWorldRunRepository(self._repository_root)

    def _current_snapshot_if_present(self) -> StewardshipStateSnapshotRef | None:
        if not (self._repository_root / "current.json").is_file():
            return None
        return _shared_snapshot(self._repository().current_snapshot())

    def _verification_report(self) -> PumpStationVerificationReport:
        run = self._resume_run()
        initial_state = run.repository.load_state(run.manifest.initial_state_id)
        return verify_stewardship_run(
            run.model,
            initial_state,
            run.steps(),
            record_versions=run.manifest.record_versions,
        )

    def _resume_run(self) -> PumpStationWorldRun:
        repository = self._repository()
        manifest = repository.load_manifest()
        snapshot = repository.current_snapshot()
        package = load_reference_package(self._package_root)
        model = pump_station_model_from_package(package)
        return PumpStationWorldRun.resume(
            repository=repository,
            package=package,
            model=model,
            snapshot=PumpStationStateSnapshotRef(
                snapshot_version=manifest.snapshot_version,
                run_id=snapshot.run_id,
                episode_id=snapshot.episode_id,
                world_branch_id=snapshot.world_branch_id,
                sequence=snapshot.sequence,
                state_id=snapshot.state_id,
                commit_id=snapshot.commit_id,
            ),
        )

    def _require_authority(self, authority_id: str) -> None:
        if authority_id not in self._authorised_principal_ids:
            raise WorldInterfaceError(
                "control-unauthorised",
                authority_id,
            )
