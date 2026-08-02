# ABOUTME: Defines the strict request envelope for the installed pump-station JSON interface.
# ABOUTME: Keeps actor calls and host-control calls separate in one machine-readable transport.

from __future__ import annotations

from typing import Literal, Self

from pydantic import model_validator

from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.contracts.world_interface import (
    WorldActorActionRequest,
    WorldControlRequest,
)
from aec_bench.contracts.world_session import WorldSessionOpenMode, WorldSessionRequest
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rollout_interface import (
    PumpStationRolloutControlRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_control import (
    PumpStationEvidenceControlRequest,
)

PUMP_STATION_LOCAL_INTERFACE_SCHEMA_VERSION = "pump-station.local-interface.v1"


class PumpStationLocalInterfaceRequest(FrozenStrictModel):
    """One strict actor or control request accepted by the installed interface."""

    schema_version: str = PUMP_STATION_LOCAL_INTERFACE_SCHEMA_VERSION
    surface: Literal["actor", "control"]
    operation: NonEmptyStr
    session_request: WorldSessionRequest | None = None
    action_request: WorldActorActionRequest | None = None
    control_request: (
        WorldControlRequest | PumpStationEvidenceControlRequest | PumpStationRolloutControlRequest | None
    ) = None
    authority_id: NonEmptyStr | None = None
    evidence_health: bool = False

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.schema_version != PUMP_STATION_LOCAL_INTERFACE_SCHEMA_VERSION:
            raise ValueError("unsupported pump-station local interface schema version")
        if self.surface == "actor":
            if self.operation not in {"capabilities", "observe", "invoke"}:
                raise ValueError("actor local-interface operation is unavailable")
            if self.session_request is None:
                raise ValueError("actor local-interface request requires a session")
            if self.session_request.open_mode is not WorldSessionOpenMode.RESUME:
                raise ValueError("actor local-interface session must resume an existing run")
            if (self.operation == "invoke") != (self.action_request is not None):
                raise ValueError("actor invoke requires exactly one action request")
            if self.control_request is not None or self.authority_id is not None:
                raise ValueError("actor local-interface request cannot contain host control")
            if self.evidence_health:
                raise ValueError("actor local-interface request cannot select a host profile")
            return self
        if self.operation not in {"capabilities", "execute"}:
            raise ValueError("control local-interface operation is unavailable")
        if self.session_request is not None or self.action_request is not None:
            raise ValueError("control local-interface request cannot contain actor session data")
        if self.operation == "execute":
            if self.control_request is None or self.authority_id is not None:
                raise ValueError("control execute requires exactly one control request")
        elif self.authority_id is None or self.control_request is not None:
            raise ValueError("control capabilities requires exactly one authority identity")
        return self
