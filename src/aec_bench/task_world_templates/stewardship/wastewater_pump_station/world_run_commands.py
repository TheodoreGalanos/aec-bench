# ABOUTME: Rebuilds strict pump actor and root-control inputs from durable registered commands.
# ABOUTME: Verifies command content identity before repository selection or replay.

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import NoReturn, cast

from pydantic import JsonValue

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationCommonBoundaryRequest,
    PumpStationCoupledTreatmentRequest,
    PumpStationOperationsBoundaryReviewRequest,
    PumpStationProcessOutcomeRequest,
    PumpStationRootControl,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationCommand,
    PumpStationWorldRunError,
)

type PumpStationDecodedCommand = WorldActorActionRequest | PumpStationRootControl

_ROOT_CONTROL_ARGUMENT_FIELDS = {
    "operations_review": frozenset(
        {
            "version",
            "review_id",
            "review_kind",
            "pump_id",
            "restriction_or_isolation_permit_id",
            "accepted_evidence_id",
            "requested_outcome",
            "base_state_id",
            "operations_authority_id",
            "reason",
        }
    ),
    "process_outcome": frozenset(
        {
            "version",
            "request_id",
            "authority_id",
            "process_id",
            "outcome",
            "evidence_id",
            "base_state_id",
        }
    ),
    "common_boundary": frozenset(
        {
            "version",
            "request_id",
            "authority_id",
            "boundary_kind",
            "available",
            "base_state_id",
        }
    ),
    "coupled_treatment": frozenset(
        {
            "version",
            "request_id",
            "authority_id",
            "treatment_label",
            "affected_pump_ids",
            "obstruction_delta",
            "clearance_loss_delta",
            "base_state_id",
        }
    ),
}


def _fail(code: str, detail: str) -> NoReturn:
    raise PumpStationWorldRunError(code, detail)


def decode_pump_station_command(
    command: PumpStationCommand,
) -> PumpStationDecodedCommand:
    """Rebuild and verify the exact public or task-semantic command input."""
    arguments = json.loads(command.arguments_json)
    if not isinstance(arguments, dict):
        _fail("command-content", "command arguments are not an object")
    if command.kind == "actor":
        request = _actor_request_from_command(
            command,
            cast(dict[str, JsonValue], arguments),
        )
        if (
            canonical_content_sha256(
                {
                    "request_id": request.request_id,
                    "decision_id": request.decision_id,
                    "action_name": request.action_name,
                    "arguments": request.arguments,
                }
            )
            != command.request_content_id
        ):
            _fail("command-content", "actor request content identity differs")
        return request
    control = _root_control_from_command(command, arguments)
    if control.content_id != command.request_content_id:
        _fail("command-content", "root-control content identity differs")
    authority_id = (
        control.operations_authority_id
        if isinstance(control, PumpStationOperationsBoundaryReviewRequest)
        else control.authority_id
    )
    if authority_id != command.authority_id:
        _fail("command-content", "root-control authority differs")
    return control


def _actor_request_from_command(
    command: PumpStationCommand,
    arguments: dict[str, JsonValue],
) -> WorldActorActionRequest:
    actor_fields = (
        command.decision_id,
        command.actor_id,
        command.agent_tenure_id,
        command.actor_view_id,
        command.information_set_id,
    )
    if any(value is None for value in actor_fields):
        _fail("command-content", "actor command lacks its binding")
    return WorldActorActionRequest(
        request_id=command.request_id,
        decision_id=cast(str, command.decision_id),
        action_name=command.action_name,
        arguments=arguments,
    )


