# ABOUTME: Compiles frozen world catalogues into DeepSeek native tools backed by shared actor authority.
# ABOUTME: Keeps trusted request identity and the model-visible decision cursor outside task schemas.

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from pydantic import JsonValue

from aec_bench.adapters.deepseek_harness.tool_gateway import (
    NativeToolDefinition,
    NativeToolDisposition,
    NativeToolInvocation,
    NativeToolRequestSemantics,
    NativeToolResponse,
    native_tool_manifest,
)
from aec_bench.contracts.world_interface import WorldActorCapabilityCatalogue, WorldActorObservation
from aec_bench.harness.world_actor import (
    ActorCorrelation,
    ActorInvocationAuthority,
    ActorInvocationError,
    ActorInvocationOutcomeClass,
    ActorInvocationRequest,
    ActorTurnDisposition,
    actor_catalogue_sha256,
    canonical_actor_catalogue,
)

NATIVE_WORLD_TRANSPORT = "deepseek-native-world"
NATIVE_WORLD_TOOL_SURFACE_SCHEMA = "aec-bench/native-world-tool-surface/1"
WORLD_OBSERVE_TOOL_NAME = "world_observe"
WORLD_OBSERVE_DESCRIPTION = "Read the complete current actor-visible world observation."
_EMPTY_OBJECT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}
_SUPPORTED_SCHEMA_KEYS = frozenset(
    {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "anyOf",
        "description",
        "title",
        "default",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
        "pattern",
        "minItems",
        "maxItems",
        "uniqueItems",
    }
)
_SUPPORTED_SCHEMA_TYPES = frozenset({"object", "array", "string", "integer", "number", "boolean", "null"})
_INFRASTRUCTURE_ARGUMENTS = frozenset({"request_id", "decision_id"})


@dataclass
class _CursorRequest:
    decision_id: str
    completion_applied: bool = False


@dataclass(frozen=True)
class DeepSeekNativeWorldEvidence:
    """Supply task-owned world identity and actor evidence to one DeepSeek run."""

    surface_record: dict[str, Any]
    actor_authority_evidence_path: Path

    def __post_init__(self) -> None:
        surface = _canonical_json(self.surface_record)
        if surface.get("schema") != NATIVE_WORLD_TOOL_SURFACE_SCHEMA:
            raise ValueError("native world evidence requires the current tool-surface schema")
        for name in ("task_world_id", "catalogue_sha256", "public_tool_surface_sha256"):
            value = surface.get(name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"native world evidence requires {name}")
        for name in ("catalogue_sha256", "public_tool_surface_sha256"):
            value = surface[name]
            if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                raise ValueError(f"native world evidence requires a canonical {name}")
        surface_identity = {
            "action_mapping": surface.get("action_mapping"),
            "tools": surface.get("tools"),
        }
        if _json_sha256(surface_identity) != surface["public_tool_surface_sha256"]:
            raise ValueError("native world evidence public tool-surface hash does not match its content")
        source_path = Path(self.actor_authority_evidence_path)
        if source_path.is_symlink() or not source_path.is_file():
            raise ValueError("native world evidence requires a regular actor authority evidence file")
        evidence_path = source_path.resolve()
        object.__setattr__(self, "surface_record", surface)
        object.__setattr__(self, "actor_authority_evidence_path", evidence_path)


