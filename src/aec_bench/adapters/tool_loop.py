# ABOUTME: Multi-turn tool-loop adapter for tool-using executions in aec-bench Python.
# ABOUTME: Enforces task-declared tool allowlists and records tool-call transcripts explicitly.

import json as _json
import logging
from dataclasses import dataclass
from typing import Any, Protocol, cast, runtime_checkable

from aec_bench.adapters.advisor import default_advise
from aec_bench.adapters.base import (
    AdapterFailureKind,
    AdapterRequest,
    AdapterResult,
    SerializedAdapterExecution,
    SerializedClientSpec,
    client_spec_to_payload,
)
from aec_bench.adapters.config import record_effective_configuration, resolve_model_alias
from aec_bench.adapters.rlm.client import RlmClient
from aec_bench.adapters.transcript import (
    TokenUsage,
    TranscriptEntry,
    TranscriptEvent,
    TranscriptRole,
    initialize_transcript,
)
from aec_bench.contracts.advisor import AdvisorConfig, AdvisorRequest
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolCall:
    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolExecutionResult:
    output_text: str
    error_message: str | None = None


@dataclass(frozen=True)
class ToolLoopRequest:
    model: str
    instruction: str
    system_prompt: str | None = None
    configuration: dict[str, Any] | None = None
    transcript: list[TranscriptEntry] | None = None


@dataclass(frozen=True)
class ToolLoopCompletionResponse:
    output_text: str = ""
    tool_call: ToolCall | None = None
    error_message: str | None = None
    usage_input_tokens: int | None = None
    usage_output_tokens: int | None = None
    usage_cache_read_tokens: int | None = None
    usage_cache_write_tokens: int | None = None
    timed_out: bool = False
    done: bool = False


class ToolLoopClient(Protocol):
    def next_turn(self, request: ToolLoopRequest) -> ToolLoopCompletionResponse: ...


@runtime_checkable
class RemoteToolLoopClient(ToolLoopClient, Protocol):
    def serialize_client(self) -> SerializedClientSpec: ...


class ReplayToolLoopClient:
    def __init__(self, responses: list[ToolLoopCompletionResponse]) -> None:
        self._responses = list(responses)
        self._index = 0

    def next_turn(self, request: ToolLoopRequest) -> ToolLoopCompletionResponse:
        del request
        response = self._responses[self._index]
        self._index += 1
        return response

    def serialize_client(self) -> SerializedClientSpec:
        return SerializedClientSpec(
            client_kind="replay",
            payload={"responses": [_response_payload(response) for response in self._responses]},
        )


class ToolExecutor(Protocol):
    def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolExecutionResult: ...


