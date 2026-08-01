# ABOUTME: Implements the host-only pump-station run-control surface and immutable receipts.
# ABOUTME: Keeps controls separate from actor actions and rejects raw state or undeclared operations.

from __future__ import annotations

from pathlib import Path

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
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationWorldSessionFactory,
)

PUMP_STATION_CONTROL_INTERFACE_VERSION = "pump-station.control.v1"
PUMP_STATION_CONTROL_OPERATIONS = (
    "create_session",
    "open_session",
    "resume_session",
    "inspect_progress",
    "snapshot",
    "verify",
)


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
    ) -> None:
        if not authorised_principal_ids or any(not item.strip() for item in authorised_principal_ids):
            raise ValueError("world control requires an authorised host principal")
        if len(authorised_principal_ids) != len(set(authorised_principal_ids)):
            raise ValueError("world control host principals must be distinct")
        self._repository_root = Path(repository_root)
        self._authorised_principal_ids = frozenset(authorised_principal_ids)
        self._package_root = package_root
        self._schedule = schedule
        self._rich_work_processes = rich_work_processes
        self._results: dict[str, tuple[WorldControlRequest, WorldControlResult]] = {}

    def capabilities(self, authority_id: str) -> WorldControlCapabilityCatalogue:
        """Return the closed host-only catalogue after authority validation."""

        self._require_authority(authority_id)
        return WorldControlCapabilityCatalogue(
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            interface_version=PUMP_STATION_CONTROL_INTERFACE_VERSION,
            operations=tuple(
                WorldControlOperationCapability(
                    operation=operation,
                    version="v1",
                    changes_durable_state=operation in {"create_session", "open_session"},
                )
                for operation in PUMP_STATION_CONTROL_OPERATIONS
            ),
        )

    def execute(self, request: WorldControlRequest) -> WorldControlResult:
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
        cached = self._results.get(request.request_id)
        if cached is not None:
            cached_request, cached_result = cached
            if cached_request != request:
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
            assert request.session_request is not None
            session = self._factory().open(request.session_request)
            session_result = session.result
            result_snapshot = session.result.snapshot
            state_changed = prior_snapshot is None and request.session_request.open_mode is WorldSessionOpenMode.START
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

    def _factory(self) -> PumpStationWorldSessionFactory:
        return PumpStationWorldSessionFactory(
            self._repository_root,
            package_root=self._package_root,
            schedule=self._schedule,
            rich_work_processes=self._rich_work_processes,
        )

    def _repository(self) -> PumpStationWorldRunRepository:
        return PumpStationWorldRunRepository(self._repository_root)

    def _current_snapshot_if_present(self) -> StewardshipStateSnapshotRef | None:
        if not (self._repository_root / "current.json").is_file():
            return None
        return _shared_snapshot(self._repository().current_snapshot())

    def _verification_report(self) -> PumpStationVerificationReport:
        repository = self._repository()
        manifest = repository.load_manifest()
        snapshot = repository.current_snapshot()
        package = load_reference_package(self._package_root)
        model = pump_station_model_from_package(package)
        run = PumpStationWorldRun.resume(
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
        initial_state = repository.load_state(manifest.initial_state_id)
        return verify_stewardship_run(model, initial_state, run.steps())

    def _require_authority(self, authority_id: str) -> None:
        if authority_id not in self._authorised_principal_ids:
            raise WorldInterfaceError(
                "control-unauthorised",
                authority_id,
            )