class NativeWorldToolTransport:
    """Own one DeepSeek actor session's private model-visible decision cursor."""

    def __init__(self, authority: ActorInvocationAuthority) -> None:
        self._authority = authority
        self._lock = threading.Lock()
        self._cursor: str | None = None
        self._requests: dict[str, _CursorRequest] = {}
        self._frozen_request_id: str | None = None
        self._closed = False

    def definitions(self, catalogue: WorldActorCapabilityCatalogue) -> tuple[NativeToolDefinition, ...]:
        """Return one observation tool and one exact tool for each catalogue action."""
        observation = NativeToolDefinition(
            name=WORLD_OBSERVE_TOOL_NAME,
            description=WORLD_OBSERVE_DESCRIPTION,
            parameters_schema=_EMPTY_OBJECT_SCHEMA,
            handler=self._observe,
            request_semantics=NativeToolRequestSemantics.HANDLER_AUTHORITY,
        )
        actions = tuple(
            NativeToolDefinition(
                name=action.name,
                description=action.description,
                parameters_schema=_canonical_json(action.input_schema),
                handler=self._action_handler(action.name),
                request_semantics=NativeToolRequestSemantics.HANDLER_AUTHORITY,
            )
            for action in sorted(catalogue.actions, key=lambda action: action.name)
        )
        return (observation, *actions)

    def _observe(
        self,
        invocation: NativeToolInvocation,
        _arguments: Mapping[str, JsonValue],
    ) -> NativeToolResponse:
        with self._lock:
            if self._closed:
                return _local_error_response(
                    "episode-closed",
                    "The world episode is closed.",
                    disposition=NativeToolDisposition.CONCLUDE_TURN,
                )
            if self._frozen_request_id is not None:
                return _local_error_response(
                    "world-action-outcome-unknown",
                    "The prior world action outcome must be reconciled before another observation.",
                    outcome=ActorInvocationOutcomeClass.UNKNOWN,
                    disposition=NativeToolDisposition.CONCLUDE_TURN,
                )
        try:
            observation = self._authority.observe(correlation=_correlation(invocation))
        except ActorInvocationError as error:
            return _error_response(error)
        with self._lock:
            if self._authority.terminal:
                self._closed = True
                self._cursor = None
                disposition = NativeToolDisposition.CONCLUDE_TURN
            else:
                self._cursor = observation.decision_id
                disposition = NativeToolDisposition.CONTINUE
        return NativeToolResponse(result=observation.model_dump(mode="json"), disposition=disposition)

    def _action_handler(self, action_name: str) -> Callable[..., NativeToolResponse]:
        def handle(
            invocation: NativeToolInvocation,
            arguments: Mapping[str, JsonValue],
        ) -> NativeToolResponse:
            request, error = self._prepare_request(invocation.request_id)
            if error is not None:
                return error
            assert request is not None
            try:
                outcome = self._authority.invoke(
                    ActorInvocationRequest(
                        request_id=invocation.request_id,
                        decision_id=request.decision_id,
                        action_name=action_name,
                        arguments=dict(arguments),
                        transport=NATIVE_WORLD_TRANSPORT,
                        correlation=_correlation(invocation),
                    )
                )
            except ActorInvocationError as actor_error:
                self._apply_error(request, invocation.request_id, actor_error)
                return _error_response(actor_error)
            self._apply_outcome(request, outcome.result.next_observation, outcome.disposition)
            return NativeToolResponse(
                result=outcome.result.model_dump(mode="json"),
                disposition=_native_disposition(outcome.disposition),
            )

        return handle

    def _prepare_request(
        self,
        request_id: str,
    ) -> tuple[_CursorRequest | None, NativeToolResponse | None]:
        with self._lock:
            existing = self._requests.get(request_id)
            if existing is not None:
                return existing, None
            if self._frozen_request_id is not None:
                return None, _local_error_response(
                    "world-action-outcome-unknown",
                    "The prior world action outcome must be reconciled before another action.",
                    outcome=ActorInvocationOutcomeClass.UNKNOWN,
                    disposition=NativeToolDisposition.CONCLUDE_TURN,
                )
            if self._closed:
                return None, _local_error_response(
                    "episode-closed",
                    "The world episode is closed.",
                    disposition=NativeToolDisposition.CONCLUDE_TURN,
                )
            if self._cursor is None:
                return None, _local_error_response(
                    "world-observation-required",
                    "Call world_observe before invoking a world action.",
                )
            request = _CursorRequest(decision_id=self._cursor)
            self._requests[request_id] = request
            self._cursor = None
            return request, None

    def _apply_outcome(
        self,
        request: _CursorRequest,
        next_observation: WorldActorObservation | None,
        disposition: ActorTurnDisposition,
    ) -> None:
        with self._lock:
            if request.completion_applied:
                return
            request.completion_applied = True
            if disposition is ActorTurnDisposition.CONCLUDE_TURN:
                self._closed = True
                self._cursor = None
            elif next_observation is not None:
                self._cursor = next_observation.decision_id

    def _apply_error(
        self,
        request: _CursorRequest,
        request_id: str,
        error: ActorInvocationError,
    ) -> None:
        with self._lock:
            if request.completion_applied:
                return
            request.completion_applied = True
            if error.outcome is ActorInvocationOutcomeClass.UNKNOWN:
                self._frozen_request_id = request_id
                self._cursor = None
            elif error.code == "decision-stale":
                self._cursor = None
            elif error.disposition is ActorTurnDisposition.CONCLUDE_TURN:
                self._closed = True
                self._cursor = None