class ToolLoopAdapter:
    def __init__(
        self,
        *,
        adapter_name: str,
        model_name: str,
        client: ToolLoopClient,
        tool_executor: ToolExecutor | None,
        aliases: dict[str, str] | None = None,
        advisor_client: RlmClient | None = None,
        advisor_config: AdvisorConfig | None = None,
    ) -> None:
        self._adapter_name = adapter_name
        self._resolved_model = resolve_model_alias(model_name, aliases=aliases or {})
        self._client = client
        self._tool_executor = tool_executor
        self._advisor_client = advisor_client
        self._advisor_config = advisor_config
        self._advisor_calls_made = 0
        self._advisor_input_tokens = 0
        self._advisor_output_tokens = 0

    def serialize_execution(self) -> SerializedAdapterExecution:
        if not isinstance(self._client, RemoteToolLoopClient):
            msg = "tool-loop adapter client is not serializable for remote execution"
            raise TypeError(msg)

        client_spec = self._client.serialize_client()
        return SerializedAdapterExecution(
            adapter_kind="tool_loop",
            adapter_name=self._adapter_name,
            resolved_model=self._resolved_model,
            payload={"client": client_spec_to_payload(client_spec)},
        )

    def execute(self, request: AdapterRequest) -> AdapterResult:
        transcript = initialize_transcript(request)
        max_turns = int(request.configuration.get("max_turns", 8))
        allowed_tools = {tool.name for tool in request.tools}

        for _ in range(max_turns):
            response = self._client.next_turn(
                ToolLoopRequest(
                    model=self._resolved_model,
                    instruction=request.instruction,
                    system_prompt=request.system_prompt,
                    configuration=request.configuration,
                    transcript=list(transcript),
                )
            )

            if response.tool_call is not None:
                tool_call = response.tool_call
                transcript.append(
                    TranscriptEntry(
                        role=TranscriptRole.ASSISTANT,
                        content=f"Calling {tool_call.tool_name}.",
                        event=TranscriptEvent.TOOL_CALL,
                        tool_name=tool_call.tool_name,
                        tool_call_id=tool_call.tool_call_id,
                    )
                )

                # Intercept advisor tool calls before the allowlist check
                if (
                    tool_call.tool_name == "advisor"
                    and self._advisor_client is not None
                    and self._advisor_config is not None
                    and self._advisor_config.enabled
                ):
                    advisor_output = self._handle_advisor_call(tool_call, transcript)
                    transcript.append(
                        TranscriptEntry(
                            role=TranscriptRole.TOOL,
                            content=advisor_output,
                            event=TranscriptEvent.TOOL_RESULT,
                            tool_name=tool_call.tool_name,
                            tool_call_id=tool_call.tool_call_id,
                        )
                    )
                    continue

                if tool_call.tool_name not in allowed_tools:
                    error_message = f"undeclared tool requested: {tool_call.tool_name}"
                    transcript.append(
                        TranscriptEntry(
                            role=TranscriptRole.TOOL,
                            content=error_message,
                            event=TranscriptEvent.TOOL_RESULT,
                            tool_name=tool_call.tool_name,
                            tool_call_id=tool_call.tool_call_id,
                        )
                    )
                    adv_calls, adv_in, adv_out = self._advisor_usage()
                    return _build_result(
                        adapter_name=self._adapter_name,
                        resolved_model=self._resolved_model,
                        configuration=request.configuration,
                        request=request,
                        transcript=transcript,
                        status=AgentOutputStatus.FAILED,
                        failure_kind=AdapterFailureKind.UNDECLARED_TOOL_REQUEST,
                        error_message=error_message,
                        usage_advisor_calls=adv_calls,
                        usage_advisor_input_tokens=adv_in,
                        usage_advisor_output_tokens=adv_out,
                    )

                assert self._tool_executor is not None
                tool_result = self._tool_executor.execute(
                    tool_call.tool_name,
                    tool_call.arguments,
                )
                tool_output = tool_result.error_message or tool_result.output_text
                transcript.append(
                    TranscriptEntry(
                        role=TranscriptRole.TOOL,
                        content=tool_output,
                        event=TranscriptEvent.TOOL_RESULT,
                        tool_name=tool_call.tool_name,
                        tool_call_id=tool_call.tool_call_id,
                    )
                )
                if tool_result.error_message is not None:
                    logger.warning(
                        "tool %s returned error (surfacing to model): %s",
                        tool_call.tool_name,
                        tool_result.error_message,
                    )
                continue

            if response.output_text:
                transcript.append(
                    TranscriptEntry(
                        role=TranscriptRole.ASSISTANT,
                        content=response.output_text,
                        usage=TokenUsage(
                            input_tokens=response.usage_input_tokens,
                            output_tokens=response.usage_output_tokens,
                        ),
                    )
                )

            if response.timed_out or response.error_message is not None:
                adv_calls, adv_in, adv_out = self._advisor_usage()
                return _build_result(
                    adapter_name=self._adapter_name,
                    resolved_model=self._resolved_model,
                    configuration=request.configuration,
                    request=request,
                    transcript=transcript,
                    status=AgentOutputStatus.FAILED,
                    failure_kind=(
                        AdapterFailureKind.TIMEOUT if response.timed_out else AdapterFailureKind.PROVIDER_ERROR
                    ),
                    error_message=response.error_message,
                    raw_output_text=response.output_text or None,
                    usage_input_tokens=response.usage_input_tokens,
                    usage_output_tokens=response.usage_output_tokens,
                    usage_advisor_calls=adv_calls,
                    usage_advisor_input_tokens=adv_in,
                    usage_advisor_output_tokens=adv_out,
                )

            if response.done:
                status = AgentOutputStatus.COMPLETED if response.output_text else AgentOutputStatus.EMPTY
                adv_calls, adv_in, adv_out = self._advisor_usage()
                return _build_result(
                    adapter_name=self._adapter_name,
                    resolved_model=self._resolved_model,
                    configuration=request.configuration,
                    request=request,
                    transcript=transcript,
                    status=status,
                    failure_kind=(None if response.output_text else AdapterFailureKind.MISSING_OUTPUT),
                    raw_output_text=response.output_text or None,
                    usage_input_tokens=response.usage_input_tokens,
                    usage_output_tokens=response.usage_output_tokens,
                    usage_advisor_calls=adv_calls,
                    usage_advisor_input_tokens=adv_in,
                    usage_advisor_output_tokens=adv_out,
                )

        adv_calls, adv_in, adv_out = self._advisor_usage()
        return _build_result(
            adapter_name=self._adapter_name,
            resolved_model=self._resolved_model,
            configuration=request.configuration,
            request=request,
            transcript=transcript,
            status=AgentOutputStatus.PARTIAL,
            failure_kind=AdapterFailureKind.TURN_LIMIT_REACHED,
            error_message="turn limit reached",
            usage_advisor_calls=adv_calls,
            usage_advisor_input_tokens=adv_in,
            usage_advisor_output_tokens=adv_out,
        )

    def adapter_name(self) -> str:
        return self._adapter_name

    def resolved_model(self) -> str:
        return self._resolved_model

    def _advisor_usage(self) -> tuple[int | None, int | None, int | None]:
        """Return (calls, input_tokens, output_tokens), or all-None when no advisor wired.

        Clients that dispatch advisor tool calls internally (e.g. PydanticAI's
        ``run_sync`` completes the whole loop in one shot) can expose an
        ``advisor_usage()`` method returning authoritative stats. When that
        method is present, its values take precedence over this adapter's
        intercept counters — which stay at zero on that code path.
        """
        if self._advisor_config is None:
            return (None, None, None)
        client_usage = getattr(self._client, "advisor_usage", None)
        if callable(client_usage):
            result = client_usage()
            if result is not None:
                return result
        return (
            self._advisor_calls_made,
            self._advisor_input_tokens,
            self._advisor_output_tokens,
        )

    def _handle_advisor_call(
        self,
        tool_call: ToolCall,
        transcript: list[TranscriptEntry],
    ) -> str:
        """Handle an advisor tool call with windowed transcript context."""
        assert self._advisor_config is not None
        assert self._advisor_client is not None
        cfg = self._advisor_config

        if self._advisor_calls_made >= cfg.max_uses:
            return _json.dumps(
                {
                    "advice": (
                        f"Advisor budget exhausted ({cfg.max_uses}/{cfg.max_uses} calls used). Proceed on your own."
                    ),
                    "suggested_action": "continue",
                    "confidence": 0.0,
                    "reasoning": "max_uses reached",
                }
            )

        args = tool_call.arguments
        request = AdvisorRequest(
            goal=args.get("goal", ""),
            problem=args.get("problem", ""),
            attempt=args.get("attempt"),
        )

        # Windowed context: last N transcript entries
        context_msgs = [
            {"role": e.role.value, "content": e.content} for e in transcript[-cfg.context_window :] if e.content
        ]

        result = default_advise(
            request=request,
            context_messages=context_msgs,
            client=self._advisor_client,
            model=cfg.model,
            max_response_tokens=cfg.max_response_tokens,
            adapter_context="The executor is using a tool-loop adapter with bash and search tools.",
        )

        if result.error is None:
            self._advisor_calls_made += 1
            self._advisor_input_tokens += result.input_tokens
            self._advisor_output_tokens += result.output_tokens

        if result.response:
            return _json.dumps(
                {
                    "advice": result.response.advice,
                    "suggested_action": result.response.suggested_action,
                    "confidence": result.response.confidence,
                    "reasoning": result.response.reasoning,
                }
            )
        return _json.dumps(
            {
                "advice": "Advisor unavailable",
                "suggested_action": "continue",
                "confidence": 0.0,
                "reasoning": "",
            }
        )


