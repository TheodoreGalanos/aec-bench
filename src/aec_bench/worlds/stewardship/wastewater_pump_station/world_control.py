# ABOUTME: Implements the host-only pump-station run-control surface and immutable receipts.
# ABOUTME: Keeps controls separate from actor actions and rejects raw state or undeclared operations.

from __future__ import annotations

import json
from pathlib import Path
from typing import Self

from pydantic import JsonValue, model_validator

from aec_bench.contracts.interactive_world import InteractiveWorldProfileRef
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
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
    StewardshipStateSnapshotRef,
    WorldSessionOpenMode,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.coupled_runtime import (
    pump_station_root_control_operations,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationEpisodeHost,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationBoundControlRequest,
    PumpStationCommonBoundaryRequest,
    PumpStationCoupledTreatmentRequest,
    PumpStationOperationsBoundaryReviewRequest,
    PumpStationProcessOutcomeRequest,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationCoupledVerificationReport,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationRegisteredWorldRunManifest,
    PumpStationStateSnapshotRef,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_serialization import (
    pump_station_artifact_bytes,
    pump_station_artifact_id,
)

PUMP_STATION_CONTROL_OPERATIONS = (
    "create_session",
    "open_session",
    "resume_session",
    "inspect_progress",
    "snapshot",
    "verify",
)
PUMP_STATION_ROOT_CONTROL_OPERATIONS = (
    "operations_review",
    "process_outcome",
    "common_boundary",
    "coupled_treatment",
)


class PumpStationRootControlResult(FrozenStrictModel):
    """Host-private result for one durable registered root control."""

    request_id: NonEmptyStr
    receipt: WorldControlReceipt
    transition_receipt: dict[str, JsonValue]

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.receipt.request_id != self.request_id:
            raise ValueError("root control result and receipt identities differ")
        return self


def _shared_snapshot(snapshot: PumpStationStateSnapshotRef) -> StewardshipStateSnapshotRef:
    return StewardshipStateSnapshotRef(
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
        profile_ref: InteractiveWorldProfileRef | None = None,
        package_root: Path | None = None,
    ) -> None:
        if not authorised_principal_ids or any(not item.strip() for item in authorised_principal_ids):
            raise ValueError("world control requires an authorised host principal")
        if len(authorised_principal_ids) != len(set(authorised_principal_ids)):
            raise ValueError("world control host principals must be distinct")
        self._repository_root = Path(repository_root)
        self._authorised_principal_ids = frozenset(authorised_principal_ids)
        self._profile_ref = profile_ref
        self._package_root = package_root
        self._results: dict[str, tuple[object, object]] = {}

    def capabilities(self, authority_id: str) -> WorldControlCapabilityCatalogue:
        """Return the closed host-only catalogue after authority validation."""

        self._require_authority(authority_id)
        run = self._resume_run() if (self._repository_root / "current.json").is_file() else None
        state = run.state if run is not None else None
        operations: tuple[str, ...] = (
            *PUMP_STATION_CONTROL_OPERATIONS,
            *pump_station_root_control_operations(
                state,
                authority_id=authority_id,
            ),
        )
        if (
            authority_id == "rollout-host"
            and run is not None
            and run.manifest.initial_state_source.kind == "rollout_parent_snapshot"
        ):
            operations = (*operations, "coupled_treatment")
        return WorldControlCapabilityCatalogue(
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            operations=tuple(
                WorldControlOperationCapability(
                    operation=operation,
                    changes_durable_state=operation
                    in {
                        "create_session",
                        "open_session",
                        *PUMP_STATION_ROOT_CONTROL_OPERATIONS,
                    },
                )
                for operation in operations
            ),
        )

    def execute(
        self,
        request: WorldControlRequest | PumpStationBoundControlRequest,
    ) -> WorldControlResult | PumpStationRootControlResult:
        """Execute one declared host operation without exposing a raw state editor."""

        self._require_authority(request.authority_id)
        if isinstance(request, PumpStationBoundControlRequest):
            return self._execute_root_control(request)
        if request.task_world_id != PUMP_STATION_TASK_WORLD_ID:
            raise WorldInterfaceError(
                "control-wrong-task-world",
                request.task_world_id,
            )
        if request.operation in PUMP_STATION_ROOT_CONTROL_OPERATIONS:
            raise WorldInterfaceError(
                "control-request-invalid",
                f"{request.operation} requires a typed bound root-control request",
            )
        operations = {item.operation for item in self.capabilities(request.authority_id).operations}
        if request.operation not in operations:
            raise WorldInterfaceError(
                "control-capability-unavailable",
                request.operation,
            )
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
            session_result = self._factory(request.authority_id).open(session_request)
            result_snapshot = session_result.snapshot
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
            request_id=request.request_id,
            operation=request.operation,
            authority_id=request.authority_id,
            status="completed",
            state_changed=state_changed,
            prior_snapshot=prior_snapshot,
            result_snapshot=result_snapshot,
        )
        result = WorldControlResult(
            request_id=request.request_id,
            receipt=receipt,
            session_result=session_result,
            progress=progress,
            snapshot=snapshot,
            verification=verification,
        )
        self._results[request.request_id] = (request, result)
        return result

    def _execute_root_control(
        self,
        request: PumpStationBoundControlRequest,
    ) -> PumpStationRootControlResult:
        """Apply or recover one registered root control through the run."""
        operation = (
            "operations_review"
            if isinstance(request.control, PumpStationOperationsBoundaryReviewRequest)
            else "process_outcome"
            if isinstance(request.control, PumpStationProcessOutcomeRequest)
            else "common_boundary"
            if isinstance(request.control, PumpStationCommonBoundaryRequest)
            else "coupled_treatment"
            if isinstance(request.control, PumpStationCoupledTreatmentRequest)
            else ""
        )
        if operation not in PUMP_STATION_ROOT_CONTROL_OPERATIONS:
            raise WorldInterfaceError(
                "control-capability-unavailable",
                type(request.control).__name__,
            )
        run = self._resume_run()
        committed = run.repository.find_committed_command(request.request_id)
        if committed is None and operation not in {
            item.operation for item in self.capabilities(request.authority_id).operations
        }:
            raise WorldInterfaceError("control-capability-unavailable", operation)
        transition = run.apply_control(request)
        commit = committed or run.repository.find_committed_command(
            request.request_id,
        )
        if commit is None:
            raise WorldInterfaceError(
                "control-publication-missing",
                request.request_id,
            )
        manifest = run.manifest
        if not isinstance(manifest, PumpStationRegisteredWorldRunManifest):
            raise WorldInterfaceError(
                "control-wrong-profile",
                "root control requires a registered run",
            )
        parent = run.repository.load_commit(commit.parent_commit_id)
        prior = _shared_snapshot(
            PumpStationStateSnapshotRef(
                run_id=manifest.run_id,
                episode_id=manifest.episode_id,
                world_branch_id=manifest.world_branch_id,
                sequence=parent.sequence,
                state_id=parent.state_id,
                commit_id=commit.parent_commit_id,
            )
        )
        result_snapshot = _shared_snapshot(
            PumpStationStateSnapshotRef(
                run_id=manifest.run_id,
                episode_id=manifest.episode_id,
                world_branch_id=manifest.world_branch_id,
                sequence=commit.sequence,
                state_id=commit.state_id,
                commit_id=pump_station_artifact_id(commit),
            )
        )
        receipt = WorldControlReceipt(
            request_id=request.request_id,
            operation=operation,
            authority_id=request.authority_id,
            status="completed",
            state_changed=True,
            prior_snapshot=prior,
            result_snapshot=result_snapshot,
        )
        return PumpStationRootControlResult(
            request_id=request.request_id,
            receipt=receipt,
            transition_receipt=_artifact_payload(transition.receipt),
        )

    def _factory(self, authority_id: str) -> PumpStationEpisodeHost:
        del authority_id
        if self._profile_ref is None:
            raise WorldInterfaceError(
                "world-format-obsolete",
                "host session operations require the current registered profile",
            )
        return PumpStationEpisodeHost(self._repository_root)

    def _repository(self) -> PumpStationWorldRunRepository:
        return PumpStationWorldRunRepository(self._repository_root)

    def _current_snapshot_if_present(self) -> StewardshipStateSnapshotRef | None:
        if not (self._repository_root / "current.json").is_file():
            return None
        return _shared_snapshot(self._repository().current_snapshot())

    def _verification_report(
        self,
    ) -> PumpStationCoupledVerificationReport:
        return self._resume_run().verify()

    def _resume_run(self) -> PumpStationWorldRun:
        repository = self._repository()
        manifest = repository.load_manifest()
        if not isinstance(manifest, PumpStationRegisteredWorldRunManifest):
            raise WorldInterfaceError(
                "world-format-obsolete",
                "host controls require the current registered world",
            )
        snapshot = repository.current_snapshot()
        return PumpStationWorldRun.resume_reference_system(
            repository=repository,
            snapshot=PumpStationStateSnapshotRef(
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