def compile_world_native_tools(
    *,
    authority: ActorInvocationAuthority,
    catalogue: WorldActorCapabilityCatalogue,
) -> tuple[NativeToolDefinition, ...]:
    """Compile one frozen task catalogue into the complete DeepSeek world surface."""
    frozen = authority.capabilities(correlation=ActorCorrelation())
    expected_hash = authority.catalogue_hash
    supplied_hash = actor_catalogue_sha256(catalogue)
    if expected_hash is None or actor_catalogue_sha256(frozen) != expected_hash:
        raise ValueError("actor invocation authority does not have a valid frozen catalogue")
    if supplied_hash != expected_hash:
        raise ValueError("native world catalogue differs from the frozen actor catalogue")
    if any(action.name == WORLD_OBSERVE_TOOL_NAME for action in catalogue.actions):
        raise ValueError("world actor catalogue collides with reserved tool name: world_observe")
    for action in catalogue.actions:
        _validate_action_schema(action.name, action.input_schema)
    definitions = NativeWorldToolTransport(authority).definitions(catalogue)
    native_tool_manifest(definitions)
    return definitions


def native_world_tool_surface_record(
    *,
    catalogue: WorldActorCapabilityCatalogue,
    definitions: tuple[NativeToolDefinition, ...],
) -> dict[str, Any]:
    """Return the complete canonical catalogue, mapping, and public tool identity."""
    manifest = native_tool_manifest(definitions)
    mapping = tuple(
        {"catalogue_action": action.name, "public_tool": action.name}
        for action in sorted(catalogue.actions, key=lambda action: action.name)
    )
    surface_identity = {"action_mapping": mapping, "tools": manifest}
    return {
        "schema": NATIVE_WORLD_TOOL_SURFACE_SCHEMA,
        "task_world_id": catalogue.task_world_id,
        "catalogue_sha256": actor_catalogue_sha256(catalogue),
        "public_tool_surface_sha256": _json_sha256(surface_identity),
        "catalogue": canonical_actor_catalogue(catalogue),
        "action_mapping": mapping,
        "tools": manifest,
    }


def _validate_action_schema(action_name: str, schema: dict[str, JsonValue]) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as error:
        raise ValueError(f"invalid world action schema for {action_name}: {error.message}") from error
    if schema.get("type") != "object":
        raise ValueError(f"unsupported world action schema for {action_name}: root type must be object")
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        raise ValueError(f"unsupported world action schema for {action_name}: properties must be an object")
    hidden = _INFRASTRUCTURE_ARGUMENTS.intersection(properties)
    if hidden:
        names = ", ".join(sorted(hidden))
        raise ValueError(f"world action schema exposes infrastructure fields for {action_name}: {names}")
    _validate_schema_node(schema, path=action_name)