def _build_result(
    *,
    adapter_name: str,
    resolved_model: str,
    configuration: dict[str, Any],
    request: AdapterRequest,
    transcript: list[TranscriptEntry],
    status: AgentOutputStatus,
    failure_kind: AdapterFailureKind | None = None,
    error_message: str | None = None,
    raw_output_text: str | None = None,
    usage_input_tokens: int | None = None,
    usage_output_tokens: int | None = None,
    usage_advisor_calls: int | None = None,
    usage_advisor_input_tokens: int | None = None,
    usage_advisor_output_tokens: int | None = None,
) -> AdapterResult:
    return AdapterResult(
        adapter_name=adapter_name,
        resolved_model=resolved_model,
        configuration_record=record_effective_configuration(
            resolved_model=resolved_model,
            configuration=configuration,
        ),
        agent_output=AgentOutput(
            status=status,
            output_path=request.output_path,
            output_format=request.output_format,
            error_message=error_message,
        ),
        transcript=transcript,
        failure_kind=failure_kind,
        raw_output_text=raw_output_text,
        provider_error=error_message,
        usage_input_tokens=usage_input_tokens,
        usage_output_tokens=usage_output_tokens,
        usage_advisor_calls=usage_advisor_calls,
        usage_advisor_input_tokens=usage_advisor_input_tokens,
        usage_advisor_output_tokens=usage_advisor_output_tokens,
    )


