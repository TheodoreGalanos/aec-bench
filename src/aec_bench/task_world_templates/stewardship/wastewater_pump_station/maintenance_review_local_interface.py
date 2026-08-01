# ABOUTME: Defines the installed JSON transport for pump-station closeout review.
# ABOUTME: Keeps reviewer calls and host preparation controls in separate surfaces.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import JsonValue, model_validator

from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_control import (
    PumpStationReviewControl,
    PumpStationReviewControlRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_session import (
    PumpStationReviewHandover,
    PumpStationReviewSessionFactory,
    PumpStationReviewSessionRequest,
)

PUMP_STATION_REVIEW_LOCAL_INTERFACE_VERSION = "pump-station.review-local-interface.v1"


class PumpStationReviewLocalInterfaceRequest(FrozenStrictModel):
    """One strict reviewer or host-control JSON request."""

    schema_version: str = PUMP_STATION_REVIEW_LOCAL_INTERFACE_VERSION
    surface: Literal["reviewer", "control"]
    operation: Literal["capabilities", "execute", "observe", "invoke"]
    authority_id: NonEmptyStr | None = None
    control_request: PumpStationReviewControlRequest | None = None
    session_request: PumpStationReviewSessionRequest | None = None
    handover: PumpStationReviewHandover | None = None
    action_name: NonEmptyStr | None = None
    arguments: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.schema_version != PUMP_STATION_REVIEW_LOCAL_INTERFACE_VERSION:
            raise ValueError("unsupported review local interface version")
        if self.surface == "control":
            if self.operation not in {"capabilities", "execute"}:
                raise ValueError("control interface operation is unavailable")
            if (
                self.session_request is not None
                or self.handover is not None
                or self.action_name is not None
                or self.arguments is not None
            ):
                raise ValueError("control request cannot contain reviewer data")
            if self.operation == "capabilities":
                if self.authority_id is None or self.control_request is not None:
                    raise ValueError("control capabilities requires one authority identity")
            elif self.control_request is None or self.authority_id is not None:
                raise ValueError("control execute requires one control request")
            return self
        if self.operation not in {"observe", "invoke"}:
            raise ValueError("reviewer interface operation is unavailable")
        if self.session_request is None or self.authority_id is not None or self.control_request is not None:
            raise ValueError("reviewer request requires one session binding")
        if self.operation == "observe":
            if self.action_name is not None or self.arguments is not None:
                raise ValueError("reviewer observation cannot contain an action")
        elif self.action_name is None or self.arguments is None:
            raise ValueError("reviewer invoke requires one action and arguments")
        return self


def execute_pump_station_review_local_request(
    *,
    source_run_root: Path,
    review_repository_root: Path,
    request: PumpStationReviewLocalInterfaceRequest,
    host_authority_id: str | None = None,
) -> dict[str, Any]:
    """Execute one validated installed request through production interfaces."""
    if request.surface == "control":
        if host_authority_id is None:
            raise ValueError("review host control requires an authority identity")
        control = PumpStationReviewControl(
            source_run_root=source_run_root,
            review_repository_root=review_repository_root,
            authorised_principal_ids=(host_authority_id,),
        )
        if request.operation == "capabilities":
            if request.authority_id is None:
                raise ValueError("control capabilities lacks authority identity")
            return control.capabilities(request.authority_id).model_dump(mode="json")
        if request.control_request is None:
            raise ValueError("control execute lacks its request")
        return control.execute(request.control_request).model_dump(mode="json")
    if request.session_request is None:
        raise ValueError("reviewer request lacks its session")
    session = PumpStationReviewSessionFactory(review_repository_root).open(
        request.session_request,
        handover=request.handover,
    )
    if request.operation == "observe":
        return session.observe().model_dump(mode="json")
    if request.action_name is None or request.arguments is None:
        raise ValueError("reviewer invoke lacks its action")
    payload = session.invoke(
        request.action_name,
        dict(request.arguments),
    )
    result = json.loads(payload)
    if not isinstance(result, dict):
        raise TypeError("reviewer action result must be an object")
    return result


__all__ = (
    "PUMP_STATION_REVIEW_LOCAL_INTERFACE_VERSION",
    "PumpStationReviewLocalInterfaceRequest",
    "execute_pump_station_review_local_request",
)
