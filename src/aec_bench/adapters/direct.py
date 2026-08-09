# ABOUTME: Direct single-turn adapter for tool-free executions in aec-bench Python.
# ABOUTME: Translates one harness request into one provider completion with a canonical transcript.

from dataclasses import dataclass
from typing import Any, Protocol, cast, runtime_checkable

from aec_bench.adapters.base import (
    AdapterFailureKind,
    AdapterRequest,
    AdapterResult,
    SerializedAdapterExecution,
    SerializedClientSpec,
    client_spec_to_payload,
    initialize_transcript,
)
from aec_bench.adapters.config import record_effective_configuration, resolve_model_alias
from aec_bench.contracts.adapter_execution import (
    TokenUsage,
    TranscriptEntry,
    TranscriptRole,
)
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus


@dataclass(frozen=True)
class DirectCompletionRequest:
    model: str
    instruction: str
    system_prompt: str | None = None
    configuration: dict[str, Any] | None = None


@dataclass(frozen=True)
class DirectCompletionResponse:
    output_text: str
    error_message: str | None = None
    usage_model_calls: int | None = 1
    usage_input_tokens: int | None = None
    usage_output_tokens: int | None = None
    usage_cache_read_tokens: int | None = None
    usage_cache_write_tokens: int | None = None
    timed_out: bool = False


class DirectClient(Protocol):
    def complete(self, request: DirectCompletionRequest) -> DirectCompletionResponse: ...


@runtime_checkable
class RemoteDirectClient(DirectClient, Protocol):
    def serialize_client(self) -> SerializedClientSpec: ...


@dataclass
class ReplayDirectClient:
    response: DirectCompletionResponse

    def complete(self, request: DirectCompletionRequest) -> DirectCompletionResponse:
        del request
        return self.response

    def serialize_client(self) -> SerializedClientSpec:
        payload = {
            "output_text": self.response.output_text,
            "error_message": self.response.error_message,
            "usage_input_tokens": self.response.usage_input_tokens,
            "usage_output_tokens": self.response.usage_output_tokens,
            "timed_out": self.response.timed_out,
        }
        if self.response.usage_model_calls != 1:
            payload["usage_model_calls"] = self.response.usage_model_calls
        if self.response.usage_cache_read_tokens is not None:
            payload["usage_cache_read_tokens"] = self.response.usage_cache_read_tokens
        if self.response.usage_cache_write_tokens is not None:
            payload["usage_cache_write_tokens"] = self.response.usage_cache_write_tokens
        return SerializedClientSpec(
            client_kind="replay",
            payload=payload,
        )


class DirectAdapter:
    def __init__(
        self,
        *,
        adapter_name: str,
        model_name: str,
        client: DirectClient,
        aliases: dict[str, str] | None = None,
    ) -> None:
        self._adapter_name = adapter_name
        self._resolved_model = resolve_model_alias(model_name, aliases=aliases or {})
        self._client = client

    def serialize_execution(self) -> SerializedAdapterExecution:
        if not isinstance(self._client, RemoteDirectClient):
            msg = "direct adapter client is not serializable for remote execution"
            raise TypeError(msg)

        client_spec = self._client.serialize_client()
        return SerializedAdapterExecution(
            adapter_kind="direct",
            adapter_name=self._adapter_name,
            resolved_model=self._resolved_model,
            payload={"client": client_spec_to_payload(client_spec)},
        )

    def execute(self, request: AdapterRequest) -> AdapterResult:
        provider_request = DirectCompletionRequest(
            model=self._resolved_model,
            instruction=request.instruction,
            system_prompt=request.system_prompt,
            configuration=request.configuration,
        )
        provider_response = self._client.complete(provider_request)

        transcript = initialize_transcript(request)

        if provider_response.output_text:
            transcript.append(
                TranscriptEntry(
                    role=TranscriptRole.ASSISTANT,
                    content=provider_response.output_text,
                    usage=TokenUsage(
                        input_tokens=provider_response.usage_input_tokens,
                        output_tokens=provider_response.usage_output_tokens,
                    ),
                )
            )

        agent_output = AgentOutput(
            status=_resolve_status(provider_response),
            output_path=request.output_path,
            output_format=request.output_format,
            error_message=provider_response.error_message,
        )

        return AdapterResult(
            adapter_name=self._adapter_name,
            resolved_model=self._resolved_model,
            configuration_record=record_effective_configuration(
                resolved_model=self._resolved_model,
                configuration=request.configuration,
            ),
            agent_output=agent_output,
            transcript=transcript,
            failure_kind=_resolve_failure_kind(provider_response),
            turns_used=1,
            max_turns=1,
            raw_output_text=provider_response.output_text or None,
            provider_error=provider_response.error_message,
            usage_model_calls=provider_response.usage_model_calls,
            usage_input_tokens=provider_response.usage_input_tokens,
            usage_output_tokens=provider_response.usage_output_tokens,
            usage_cache_read_tokens=provider_response.usage_cache_read_tokens,
            usage_cache_write_tokens=provider_response.usage_cache_write_tokens,
        )

    def adapter_name(self) -> str:
        return self._adapter_name

    def resolved_model(self) -> str:
        return self._resolved_model


def _resolve_status(response: DirectCompletionResponse) -> AgentOutputStatus:
    if response.timed_out or response.error_message is not None:
        return AgentOutputStatus.FAILED
    if not response.output_text:
        return AgentOutputStatus.EMPTY
    return AgentOutputStatus.COMPLETED


def _resolve_failure_kind(response: DirectCompletionResponse) -> AdapterFailureKind | None:
    if response.timed_out:
        return AdapterFailureKind.TIMEOUT
    if response.error_message is not None:
        return AdapterFailureKind.PROVIDER_ERROR
    if not response.output_text:
        return AdapterFailureKind.MISSING_OUTPUT
    return None


def replay_direct_client_from_payload(payload: dict[str, Any]) -> ReplayDirectClient:
    return ReplayDirectClient(
        response=DirectCompletionResponse(
            output_text=cast(str, payload.get("output_text", "")),
            error_message=cast(str | None, payload.get("error_message")),
            usage_model_calls=cast(
                int | None,
                payload.get("usage_model_calls", 1),
            ),
            usage_input_tokens=cast(int | None, payload.get("usage_input_tokens")),
            usage_output_tokens=cast(int | None, payload.get("usage_output_tokens")),
            usage_cache_read_tokens=cast(
                int | None,
                payload.get("usage_cache_read_tokens"),
            ),
            usage_cache_write_tokens=cast(
                int | None,
                payload.get("usage_cache_write_tokens"),
            ),
            timed_out=bool(payload.get("timed_out", False)),
        )
    )
