# ABOUTME: Creates isolated child worlds and controls private future-world treatments.
# ABOUTME: Preserves parent state, complete lineage, exact retries, replay, and actor privacy.

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Never, overload

from aec_bench.contracts.continual_world import (
    CONTINUAL_ROLLOUT_GROUP_REQUEST_SCHEMA_VERSION,
    ContinualRolloutGroupRequest,
    ContinualRolloutLineage,
)
from aec_bench.contracts.world_session import (
    STEWARDSHIP_STATE_SNAPSHOT_SCHEMA_VERSION,
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.task_world_templates.continual.rollout_control import (
    ContinualRolloutControl,
    ContinualRolloutError,
)
from aec_bench.task_world_templates.continual.rollout_repository import (
    ContinualRolloutRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.continual_definition import (
    pump_station_continual_world_definition,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_kernel import (
    pump_station_model_from_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_treatments import (
    PUMP_STATION_PHYSICAL_TREATMENT_DECISION_RIGHT,
    PUMP_STATION_PHYSICAL_TREATMENT_VERSION,
    PUMP_STATION_PHYSICAL_TREATMENT_VISIBILITY,
    PumpStationPhysicalTreatmentActivationRequest,
    PumpStationPhysicalTreatmentClass,
    PumpStationPhysicalTreatmentRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rollout_models import (
    PUMP_STATION_FIXED_CONDITION_POLICY,
    PUMP_STATION_ROLLOUT_CHILD_RECEIPT_VERSION,
    PUMP_STATION_ROLLOUT_LINEAGE_VERSION,
    PUMP_STATION_ROLLOUT_REQUEST_VERSION,
    PUMP_STATION_TREATMENT_RECEIPT_VERSION,
    PumpStationPhysicalTreatmentActivationReceipt,
    PumpStationPhysicalTreatmentScheduleReceipt,
    PumpStationRolloutChildReceipt,
    PumpStationRolloutChildRequest,
    PumpStationRolloutGroupRequest,
    PumpStationRolloutGroupState,
    PumpStationRolloutGroupStatus,
    PumpStationRolloutLineage,
    PumpStationRolloutTreatmentStatus,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rollout_repository import (
    PumpStationRolloutRepository,
    PumpStationRolloutRepositoryError,
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
    PumpStationWorldRunManifestV2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    pump_station_artifact_bytes,
    pump_station_artifact_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationWorldSession,
    PumpStationWorldSessionFactory,
)

PumpStationRolloutError = PumpStationRolloutRepositoryError


class PumpStationRolloutControl:
    """Host-only rollout and treatment control over one verified parent world."""

    def __init__(
        self,
        *,
        parent_repository_root: Path,
        rollout_repository_root: Path,
        authorised_principal_ids: tuple[str, ...],
        package_root: Path | None = None,
        rich_work_processes: bool = False,
        evidence_health: bool = False,
    ) -> None:
        if not authorised_principal_ids or any(not item.strip() for item in authorised_principal_ids):
            raise ValueError("rollout control requires one authorised host principal")
        if len(set(authorised_principal_ids)) != len(authorised_principal_ids):
            raise ValueError("rollout control host principals must be distinct")
        self._parent_repository_root = Path(parent_repository_root)
        self._rollout_repository_root = Path(rollout_repository_root)
        self._repository = PumpStationRolloutRepository(self._rollout_repository_root)
        self._authorised_principal_ids = frozenset(authorised_principal_ids)
        self._authorised_principal_sequence = authorised_principal_ids
        self._package_root = package_root
        self._rich_work_processes = rich_work_processes or evidence_health
        self._evidence_health = evidence_health

    @overload
    def create_group(
        self,
        request: PumpStationRolloutGroupRequest,
    ) -> PumpStationRolloutLineage: ...

    @overload
    def create_group(self, request: ContinualRolloutGroupRequest) -> ContinualRolloutLineage: ...

    def create_group(
        self,
        request: PumpStationRolloutGroupRequest | ContinualRolloutGroupRequest,
    ) -> PumpStationRolloutLineage | ContinualRolloutLineage:
        """Create or exactly recover all requested children from the live parent origin."""

        if isinstance(request, ContinualRolloutGroupRequest):
            if len(request.children) < 2:
                raise PumpStationRolloutError(
                    "rollout-children",
                    "a pump rollout group requires at least two children",
                )
            try:
                return self._continual_rollout_control().create_group(request)
            except ContinualRolloutError as error:
                self._raise_continual_error(error)

        verification = self.validate_origin(request)
        parent = self._resume_run(self._parent_repository_root)
        verification_sha256 = pump_station_artifact_id(verification)
        event_schedule_sha256 = hashlib.sha256(
            pump_station_artifact_bytes(
                parent.state.scheduled_events,
                record_profile=parent.state.state_version.rsplit(".", maxsplit=1)[-1],
            )
        ).hexdigest()
        with self._repository.locked():
            self._repository.publish_group_request(request)
            children = tuple(
                self._create_child(
                    request,
                    child,
                    parent,
                    event_schedule_sha256,
                )
                for child in request.children
            )
            lineage = PumpStationRolloutLineage(
                lineage_version=PUMP_STATION_ROLLOUT_LINEAGE_VERSION,
                request_id=request.request_id,
                group_id=request.group_id,
                parent_snapshot=request.parent_snapshot,
                origin_verification_id=request.origin_verification_id,
                origin_verification_sha256=verification_sha256,
                information_boundary_id=request.information_boundary_id,
                event_schedule_id=request.event_schedule_id,
                event_schedule_sha256=event_schedule_sha256,
                fixed_future_condition_id=request.fixed_future_condition_id,
                future_condition_seed=request.future_condition_seed,
                split_group_id=request.split_group_id,
                fixed_condition_policy=request.fixed_condition_policy,
                children=children,
            )
            self._repository.publish_lineage(lineage)
            return self._repository.load_lineage(request.group_id)

    def validate_origin(
        self,
        request: PumpStationRolloutGroupRequest,
    ) -> PumpStationVerificationReport:
        """Validate the exact live parent snapshot before any child creation."""

        self._validate_group_request(request)
        parent = self._resume_run(self._parent_repository_root)
        current = parent.snapshot()
        if current != request.parent_snapshot:
            raise PumpStationRolloutError(
                "origin-snapshot",
                "rollout origin must be the current immutable parent snapshot",
            )
        initial_state = parent.repository.load_legacy_state(parent.manifest.initial_state_id)
        verification = verify_stewardship_run(
            parent.model,
            initial_state,
            parent.steps(),
            record_versions=parent.manifest.record_versions,
        )
        if not verification.valid or verification.final_state_id != current.state_id:
            raise PumpStationRolloutError(
                "origin-verification",
                "rollout origin did not pass full replay verification",
            )
        return verification

    def create_child(
        self,
        request: PumpStationRolloutGroupRequest | ContinualRolloutGroupRequest,
        child_id: str,
    ) -> PumpStationRolloutChildReceipt:
        """Create or recover one declared child without completing its sibling group."""

        if isinstance(request, ContinualRolloutGroupRequest):
            raise PumpStationRolloutError(
                "rollout-operation",
                "registered rollouts create complete groups only",
            )

        self.validate_origin(request)
        child = next((item for item in request.children if item.child_id == child_id), None)
        if child is None:
            raise PumpStationRolloutError("rollout-child-not-found", child_id)
        parent = self._resume_run(self._parent_repository_root)
        event_schedule_sha256 = hashlib.sha256(
            pump_station_artifact_bytes(
                parent.state.scheduled_events,
                record_profile=parent.state.state_version.rsplit(".", maxsplit=1)[-1],
            )
        ).hexdigest()
        with self._repository.locked():
            self._repository.publish_group_request(request)
            return self._create_child(
                request,
                child,
                parent,
                event_schedule_sha256,
            )

    def inspect_group(
        self,
        group_id: str,
    ) -> PumpStationRolloutLineage | ContinualRolloutLineage:
        """Load the complete private lineage for one rollout group."""

        if self._group_uses_continual_rollout(group_id):
            try:
                return self._continual_rollout_control().inspect_group(group_id)
            except ContinualRolloutError as error:
                self._raise_continual_error(error)
        return self._repository.load_lineage(group_id)

    def require_group_request_version(
        self,
        group_id: str,
        expected_version: str,
    ) -> None:
        """Reject an existing group that belongs to another transport version."""

        if expected_version != PUMP_STATION_ROLLOUT_REQUEST_VERSION:
            raise PumpStationRolloutError("rollout-version", expected_version)
        actual_version = (
            CONTINUAL_ROLLOUT_GROUP_REQUEST_SCHEMA_VERSION
            if self._group_uses_continual_rollout(group_id)
            else PUMP_STATION_ROLLOUT_REQUEST_VERSION
        )
        if actual_version != expected_version:
            raise PumpStationRolloutError(
                "rollout-version",
                f"group {group_id} uses {actual_version}",
            )

    def group_status(self, group_id: str) -> PumpStationRolloutGroupStatus:
        """Enumerate complete or interrupted child creation progress."""

        if self._group_uses_continual_rollout(group_id):
            try:
                status = self._continual_rollout_control().group_status(group_id)
            except ContinualRolloutError as error:
                self._raise_continual_error(error)
            return PumpStationRolloutGroupStatus(
                group_id=status.group_id,
                request_id=status.request_id,
                state=PumpStationRolloutGroupState(status.state.value),
                requested_child_ids=tuple(status.requested_child_ids),
                created_child_ids=tuple(status.created_child_ids),
            )
        request = self._repository.load_group_request(group_id)
        requested = tuple(child.child_id for child in request.children)
        created = tuple(child_id for child_id in requested if self._repository.child_receipt_exists(group_id, child_id))
        state = (
            PumpStationRolloutGroupState.READY
            if self._repository.lineage_exists(group_id) and created == requested
            else PumpStationRolloutGroupState.PREPARING
        )
        return PumpStationRolloutGroupStatus(
            group_id=group_id,
            request_id=request.request_id,
            state=state,
            requested_child_ids=requested,
            created_child_ids=created,
        )

    def parent_snapshot(self) -> PumpStationStateSnapshotRef:
        """Return the live parent snapshot for isolation checks."""

        return self._resume_run(self._parent_repository_root).snapshot()

    def open_actor_session(
        self,
        *,
        group_id: str,
        child_id: str,
        session_id: str,
        agent_tenure_id: str,
    ) -> PumpStationWorldSession:
        """Open only the selected child with no sibling or selection metadata."""

        if self._group_uses_continual_rollout(group_id):
            try:
                child_ref = self._continual_rollout_control().child_run_ref(
                    group_id,
                    child_id,
                )
            except ContinualRolloutError as error:
                self._raise_continual_error(error)
            child_root = self._continual_child_world_root(group_id, child_id)
            snapshot = PumpStationWorldRunRepository(child_root).current_snapshot()
            if (
                child_ref.group_id,
                child_ref.child_id,
                child_ref.task_world_id,
                snapshot.run_id,
                snapshot.episode_id,
                snapshot.world_branch_id,
            ) != (
                group_id,
                child_id,
                PUMP_STATION_TASK_WORLD_ID,
                child_ref.run_id,
                child_ref.episode_id,
                child_ref.world_branch_id,
            ):
                raise PumpStationRolloutError(
                    "rollout-child-run-ref",
                    "registered child identity differs from its verified run reference",
                )
            world_branch_id = child_ref.world_branch_id
        else:
            lineage = self.inspect_group(group_id)
            if not isinstance(lineage, PumpStationRolloutLineage):
                raise PumpStationRolloutError(
                    "rollout-version",
                    CONTINUAL_ROLLOUT_GROUP_REQUEST_SCHEMA_VERSION,
                )
            receipt = self._child_receipt(lineage, child_id)
            child_root = self._repository.child_world_root(group_id, child_id)
            snapshot = PumpStationWorldRunRepository(child_root).current_snapshot()
            world_branch_id = receipt.initial_snapshot.world_branch_id
        request = WorldSessionRequest(
            execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
            open_mode=WorldSessionOpenMode.RESUME,
            session_id=session_id,
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            agent_tenure_id=agent_tenure_id,
            run_id=snapshot.run_id,
            episode_id=snapshot.episode_id,
            world_branch_id=world_branch_id,
            start_snapshot=_shared_snapshot(snapshot),
        )
        return PumpStationWorldSessionFactory(
            child_root,
            package_root=self._package_root,
            rich_work_processes=self._rich_work_processes,
            evidence_health=self._evidence_health,
        ).open(
            request,
        )

    def schedule_treatment(
        self,
        request: PumpStationPhysicalTreatmentRequest,
    ) -> PumpStationPhysicalTreatmentScheduleReceipt:
        """Declare one bounded private treatment without changing the child."""

        self._require_authority(request.authority_id)
        if request.task_world_id != PUMP_STATION_TASK_WORLD_ID:
            raise PumpStationRolloutError("treatment-task-world", request.task_world_id)
        lineage = self.inspect_group(request.group_id)
        if isinstance(lineage, ContinualRolloutLineage):
            raise PumpStationRolloutError(
                "rollout-operation",
                "legacy scheduled treatments do not accept registered children",
            )
        child = self._child_receipt(lineage, request.child_id)
        run = self._resume_run(
            self._repository.child_world_root(request.group_id, request.child_id),
        )
        current = run.snapshot()
        observed_scope = (
            request.child_run_id,
            request.child_episode_id,
            request.child_world_branch_id,
            request.base_state_id,
            request.base_commit_id,
            request.based_on_sequence,
            request.parent_state_id,
        )
        expected_scope = (
            current.run_id,
            current.episode_id,
            current.world_branch_id,
            current.state_id,
            current.commit_id,
            current.sequence,
            lineage.parent_snapshot.state_id,
        )
        if observed_scope != expected_scope:
            raise PumpStationRolloutError(
                "treatment-snapshot",
                "treatment does not bind the selected child and parent lineage",
            )
        if child.initial_snapshot.state_id != lineage.parent_snapshot.state_id:
            raise PumpStationRolloutError("treatment-lineage", "child origin differs from parent")
        self._validate_treatment_envelope(run, request)
        receipt = PumpStationPhysicalTreatmentScheduleReceipt(
            receipt_version=PUMP_STATION_TREATMENT_RECEIPT_VERSION,
            request=request,
            request_content_sha256=pump_station_artifact_id(request),
            status=PumpStationRolloutTreatmentStatus.SCHEDULED,
            affected_pump_ids=request.affected_pump_ids,
            unaffected_pump_ids=tuple(
                pump_id for pump_id in run.model.pump_ids if pump_id not in request.affected_pump_ids
            ),
        )
        with self._repository.locked():
            self._repository.publish_treatment_schedule(receipt)
        return self._repository.load_treatment_schedule(
            request.group_id,
            request.child_id,
            request.request_id,
        )

    def inspect_treatment(
        self,
        *,
        group_id: str,
        child_id: str,
        treatment_request_id: str,
    ) -> PumpStationPhysicalTreatmentScheduleReceipt | PumpStationPhysicalTreatmentActivationReceipt:
        """Return private treatment progress without changing the child."""

        if self._repository.treatment_activation_exists(
            group_id,
            child_id,
            treatment_request_id,
        ):
            return self._repository.load_treatment_activation(
                group_id,
                child_id,
                treatment_request_id,
            )
        return self._repository.load_treatment_schedule(
            group_id,
            child_id,
            treatment_request_id,
        )

    def recover_treatment(
        self,
        *,
        group_id: str,
        child_id: str,
        treatment_request_id: str,
    ) -> PumpStationPhysicalTreatmentActivationReceipt:
        """Activate a due treatment or recover the exact activation after interruption."""

        with self._repository.locked():
            if self._repository.treatment_activation_exists(
                group_id,
                child_id,
                treatment_request_id,
            ):
                return self._repository.load_treatment_activation(
                    group_id,
                    child_id,
                    treatment_request_id,
                )
            scheduled = self._repository.load_treatment_schedule(
                group_id,
                child_id,
                treatment_request_id,
            )
            request = scheduled.request
            self._require_authority(request.authority_id)
            lineage = self.inspect_group(group_id)
            if isinstance(lineage, ContinualRolloutLineage):
                raise PumpStationRolloutError(
                    "rollout-operation",
                    "legacy scheduled treatments do not accept registered children",
                )
            self._child_receipt(lineage, child_id)
            child_root = self._repository.child_world_root(group_id, child_id)
            run = self._resume_run(child_root)
            if self._repository.activation_request_exists(
                group_id,
                child_id,
                treatment_request_id,
            ):
                activation = self._repository.load_activation_request(
                    group_id,
                    child_id,
                    treatment_request_id,
                )
            else:
                snapshot = run.snapshot()
                if run.state.physical.calendar_seconds < request.activation_calendar_seconds:
                    raise PumpStationRolloutError(
                        "activation-clock",
                        "child has not reached the treatment activation clock",
                    )
                activation = PumpStationPhysicalTreatmentActivationRequest(
                    request_id=f"{request.request_id}.activation",
                    schedule_request_id=request.request_id,
                    run_id=snapshot.run_id,
                    episode_id=snapshot.episode_id,
                    world_branch_id=snapshot.world_branch_id,
                    base_state_id=snapshot.state_id,
                    base_commit_id=snapshot.commit_id,
                    based_on_sequence=snapshot.sequence,
                    parent_state_id=request.parent_state_id,
                    treatment_class=request.treatment_class,
                    treatment_version=request.treatment_version,
                    affected_pump_ids=request.affected_pump_ids,
                    activation_calendar_seconds=request.activation_calendar_seconds,
                    severity=request.severity,
                    random_stream_id=request.random_stream_id,
                    random_seed=request.random_seed,
                    visibility_policy=request.visibility_policy,
                    decision_right_id=request.decision_right_id,
                )
                self._repository.publish_activation_request(
                    group_id,
                    child_id,
                    treatment_request_id,
                    activation,
                )
            prior = PumpStationStateSnapshotRef(
                snapshot_version=run.manifest.snapshot_version,
                run_id=activation.run_id,
                episode_id=activation.episode_id,
                world_branch_id=activation.world_branch_id,
                sequence=activation.based_on_sequence,
                state_id=activation.base_state_id,
                commit_id=activation.base_commit_id,
            )
            transition = run.apply_physical_treatment(activation)
            result = run.snapshot()
            receipt = PumpStationPhysicalTreatmentActivationReceipt(
                receipt_version=PUMP_STATION_TREATMENT_RECEIPT_VERSION,
                request=request,
                request_content_sha256=scheduled.request_content_sha256,
                activation_request_content_sha256=pump_station_artifact_id(activation),
                status=PumpStationRolloutTreatmentStatus.ACTIVATED,
                prior_snapshot=prior,
                activation_snapshot=result,
                transition_id=transition.receipt.transition_id,
                affected_pump_ids=scheduled.affected_pump_ids,
                unaffected_pump_ids=scheduled.unaffected_pump_ids,
            )
            self._repository.publish_treatment_activation(receipt)
            return self._repository.load_treatment_activation(
                group_id,
                child_id,
                treatment_request_id,
            )

    def _continual_child_world_root(self, group_id: str, child_id: str) -> Path:
        disjoint_roots = (self._parent_repository_root,) + (
            (Path(self._package_root),) if self._package_root is not None else ()
        )
        return ContinualRolloutRepository(
            self._rollout_repository_root,
            disjoint_roots=disjoint_roots,
        ).child_world_root(
            group_id,
            child_id,
        )

    def _continual_rollout_control(self) -> ContinualRolloutControl:
        return ContinualRolloutControl(
            pump_station_continual_world_definition(),
            parent_run_root=self._parent_repository_root,
            rollout_repository_root=self._rollout_repository_root,
            authorised_principal_ids=self._authorised_principal_sequence,
            package_root=self._package_root,
        )

    @staticmethod
    def _raise_continual_error(error: ContinualRolloutError) -> Never:
        code = {
            "request-conflict": "request-id-conflict",
            "child-request-conflict": "child-id-conflict",
            "child-receipt-conflict": "child-id-conflict",
            "lineage-conflict": "lineage-conflict",
            "authority": "rollout-unauthorised",
        }.get(error.code, error.code)
        raise PumpStationRolloutError(code, error.detail) from error

    def _create_child(
        self,
        request: PumpStationRolloutGroupRequest,
        child: PumpStationRolloutChildRequest,
        parent: PumpStationWorldRun,
        event_schedule_sha256: str,
    ) -> PumpStationRolloutChildReceipt:
        child_root = self._repository.child_world_root(request.group_id, child.child_id)
        run = PumpStationWorldRun.create(
            repository=PumpStationWorldRunRepository(child_root),
            package=parent.package,
            model=parent.model,
            initial_state=parent.state,
            run_id=child.run_id,
            episode_id=parent.manifest.episode_id,
            world_branch_id=child.world_branch_id,
            record_versions=parent.manifest.record_versions,
        )
        receipt = PumpStationRolloutChildReceipt(
            receipt_version=PUMP_STATION_ROLLOUT_CHILD_RECEIPT_VERSION,
            group_id=request.group_id,
            child_id=child.child_id,
            parent_snapshot=request.parent_snapshot,
            initial_snapshot=run.snapshot(),
            record_versions=parent.manifest.record_versions,
            package_content_id=parent.manifest.package_content_id,
            model_id=parent.manifest.model_id,
            information_boundary_id=request.information_boundary_id,
            event_schedule_id=request.event_schedule_id,
            event_schedule_sha256=event_schedule_sha256,
            fixed_future_condition_id=request.fixed_future_condition_id,
            future_condition_seed=request.future_condition_seed,
            agent_condition_id=child.agent_condition_id,
            agent_seed=child.agent_seed,
            split_group_id=request.split_group_id,
            fixed_condition_policy=request.fixed_condition_policy,
        )
        self._repository.publish_child_receipt(receipt)
        return self._repository.load_child_receipt(request.group_id, child.child_id)

    def _resume_run(self, root: Path) -> PumpStationWorldRun[Any, Any]:
        repository = PumpStationWorldRunRepository(root)
        snapshot = repository.current_snapshot()
        if isinstance(repository.load_manifest(), PumpStationWorldRunManifestV2):
            return PumpStationWorldRun.resume_reference_system(
                repository=repository,
                snapshot=snapshot,
            )
        package = load_reference_package(self._package_root)
        model = pump_station_model_from_package(package)
        return PumpStationWorldRun.resume(
            repository=repository,
            package=package,
            model=model,
            snapshot=snapshot,
        )

    def _validate_group_request(self, request: PumpStationRolloutGroupRequest) -> None:
        self._require_authority(request.authority_id)
        if request.request_version != PUMP_STATION_ROLLOUT_REQUEST_VERSION:
            raise PumpStationRolloutError("rollout-version", request.request_version)
        if request.task_world_id != PUMP_STATION_TASK_WORLD_ID:
            raise PumpStationRolloutError("rollout-task-world", request.task_world_id)
        if request.fixed_condition_policy != PUMP_STATION_FIXED_CONDITION_POLICY:
            raise PumpStationRolloutError(
                "fixed-condition-policy",
                request.fixed_condition_policy,
            )
        if len(request.children) < 2:
            raise PumpStationRolloutError("rollout-children", "a group requires at least two children")
        identities = tuple(child.child_id for child in request.children)
        run_ids = tuple(child.run_id for child in request.children)
        branches = tuple(child.world_branch_id for child in request.children)
        if (
            len(set(identities)) != len(identities)
            or len(set(run_ids)) != len(run_ids)
            or len(set(branches)) != len(branches)
            or request.parent_snapshot.world_branch_id in branches
        ):
            raise PumpStationRolloutError(
                "rollout-children",
                "child, run, and branch identities must be distinct from the parent",
            )

    def _validate_treatment_envelope(
        self,
        run: PumpStationWorldRun,
        request: PumpStationPhysicalTreatmentRequest,
    ) -> None:
        if (
            request.treatment_version != PUMP_STATION_PHYSICAL_TREATMENT_VERSION
            or request.visibility_policy != PUMP_STATION_PHYSICAL_TREATMENT_VISIBILITY
            or request.decision_right_id != PUMP_STATION_PHYSICAL_TREATMENT_DECISION_RIGHT
        ):
            raise PumpStationRolloutError(
                "treatment-policy",
                "treatment version, visibility, or decision right is unsupported",
            )
        expected_pumps = set(run.model.pump_ids)
        affected = set(request.affected_pump_ids)
        common_cause = request.treatment_class is PumpStationPhysicalTreatmentClass.COMMON_CAUSE_OBSTRUCTION
        if (
            len(affected) != len(request.affected_pump_ids)
            or not affected <= expected_pumps
            or common_cause
            and affected != expected_pumps
            or not common_cause
            and len(affected) != 1
        ):
            raise PumpStationRolloutError(
                "affected-entities",
                "treatment class and affected pump set differ",
            )
        now = run.state.physical.calendar_seconds
        if (
            request.activation_calendar_seconds < now
            or request.activation_calendar_seconds > run.model.exposure_limits.calendar_seconds
            or request.random_seed < 0
        ):
            raise PumpStationRolloutError(
                "treatment-envelope",
                "activation clock or random seed is outside the approved envelope",
            )

    @staticmethod
    def _child_receipt(
        lineage: PumpStationRolloutLineage,
        child_id: str,
    ) -> PumpStationRolloutChildReceipt:
        for child in lineage.children:
            if child.child_id == child_id:
                return child
        raise PumpStationRolloutError("rollout-child-not-found", child_id)

    def _group_uses_continual_rollout(self, group_id: str) -> bool:
        payload = self._repository.group_request_payload_if_present(group_id)
        if payload is None:
            return False
        try:
            value = json.loads(payload)
        except (TypeError, ValueError) as error:
            raise PumpStationRolloutError(
                "rollout-artifact",
                "group request is not strict JSON",
            ) from error
        if not isinstance(value, dict) or "schema_version" not in value:
            return False
        if value.get("schema_version") != CONTINUAL_ROLLOUT_GROUP_REQUEST_SCHEMA_VERSION:
            raise PumpStationRolloutError(
                "rollout-version",
                str(value.get("schema_version")),
            )
        try:
            ContinualRolloutGroupRequest.model_validate_json(payload)
        except ValueError as error:
            raise PumpStationRolloutError(
                "rollout-artifact",
                "continual rollout request is invalid",
            ) from error
        return True

    def _require_authority(self, authority_id: str) -> None:
        if authority_id not in self._authorised_principal_ids:
            raise PumpStationRolloutError("rollout-unauthorised", authority_id)


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
