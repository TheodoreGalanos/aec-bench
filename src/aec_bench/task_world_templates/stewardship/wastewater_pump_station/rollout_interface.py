# ABOUTME: Defines strict machine-readable rollout and physical-treatment control requests.
# ABOUTME: Converts installed host calls into the same task-owned rollout control operations.

from __future__ import annotations

from typing import Literal, Self

from pydantic import model_validator

from aec_bench.contracts.harness_kernel import ContentAddressedModel
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.contracts.world_session import WorldSessionResult
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_treatments import (
    PumpStationPhysicalTreatmentRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rollout_control import (
    PumpStationRolloutControl,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rollout_models import (
    PumpStationPhysicalTreatmentActivationReceipt,
    PumpStationPhysicalTreatmentScheduleReceipt,
    PumpStationRolloutChildReceipt,
    PumpStationRolloutGroupRequest,
    PumpStationRolloutGroupStatus,
    PumpStationRolloutLineage,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationVerificationReport,
)

PUMP_STATION_ROLLOUT_CONTROL_INTERFACE_VERSION = "pump-station.rollout-control.v1"


class PumpStationRolloutControlRequest(ContentAddressedModel):
    """One closed installed request for rollout or treatment control."""

    schema_version: str = PUMP_STATION_ROLLOUT_CONTROL_INTERFACE_VERSION
    request_id: NonEmptyStr
    operation: Literal[
        "validate_rollout_origin",
        "create_rollout_child",
        "create_rollout_group",
        "inspect_rollout_group",
        "open_rollout_actor_session",
        "schedule_physical_treatment",
        "inspect_physical_treatment",
        "recover_physical_treatment",
    ]
    task_world_id: NonEmptyStr
    authority_id: NonEmptyStr
    group_request: PumpStationRolloutGroupRequest | None = None
    group_id: NonEmptyStr | None = None
    child_id: NonEmptyStr | None = None
    session_id: NonEmptyStr | None = None
    agent_tenure_id: NonEmptyStr | None = None
    treatment_request: PumpStationPhysicalTreatmentRequest | None = None
    treatment_request_id: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.schema_version != PUMP_STATION_ROLLOUT_CONTROL_INTERFACE_VERSION:
            raise ValueError("unsupported pump-station rollout control version")
        if self.operation in {
            "validate_rollout_origin",
            "create_rollout_child",
            "create_rollout_group",
        }:
            child_required = self.operation == "create_rollout_child"
            if (
                self.group_request is None
                or (self.child_id is not None) != child_required
                or any(
                    item is not None
                    for item in (
                        self.group_id,
                        self.session_id,
                        self.agent_tenure_id,
                        self.treatment_request,
                        self.treatment_request_id,
                    )
                )
            ):
                raise ValueError("rollout origin and creation operations require one group request")
            if self.group_request.request_id != self.request_id:
                raise ValueError("rollout request identities differ")
            return self
        if self.operation == "inspect_rollout_group":
            if self.group_id is None or any(
                item is not None
                for item in (
                    self.group_request,
                    self.child_id,
                    self.session_id,
                    self.agent_tenure_id,
                    self.treatment_request,
                    self.treatment_request_id,
                )
            ):
                raise ValueError("inspect rollout group requires exactly one group identity")
            return self
        if self.operation == "open_rollout_actor_session":
            if any(
                item is None
                for item in (
                    self.group_id,
                    self.child_id,
                    self.session_id,
                    self.agent_tenure_id,
                )
            ) or any(
                item is not None
                for item in (
                    self.group_request,
                    self.treatment_request,
                    self.treatment_request_id,
                )
            ):
                raise ValueError("open rollout actor session requires exact child session identities")
            return self
        if self.operation == "schedule_physical_treatment":
            if self.treatment_request is None or any(
                item is not None
                for item in (
                    self.group_request,
                    self.group_id,
                    self.child_id,
                    self.session_id,
                    self.agent_tenure_id,
                    self.treatment_request_id,
                )
            ):
                raise ValueError("schedule physical treatment requires exactly one treatment request")
            if self.treatment_request.request_id != self.request_id:
                raise ValueError("physical treatment request identities differ")
            return self
        if any(item is None for item in (self.group_id, self.child_id, self.treatment_request_id)):
            raise ValueError("treatment inspection and recovery require exact treatment identity")
        if any(
            item is not None
            for item in (
                self.group_request,
                self.session_id,
                self.agent_tenure_id,
                self.treatment_request,
            )
        ):
            raise ValueError("treatment inspection and recovery contain unrelated fields")
        return self


class PumpStationRolloutControlResult(ContentAddressedModel):
    """Machine-readable result from one rollout control operation."""

    schema_version: str = PUMP_STATION_ROLLOUT_CONTROL_INTERFACE_VERSION
    request_content_sha256: NonEmptyStr
    operation: NonEmptyStr
    origin_verification: PumpStationVerificationReport | None = None
    child_receipt: PumpStationRolloutChildReceipt | None = None
    group_status: PumpStationRolloutGroupStatus | None = None
    lineage: PumpStationRolloutLineage | None = None
    session_result: WorldSessionResult | None = None
    treatment_schedule: PumpStationPhysicalTreatmentScheduleReceipt | None = None
    treatment_activation: PumpStationPhysicalTreatmentActivationReceipt | None = None


def execute_pump_station_rollout_request(
    control: PumpStationRolloutControl,
    request: PumpStationRolloutControlRequest,
) -> PumpStationRolloutControlResult:
    """Execute one strict request through the common rollout control."""

    lineage = None
    session_result = None
    treatment_schedule = None
    treatment_activation = None
    origin_verification = None
    child_receipt = None
    group_status = None
    if request.operation == "validate_rollout_origin":
        assert request.group_request is not None
        origin_verification = control.validate_origin(request.group_request)
    elif request.operation == "create_rollout_child":
        assert request.group_request is not None
        assert request.child_id is not None
        child_receipt = control.create_child(
            request.group_request,
            request.child_id,
        )
        group_status = control.group_status(request.group_request.group_id)
    elif request.operation == "create_rollout_group":
        assert request.group_request is not None
        lineage = control.create_group(request.group_request)
    elif request.operation == "inspect_rollout_group":
        assert request.group_id is not None
        group_status = control.group_status(request.group_id)
        if group_status.state.value == "ready":
            lineage = control.inspect_group(request.group_id)
    elif request.operation == "open_rollout_actor_session":
        assert request.group_id is not None
        assert request.child_id is not None
        assert request.session_id is not None
        assert request.agent_tenure_id is not None
        session_result = control.open_actor_session(
            group_id=request.group_id,
            child_id=request.child_id,
            session_id=request.session_id,
            agent_tenure_id=request.agent_tenure_id,
        ).result
    elif request.operation == "schedule_physical_treatment":
        assert request.treatment_request is not None
        treatment_schedule = control.schedule_treatment(request.treatment_request)
    elif request.operation == "inspect_physical_treatment":
        assert request.group_id is not None
        assert request.child_id is not None
        assert request.treatment_request_id is not None
        treatment = control.inspect_treatment(
            group_id=request.group_id,
            child_id=request.child_id,
            treatment_request_id=request.treatment_request_id,
        )
        if isinstance(treatment, PumpStationPhysicalTreatmentActivationReceipt):
            treatment_activation = treatment
        else:
            treatment_schedule = treatment
    else:
        assert request.group_id is not None
        assert request.child_id is not None
        assert request.treatment_request_id is not None
        treatment_activation = control.recover_treatment(
            group_id=request.group_id,
            child_id=request.child_id,
            treatment_request_id=request.treatment_request_id,
        )
    return PumpStationRolloutControlResult(
        request_content_sha256=request.content_sha256,
        operation=request.operation,
        origin_verification=origin_verification,
        child_receipt=child_receipt,
        group_status=group_status,
        lineage=lineage,
        session_result=session_result,
        treatment_schedule=treatment_schedule,
        treatment_activation=treatment_activation,
    )
