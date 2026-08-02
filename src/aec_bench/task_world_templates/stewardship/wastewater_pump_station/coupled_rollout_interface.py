# ABOUTME: Defines the strict ASW-8 rollout-control v2 request and result contract.
# ABOUTME: Routes direct and Harbor control through the same isolated child operations.

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, model_validator

from aec_bench.contracts.harness_kernel import ContentAddressedModel
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.actor_interface import (
    validate_pump_station_actor_arguments_v2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_rollout import (
    PUMP_STATION_COUPLED_ROLLOUT_CONTROL_VERSION,
    PUMP_STATION_COUPLED_ROLLOUT_REQUEST_VERSION,
    PumpStationCoupledRolloutChildRequest,
    PumpStationCoupledRolloutControl,
    PumpStationCoupledRolloutGroupRequest,
    PumpStationCoupledSnapshotRef,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
    PUMP_STATION_COUPLED_TREATMENT_VERSION,
    PumpStationCoupledTreatmentRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_temporal import (
    execute_coupled_temporal_action,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    canonical_stewardship_value,
)

_TASK_WORLD_ID = "wastewater-pump-station-stewardship.v1"


class PumpStationCoupledSnapshotRecord(FrozenStrictModel):
    """Strict JSON form of one exact coupled parent snapshot."""

    run_id: NonEmptyStr
    episode_id: NonEmptyStr
    world_branch_id: NonEmptyStr
    sequence: int
    state_id: NonEmptyStr
    commit_id: NonEmptyStr

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        if self.sequence < 0:
            raise ValueError("coupled rollout snapshot sequence must be non-negative")
        return self

    def to_runtime(self) -> PumpStationCoupledSnapshotRef:
        """Return the task-owned immutable runtime snapshot."""
        return PumpStationCoupledSnapshotRef(**self.model_dump(mode="python"))


class PumpStationCoupledRolloutChildRecord(FrozenStrictModel):
    """Strict content-addressed JSON form of one v2 child request."""

    request_version: NonEmptyStr
    child_id: NonEmptyStr
    run_id: NonEmptyStr
    world_branch_id: NonEmptyStr
    agent_condition_id: NonEmptyStr
    agent_seed: int

    @model_validator(mode="after")
    def validate_child(self) -> Self:
        if self.request_version != PUMP_STATION_COUPLED_ROLLOUT_REQUEST_VERSION:
            raise ValueError("unsupported coupled rollout child version")
        return self

    def to_runtime(self) -> PumpStationCoupledRolloutChildRequest:
        """Return the task-owned immutable runtime child request."""
        return PumpStationCoupledRolloutChildRequest(**self.model_dump(mode="python"))

    @property
    def content_id(self) -> str:
        """Return the canonical identity of the complete v2 child request."""
        return self.to_runtime().content_id


class PumpStationCoupledRolloutGroupRecord(FrozenStrictModel):
    """Strict JSON form of one complete v2 coupled rollout group request."""

    request_version: NonEmptyStr
    request_id: NonEmptyStr
    group_id: NonEmptyStr
    task_world_id: NonEmptyStr
    authority_id: NonEmptyStr
    parent_snapshot: PumpStationCoupledSnapshotRecord
    parent_manifest_content_id: NonEmptyStr
    origin_verification_content_id: NonEmptyStr
    reference_system_content_id: NonEmptyStr
    event_schedule_sha256: NonEmptyStr
    information_boundary_id: NonEmptyStr
    temporal_bundle_content_id: NonEmptyStr
    child_request_content_ids: tuple[NonEmptyStr, ...]
    children: tuple[PumpStationCoupledRolloutChildRecord, ...]

    @model_validator(mode="after")
    def validate_group(self) -> Self:
        if self.request_version != PUMP_STATION_COUPLED_ROLLOUT_REQUEST_VERSION:
            raise ValueError("unsupported coupled rollout group version")
        if self.task_world_id != _TASK_WORLD_ID:
            raise ValueError("unsupported coupled rollout task world")
        if not self.children:
            raise ValueError("coupled rollout group requires at least one child")
        expected = tuple(child.content_id for child in self.children)
        if self.child_request_content_ids != expected:
            raise ValueError("coupled rollout child content identities differ")
        return self

    def to_runtime(self) -> PumpStationCoupledRolloutGroupRequest:
        """Return the task-owned immutable runtime group request."""
        return PumpStationCoupledRolloutGroupRequest(
            request_version=self.request_version,
            request_id=self.request_id,
            group_id=self.group_id,
            task_world_id=self.task_world_id,
            authority_id=self.authority_id,
            parent_snapshot=self.parent_snapshot.to_runtime(),
            parent_manifest_content_id=self.parent_manifest_content_id,
            origin_verification_content_id=self.origin_verification_content_id,
            reference_system_content_id=self.reference_system_content_id,
            event_schedule_sha256=self.event_schedule_sha256,
            information_boundary_id=self.information_boundary_id,
            temporal_bundle_content_id=self.temporal_bundle_content_id,
            child_request_content_ids=self.child_request_content_ids,
            children=tuple(child.to_runtime() for child in self.children),
        )

    @property
    def content_id(self) -> str:
        """Return the canonical identity of the complete v2 group request."""
        return self.to_runtime().content_id


class PumpStationCoupledTreatmentRecord(FrozenStrictModel):
    """Strict JSON form of one child-private three-pump treatment request."""

    version: NonEmptyStr
    request_id: NonEmptyStr
    authority_id: NonEmptyStr
    treatment_label: NonEmptyStr
    affected_pump_ids: tuple[NonEmptyStr, ...]
    obstruction_delta: Decimal
    clearance_loss_delta: Decimal
    base_state_id: NonEmptyStr

    @model_validator(mode="after")
    def validate_treatment(self) -> Self:
        if self.version != PUMP_STATION_COUPLED_TREATMENT_VERSION:
            raise ValueError("unsupported coupled treatment version")
        return self

    def to_runtime(self) -> PumpStationCoupledTreatmentRequest:
        """Return the task-owned immutable runtime treatment request."""
        return PumpStationCoupledTreatmentRequest(**self.model_dump(mode="python"))


class PumpStationCoupledRolloutControlRequest(ContentAddressedModel):
    """One closed installed or Harbor request for rollout-control v2."""

    schema_version: str = PUMP_STATION_COUPLED_ROLLOUT_CONTROL_VERSION
    request_id: NonEmptyStr
    operation: Literal[
        "create_rollout_group",
        "inspect_rollout_group",
        "apply_child_actor",
        "apply_child_treatment",
    ]
    task_world_id: NonEmptyStr
    authority_id: NonEmptyStr
    group_request: PumpStationCoupledRolloutGroupRecord | None = None
    group_id: NonEmptyStr | None = None
    child_id: NonEmptyStr | None = None
    action_name: NonEmptyStr | None = None
    arguments: dict[str, Any] | None = None
    agent_tenure_id: NonEmptyStr | None = None
    session_id: NonEmptyStr | None = None
    treatment_request: PumpStationCoupledTreatmentRecord | None = None

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.schema_version != PUMP_STATION_COUPLED_ROLLOUT_CONTROL_VERSION:
            raise ValueError("unsupported coupled rollout-control interface version")
        if self.task_world_id != _TASK_WORLD_ID:
            raise ValueError("unsupported coupled rollout-control task world")
        if self.operation == "create_rollout_group":
            if self.group_request is None or any(
                value is not None
                for value in (
                    self.group_id,
                    self.child_id,
                    self.action_name,
                    self.arguments,
                    self.agent_tenure_id,
                    self.session_id,
                    self.treatment_request,
                )
            ):
                raise ValueError("create rollout group requires exactly one group request")
            if self.request_id != self.group_request.request_id or self.authority_id != self.group_request.authority_id:
                raise ValueError("rollout-control and group identities differ")
            return self
        if self.operation == "inspect_rollout_group":
            if self.group_id is None or any(
                value is not None
                for value in (
                    self.group_request,
                    self.child_id,
                    self.action_name,
                    self.arguments,
                    self.agent_tenure_id,
                    self.session_id,
                    self.treatment_request,
                )
            ):
                raise ValueError("inspect rollout group requires exactly one group identity")
            return self
        if self.operation == "apply_child_actor":
            if any(value is None for value in (self.group_id, self.child_id, self.action_name, self.arguments)) or any(
                value is not None for value in (self.group_request, self.treatment_request)
            ):
                raise ValueError("child actor control requires exact child action fields")
            temporal = self.action_name in {"search_evidence", "fetch_evidence"}
            if temporal != (self.agent_tenure_id is not None and self.session_id is not None):
                raise ValueError("child temporal action requires exact tenure and session identities")
            return self
        if (
            self.group_id is None
            or self.child_id is None
            or self.treatment_request is None
            or any(
                value is not None
                for value in (
                    self.group_request,
                    self.action_name,
                    self.arguments,
                    self.agent_tenure_id,
                    self.session_id,
                )
            )
        ):
            raise ValueError("child treatment control requires exact child treatment fields")
        if (
            self.request_id != self.treatment_request.request_id
            or self.authority_id != self.treatment_request.authority_id
        ):
            raise ValueError("rollout-control and treatment identities differ")
        return self


class PumpStationCoupledRolloutControlResult(ContentAddressedModel):
    """Transport-safe result from one rollout-control v2 operation."""

    schema_version: str = PUMP_STATION_COUPLED_ROLLOUT_CONTROL_VERSION
    request_content_sha256: NonEmptyStr
    operation: NonEmptyStr
    payload: dict[str, Any]


def execute_coupled_rollout_request(
    control: PumpStationCoupledRolloutControl,
    request: PumpStationCoupledRolloutControlRequest,
) -> PumpStationCoupledRolloutControlResult:
    """Execute one strict request through the common v2 rollout control."""
    if request.operation == "create_rollout_group":
        assert request.group_request is not None
        payload: object = control.create_group(request.group_request.to_runtime())
    elif request.operation == "inspect_rollout_group":
        assert request.group_id is not None
        payload = control.inspect_group(request.group_id)
    elif request.operation == "apply_child_actor":
        assert request.group_id is not None
        assert request.child_id is not None
        assert request.action_name is not None
        assert request.arguments is not None
        arguments = validate_pump_station_actor_arguments_v2(
            request.action_name,
            request.arguments,
        )
        if request.action_name in {"search_evidence", "fetch_evidence"}:
            assert request.agent_tenure_id is not None
            assert request.session_id is not None
            child = control.open_child(request.group_id, request.child_id)
            payload = execute_coupled_temporal_action(
                run_root=control.child_run_root(request.group_id, request.child_id),
                run=child,
                request_id=request.request_id,
                action_name=request.action_name,
                arguments=arguments,
                agent_tenure_id=request.agent_tenure_id,
                session_id=request.session_id,
            )
        else:
            payload = control.apply_child_actor(
                request.group_id,
                request.child_id,
                request_id=request.request_id,
                action_name=request.action_name,
                arguments=arguments,
            ).state
    else:
        assert request.group_id is not None
        assert request.child_id is not None
        assert request.treatment_request is not None
        payload = control.apply_child_treatment(
            request.group_id,
            request.child_id,
            request.treatment_request.to_runtime(),
        ).state
    return PumpStationCoupledRolloutControlResult(
        request_content_sha256=request.content_sha256,
        operation=request.operation,
        payload=_transport_payload(payload),
    )


def execute_coupled_harbor_rollout_request(
    *,
    parent_repository_root: Path,
    rollout_repository_root: Path,
    authorised_principal_id: str,
    request: PumpStationCoupledRolloutControlRequest,
) -> PumpStationCoupledRolloutControlResult:
    """Dispatch Harbor rollout-control v2 through the same strict operation path."""
    if request.authority_id != authorised_principal_id:
        raise ValueError("Harbor rollout authority differs from the signed request")
    control = PumpStationCoupledRolloutControl(
        parent_repository_root=parent_repository_root,
        rollout_repository_root=rollout_repository_root,
        authorised_principal_ids=(authorised_principal_id,),
    )
    return execute_coupled_rollout_request(control, request)


def _transport_payload(value: object) -> dict[str, Any]:
    serialized = (
        value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else canonical_stewardship_value(value, record_profile="v4")
    )
    if not isinstance(serialized, dict):
        raise TypeError("coupled rollout result payload must be an object")
    return serialized


__all__ = (
    "PumpStationCoupledRolloutChildRecord",
    "PumpStationCoupledRolloutControlRequest",
    "PumpStationCoupledRolloutControlResult",
    "PumpStationCoupledRolloutGroupRecord",
    "PumpStationCoupledSnapshotRecord",
    "PumpStationCoupledTreatmentRecord",
    "execute_coupled_harbor_rollout_request",
    "execute_coupled_rollout_request",
)