def _validate_schema_node(schema: Mapping[str, Any], *, path: str) -> None:
    unsupported = set(schema) - _SUPPORTED_SCHEMA_KEYS
    if unsupported:
        names = ", ".join(sorted(unsupported))
        raise ValueError(f"unsupported JSON Schema keywords at {path}: {names}")
    schema_type = schema.get("type")
    if schema_type is not None and schema_type not in _SUPPORTED_SCHEMA_TYPES:
        raise ValueError(f"unsupported JSON Schema type at {path}: {schema_type}")
    properties = schema.get("properties")
    if properties is not None:
        if not isinstance(properties, dict):
            raise ValueError(f"JSON Schema properties must be an object at {path}")
        for name, child in properties.items():
            if not isinstance(child, dict):
                raise ValueError(f"JSON Schema property must be an object at {path}.{name}")
            _validate_schema_node(child, path=f"{path}.{name}")
    items = schema.get("items")
    if items is not None:
        if not isinstance(items, dict):
            raise ValueError(f"JSON Schema items must be an object at {path}")
        _validate_schema_node(items, path=f"{path}[]")
    additional = schema.get("additionalProperties")
    if additional is not None and not isinstance(additional, bool):
        raise ValueError(f"JSON Schema additionalProperties must be boolean at {path}")
    alternatives = schema.get("anyOf")
    if alternatives is not None:
        if not isinstance(alternatives, list) or len(alternatives) != 2:
            raise ValueError(f"JSON Schema anyOf must be one nullable union at {path}")
        if not all(isinstance(item, dict) for item in alternatives):
            raise ValueError(f"JSON Schema anyOf members must be objects at {path}")
        if sum(item.get("type") == "null" for item in alternatives) != 1:
            raise ValueError(f"JSON Schema anyOf must contain exactly one null type at {path}")
        for index, item in enumerate(alternatives):
            _validate_schema_node(item, path=f"{path}.anyOf[{index}]")


def _correlation(invocation: NativeToolInvocation) -> ActorCorrelation:
    return ActorCorrelation(
        transport_request_id=invocation.request_id,
        provider_session_id=invocation.deepseek_session_id,
        provider_tool_call_id=invocation.deepseek_tool_call_id,
        model_turn=invocation.model_turn,
    )


def _error_response(error: ActorInvocationError) -> NativeToolResponse:
    return _local_error_response(
        error.code,
        error.detail,
        outcome=error.outcome,
        action_sequence=error.action_sequence,
        disposition=_native_disposition(error.disposition),
    )


def _local_error_response(
    code: str,
    detail: str,
    *,
    outcome: ActorInvocationOutcomeClass = ActorInvocationOutcomeClass.NOT_DISPATCHED,
    action_sequence: int | None = None,
    disposition: NativeToolDisposition = NativeToolDisposition.CONTINUE,
) -> NativeToolResponse:
    result: dict[str, JsonValue] = {
        "status": "error",
        "error": {
            "code": code,
            "detail": detail,
            "outcome": outcome.value,
            "action_sequence": action_sequence,
        },
    }
    return NativeToolResponse(result=result, disposition=disposition)


def _native_disposition(disposition: ActorTurnDisposition) -> NativeToolDisposition:
    if disposition is ActorTurnDisposition.CONCLUDE_TURN:
        return NativeToolDisposition.CONCLUDE_TURN
    return NativeToolDisposition.CONTINUE


def _canonical_json(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False))


def _json_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "NATIVE_WORLD_TOOL_SURFACE_SCHEMA",
    "NATIVE_WORLD_TRANSPORT",
    "WORLD_OBSERVE_DESCRIPTION",
    "WORLD_OBSERVE_TOOL_NAME",
    "DeepSeekNativeWorldEvidence",
    "NativeWorldToolTransport",
    "compile_world_native_tools",
    "native_world_tool_surface_record",
]