def _root_control_from_command(
    command: PumpStationCommand,
    arguments: dict[str, object],
) -> PumpStationRootControl:
    expected_fields = _ROOT_CONTROL_ARGUMENT_FIELDS.get(command.kind)
    if expected_fields is None:
        _fail("command-content", f"unsupported registered control kind {command.kind}")
    observed_fields = frozenset(arguments)
    if observed_fields != expected_fields:
        missing = sorted(expected_fields - observed_fields)
        extra = sorted(observed_fields - expected_fields)
        _fail(
            "command-content",
            f"{command.kind} control fields differ: missing={missing}, extra={extra}",
        )
    if command.kind == "operations_review":
        return PumpStationOperationsBoundaryReviewRequest(
            version=_text_argument(arguments, "version"),
            review_id=_text_argument(arguments, "review_id"),
            review_kind=_text_argument(arguments, "review_kind"),
            pump_id=_text_argument(arguments, "pump_id"),
            restriction_or_isolation_permit_id=_text_argument(
                arguments,
                "restriction_or_isolation_permit_id",
            ),
            accepted_evidence_id=_text_argument(arguments, "accepted_evidence_id"),
            requested_outcome=_text_argument(arguments, "requested_outcome"),
            base_state_id=_text_argument(arguments, "base_state_id"),
            operations_authority_id=_text_argument(
                arguments,
                "operations_authority_id",
            ),
            reason=_text_argument(arguments, "reason"),
        )
    if command.kind == "process_outcome":
        return PumpStationProcessOutcomeRequest(
            version=_text_argument(arguments, "version"),
            request_id=_text_argument(arguments, "request_id"),
            authority_id=_text_argument(arguments, "authority_id"),
            process_id=_text_argument(arguments, "process_id"),
            outcome=_text_argument(arguments, "outcome"),
            evidence_id=_text_argument(arguments, "evidence_id"),
            base_state_id=_text_argument(arguments, "base_state_id"),
        )
    if command.kind == "common_boundary":
        return PumpStationCommonBoundaryRequest(
            version=_text_argument(arguments, "version"),
            request_id=_text_argument(arguments, "request_id"),
            authority_id=_text_argument(arguments, "authority_id"),
            boundary_kind=_text_argument(arguments, "boundary_kind"),
            available=_bool_argument(arguments, "available"),
            base_state_id=_text_argument(arguments, "base_state_id"),
        )
    if command.kind == "coupled_treatment":
        return PumpStationCoupledTreatmentRequest(
            version=_text_argument(arguments, "version"),
            request_id=_text_argument(arguments, "request_id"),
            authority_id=_text_argument(arguments, "authority_id"),
            treatment_label=_text_argument(arguments, "treatment_label"),
            affected_pump_ids=_text_tuple_argument(arguments, "affected_pump_ids"),
            obstruction_delta=_decimal_argument(arguments, "obstruction_delta"),
            clearance_loss_delta=_decimal_argument(arguments, "clearance_loss_delta"),
            base_state_id=_text_argument(arguments, "base_state_id"),
        )
    _fail("command-content", f"unsupported registered control kind {command.kind}")


def _text_argument(arguments: dict[str, object], field_name: str) -> str:
    value = arguments.get(field_name)
    if not isinstance(value, str) or not value.strip():
        _fail("command-content", f"control field {field_name} must be non-empty text")
    return value


def _bool_argument(arguments: dict[str, object], field_name: str) -> bool:
    value = arguments.get(field_name)
    if not isinstance(value, bool):
        _fail("command-content", f"control field {field_name} must be Boolean")
    return value


def _text_tuple_argument(
    arguments: dict[str, object],
    field_name: str,
) -> tuple[str, ...]:
    value = arguments.get(field_name)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        _fail("command-content", f"control field {field_name} must be a text list")
    return tuple(value)


def _decimal_argument(arguments: dict[str, object], field_name: str) -> Decimal:
    value = arguments.get(field_name)
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        _fail("command-content", f"control field {field_name} must be decimal content")
    try:
        return Decimal(str(value))
    except InvalidOperation as error:
        raise PumpStationWorldRunError(
            "command-content",
            f"control field {field_name} must be decimal content",
        ) from error
