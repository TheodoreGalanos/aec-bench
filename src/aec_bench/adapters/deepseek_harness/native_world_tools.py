# ABOUTME: Translates DeepSeek native world calls into the shared actor invocation authority.
# ABOUTME: Keeps model presentation and correlation outside world action semantics.

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import JsonValue

from aec_bench.adapters.deepseek_harness.tool_gateway import (
    NativeToolDefinition,
    NativeToolDisposition,
    NativeToolInvocation,
    NativeToolRequestSemantics,
    NativeToolResponse,
)
from aec_bench.harness.world_actor import (
    ActorCorrelation,
    ActorInvocationAuthority,
    ActorInvocationError,
    ActorTurnDisposition,
)

NATIVE_WORLD_TRANSPORT = "deepseek-native-world"


class NativeWorldToolTransport:
    """Present model-native world tools while delegating semantics to one authority."""

    def __init__(self, authority: ActorInvocationAuthority) -> None:
        self._authority = authority

    def observation_definition(
        self,
        *,
        name: str,
        description: str,
        parameters_schema: dict[str, Any],
    ) -> NativeToolDefinition:
        """Define one read-only native observation tool."""

        def handle(
            invocation: NativeToolInvocation,
            _arguments: Mapping[str, JsonValue],
        ) -> NativeToolResponse:
            try:
                observation = self._authority.observe(correlation=_correlation(invocation))
            except ActorInvocationError as error:
                return _error_response(error)
            return NativeToolResponse(result=observation.model_dump(mode="json"))

        return NativeToolDefinition(
            name=name,
            description=description,
            parameters_schema=parameters_schema,
            handler=handle,
            request_semantics=NativeToolRequestSemantics.HANDLER_AUTHORITY,
        )

    def action_definition(
        self,
        *,
        name: str,
        description: str,
        parameters_schema: dict[str, Any],
    ) -> NativeToolDefinition:
        """Define one native action whose logical request is owned by the authority."""

        def handle(
            invocation: NativeToolInvocation,
            arguments: Mapping[str, JsonValue],
        ) -> NativeToolResponse:
            correlation = _correlation(invocation)
            try:
                outcome = self._authority.invoke_current(
                    request_id=invocation.request_id,
                    action_name=name,
                    arguments=dict(arguments),
                    transport=NATIVE_WORLD_TRANSPORT,
                    correlation=correlation,
                )
            except ActorInvocationError as error:
                return _error_response(error)
            return NativeToolResponse(
                result=outcome.result.model_dump(mode="json"),
                disposition=_native_disposition(outcome.disposition),
            )

        return NativeToolDefinition(
            name=name,
            description=description,
            parameters_schema=parameters_schema,
            handler=handle,
            request_semantics=NativeToolRequestSemantics.HANDLER_AUTHORITY,
        )


def _correlation(invocation: NativeToolInvocation) -> ActorCorrelation:
    return ActorCorrelation(
        transport_request_id=invocation.request_id,
        provider_session_id=invocation.deepseek_session_id,
        provider_tool_call_id=invocation.deepseek_tool_call_id,
        model_turn=invocation.model_turn,
    )


def _error_response(error: ActorInvocationError) -> NativeToolResponse:
    result: dict[str, JsonValue] = {
        "status": "error",
        "error": {
            "code": error.code,
            "detail": error.detail,
            "outcome": error.outcome.value,
            "action_sequence": error.action_sequence,
        },
    }
    return NativeToolResponse(
        result=result,
        disposition=_native_disposition(error.disposition),
    )


def _native_disposition(disposition: ActorTurnDisposition) -> NativeToolDisposition:
    if disposition is ActorTurnDisposition.CONCLUDE_TURN:
        return NativeToolDisposition.CONCLUDE_TURN
    return NativeToolDisposition.CONTINUE


__all__ = ["NATIVE_WORLD_TRANSPORT", "NativeWorldToolTransport"]