def replay_tool_loop_client_from_payload(payload: dict[str, Any]) -> ReplayToolLoopClient:
    responses = cast(list[dict[str, Any]], payload.get("responses", []))
    return ReplayToolLoopClient(responses=[_response_from_payload(response) for response in responses])


def _response_payload(response: ToolLoopCompletionResponse) -> dict[str, Any]:
    tool_call: dict[str, Any] | None = None
    if response.tool_call is not None:
        tool_call = {
            "tool_call_id": response.tool_call.tool_call_id,
            "tool_name": response.tool_call.tool_name,
            "arguments": response.tool_call.arguments,
        }
    return {
        "output_text": response.output_text,
        "tool_call": tool_call,
        "error_message": response.error_message,
        "usage_input_tokens": response.usage_input_tokens,
        "usage_output_tokens": response.usage_output_tokens,
        "timed_out": response.timed_out,
        "done": response.done,
    }


def _response_from_payload(payload: dict[str, Any]) -> ToolLoopCompletionResponse:
    tool_call_payload = cast(dict[str, Any] | None, payload.get("tool_call"))
    tool_call = None
    if tool_call_payload is not None:
        tool_call = ToolCall(
            tool_call_id=cast(str, tool_call_payload["tool_call_id"]),
            tool_name=cast(str, tool_call_payload["tool_name"]),
            arguments=cast(dict[str, Any], tool_call_payload.get("arguments", {})),
        )
    return ToolLoopCompletionResponse(
        output_text=cast(str, payload.get("output_text", "")),
        tool_call=tool_call,
        error_message=cast(str | None, payload.get("error_message")),
        usage_input_tokens=cast(int | None, payload.get("usage_input_tokens")),
        usage_output_tokens=cast(int | None, payload.get("usage_output_tokens")),
        timed_out=bool(payload.get("timed_out", False)),
        done=bool(payload.get("done", False)),
    )
